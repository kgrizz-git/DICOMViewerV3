"""
DICOM Image Processor

This module handles image processing operations on DICOM data including:
- Window/level adjustment
- Image array extraction
- Average and Maximum Intensity Projections (AIP/MIP)
- Image format conversions

Inputs:
    - pydicom.Dataset objects
    - Window/level values
    - Slice indices for projections
    
Outputs:
    - Processed image arrays
    - PIL Image objects
    - NumPy arrays
    
Requirements:
    - pydicom library
    - numpy for array operations
    - PIL/Pillow for image handling
"""

import logging
from typing import ClassVar

import numpy as np
from PIL import Image
from pydicom.dataset import Dataset

# Try to import pydicom's convert_color_space (available in pydicom 3.0+)
try:
    # pydicom 3.x: convert_color_space lives in pydicom.pixels.processing (absent in 2.x).
    from pydicom.pixels.processing import (  # pyright: ignore[reportMissingImports]
        convert_color_space,
    )

    pydicom_convert_available = True
except ImportError:
    pydicom_convert_available = False
    convert_color_space = None

# Phase 2 refactor: domain modules (facade delegates to these)
from core import (
    dicom_color,
    dicom_image_render,
    dicom_palette,
    dicom_pixel_array,
    dicom_pixel_stats,
    dicom_projections,
    dicom_rescale,
    dicom_window_level,
)

_logger = logging.getLogger(__name__)


class DICOMProcessor:
    """
    Processes DICOM image data for display and analysis.
    
    Handles:
    - Extracting pixel arrays from DICOM datasets
    - Applying window/level transformations
    - Creating intensity projections (AIP/MIP)
    - Converting to displayable formats
    """

    # Class-level set to track files that have shown compression errors (to suppress redundant messages)
    _compression_error_files: ClassVar[set[str]] = set()

    @staticmethod
    def get_rescale_parameters(dataset: Dataset) -> tuple[float | None, float | None, str | None]:
        """Extract rescale parameters from DICOM dataset. Delegates to core.dicom_rescale."""
        return dicom_rescale.get_rescale_parameters(dataset)

    @staticmethod
    def infer_rescale_type(
        dataset: Dataset,
        rescale_slope: float | None,
        rescale_intercept: float | None,
        rescale_type: str | None
    ) -> str | None:
        """Infer rescale type when RescaleType tag is missing. Delegates to core.dicom_rescale."""
        return dicom_rescale.infer_rescale_type(dataset, rescale_slope, rescale_intercept, rescale_type)

    @staticmethod
    def is_color_image(dataset: Dataset) -> tuple[bool, str | None]:
        """Detect if a DICOM image is a color image. Delegates to core.dicom_color."""
        return dicom_color.is_color_image(dataset)

    @staticmethod
    def _is_already_rgb(pixel_array: np.ndarray) -> bool:
        """Check if pixel array appears to already be RGB (not YBR). Delegates to core.dicom_color."""
        return dicom_color._is_already_rgb(pixel_array)

    @staticmethod
    def convert_ybr_to_rgb(ybr_array: np.ndarray,
                          photometric_interpretation: str | None = None,
                          transfer_syntax: str | None = None) -> np.ndarray:
        """Convert YBR color space array to RGB. Delegates to core.dicom_color."""
        return dicom_color.convert_ybr_to_rgb(ybr_array, photometric_interpretation, transfer_syntax)

    @staticmethod
    def detect_and_fix_rgb_channel_order(pixel_array: np.ndarray,
                                         photometric_interpretation: str | None = None,
                                         transfer_syntax: str | None = None,
                                         dataset: Dataset | None = None) -> np.ndarray:
        """Detect and fix RGB/BGR channel order issues. Delegates to core.dicom_color."""
        return dicom_color.detect_and_fix_rgb_channel_order(
            pixel_array, photometric_interpretation, transfer_syntax, dataset
        )

    @staticmethod
    def _convert_ybr_to_rgb_2d(ybr_array: np.ndarray, use_rct: bool = False) -> np.ndarray:
        """Convert 2D YBR array to RGB. Delegates to core.dicom_color."""
        return dicom_color._convert_ybr_to_rgb_2d(ybr_array, use_rct)

    @staticmethod
    def _handle_planar_configuration(pixel_array: np.ndarray, dataset: Dataset) -> np.ndarray:
        """Handle PlanarConfiguration tag. Delegates to core.dicom_pixel_array."""
        return dicom_pixel_array.handle_planar_configuration(pixel_array, dataset)

    @staticmethod
    def get_pixel_array(dataset: Dataset) -> np.ndarray | None:
        """Extract pixel array from DICOM dataset. Delegates to core.dicom_pixel_array."""
        return dicom_pixel_array.get_pixel_array(dataset)

    @staticmethod
    def apply_window_level(pixel_array: np.ndarray, window_center: float,
                          window_width: float,
                          rescale_slope: float | None = None,
                          rescale_intercept: float | None = None) -> np.ndarray:
        """Apply window/level transformation to pixel array. Delegates to core.dicom_window_level."""
        return dicom_window_level.apply_window_level(
            pixel_array, window_center, window_width, rescale_slope, rescale_intercept
        )

    @staticmethod
    def apply_color_window_level_luminance(pixel_array: np.ndarray, window_center: float,
                                          window_width: float,
                                          rescale_slope: float | None = None,
                                          rescale_intercept: float | None = None) -> np.ndarray:
        """Apply window/level to color images (luminance-based). Delegates to core.dicom_window_level."""
        return dicom_window_level.apply_color_window_level_luminance(
            pixel_array, window_center, window_width, rescale_slope, rescale_intercept
        )

    @staticmethod
    def convert_window_level_rescaled_to_raw(center: float, width: float,
                                            slope: float, intercept: float) -> tuple[float, float]:
        """Convert window/level from rescaled to raw. Delegates to core.dicom_window_level."""
        return dicom_window_level.convert_window_level_rescaled_to_raw(center, width, slope, intercept)

    @staticmethod
    def convert_window_level_raw_to_rescaled(center: float, width: float,
                                             slope: float, intercept: float) -> tuple[float, float]:
        """Convert window/level from raw to rescaled. Delegates to core.dicom_window_level."""
        return dicom_window_level.convert_window_level_raw_to_rescaled(center, width, slope, intercept)

    @staticmethod
    def get_window_level_from_dataset(dataset: Dataset,
                                     rescale_slope: float | None = None,
                                     rescale_intercept: float | None = None) -> tuple[float | None, float | None, bool]:
        """Get window center and width from DICOM dataset. Delegates to core.dicom_window_level."""
        return dicom_window_level.get_window_level_from_dataset(
            dataset, rescale_slope, rescale_intercept
        )

    @staticmethod
    def get_window_level_presets_from_dataset(dataset: Dataset,
                                             rescale_slope: float | None = None,
                                             rescale_intercept: float | None = None) -> list[tuple[float, float, bool, str | None]]:
        """Get all window/level presets from DICOM dataset. Delegates to core.dicom_window_level."""
        return dicom_window_level.get_window_level_presets_from_dataset(
            dataset, rescale_slope, rescale_intercept
        )

    @staticmethod
    def dataset_to_image(dataset: Dataset, window_center: float | None = None,
                        window_width: float | None = None, apply_rescale: bool = False) -> Image.Image | None:
        """
        Convert DICOM dataset to PIL Image.

        Args:
            dataset: pydicom Dataset
            window_center: Optional window center (uses dataset default if None)
            window_width: Optional window width (uses dataset default if None)
            apply_rescale: If True, apply rescale slope/intercept in window/level calculation

        Returns:
            PIL Image or None if conversion fails
        """
        pixel_array = dicom_pixel_array.get_pixel_array(dataset)
        if pixel_array is None:
            return None

        is_color, photometric_interpretation = dicom_color.is_color_image(dataset)

        transfer_syntax = None
        if hasattr(dataset, 'file_meta') and hasattr(dataset.file_meta, 'TransferSyntaxUID'):
            transfer_syntax = str(dataset.file_meta.TransferSyntaxUID)

        is_multi_frame_color, is_single_frame_color = dicom_image_render.classify_color_shape(
            dataset, pixel_array, is_color
        )

        window_center, window_width, rescale_slope, rescale_intercept = (
            dicom_window_level.resolve_window_level_and_rescale(
                dataset, window_center, window_width, apply_rescale
            )
        )

        # PALETTE COLOR must be converted before YBR conversion and window/level application.
        if photometric_interpretation:
            pi_upper = photometric_interpretation.upper()
            if 'PALETTE' in pi_upper and 'COLOR' in pi_upper:
                pixel_array, converted = dicom_palette.convert_palette_color_to_rgb(pixel_array, dataset)
                if converted:
                    is_color = True
                    is_multi_frame_color, is_single_frame_color = dicom_image_render.reclassify_color_shape(
                        pixel_array
                    )

        if is_color and (is_single_frame_color or is_multi_frame_color):
            pixel_array, did_ybr_convert = dicom_image_render.convert_color_pixel_array(
                pixel_array, photometric_interpretation, transfer_syntax, dataset
            )
            if did_ybr_convert:
                is_multi_frame_color, is_single_frame_color = dicom_image_render.reclassify_color_shape(
                    pixel_array
                )

        if is_color and (is_single_frame_color or is_multi_frame_color):
            return dicom_image_render.render_color_image(
                pixel_array, window_center, window_width,
                rescale_slope, rescale_intercept, is_multi_frame_color
            )

        return dicom_image_render.render_grayscale_image(
            pixel_array, window_center, window_width, rescale_slope, rescale_intercept
        )

    @staticmethod
    def average_intensity_projection(slices: list[Dataset]) -> np.ndarray | None:
        """Create Average Intensity Projection from multiple slices. Delegates to core.dicom_projections."""
        return dicom_projections.average_intensity_projection(slices)

    @staticmethod
    def maximum_intensity_projection(slices: list[Dataset]) -> np.ndarray | None:
        """Create Maximum Intensity Projection from multiple slices. Delegates to core.dicom_projections."""
        return dicom_projections.maximum_intensity_projection(slices)

    @staticmethod
    def minimum_intensity_projection(slices: list[Dataset]) -> np.ndarray | None:
        """Create Minimum Intensity Projection from multiple slices. Delegates to core.dicom_projections."""
        return dicom_projections.minimum_intensity_projection(slices)

    @staticmethod
    def get_pixel_value_range(dataset: Dataset, apply_rescale: bool = False) -> tuple[float | None, float | None]:
        """Get min/max pixel values from a DICOM dataset. Delegates to core.dicom_pixel_stats."""
        return dicom_pixel_stats.get_pixel_value_range(dataset, apply_rescale)

    @staticmethod
    def get_series_pixel_value_range(datasets: list[Dataset], apply_rescale: bool = False) -> tuple[float | None, float | None]:
        """Get min/max pixel values across a series. Delegates to core.dicom_pixel_stats."""
        return dicom_pixel_stats.get_series_pixel_value_range(datasets, apply_rescale)

    @staticmethod
    def get_series_pixel_median(datasets: list[Dataset], apply_rescale: bool = False) -> float | None:
        """Get median pixel value across a series. Delegates to core.dicom_pixel_stats."""
        return dicom_pixel_stats.get_series_pixel_median(datasets, apply_rescale)
