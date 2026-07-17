"""
Export rendering — Pillow rasterization, projection, and overlay/ROI drawing for export.

Extracted from ``export_manager`` for cohesion. ``ExportManager`` delegates here.

Requirements: PIL, numpy, pydicom, ``core.dicom_processor``, ``gui.overlay_text_builder``,
``utils.dicom_utils``.
"""
import copy
import logging
import os
import sys
from pathlib import Path
from typing import Any, NamedTuple

import numpy as np
import pydicom.uid
from PIL import Image, ImageDraw, ImageFont
from pydicom.dataset import Dataset

from core.dicom_parser import DICOMParser
from core.dicom_processor import DICOMProcessor
from gui.overlay_text_builder import get_corner_text, get_modality
from tools.angle_measurement_items import AngleMeasurementItem
from utils.dicom_utils import get_composite_series_key, get_slice_thickness
from utils.log_sanitizer import sanitized_format_exc
from utils.privacy.console import print_redacted

_logger = logging.getLogger(__name__)

RGB = tuple[int, int, int]


def _get_bundled_font_path(filename: str) -> str:
    """Return the absolute path to a font bundled in resources/fonts/, works in dev and PyInstaller."""
    if getattr(sys, 'frozen', False):
        # PyInstaller sets sys._MEIPASS at runtime; keep a safe fallback for typing.
        meipass = getattr(sys, "_MEIPASS", "")
        base = Path(meipass) if meipass else Path(__file__).parent.parent.parent
    else:
        base = Path(__file__).parent.parent.parent
    return str(base / "resources" / "fonts" / filename)


def _load_font_with_fallback(size: int, variant: str = "Bold",
                             font_family: str = "IBM Plex Sans") -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Load a TrueType font at *size* with a robust cross-platform fallback chain.

    Priority:
      1. Requested bundled font (font_family + variant)
      2. Remaining bundled fonts as ordered fallbacks
      3. Common system font paths (Windows via WINDIR, macOS, various Linux distros)
      4. matplotlib.font_manager.findfont() – always returns a valid path
      5. PIL ImageFont.load_default() – bitmap fallback of last resort
    """
    from utils.bundled_fonts import (
        BUNDLED_FONTS,
        get_bundled_ttf_path,
        get_variant_weight_italic,
    )
    _weight_int, _ = get_variant_weight_italic(variant)
    _is_bold = _weight_int >= 600
    _win_fonts = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts")

    # Start with the user's chosen family, then fall through remaining bundled fonts.
    # resolve_font (called inside get_bundled_ttf_path) handles variant fallback automatically.
    ordered_families = [font_family] + [f for f in BUNDLED_FONTS if f != font_family]
    bundled_candidates = []
    for fam in ordered_families:
        bundled_candidates.append(get_bundled_ttf_path(fam, variant))

    candidates: list[str] = [
        *bundled_candidates,
        # System fonts – bold variants first when requested
        *([
            os.path.join(_win_fonts, "arialbd.ttf"),
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
            "/usr/share/fonts/liberation-sans/LiberationSans-Bold.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf",
        ] if _is_bold else []),
        # System fonts – regular paths (Debian/Ubuntu, Fedora, Arch, openSUSE)
        os.path.join(_win_fonts, "arial.ttf"),
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/usr/share/fonts/liberation-sans/LiberationSans-Regular.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/TTF/DejaVuSans.ttf",
        "/usr/share/fonts/dejavu/DejaVuSans.ttf",
        # macOS
        "/System/Library/Fonts/Helvetica.ttc",
        "/System/Library/Fonts/Arial.ttf",
        "/Library/Fonts/Arial.ttf",
    ]

    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            continue

    # 3. matplotlib findfont – always resolves to a real file
    try:
        from matplotlib import font_manager as _fm
        weight = "bold" if _is_bold else "normal"
        _prop = _fm.FontProperties(family="sans-serif", weight=weight)
        _path = _fm.findfont(_prop)
        return ImageFont.truetype(_path, size)
    except Exception:
        pass

    # 4. Last resort bitmap font
    return ImageFont.load_default()


# Export scale factor choices (plan: cap output max dimension at 8192)
MAX_EXPORT_DIMENSION = 8192
EXPORT_SCALE_NATIVE = 1.0
EXPORT_SCALE_1_5 = 1.5
EXPORT_SCALE_2 = 2.0
EXPORT_SCALE_4 = 4.0
EXPORT_SCALE_CHOICES = (EXPORT_SCALE_NATIVE, EXPORT_SCALE_1_5, EXPORT_SCALE_2, EXPORT_SCALE_4)
# Ordered scale steps for fallback: try requested then next down until under limit
EXPORT_SCALE_ORDERED = (4.0, 2.0, 1.5, 1.0)

# Formula-based annotation sizing (no magnification): line_thickness = (1/100)*(setting/2)*(w+h)/2;
# text_size = (1/100)*setting*(w+h)/2. With "enlarge by same factor", multiply by export scale.
MIN_EXPORT_LINE_THICKNESS = 1
MIN_EXPORT_FONT_SIZE = 8
MAX_EXPORT_FONT_SIZE = 72




def effective_scale_for_image(width: int, height: int, requested_scale: float) -> float:
    """
    Return the scale to use for export so that max dimension does not exceed MAX_EXPORT_DIMENSION.
    Tries requested scale, then next magnification down (4→2→1.5→1), until under limit or native.
    Never returns a scale that would make the image smaller than native.
    """
    if requested_scale <= 1.0 or width <= 0 or height <= 0:
        return 1.0
    max_dim = max(width, height)
    for s in EXPORT_SCALE_ORDERED:
        if s <= requested_scale and max_dim * s <= MAX_EXPORT_DIMENSION:
            return float(s)
    return 1.0



def export_line_thickness_pixels(
    setting: int,
    width: int,
    height: int,
    scale_factor: float = 1.0
) -> int:
    """
    Compute line thickness in pixels for export.
    Formula: (1/100) * (setting/2) * (width+height)/2 * scale_factor.
    Result is multiplied by 0.5 (half) for export line thickness.
    """
    if width <= 0 or height <= 0:
        return MIN_EXPORT_LINE_THICKNESS
    base = (1.0 / 100.0) * (setting / 2.0) * ((width + height) / 2.0) * scale_factor
    base = base * 0.5  # Reduce line thickness by half for export
    return max(MIN_EXPORT_LINE_THICKNESS, int(round(base)))

def export_text_size_pixels(
    setting: int,
    width: int,
    height: int,
    scale_factor: float = 1.0
) -> int:
    """
    Compute text/font size in pixels for export. Clamped to [MIN_EXPORT_FONT_SIZE, MAX_EXPORT_FONT_SIZE].
    Formula: (1/100) * setting * (width+height)/2 * scale_factor.
    Result is multiplied by 0.25 (one quarter) for export text size.
    """
    if width <= 0 or height <= 0:
        return MIN_EXPORT_FONT_SIZE
    base = (1.0 / 100.0) * setting * ((width + height) / 2.0) * scale_factor
    base = base * 0.25  # Reduce text size to one quarter for export
    return max(MIN_EXPORT_FONT_SIZE, min(MAX_EXPORT_FONT_SIZE, int(round(base))))

def process_image_by_photometric_interpretation(image: Image.Image, dataset: Dataset) -> Image.Image:
    """
    Process image based on PhotometricInterpretation tag.
    
    Handles:
    - MONOCHROME1: Invert image (pixel values increase with decreasing brightness)
    - MONOCHROME2: No inversion needed (standard grayscale)
    - RGB: No special handling needed (already RGB)
    - YBR_FULL, YBR_FULL_422, YBR_ICT, YBR_RCT: Convert to RGB
    - PALETTE COLOR: Handle palette lookup (basic support)
    
    Args:
        image: PIL Image to process
        dataset: DICOM dataset containing PhotometricInterpretation tag
        
    Returns:
        Processed PIL Image ready for export
    """
    try:
        # Get PhotometricInterpretation tag (default to MONOCHROME2)
        photometric_interpretation = getattr(dataset, 'PhotometricInterpretation', 'MONOCHROME2')

        # Handle string or list/tuple values
        if isinstance(photometric_interpretation, (list, tuple)):
            photometric_interpretation = str(photometric_interpretation[0]).strip()
        else:
            photometric_interpretation = str(photometric_interpretation).strip()

        if not photometric_interpretation:
            photometric_interpretation = 'MONOCHROME2'  # Default

        pi_upper = photometric_interpretation.upper()

        # Handle MONOCHROME1: Invert image
        if pi_upper == 'MONOCHROME1':
            img_array = np.array(image)
            if len(img_array.shape) == 2:
                # Grayscale
                img_array = 255 - img_array
                image = Image.fromarray(img_array, mode='L')
            elif len(img_array.shape) == 3:
                # Color (shouldn't happen for MONOCHROME1, but handle gracefully)
                img_array = 255 - img_array
                image = Image.fromarray(img_array, mode=image.mode)

        # Handle MONOCHROME2: No inversion needed (standard grayscale)
        elif pi_upper == 'MONOCHROME2':
            # No processing needed - MONOCHROME2 is the standard format
            pass

        # Handle RGB: Check for JPEGLS-RGB channel order issues
        elif pi_upper == 'RGB':
            # Already RGB, but check for JPEGLS-RGB channel order issues
            img_array = np.array(image)
            if len(img_array.shape) == 3 and img_array.shape[2] == 3:
                # Get transfer syntax for RGB/BGR detection
                transfer_syntax = None
                if hasattr(dataset, 'file_meta') and hasattr(dataset.file_meta, 'TransferSyntaxUID'):
                    transfer_syntax = str(dataset.file_meta.TransferSyntaxUID)
                # Check and fix RGB/BGR channel order for JPEGLS-RGB
                rgb_array = DICOMProcessor.detect_and_fix_rgb_channel_order(
                    img_array,
                    photometric_interpretation=photometric_interpretation,
                    transfer_syntax=transfer_syntax,
                    dataset=dataset
                )
                image = Image.fromarray(rgb_array, mode='RGB')

        # Handle YBR formats: Convert to RGB
        elif any(ybr_type in pi_upper for ybr_type in ['YBR_FULL', 'YBR_FULL_422', 'YBR_ICT', 'YBR_RCT']):
            # Convert YBR to RGB (pass PhotometricInterpretation for correct coefficient selection)
            img_array = np.array(image)
            if len(img_array.shape) == 3 and img_array.shape[2] == 3:
                # Get transfer syntax for YBR conversion
                transfer_syntax = None
                if hasattr(dataset, 'file_meta') and hasattr(dataset.file_meta, 'TransferSyntaxUID'):
                    transfer_syntax = str(dataset.file_meta.TransferSyntaxUID)
                # Convert YBR to RGB
                rgb_array = DICOMProcessor.convert_ybr_to_rgb(
                    img_array,
                    photometric_interpretation=photometric_interpretation,
                    transfer_syntax=transfer_syntax
                )
                image = Image.fromarray(rgb_array, mode='RGB')
            else:
                # Unexpected shape for YBR, log warning but continue
                print(f"[EXPORT] Warning: Unexpected image shape for YBR format: {img_array.shape}")

        # Handle PALETTE COLOR: Basic support (may need palette lookup table in future)
        elif 'PALETTE' in pi_upper or 'COLOR' in pi_upper:
            # For now, just ensure it's RGB mode
            # Future enhancement: Apply palette lookup table if available
            if image.mode != 'RGB':
                image = image.convert('RGB')

        # Unknown format: Try to ensure RGB mode for color images
        else:
            # For unknown formats, ensure RGB mode if it's a color image
            if image.mode not in ['L', 'RGB']:
                image = image.convert('RGB')

        return image

    except Exception as e:
        print_redacted(f"[EXPORT] Error processing image by PhotometricInterpretation: {e}")
        _logger.debug("%s", sanitized_format_exc())
        # Return original image on error
        return image



def create_projection_for_export(
    dataset: Dataset,
    studies: dict[str, dict[str, list[Dataset]]],
    study_uid: str,
    series_uid: str,
    slice_index: int,
    projection_type: str,
    projection_slice_count: int,
    window_center: float | None,
    window_width: float | None,
    use_rescaled_values: bool
) -> Image.Image | None:
    """
    Create a projection image for export.
    
    Args:
        dataset: Current dataset (for metadata)
        studies: Dictionary of studies
        study_uid: Study UID
        series_uid: Series UID
        slice_index: Current slice index
        projection_type: Type of projection ("aip", "mip", or "minip")
        projection_slice_count: Number of slices to combine
        window_center: Window center value
        window_width: Window width value
        use_rescaled_values: Whether to use rescaled values
        
    Returns:
        PIL Image or None if projection failed
    """
    try:
        # Get series datasets
        if study_uid not in studies or series_uid not in studies[study_uid]:
            return None

        series_datasets = studies[study_uid][series_uid]
        total_slices = len(series_datasets)

        if total_slices < 2:
            # Need at least 2 slices for projection
            return None

        # Calculate slice range - match viewer behavior
        start_slice = max(0, slice_index)
        end_slice = min(total_slices - 1, slice_index + projection_slice_count - 1)

        # Ensure we have at least 2 slices
        if end_slice - start_slice + 1 < 2:
            return None

        # Gather slices for projection
        projection_slices = []
        for i in range(start_slice, end_slice + 1):
            if 0 <= i < total_slices:
                projection_slices.append(series_datasets[i])

        if len(projection_slices) < 2:
            return None

        # Calculate projection based on type
        projection_array = None
        if projection_type == "aip":
            projection_array = DICOMProcessor.average_intensity_projection(projection_slices)
        elif projection_type == "mip":
            projection_array = DICOMProcessor.maximum_intensity_projection(projection_slices)
        elif projection_type == "minip":
            projection_array = DICOMProcessor.minimum_intensity_projection(projection_slices)

        if projection_array is None:
            return None

        # Apply rescale if needed
        if use_rescaled_values:
            rescale_slope, rescale_intercept, _ = DICOMProcessor.get_rescale_parameters(dataset)
            if rescale_slope is not None and rescale_intercept is not None:
                projection_array = projection_array.astype(np.float32) * float(rescale_slope) + float(rescale_intercept)

        # Apply window/level
        if window_center is not None and window_width is not None:
            processed_array = DICOMProcessor.apply_window_level(
                projection_array,
                window_center,
                window_width
            )
        else:
            # No window/level, normalize to 0-255
            processed_array = projection_array.astype(np.float32)
            if processed_array.max() > processed_array.min():
                processed_array = ((processed_array - processed_array.min()) /
                                 (processed_array.max() - processed_array.min()) * 255.0)
            processed_array = np.clip(processed_array, 0, 255).astype(np.uint8)

        # Convert to PIL Image
        if len(processed_array.shape) == 2:
            # Grayscale
            image = Image.fromarray(processed_array, mode='L')
        elif len(processed_array.shape) == 3 and processed_array.shape[2] == 3:
            # RGB
            image = Image.fromarray(processed_array, mode='RGB')
        else:
            # Fallback
            image = Image.fromarray(processed_array)

        return image
    except Exception as e:
        print_redacted(f"Error creating projection for export: {e}")
        _logger.debug("%s", sanitized_format_exc())
        return None

def create_projection_dataset(
    dataset: Dataset,
    studies: dict[str, dict[str, list[Dataset]]],
    study_uid: str,
    series_uid: str,
    slice_index: int,
    projection_type: str,
    projection_slice_count: int,
    use_rescaled_values: bool
) -> Dataset | None:
    """
    Create a projection dataset for DICOM export.
    
    Args:
        dataset: Current dataset (for metadata)
        studies: Dictionary of studies
        study_uid: Study UID
        series_uid: Series UID
        slice_index: Current slice index
        projection_type: Type of projection ("aip", "mip", or "minip")
        projection_slice_count: Number of slices to combine
        use_rescaled_values: Whether to use rescaled values
        
    Returns:
        Modified Dataset with projection as pixel data, or None if failed
    """
    try:
        # Get series datasets
        if study_uid not in studies or series_uid not in studies[study_uid]:
            return None

        series_datasets = studies[study_uid][series_uid]
        total_slices = len(series_datasets)

        if total_slices < 1:
            return None

        # Calculate slice range
        start_slice = max(0, slice_index)
        end_slice = min(total_slices - 1, slice_index + projection_slice_count - 1)

        # Gather slices for projection
        projection_slices = []
        for i in range(start_slice, end_slice + 1):
            if 0 <= i < total_slices:
                projection_slices.append(series_datasets[i])

        if len(projection_slices) < 1:
            return None

        # Create a copy of the first dataset to preserve metadata
        projection_dataset = copy.deepcopy(dataset)

        # Determine if we actually compute a projection or just copy the single slice
        is_actual_projection = len(projection_slices) >= 2

        if is_actual_projection:
            # Calculate projection based on type
            projection_array = None
            if projection_type == "aip":
                projection_array = DICOMProcessor.average_intensity_projection(projection_slices)
            elif projection_type == "mip":
                projection_array = DICOMProcessor.maximum_intensity_projection(projection_slices)
            elif projection_type == "minip":
                projection_array = DICOMProcessor.minimum_intensity_projection(projection_slices)

            if projection_array is None:
                return None

            # Update pixel data with projection array
            # The projection array is float32 from averaging/max/min operations
            # Need to convert it properly to integer format for DICOM storage

            # Get original pixel characteristics
            original_pixel_array = DICOMProcessor.get_pixel_array(dataset)
            if original_pixel_array is None:
                # Cannot infer dtype / bounds for projection pixel conversion.
                return None
            original_dtype = original_pixel_array.dtype
            bits_stored = getattr(dataset, 'BitsStored', 16)

            # Convert projection array to appropriate integer type
            if np.issubdtype(original_dtype, np.integer):
                # Original is integer type - convert projection to same type
                if np.issubdtype(original_dtype, np.unsignedinteger):
                    # Unsigned integer
                    if bits_stored <= 8:
                        target_dtype = np.uint8
                    elif bits_stored <= 16:
                        target_dtype = np.uint16
                    else:
                        target_dtype = np.uint32
                else:
                    # Signed integer
                    if bits_stored <= 8:
                        target_dtype = np.int8
                    elif bits_stored <= 16:
                        target_dtype = np.int16
                    else:
                        target_dtype = np.int32

                # Clip to valid range for the data type
                info = np.iinfo(target_dtype)
                projection_array_clipped = np.clip(projection_array, info.min, info.max)
                projection_array_int = projection_array_clipped.astype(target_dtype)
            else:
                # Original is float - this is unusual, default to uint16
                target_dtype = np.uint16
                projection_array_clipped = np.clip(projection_array, 0, 65535)
                projection_array_int = projection_array_clipped.astype(target_dtype)

            # Update pixel data
            projection_dataset.PixelData = projection_array_int.tobytes()

            # Update DICOM tags to match the pixel data
            projection_dataset.Rows = projection_array.shape[0]
            projection_dataset.Columns = projection_array.shape[1]

            # Ensure bits are correct
            if target_dtype == np.uint8:
                projection_dataset.BitsAllocated = 8
                projection_dataset.BitsStored = 8
                projection_dataset.HighBit = 7
                projection_dataset.PixelRepresentation = 0
            elif target_dtype == np.int8:
                projection_dataset.BitsAllocated = 8
                projection_dataset.BitsStored = 8
                projection_dataset.HighBit = 7
                projection_dataset.PixelRepresentation = 1
            elif target_dtype == np.uint16:
                projection_dataset.BitsAllocated = 16
                projection_dataset.BitsStored = 16
                projection_dataset.HighBit = 15
                projection_dataset.PixelRepresentation = 0
            elif target_dtype == np.int16:
                projection_dataset.BitsAllocated = 16
                projection_dataset.BitsStored = 16
                projection_dataset.HighBit = 15
                projection_dataset.PixelRepresentation = 1
            elif target_dtype == np.uint32:
                projection_dataset.BitsAllocated = 32
                projection_dataset.BitsStored = 32
                projection_dataset.HighBit = 31
                projection_dataset.PixelRepresentation = 0
            elif target_dtype == np.int32:
                projection_dataset.BitsAllocated = 32
                projection_dataset.BitsStored = 32
                projection_dataset.HighBit = 31
                projection_dataset.PixelRepresentation = 1
        else:
            # Single slice - keep original pixel data but modify metadata
            # Pixel data is already in projection_dataset from deepcopy
            # No need to modify pixel-related tags
            pass

        # Update relevant DICOM tags (for both single and multi-slice)
        projection_name_map = {
            "aip": "Average Intensity Projection (AIP)",
            "mip": "Maximum Intensity Projection (MIP)",
            "minip": "Minimum Intensity Projection (MinIP)"
        }
        projection_display_name = projection_name_map.get(projection_type, "Projection")

        # Update ImageComments to indicate projection
        existing_comments = getattr(projection_dataset, 'ImageComments', '')
        if is_actual_projection:
            projection_info = f"{projection_display_name} - {len(projection_slices)} slices (instances {start_slice+1} to {end_slice+1})"
        else:
            projection_info = f"Derived from instance {start_slice+1} (part of projection export)"

        if existing_comments:
            projection_dataset.ImageComments = f"{existing_comments}; {projection_info}"
        else:
            projection_dataset.ImageComments = projection_info

        # Update SeriesDescription to indicate projection
        existing_desc = getattr(projection_dataset, 'SeriesDescription', '')
        if existing_desc:
            projection_dataset.SeriesDescription = f"{existing_desc} - {projection_type.upper()}"
        else:
            projection_dataset.SeriesDescription = f"{projection_type.upper()}"

        # Update Slice Thickness to combined thickness (only for actual projections)
        if is_actual_projection:
            # Calculate total thickness from projection slices
            total_thickness = 0.0
            thickness_count = 0
            for proj_slice in projection_slices:
                thickness = get_slice_thickness(proj_slice)
                if thickness is not None:
                    total_thickness += thickness
                    thickness_count += 1

            if thickness_count > 0:
                projection_dataset.SliceThickness = total_thickness
        # else: keep original slice thickness for single slice

        # Update Image Type to indicate this is a DERIVED image
        # Image Type is multi-valued: [ORIGINAL/DERIVED, PRIMARY/SECONDARY, additional values]
        projection_type_map = {
            "mip": "MAXIMUM INTENSITY PROJECTION",
            "aip": "AVERAGE INTENSITY PROJECTION",
            "minip": "MINIMUM INTENSITY PROJECTION"
        }
        projection_image_type = projection_type_map.get(projection_type, "PROJECTION")
        projection_dataset.ImageType = ["DERIVED", "SECONDARY", projection_image_type]

        # Keep original Modality (CT, MR, PT, etc.) - do NOT change to SC
        # The modality tag should remain as the original acquisition modality

        # Update or remove Spacing Between Slices
        if hasattr(projection_dataset, 'SpacingBetweenSlices'):
            # For a single projection image, this doesn't apply
            delattr(projection_dataset, 'SpacingBetweenSlices')

        # Update Instance Number to avoid conflicts
        # Use a high number to indicate it's derived
        if hasattr(projection_dataset, 'InstanceNumber'):
            projection_dataset.InstanceNumber = 9000 + slice_index

        # Update SOP Instance UID to make it unique
        projection_dataset.SOPInstanceUID = pydicom.uid.generate_uid()

        return projection_dataset
    except Exception as e:
        print_redacted(f"Error creating projection dataset: {e}")
        _logger.debug("%s", sanitized_format_exc())
        return None

class _Annotations(NamedTuple):
    """Annotations resolved for one exported slice."""

    rois: list[Any]
    measurements: list[Any]
    text_items: list[Any]
    arrow_items: list[Any]


def _normalize_rgb(color: Any, default: RGB | None) -> RGB | None:
    """Coerce a colour sequence to an ``(r, g, b)`` int tuple, else return ``default``."""
    if isinstance(color, (list, tuple)) and len(color) >= 3:
        return (int(color[0]), int(color[1]), int(color[2]))
    return default


def _overlay_text_color(font_color: Any) -> RGB:
    """Overlay corner-text colour: honour the user's choice, but never pure black."""
    rgb = _normalize_rgb(font_color, None)
    if rgb is None:
        return (255, 255, 0)  # bright yellow when unspecified
    if rgb == (0, 0, 0):
        return (255, 255, 255)  # pure black would be invisible
    return rgb


def _resolve_series_keys(
    dataset: Dataset, study_uid: str | None, series_uid: str | None
) -> tuple[str, str]:
    """Dataset-derived lookup keys, matching the app's ``get_composite_series_key``."""
    export_study_uid = getattr(dataset, 'StudyInstanceUID', '') or (study_uid or '')
    export_series_uid = get_composite_series_key(dataset) or (series_uid or '')
    return export_study_uid, export_series_uid


def _safe_fetch(fetch: Any, *args: Any) -> list[Any]:
    """Call a tool's per-slice getter, treating any failure as "no annotations"."""
    try:
        return list(fetch(*args))
    except Exception:
        return []


def _collect_annotations(
    study_uid: str,
    series_uid: str,
    slice_index: int,
    roi_manager,
    measurement_tool,
    text_annotation_tool,
    arrow_annotation_tool,
    subwindow_annotation_managers: list[dict[str, Any]] | None,
    include_config_annotations: bool,
) -> _Annotations:
    """
    Resolve the annotations to draw for one slice.

    When ``subwindow_annotation_managers`` is provided the annotations of every
    subwindow are aggregated; otherwise the single passed-in managers are used.
    Text and arrow annotations are only collected when a config manager is
    available, since their styling comes from it.
    """
    if subwindow_annotation_managers:
        rois: list[Any] = []
        measurements: list[Any] = []
        text_items: list[Any] = []
        arrow_items: list[Any] = []
        for managers in subwindow_annotation_managers:
            roi_mgr = managers.get('roi_manager')
            if roi_mgr:
                rois.extend(roi_mgr.get_rois_for_slice(study_uid, series_uid, slice_index))
            meas_tool = managers.get('measurement_tool')
            if meas_tool:
                measurements.extend(
                    meas_tool.measurements.get((study_uid, series_uid, slice_index), [])
                )
            text_tool = managers.get('text_annotation_tool')
            if text_tool:
                text_items.extend(
                    _safe_fetch(
                        text_tool.get_annotations_for_slice,
                        study_uid, series_uid, slice_index,
                    )
                )
            arrow_tool = managers.get('arrow_annotation_tool')
            if arrow_tool:
                arrow_items.extend(
                    _safe_fetch(
                        arrow_tool.get_arrows_for_slice,
                        study_uid, series_uid, slice_index,
                    )
                )
        return _Annotations(rois, measurements, text_items, arrow_items)

    single_rois = (
        roi_manager.get_rois_for_slice(study_uid, series_uid, slice_index)
        if roi_manager else []
    )
    single_measurements = (
        measurement_tool.measurements.get((study_uid, series_uid, slice_index), [])
        if measurement_tool else []
    )
    single_text: list[Any] = []
    single_arrows: list[Any] = []
    if include_config_annotations:
        if text_annotation_tool:
            single_text = _safe_fetch(
                text_annotation_tool.get_annotations_for_slice,
                study_uid, series_uid, slice_index,
            )
        if arrow_annotation_tool:
            single_arrows = _safe_fetch(
                arrow_annotation_tool.get_arrows_for_slice,
                study_uid, series_uid, slice_index,
            )
    return _Annotations(single_rois, single_measurements, single_text, single_arrows)


def _roi_stats_text(roi) -> str:
    """Assemble the visible-statistics block for one ROI."""
    formats: list[tuple[str, str]] = [
        ("mean", "Mean: {:.2f}"),
        ("std", "Std Dev: {:.2f}"),
        ("min", "Min: {:.2f}"),
        ("max", "Max: {:.2f}"),
        ("area", "Area: {:.2f}"),
    ]
    lines = [
        template.format(roi.statistics[key])
        for key, template in formats
        if key in roi.visible_statistics and key in roi.statistics
    ]
    if "count" in roi.visible_statistics and "count" in roi.statistics:
        lines.append(f"Count: {int(roi.statistics['count'])}")
    return "\n".join(lines)


def _draw_rois(
    draw: ImageDraw.ImageDraw,
    rois: list[Any],
    size: tuple[int, int],
    anno_scale: float,
    coordinate_scale: float,
    config_manager,
) -> None:
    """Draw ROI outlines plus their statistics text."""
    if not rois:
        return
    width, height = size

    line_color: Any = (255, 0, 0)
    font_color: Any = (255, 255, 0)
    line_thickness_setting = 2
    font_size_setting = 6
    if config_manager:
        line_color = config_manager.get_roi_line_color()
        font_color = config_manager.get_roi_font_color()
        line_thickness_setting = config_manager.get_roi_line_thickness()
        font_size_setting = config_manager.get_roi_font_size()

    line_thickness = export_line_thickness_pixels(
        line_thickness_setting, width, height, anno_scale
    )
    font_size = export_text_size_pixels(font_size_setting, width, height, anno_scale)
    font_family = config_manager.get_roi_font_family() if config_manager else "IBM Plex Sans"
    font_variant = config_manager.get_roi_font_variant() if config_manager else "Bold"

    for roi in rois:
        bounds = roi.get_bounds()
        x1 = int(max(0, min(bounds.left() * coordinate_scale, width)))
        y1 = int(max(0, min(bounds.top() * coordinate_scale, height)))
        x2 = int(max(0, min(bounds.right() * coordinate_scale, width)))
        y2 = int(max(0, min(bounds.bottom() * coordinate_scale, height)))

        if roi.shape_type == "rectangle":
            draw.rectangle([x1, y1, x2, y2], outline=line_color, width=line_thickness)
        elif roi.shape_type == "ellipse":
            draw.ellipse([x1, y1, x2, y2], outline=line_color, width=line_thickness)

        if not (roi.statistics and roi.statistics_overlay_visible):
            continue
        font = _load_font_with_fallback(font_size, variant=font_variant, font_family=font_family)
        if not font:
            continue
        stats_text = _roi_stats_text(roi)
        if stats_text:
            draw.text((int(x2 + 5), int(y1 + 5)), stats_text, fill=font_color, font=font)


def _draw_measurements(
    draw: ImageDraw.ImageDraw,
    measurements: list[Any],
    size: tuple[int, int],
    anno_scale: float,
    coordinate_scale: float,
    config_manager,
) -> None:
    """Draw distance and angle measurements with their labels."""
    if not measurements:
        return
    width, height = size

    line_color: Any = (0, 255, 0)
    font_color: Any = (0, 255, 0)
    line_thickness_setting = 2
    font_size_setting = 6
    if config_manager:
        line_color = config_manager.get_measurement_line_color()
        font_color = config_manager.get_measurement_font_color()
        line_thickness_setting = config_manager.get_measurement_line_thickness()
        font_size_setting = config_manager.get_measurement_font_size()

    line_thickness = max(
        2, export_line_thickness_pixels(line_thickness_setting, width, height, anno_scale)
    )
    font_size = export_text_size_pixels(font_size_setting, width, height, anno_scale)
    font_family = (
        config_manager.get_measurement_font_family() if config_manager else "IBM Plex Sans"
    )
    font_variant = config_manager.get_measurement_font_variant() if config_manager else "Bold"

    for measurement in measurements:
        if isinstance(measurement, AngleMeasurementItem):
            ax1 = int(measurement.p1.x() * coordinate_scale)
            ay1 = int(measurement.p1.y() * coordinate_scale)
            ax2 = int(measurement.p2.x() * coordinate_scale)
            ay2 = int(measurement.p2.y() * coordinate_scale)
            ax3 = int(measurement.p3.x() * coordinate_scale)
            ay3 = int(measurement.p3.y() * coordinate_scale)
            draw.line([(ax1, ay1), (ax2, ay2)], fill=line_color, width=line_thickness)
            draw.line([(ax2, ay2), (ax3, ay3)], fill=line_color, width=line_thickness)
            label_x = int((ax1 + ax2 + ax3) / 3)
            label_y = int((ay1 + ay2 + ay3) / 3)
            label = measurement.angle_formatted
        else:
            start_x = int(measurement.start_point.x() * coordinate_scale)
            start_y = int(measurement.start_point.y() * coordinate_scale)
            end_x = int(
                (measurement.start_point.x() + measurement.end_relative.x()) * coordinate_scale
            )
            end_y = int(
                (measurement.start_point.y() + measurement.end_relative.y()) * coordinate_scale
            )
            draw.line(
                [(start_x, start_y), (end_x, end_y)], fill=line_color, width=line_thickness
            )
            label_x = int((start_x + end_x) / 2)
            label_y = int((start_y + end_y) / 2)
            label = measurement.distance_formatted

        font = _load_font_with_fallback(font_size, variant=font_variant, font_family=font_family)
        if font:
            draw.text((label_x, label_y), label, fill=font_color, font=font)


def _draw_text_annotations(
    draw: ImageDraw.ImageDraw,
    text_items: list[Any],
    size: tuple[int, int],
    anno_scale: float,
    coordinate_scale: float,
    config_manager,
) -> None:
    """Draw free-text annotations, clamped inside the image."""
    if not text_items or not config_manager:
        return
    width, height = size
    try:
        font_size = export_text_size_pixels(
            config_manager.get_text_annotation_font_size(), width, height, anno_scale
        )
        fill_color = _normalize_rgb(
            config_manager.get_text_annotation_color(), (255, 255, 0)
        )
        font = _load_font_with_fallback(
            font_size,
            variant=config_manager.get_text_annotation_font_variant(),
            font_family=config_manager.get_text_annotation_font_family(),
        )
        if not font:
            return
        for item in text_items:
            try:
                sx = item.scenePos().x() * coordinate_scale
                sy = item.scenePos().y() * coordinate_scale
                tx = int(max(0, min(sx, width - 1)))
                ty = int(max(0, min(sy, height - 1)))
                text = item.toPlainText() or ""
                if text:
                    draw.text((tx, ty), text, fill=fill_color, font=font)
            except Exception:
                continue
    except Exception:
        pass


def _draw_arrow_annotations(
    draw: ImageDraw.ImageDraw,
    arrow_items: list[Any],
    size: tuple[int, int],
    anno_scale: float,
    coordinate_scale: float,
    config_manager,
) -> None:
    """Draw arrow annotations, clamped inside the image."""
    if not arrow_items or not config_manager:
        return
    width, height = size
    try:
        size_setting = getattr(config_manager, 'get_arrow_annotation_size', lambda: 2)()
        thickness = max(
            1, export_line_thickness_pixels(size_setting, width, height, anno_scale)
        )
        raw_color = getattr(
            config_manager, 'get_arrow_annotation_color', lambda: (255, 255, 0)
        )()
        line_color = _normalize_rgb(raw_color, (255, 255, 0))

        for item in arrow_items:
            try:
                pos = item.pos()
                dx = item.end_point.x() - item.start_point.x()
                dy = item.end_point.y() - item.start_point.y()
                start_x = max(0, min(int(pos.x() * coordinate_scale), width))
                start_y = max(0, min(int(pos.y() * coordinate_scale), height))
                end_x = max(0, min(int((pos.x() + dx) * coordinate_scale), width))
                end_y = max(0, min(int((pos.y() + dy) * coordinate_scale), height))
                draw.line(
                    [(start_x, start_y), (end_x, end_y)], fill=line_color, width=thickness
                )
            except Exception:
                continue
    except Exception:
        pass


def _compute_projection_range(
    studies: dict[str, dict[str, list[Dataset]]] | None,
    study_uid: str | None,
    series_uid: str | None,
    slice_index: int | None,
    projection_slice_count: int,
) -> tuple[int | None, int | None, float | None]:
    """Slice range and accumulated thickness covered by the projection, if any."""
    if not (studies and study_uid and series_uid and slice_index is not None):
        return None, None, None
    if study_uid not in studies or series_uid not in studies[study_uid]:
        return None, None, None

    series_datasets = studies[study_uid][series_uid]
    start_slice = max(0, slice_index)
    end_slice = min(len(series_datasets) - 1, slice_index + projection_slice_count - 1)

    total_thickness = 0.0
    thickness_count = 0
    for i in range(start_slice, end_slice + 1):
        if 0 <= i < len(series_datasets):
            thickness = get_slice_thickness(series_datasets[i])
            if thickness is not None:
                total_thickness += thickness
                thickness_count += 1

    return start_slice, end_slice, (total_thickness if thickness_count > 0 else None)


def _draw_corner_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: Any,
    color: RGB,
    x: float,
    y: float,
    align: str,
    is_bottom: bool,
) -> None:
    """Draw one corner block, right-aligning line by line when required."""
    bbox = draw.textbbox((0, 0), text, font=font)
    if is_bottom:
        y -= bbox[3] - bbox[1]

    if align != "right":
        draw.text((x, y), text, fill=color, font=font)
        return

    current_y = y
    for line in text.split('\n'):
        if line.strip():
            line_bbox = draw.textbbox((0, 0), line, font=font)
            # Position each line so it ends at x (the right edge position)
            draw.text((x - (line_bbox[2] - line_bbox[0]), current_y), line, fill=color, font=font)
            current_y += line_bbox[3] - line_bbox[1]
        else:
            empty_bbox = draw.textbbox((0, 0), "A", font=font)
            current_y += empty_bbox[3] - empty_bbox[1]


def _draw_corner_overlays(
    draw: ImageDraw.ImageDraw,
    dataset: Dataset,
    size: tuple[int, int],
    anno_scale: float,
    overlay_manager,
    config_manager,
    slice_index: int | None,
    total_slices: int | None,
    projection_enabled: bool,
    projection_type: str,
    projection_range: tuple[int | None, int | None, float | None],
) -> None:
    """Draw the four DICOM corner-text blocks."""
    if not (overlay_manager and config_manager):
        return
    width, height = size

    parser = DICOMParser(dataset)
    corner_tags = config_manager.get_overlay_tags(get_modality(parser))
    font_size = export_text_size_pixels(
        config_manager.get_overlay_font_size(), width, height, anno_scale
    )
    text_color = _overlay_text_color(overlay_manager.font_color)
    # Bold variant matches the viewer, which uses setBold(True).
    font = _load_font_with_fallback(
        font_size,
        variant=config_manager.get_overlay_font_variant(),
        font_family=config_manager.get_overlay_font_family(),
    )
    if not font:
        return

    projection_start, projection_end, projection_thickness = projection_range
    margin = 10
    corners = [
        ("upper_left", margin, margin, "left", False),
        ("upper_right", width - margin, margin, "right", False),
        ("lower_left", margin, height - margin, "left", True),
        ("lower_right", width - margin, height - margin, "right", True),
    ]

    for corner_name, x, y, align, is_bottom in corners:
        tags = corner_tags.get(corner_name, [])
        if not tags:
            continue

        # get_corner_text() owns "Slice X/Y" formatting, projection info and edge cases.
        text = get_corner_text(
            parser, tags, overlay_manager.privacy_mode, total_slices,
            projection_enabled=projection_enabled,
            projection_start_slice=projection_start,
            projection_end_slice=projection_end,
            projection_total_thickness=projection_thickness,
            projection_type=projection_type,
            stack_position=(slice_index + 1) if slice_index is not None else None,
        )
        if not text:
            continue
        _draw_corner_text(draw, text, font, text_color, x, y, align, is_bottom)


def render_overlays_and_rois(
    image: Image.Image,
    dataset: Dataset,
    roi_manager,
    overlay_manager,
    measurement_tool,
    config_manager,
    text_annotation_tool=None,
    arrow_annotation_tool=None,
    study_uid: str | None = None,
    series_uid: str | None = None,
    slice_index: int | None = None,
    total_slices: int | None = None,
    coordinate_scale: float = 1.0,
    export_scale: float = 1.0,
    scale_annotations_with_image: bool = False,
    projection_enabled: bool = False,
    projection_type: str = "aip",
    projection_slice_count: int = 4,
    studies: dict[str, dict[str, list[Dataset]]] | None = None,
    subwindow_annotation_managers: list[dict[str, Any]] | None = None
) -> Image.Image:
    """
    Render overlays, ROIs, and measurements onto a PIL Image.

    Annotation sizes use formula: line_thickness = (1/100)*(setting/2)*(w+h)/2,
    text_size = (1/100)*setting*(w+h)/2; optional scale by export_scale when
    scale_annotations_with_image.
    """
    # Convert to RGB if grayscale (needed for drawing colored ROIs)
    if image.mode == 'L':
        image = image.convert('RGB')

    draw = ImageDraw.Draw(image)
    size = image.size
    anno_scale = export_scale if scale_annotations_with_image else 1.0

    export_study_uid, export_series_uid = _resolve_series_keys(dataset, study_uid, series_uid)

    if export_study_uid and export_series_uid and slice_index is not None:
        annotations = _collect_annotations(
            export_study_uid, export_series_uid, slice_index,
            roi_manager, measurement_tool, text_annotation_tool, arrow_annotation_tool,
            subwindow_annotation_managers,
            include_config_annotations=bool(config_manager),
        )
        _draw_rois(
            draw, annotations.rois, size, anno_scale, coordinate_scale, config_manager
        )
        _draw_measurements(
            draw, annotations.measurements, size, anno_scale, coordinate_scale, config_manager
        )
        _draw_text_annotations(
            draw, annotations.text_items, size, anno_scale, coordinate_scale, config_manager
        )
        _draw_arrow_annotations(
            draw, annotations.arrow_items, size, anno_scale, coordinate_scale, config_manager
        )

    projection_range = _compute_projection_range(
        studies if projection_enabled else None,
        study_uid, series_uid, slice_index, projection_slice_count,
    )
    _draw_corner_overlays(
        draw, dataset, size, anno_scale, overlay_manager, config_manager,
        slice_index, total_slices, projection_enabled, projection_type, projection_range,
    )

    return image
