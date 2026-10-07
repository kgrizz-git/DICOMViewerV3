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

import pydicom.uid
from PIL import Image
from pydicom.dataset import Dataset
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QProgressDialog

from core.dicom_processor import DICOMProcessor
from core.lut_display import grayscale_export_kwargs, invert_color_export_image
from core.projection_dicom_export import (
    create_projection_dataset,
    save_projection_dataset,
)
from gui import export_rendering as _er
from gui.export_paths import (
    export_filename,
    instance_number_for,
    series_directory,
    series_folder_dataset,
)
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



def _projection_dicom_type(request: "ExportSelectedRequest") -> str | None:
    """Projection type when the request writes projection DICOM, else None."""
    if request.projection_enabled and request.format == "DICOM" and request.studies:
        return request.projection_type
    return None


def not_exported_note(selected_count: int, exported_count: int) -> str:
    """Return a dialog note for selected images that produced no file, or ""."""
    missing = selected_count - exported_count
    if missing <= 0:
        return ""
    return (
        f"\n\n{missing} of {selected_count} selected image(s) were not exported. "
        "The export was cancelled, or those images could not be written."
    )

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
    image_inverted: bool = False
    lut: Any = None
    voi_from_dicom: bool = False


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
    image_inverted: bool = False
    lut: Any = None
    voi_from_dicom: bool = False
    # Projection DICOM: SeriesInstanceUID shared by the export run, and the
    # 1-based InstanceNumber within that new series.
    projection_series_uid: str | None = None
    projection_instance_number: int | None = None
    # Projection already built (and anonymized) by export_selected; saved as is.
    prebuilt_projection: Dataset | None = None


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
    def group_selection(
        selected_items: dict[tuple[str, str, int], Dataset],
    ) -> dict[tuple[str, str], list[tuple[int, Dataset]]]:
        """Group selected items by (study, series), sorted by slice index."""
        grouped: dict[tuple[str, str], list[tuple[int, Dataset]]] = {}
        for (study_uid, series_uid, slice_index), dataset in selected_items.items():
            grouped.setdefault((study_uid, series_uid), []).append((slice_index, dataset))
        for items in grouped.values():
            items.sort(key=lambda x: x[0])
        return grouped

    @staticmethod
    def projection_anonymization_active(
        deep_anonymize: bool, export_format: str, projection_enabled: bool, studies: Any
    ) -> bool:
        """True when DICOM projections are built and then deep-anonymized."""
        return bool(
            deep_anonymize and export_format == "DICOM" and projection_enabled and studies
        )

    @staticmethod
    def build_anonymized_projections(
        items_by_study_series: dict[tuple[str, str], list[tuple[int, Dataset]]],
        studies: dict[str, dict[str, list[Dataset]]],
        projection_type: str,
        projection_slice_count: int,
        use_rescaled_values: bool,
        deep_anonymizer_options: Optional["DeepAnonymizerOptions"] = None,
    ) -> dict[tuple[str, str, int], Dataset]:
        """Build raw projection datasets for every item, then anonymize them as one batch.

        Items whose projection cannot be built are left out of the result; the
        raw source is never substituted.
        """
        keys: list[tuple[str, str, int]] = []
        built: list[Dataset] = []
        for (study_uid, series_uid), items in items_by_study_series.items():
            new_series_uid = pydicom.uid.generate_uid()
            for position, (slice_index, dataset) in enumerate(items, start=1):
                projection = create_projection_dataset(
                    dataset, studies, study_uid, series_uid, slice_index,
                    projection_type, projection_slice_count, use_rescaled_values,
                    new_series_uid=new_series_uid,
                    instance_number=position,
                )
                if projection is not None:
                    keys.append((study_uid, series_uid, slice_index))
                    built.append(projection)
        anonymized = DeepDICOMAnonymizer(deep_anonymizer_options).anonymize_batch(built)
        return dict(zip(keys, anonymized, strict=True))

    @staticmethod
    def build_anonymized_projections_for_selection(
        selected_items: dict[tuple[str, str, int], Dataset],
        studies: dict[str, dict[str, list[Dataset]]],
        projection_type: str,
        projection_slice_count: int,
        use_rescaled_values: bool,
        deep_anonymizer_options: Optional["DeepAnonymizerOptions"] = None,
    ) -> dict[tuple[str, str, int], Dataset]:
        """Group ``selected_items`` and build the anonymized projection batch.

        Dialogs call this once and hand the same map to the overwrite preview and
        to ``export_selected`` so both use one batch (one date shift, one UID map).
        """
        return ExportManager.build_anonymized_projections(
            ExportManager.group_selection(selected_items),
            studies,
            projection_type,
            projection_slice_count,
            use_rescaled_values,
            deep_anonymizer_options,
        )

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
        studies: dict[str, dict[str, list[Dataset]]] | None = None,
        use_rescaled_values: bool = False,
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
                so randomized date shifting matches the subsequent export. For
                DICOM projection + deep-anonymize it is the built projection
                batch (``build_anonymized_projections_for_selection``).
            studies: Needed with ``projection_enabled`` to predict built projections
            use_rescaled_values: Forwarded to the projection builder
            
        Returns:
            List of absolute paths that would be written
        """
        _reject_legacy_anonymize(anonymize, deep_anonymize=deep_anonymize)

        paths: list[str] = []
        items_by_study_series = ExportManager.group_selection(selected_items)
        deep_dicom = bool(deep_anonymize and format == "DICOM")
        projection_dicom = bool(projection_enabled and format == "DICOM" and studies)
        projection_anon = ExportManager.projection_anonymization_active(
            deep_anonymize, format, projection_enabled, studies
        )
        pre_anonymized: dict[tuple[str, str, int], Dataset] = {}
        if projection_anon:
            pre_anonymized = deep_anonymized_items or (
                ExportManager.build_anonymized_projections_for_selection(
                    selected_items, studies or {}, projection_type,
                    projection_slice_count, use_rescaled_values, deep_anonymizer_options,
                )
            )
        elif deep_dicom:
            pre_anonymized = deep_anonymized_items or ExportManager.build_deep_anonymized_selection(
                selected_items,
                deep_anonymizer_options,
            )
        for (study_uid, series_uid), items in items_by_study_series.items():
            folder_dataset = series_folder_dataset(
                study_uid, series_uid, items, pre_anonymized, deep_dicom, projection_anon,
                projection_type if projection_dicom else None,
            )
            if folder_dataset is None:
                continue
            series_dir = series_directory(output_dir, folder_dataset)
            for position, (slice_index, dataset) in enumerate(items, start=1):
                slice_key = (study_uid, series_uid, slice_index)
                if projection_anon and slice_key not in pre_anonymized:
                    continue  # projection could not be built; nothing is written
                output_dataset = pre_anonymized.get(slice_key, dataset)
                instance_num = instance_number_for(
                    position, output_dataset, slice_index, projection_dicom
                )
                filename = export_filename(
                    instance_num, format, projection_enabled,
                    projection_type, projection_slice_count,
                )
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
        projection_enabled = request.projection_enabled
        projection_type = request.projection_type
        projection_slice_count = request.projection_slice_count
        subwindow_annotation_managers = request.subwindow_annotation_managers
        image_inverted = request.image_inverted
        lut = request.lut
        voi_from_dicom = request.voi_from_dicom

        _reject_legacy_anonymize(anonymize, deep_anonymize=deep_anonymize)

        exported = 0
        downgraded: list[tuple[str, float, float]] = []  # (filename, requested_scale, actual_scale)

        # Create progress dialog
        progress = QProgressDialog("Exporting images...", "Cancel", 0, len(selected_items))
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(0)

        # Group by study and series for directory structure (sorted by slice index)
        items_by_study_series = self.group_selection(selected_items)
        deep_dicom = bool(deep_anonymize and export_format == "DICOM")
        folder_projection_type = _projection_dicom_type(request)

        pre_anonymized, projection_dicom_anon = self._select_pre_anonymized(
            request, items_by_study_series
        )
        failed = 0

        try:
            for (study_uid, series_uid), items in items_by_study_series.items():
                # Anonymized tags name the folder when deep anonymizing; built
                # projections name the derived series.
                folder_dataset = series_folder_dataset(
                    study_uid, series_uid, items, pre_anonymized, deep_dicom,
                    projection_dicom_anon,
                    folder_projection_type,
                )
                if folder_dataset is None:
                    failed += len(items)
                    continue
                series_dir = series_directory(output_dir, folder_dataset)
                os.makedirs(series_dir, exist_ok=True)

                # One derived series per (source series, projection type, slab) run.
                projection_series_uid = pydicom.uid.generate_uid()

                for position, (slice_index, dataset) in enumerate(items, start=1):
                    if progress.wasCanceled():
                        break

                    slice_key = (study_uid, series_uid, slice_index)
                    if projection_dicom_anon and slice_key not in pre_anonymized:
                        # Fail closed: never build from the raw source here.
                        failed += 1
                        continue
                    export_dataset = dataset
                    if deep_dicom:
                        export_dataset = pre_anonymized.get(slice_key, dataset)

                    instance_num = instance_number_for(
                        position, export_dataset, slice_index,
                        folder_projection_type is not None,
                    )
                    filename = export_filename(
                        instance_num, export_format, projection_enabled,
                        projection_type, projection_slice_count,
                    )
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
                            image_inverted=image_inverted,
                            lut=lut,
                            voi_from_dicom=voi_from_dicom,
                            projection_series_uid=projection_series_uid,
                            projection_instance_number=position,
                            prebuilt_projection=(
                                pre_anonymized.get(slice_key) if projection_dicom_anon else None
                            ),
                        )
                    )
                    if not success:
                        failed += 1
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

        if failed:
            print_redacted(f"Export: {failed} item(s) could not be exported.")
        return (exported, downgraded)

    def _select_pre_anonymized(
        self,
        request: ExportSelectedRequest,
        items_by_study_series: dict[tuple[str, str], list[tuple[int, Dataset]]],
    ) -> tuple[dict[tuple[str, str, int], Dataset], bool]:
        """Return (pre-anonymized map, whether it holds built projection datasets)."""
        if not (request.deep_anonymize and request.format == "DICOM"):
            return {}, False
        options = request.deep_anonymizer_options
        if self.projection_anonymization_active(
            True, request.format, request.projection_enabled, request.studies
        ):
            # Reuse the dialog's batch (so the overwrite preview matches); else build from the raw source, then anonymize the built batch so the
            # reference sequences get the same UID remap as the datasets.
            return request.deep_anonymized_items or self.build_anonymized_projections(
                items_by_study_series,
                request.studies or {},
                request.projection_type,
                request.projection_slice_count,
                request.use_rescaled_values,
                options,
            ), True
        return request.deep_anonymized_items or self.build_deep_anonymized_selection(
            request.selected_items, options
        ), False

    @staticmethod
    def _export_dicom_slice(request: ExportSliceRequest) -> bool:
        """Write one DICOM (deep-anonymized or original dataset already selected by caller).

        Returns False, writing nothing, when a projection cannot be built or when a
        deep-anonymized projection arrives without its prebuilt dataset.
        """
        dataset = request.dataset
        output_path = request.output_path
        if request.prebuilt_projection is not None:
            save_projection_dataset(request.prebuilt_projection, output_path)
            return True
        studies = request.studies
        if not (
            request.projection_enabled and studies and request.study_uid
            and request.series_uid and request.slice_index is not None
        ):
            dataset.save_as(output_path)
            return True
        if request.dataset_pre_anonymized:
            return False  # fail closed: never build from raw source and write it
        projection_dataset = create_projection_dataset(
            dataset, studies, request.study_uid, request.series_uid, request.slice_index,
            request.projection_type, request.projection_slice_count,
            request.use_rescaled_values,
            new_series_uid=request.projection_series_uid,
            instance_number=request.projection_instance_number,
        )
        if projection_dataset is None:
            return False
        save_projection_dataset(projection_dataset, output_path)
        return True

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
        image_inverted = request.image_inverted
        lut = request.lut
        voi_from_dicom = request.voi_from_dicom

        _reject_legacy_anonymize(anonymize)

        try:
            if export_format == "DICOM":
                return (self._export_dicom_slice(request), None)
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
                        window_center, window_width, use_rescaled_values,
                        image_inverted=image_inverted, lut=lut,
                    )
                    if image is None:
                        # Fall back to single slice if projection fails
                        image = DICOMProcessor.dataset_to_image(
                            dataset,
                            window_center=window_center,
                            window_width=window_width,
                            apply_rescale=use_rescaled_values,
                            **grayscale_export_kwargs(dataset, image_inverted, lut, voi_from_dicom),
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
                        apply_rescale=use_rescaled_values,
                        **grayscale_export_kwargs(dataset, image_inverted, lut, voi_from_dicom),
                    )

                if image is None:
                    return (False, None)

                # Handle PhotometricInterpretation (MONOCHROME1 inversion, YBR conversion, etc.)
                # Only apply for non-projection images (projections are already processed)
                # Note: Fallback single-slice images need photometric processing even if projection was enabled
                if not is_projection_image:
                    image = _er.process_image_by_photometric_interpretation(image, dataset)
                image = invert_color_export_image(image, dataset, image_inverted)

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
