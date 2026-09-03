"""
Export Manager – core export execution for DICOM images.

This module provides the ExportManager class that performs export of selected
slices to JPEG, PNG, or DICOM with window/level, overlays, ROIs, measurements,
and projection support. Used by the Export dialog (gui.dialogs.export_dialog).

Purpose:
    - Execute export_selected and export_slice with progress and folder structure
    - Delegates rasterization, projection, and overlay drawing to export_rendering

Inputs:
    - selected_items or single dataset, output path, format, window/level, options

Outputs:
    - Exported files on disk

Requirements:
    - PySide6 (QProgressDialog, Qt)
    - PIL/Pillow, pydicom (Dataset)
    - core.dicom_processor, core.export_rendering
"""
import os
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Optional

from PIL import Image
from pydicom.dataset import Dataset
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QProgressDialog

from core.dicom_processor import DICOMProcessor
from gui import export_rendering as _er
from utils.deep_anonymizer import DeepDICOMAnonymizer
from utils.privacy.console import print_redacted

if TYPE_CHECKING:
    from utils.deep_anonymizer import DeepAnonymizerOptions


_LEGACY_ANONYMIZE_ERROR = (
    "Standalone legacy anonymization is disabled; use deep_anonymize=True for DICOM export."
)


def _reject_legacy_anonymize(anonymize: bool, *, deep_anonymize: bool = False) -> None:
    """Reject the obsolete standalone base-anonymizer export request path."""
    if anonymize and not deep_anonymize:
        raise ValueError(_LEGACY_ANONYMIZE_ERROR)


@dataclass
class ExportSelectedRequest:
    """Inputs for :meth:`ExportManager.export_selected`."""

    selected_items: dict[tuple[str, str, int], Dataset]
    output_dir: str
    format: str
    window_level_option: str = "dataset"
    current_window_center: float | None = None
    current_window_width: float | None = None
    include_overlays: bool = False
    use_rescaled_values: bool = False
    roi_manager: Any = None
    overlay_manager: Any = None
    measurement_tool: Any = None
    config_manager: Any = None
    text_annotation_tool: Any = None
    arrow_annotation_tool: Any = None
    studies: dict[str, dict[str, list[Dataset]]] | None = None
    export_scale: float = 1.0
    scale_annotations_with_image: bool = False
    # Compatibility-only: standalone use fails closed; use deep_anonymize for DICOM.
    anonymize: bool = False
    deep_anonymize: bool = False
    deep_anonymizer_options: Optional["DeepAnonymizerOptions"] = None
    projection_enabled: bool = False
    projection_type: str = "aip"
    projection_slice_count: int = 4
    subwindow_annotation_managers: list[dict[str, Any]] | None = None
    deep_anonymized_items: dict[tuple[str, str, int], Dataset] | None = None


@dataclass
class ExportSliceRequest:
    """Inputs for :meth:`ExportManager.export_slice`."""

    dataset: Dataset
    output_path: str
    format: str
    window_level_option: str = "dataset"
    current_window_center: float | None = None
    current_window_width: float | None = None
    include_overlays: bool = False
    use_rescaled_values: bool = False
    roi_manager: Any = None
    overlay_manager: Any = None
    measurement_tool: Any = None
    config_manager: Any = None
    text_annotation_tool: Any = None
    arrow_annotation_tool: Any = None
    study_uid: str | None = None
    series_uid: str | None = None
    slice_index: int | None = None
    total_slices: int | None = None
    export_scale: float = 1.0
    scale_annotations_with_image: bool = False
    # Compatibility-only: standalone use fails closed; callers receive a ValueError.
    anonymize: bool = False
    # Compatibility-only: deep export already supplies the transformed dataset.
    # Kept so callers can signal pre-anonymized input; export_slice does not branch on it.
    dataset_pre_anonymized: bool = False
    projection_enabled: bool = False
    projection_type: str = "aip"
    projection_slice_count: int = 4
    studies: dict[str, dict[str, list[Dataset]]] | None = None
    subwindow_annotation_managers: list[dict[str, Any]] | None = None


class ExportManager:
    """
    Manages export operations (orchestration). Rendering lives in export_rendering.
    """

    def __init__(self):
        """Initialize the export manager."""
        pass

    @staticmethod
    def build_deep_anonymized_selection(
        selected_items: dict[tuple[str, str, int], Dataset],
        deep_anonymizer_options: Optional["DeepAnonymizerOptions"] = None,
    ) -> dict[tuple[str, str, int], Dataset]:
        """Return a deep-anonymized dataset map preserving selection keys."""
        ordered_keys = list(selected_items.keys())
        ordered_datasets = [selected_items[k] for k in ordered_keys]
        deep_anonymizer = DeepDICOMAnonymizer(deep_anonymizer_options)
        anon_datasets = deep_anonymizer.anonymize_batch(ordered_datasets)
        return {ordered_keys[i]: anon_datasets[i] for i in range(len(ordered_keys))}

    @staticmethod
    def _effective_scale_for_image(width: int, height: int, requested_scale: float) -> float:
        return _er.effective_scale_for_image(width, height, requested_scale)

    @staticmethod
    def export_line_thickness_pixels(
        setting: int,
        width: int,
        height: int,
        scale_factor: float = 1.0,
    ) -> int:
        return _er.export_line_thickness_pixels(setting, width, height, scale_factor)

    @staticmethod
    def export_text_size_pixels(
        setting: int,
        width: int,
        height: int,
        scale_factor: float = 1.0,
    ) -> int:
        return _er.export_text_size_pixels(setting, width, height, scale_factor)

    @staticmethod
    def process_image_by_photometric_interpretation(image, dataset):
        return _er.process_image_by_photometric_interpretation(image, dataset)

    @staticmethod
    def get_export_paths_for_selection(
        selected_items: dict[tuple[str, str, int], Dataset],
        output_dir: str,
        format: str,
        projection_enabled: bool = False,
        projection_type: str = "aip",
        projection_slice_count: int = 4,
        anonymize: bool = False,
        deep_anonymize: bool = False,
        deep_anonymizer_options: Optional["DeepAnonymizerOptions"] = None,
        deep_anonymized_items: dict[tuple[str, str, int], Dataset] | None = None,
    ) -> list[str]:
        """
        Return the list of file paths that would be written by export_selected.
        Used to check for overwrites before exporting.
        
        Args:
            selected_items: Same as export_selected
            output_dir: Output directory
            format: "PNG", "JPG", or "DICOM"
            projection_enabled: Whether projection suffix is added to filenames
            projection_type: "aip", "mip", or "minip"
            projection_slice_count: Number of slices (for suffix)
            anonymize: Deprecated compatibility flag. Standalone use raises;
                select deep_anonymize for DICOM metadata de-identification.
            deep_anonymize: Whether DICOM export uses deep metadata de-identification
            deep_anonymizer_options: Options used by deep anonymization
            deep_anonymized_items: Precomputed deep-anonymized selection, reused
                so randomized date shifting matches the subsequent export
            
        Returns:
            List of absolute paths that would be written
        """
        _reject_legacy_anonymize(anonymize, deep_anonymize=deep_anonymize)

        paths: list[str] = []
        invalid_chars = '<>:"/\\|?*'

        def sanitize(name: str) -> str:
            s = str(name)
            for c in invalid_chars:
                s = s.replace(c, '_')
            s = s.replace(' ', '_').strip('. ')
            return s or 'UNKNOWN'

        items_by_study_series: dict[tuple[str, str], list[tuple[int, Dataset]]] = {}
        for (study_uid, series_uid, slice_index), dataset in selected_items.items():
            key = (study_uid, series_uid)
            if key not in items_by_study_series:
                items_by_study_series[key] = []
            items_by_study_series[key].append((slice_index, dataset))

        for key in items_by_study_series:
            items_by_study_series[key].sort(key=lambda x: x[0])

        pre_anonymized: dict[tuple[str, str, int], Dataset] = {}
        if deep_anonymize and format == "DICOM":
            pre_anonymized = deep_anonymized_items or ExportManager.build_deep_anonymized_selection(
                selected_items,
                deep_anonymizer_options,
            )
        for (study_uid, series_uid), items in items_by_study_series.items():
            if not items:
                continue
            first_dataset = items[0][1]
            first_key = (study_uid, series_uid, items[0][0])
            if deep_anonymize and format == "DICOM":
                folder_dataset = pre_anonymized.get(first_key, first_dataset)
            else:
                folder_dataset = first_dataset

            patient_id = sanitize(getattr(folder_dataset, 'PatientID', 'UNKNOWN_PATIENT'))
            study_date = sanitize(getattr(folder_dataset, 'StudyDate', 'UNKNOWN_DATE'))
            study_description = sanitize(getattr(folder_dataset, 'StudyDescription', 'UNKNOWN_STUDY'))
            series_number = getattr(folder_dataset, 'SeriesNumber', None)
            series_description = sanitize(getattr(folder_dataset, 'SeriesDescription', 'UNKNOWN_SERIES'))
            if series_number is None or series_number == '':
                series_number = 'UNKNOWN_SERIES_NUM'
            else:
                series_number = str(int(series_number)) if isinstance(series_number, (int, float)) else str(series_number)
            series_number_sanitized = sanitize(series_number)

            patient_dir = os.path.join(output_dir, patient_id)
            study_dir = os.path.join(patient_dir, f"{study_date}-{study_description}")
            series_dir = os.path.join(study_dir, f"{series_number_sanitized}-{series_description}")

            projection_suffix = ""
            if projection_enabled:
                projection_suffix = f"_{projection_type.upper()}_{projection_slice_count}slices"

            for slice_index, dataset in items:
                slice_key = (study_uid, series_uid, slice_index)
                output_dataset = pre_anonymized.get(slice_key, dataset)
                instance_num = getattr(output_dataset, 'InstanceNumber', slice_index + 1)
                if format == "DICOM":
                    filename = f"Instance_{instance_num:04d}{projection_suffix}.dcm"
                elif format == "PNG":
                    filename = f"Instance_{instance_num:04d}{projection_suffix}.png"
                else:
                    filename = f"Instance_{instance_num:04d}{projection_suffix}.jpg"
                paths.append(os.path.join(series_dir, filename))

        return paths

    def export_selected(
        self, request: ExportSelectedRequest
    ) -> tuple[int, list[tuple[str, float, float]]]:
        """
        Export selected items based on hierarchical selection.

        Args:
            request: ``ExportSelectedRequest`` holding export options and the
                hierarchical selection fields (items, output dir, format, W/L,
                overlays, anonymization, projection, and related managers).

        Returns:
            (exported_count, downgraded_list). downgraded_list is a list of
            (filename, requested_scale, actual_scale) for images exported at
            a lower magnification than requested (PNG/JPG only).
        """
        selected_items = request.selected_items
        output_dir = request.output_dir
        export_format = request.format
        window_level_option = request.window_level_option
        current_window_center = request.current_window_center
        current_window_width = request.current_window_width
        include_overlays = request.include_overlays
        use_rescaled_values = request.use_rescaled_values
        roi_manager = request.roi_manager
        overlay_manager = request.overlay_manager
        measurement_tool = request.measurement_tool
        config_manager = request.config_manager
        text_annotation_tool = request.text_annotation_tool
        arrow_annotation_tool = request.arrow_annotation_tool
        studies = request.studies
        export_scale = request.export_scale
        scale_annotations_with_image = request.scale_annotations_with_image
        anonymize = request.anonymize
        deep_anonymize = request.deep_anonymize
        deep_anonymizer_options = request.deep_anonymizer_options
        projection_enabled = request.projection_enabled
        projection_type = request.projection_type
        projection_slice_count = request.projection_slice_count
        subwindow_annotation_managers = request.subwindow_annotation_managers
        deep_anonymized_items = request.deep_anonymized_items

        _reject_legacy_anonymize(anonymize, deep_anonymize=deep_anonymize)

        exported = 0
        downgraded: list[tuple[str, float, float]] = []  # (filename, requested_scale, actual_scale)

        # Create progress dialog
        progress = QProgressDialog("Exporting images...", "Cancel", 0, len(selected_items))
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(0)

        # Group by study and series for directory structure
        items_by_study_series: dict[tuple[str, str], list[tuple[int, Dataset]]] = {}
        for (study_uid, series_uid, slice_index), dataset in selected_items.items():
            key = (study_uid, series_uid)
            if key not in items_by_study_series:
                items_by_study_series[key] = []
            items_by_study_series[key].append((slice_index, dataset))

        # Sort by slice index within each series
        for key in items_by_study_series:
            items_by_study_series[key].sort(key=lambda x: x[0])

        # Deep anonymize batch (DICOM): consistent UID remap and date shift across selection
        pre_anonymized: dict[tuple[str, str, int], Dataset] = {}
        if deep_anonymize and export_format == "DICOM":
            pre_anonymized = deep_anonymized_items or self.build_deep_anonymized_selection(
                selected_items,
                deep_anonymizer_options,
            )

        try:
            for (study_uid, series_uid), items in items_by_study_series.items():
                # Get first dataset to extract folder structure info
                first_dataset = items[0][1] if items else None
                if first_dataset is None:
                    continue

                # Use anonymized tags for folder structure when anonymize or deep anonymize
                if deep_anonymize and export_format == "DICOM":
                    first_key = (study_uid, series_uid, items[0][0])
                    folder_dataset = pre_anonymized.get(first_key, items[0][1])
                else:
                    folder_dataset = first_dataset

                # Extract DICOM tags for folder structure: Patient ID / Study Date - Study Description / Series Number - Series Description
                patient_id = getattr(folder_dataset, 'PatientID', 'UNKNOWN_PATIENT')
                study_date = getattr(folder_dataset, 'StudyDate', 'UNKNOWN_DATE')
                study_description = getattr(folder_dataset, 'StudyDescription', 'UNKNOWN_STUDY')
                series_number = getattr(folder_dataset, 'SeriesNumber', None)
                series_description = getattr(folder_dataset, 'SeriesDescription', 'UNKNOWN_SERIES')

                # Handle missing or empty SeriesNumber
                if series_number is None or series_number == '':
                    series_number = 'UNKNOWN_SERIES_NUM'
                else:
                    series_number = str(int(series_number)) if isinstance(series_number, (int, float)) else str(series_number)

                # Sanitize folder names (remove invalid characters)
                def sanitize_folder_name(name: str) -> str:
                    # Replace invalid characters with underscore
                    invalid_chars = '<>:"/\\|?*'
                    for char in invalid_chars:
                        name = name.replace(char, '_')
                    # Replace spaces with underscore
                    name = name.replace(' ', '_')
                    # Remove leading/trailing dots and spaces
                    name = name.strip('. ')
                    return name if name else 'UNKNOWN'

                # Sanitize all components
                patient_id_sanitized = sanitize_folder_name(str(patient_id))
                study_date_sanitized = sanitize_folder_name(str(study_date))
                study_description_sanitized = sanitize_folder_name(str(study_description))
                series_number_sanitized = sanitize_folder_name(str(series_number))
                series_description_sanitized = sanitize_folder_name(str(series_description))

                # Construct the new folder hierarchy: Patient ID / Study Date - Study Description / Series Number - Series Description
                patient_dir = os.path.join(output_dir, patient_id_sanitized)

                # Combine Study Date and Study Description
                study_folder_name = f"{study_date_sanitized}-{study_description_sanitized}"
                study_dir = os.path.join(patient_dir, study_folder_name)

                # Combine Series Number and Series Description
                series_folder_name = f"{series_number_sanitized}-{series_description_sanitized}"
                series_dir = os.path.join(study_dir, series_folder_name)

                os.makedirs(series_dir, exist_ok=True)

                for slice_index, dataset in items:
                    if progress.wasCanceled():
                        break

                    export_dataset = dataset
                    if deep_anonymize and export_format == "DICOM":
                        slice_key = (study_uid, series_uid, slice_index)
                        export_dataset = pre_anonymized.get(slice_key, dataset)

                    # Generate filename
                    instance_num = getattr(export_dataset, 'InstanceNumber', slice_index + 1)

                    # Add projection info to filename if enabled
                    projection_suffix = ""
                    if projection_enabled:
                        projection_type_upper = projection_type.upper()
                        projection_suffix = f"_{projection_type_upper}_{projection_slice_count}slices"

                    if export_format == "DICOM":
                        filename = f"Instance_{instance_num:04d}{projection_suffix}.dcm"
                    elif export_format == "PNG":
                        filename = f"Instance_{instance_num:04d}{projection_suffix}.png"
                    else:  # JPG
                        filename = f"Instance_{instance_num:04d}{projection_suffix}.jpg"

                    output_path = os.path.join(series_dir, filename)

                    # Calculate total slices for this series
                    total_slices = None
                    if studies and study_uid in studies and series_uid in studies[study_uid]:
                        total_slices = len(studies[study_uid][series_uid])

                    success, downgrade_info = self.export_slice(
                        ExportSliceRequest(
                            export_dataset,
                            output_path,
                            export_format,
                            window_level_option,
                            current_window_center,
                            current_window_width,
                            include_overlays,
                            use_rescaled_values,
                            roi_manager,
                            overlay_manager,
                            measurement_tool,
                            config_manager,
                            text_annotation_tool,
                            arrow_annotation_tool,
                            study_uid,
                            series_uid,
                            slice_index,
                            total_slices,
                            export_scale,
                            scale_annotations_with_image,
                            anonymize=False,
                            dataset_pre_anonymized=deep_anonymize and export_format == "DICOM",
                            projection_enabled=projection_enabled,
                            projection_type=projection_type,
                            projection_slice_count=projection_slice_count,
                            studies=studies,
                            subwindow_annotation_managers=subwindow_annotation_managers,
                        )
                    )
                    if success:
                        exported += 1
                        if downgrade_info is not None and export_format in ("PNG", "JPG"):
                            req, act = downgrade_info
                            downgraded.append((os.path.basename(output_path), req, act))

                    progress.setValue(exported)

            progress.close()
        except Exception as e:
            progress.close()
            raise e

        return (exported, downgraded)

    def export_slice(
        self, request: ExportSliceRequest
    ) -> tuple[bool, tuple[float, float] | None]:
        """
        Export a single slice or projection image.

        Args:
            request: ``ExportSliceRequest`` holding the dataset, output path,
                format, W/L, overlay/annotation managers, anonymization, and
                optional projection fields.

        Returns:
            (success, downgrade_info). downgrade_info is (requested_scale, actual_scale) when
            image was exported at lower magnification than requested (PNG/JPG only), else None.
        """
        dataset = request.dataset
        output_path = request.output_path
        export_format = request.format
        window_level_option = request.window_level_option
        current_window_center = request.current_window_center
        current_window_width = request.current_window_width
        include_overlays = request.include_overlays
        use_rescaled_values = request.use_rescaled_values
        roi_manager = request.roi_manager
        overlay_manager = request.overlay_manager
        measurement_tool = request.measurement_tool
        config_manager = request.config_manager
        text_annotation_tool = request.text_annotation_tool
        arrow_annotation_tool = request.arrow_annotation_tool
        study_uid = request.study_uid
        series_uid = request.series_uid
        slice_index = request.slice_index
        total_slices = request.total_slices
        export_scale = request.export_scale
        scale_annotations_with_image = request.scale_annotations_with_image
        anonymize = request.anonymize
        # dataset_pre_anonymized remains on ExportSliceRequest for API compatibility.
        # Deep de-id already swaps the dataset before this method; both former branches
        # only called save_as after the legacy anonymize=True path was removed.
        projection_enabled = request.projection_enabled
        projection_type = request.projection_type
        projection_slice_count = request.projection_slice_count
        studies = request.studies
        subwindow_annotation_managers = request.subwindow_annotation_managers

        _reject_legacy_anonymize(anonymize)

        try:
            if export_format == "DICOM":
                # Export as DICOM (deep-anonymized or original dataset already selected by caller)
                if projection_enabled and studies and study_uid and series_uid and slice_index is not None:
                    # Create projection dataset for DICOM export
                    projection_dataset = _er.create_projection_dataset(
                        dataset, studies, study_uid, series_uid, slice_index,
                        projection_type, projection_slice_count, use_rescaled_values
                    )
                    if projection_dataset is None:
                        # Fall back to single slice if projection fails
                        projection_dataset = dataset
                    projection_dataset.save_as(output_path)
                else:
                    dataset.save_as(output_path)
                return (True, None)
            else:
                # Export as image (PNG or JPG)
                window_center = None
                window_width = None

                if window_level_option == "current" and current_window_center is not None and current_window_width is not None:
                    window_center = current_window_center
                    window_width = current_window_width

                # Check if we should create a projection image
                is_projection_image = False  # Track if we actually have a projection (not just enabled)
                if projection_enabled and studies and study_uid and series_uid and slice_index is not None:
                    # Create projection image
                    image = _er.create_projection_for_export(
                        dataset, studies, study_uid, series_uid, slice_index,
                        projection_type, projection_slice_count,
                        window_center, window_width, use_rescaled_values
                    )
                    if image is None:
                        # Fall back to single slice if projection fails
                        image = DICOMProcessor.dataset_to_image(
                            dataset,
                            window_center=window_center,
                            window_width=window_width,
                            apply_rescale=use_rescaled_values
                        )
                        # is_projection_image remains False - this is a fallback single slice
                    else:
                        # Projection was successful
                        is_projection_image = True
                else:
                    # Convert single slice to image - use apply_rescale to match viewer behavior
                    image = DICOMProcessor.dataset_to_image(
                        dataset,
                        window_center=window_center,
                        window_width=window_width,
                        apply_rescale=use_rescaled_values
                    )

                if image is None:
                    return (False, None)

                # Handle PhotometricInterpretation (MONOCHROME1 inversion, YBR conversion, etc.)
                # Only apply for non-projection images (projections are already processed)
                # Note: Fallback single-slice images need photometric processing even if projection was enabled
                if not is_projection_image:
                    image = _er.process_image_by_photometric_interpretation(image, dataset)

                # Apply export scale: use effective scale (may be lower than requested to stay under 8192 px)
                effective_scale = _er.effective_scale_for_image(
                    image.width, image.height, export_scale
                )
                downgrade_info: tuple[float, float] | None = (export_scale, effective_scale) if effective_scale < export_scale else None
                if effective_scale > 1.0:
                    new_width = int(image.width * effective_scale)
                    new_height = int(image.height * effective_scale)
                    image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)

                # Render overlays and ROIs if requested (on final-size image)
                if include_overlays:
                    image = _er.render_overlays_and_rois(
                        _er.RenderOverlaysRequest(
                            image,
                            dataset,
                            roi_manager,
                            overlay_manager,
                            measurement_tool,
                            config_manager,
                            text_annotation_tool,
                            arrow_annotation_tool,
                            study_uid,
                            series_uid,
                            slice_index,
                            total_slices,
                            coordinate_scale=effective_scale,
                            export_scale=effective_scale,
                            scale_annotations_with_image=scale_annotations_with_image,
                            projection_enabled=projection_enabled,
                            projection_type=projection_type,
                            projection_slice_count=projection_slice_count,
                            studies=studies,
                            subwindow_annotation_managers=subwindow_annotation_managers
                        )
                    )

                if export_format == "PNG":
                    image.save(output_path, "PNG")
                elif export_format == "JPG":
                    image.save(output_path, "JPEG", quality=95)

                return (True, downgrade_info)
        except Exception as e:
            print_redacted(f"Error exporting slice: {e}")
            return (False, None)
