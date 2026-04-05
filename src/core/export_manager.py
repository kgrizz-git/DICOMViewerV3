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
from pathlib import Path
from typing import Optional, List, Dict, Tuple, Any

from PIL import Image
from pydicom.dataset import Dataset
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QProgressDialog

from core.dicom_processor import DICOMProcessor

from core import export_rendering as _er

class ExportManager:
    """
    Manages export operations (orchestration). Rendering lives in export_rendering.
    """

    def __init__(self):
        """Initialize the export manager."""
        pass

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
        selected_items: Dict[Tuple[str, str, int], Dataset],
        output_dir: str,
        format: str,
        projection_enabled: bool = False,
        projection_type: str = "aip",
        projection_slice_count: int = 4
    ) -> List[str]:
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
            
        Returns:
            List of absolute paths that would be written
        """
        paths: List[str] = []
        invalid_chars = '<>:"/\\|?*'
        
        def sanitize(name: str) -> str:
            s = str(name)
            for c in invalid_chars:
                s = s.replace(c, '_')
            s = s.replace(' ', '_').strip('. ')
            return s or 'UNKNOWN'
        
        items_by_study_series: Dict[Tuple[str, str], List[Tuple[int, Dataset]]] = {}
        for (study_uid, series_uid, slice_index), dataset in selected_items.items():
            key = (study_uid, series_uid)
            if key not in items_by_study_series:
                items_by_study_series[key] = []
            items_by_study_series[key].append((slice_index, dataset))
        
        for key in items_by_study_series:
            items_by_study_series[key].sort(key=lambda x: x[0])
        
        for (study_uid, series_uid), items in items_by_study_series.items():
            if not items:
                continue
            first_dataset = items[0][1]
            patient_id = sanitize(getattr(first_dataset, 'PatientID', 'UNKNOWN_PATIENT'))
            study_date = sanitize(getattr(first_dataset, 'StudyDate', 'UNKNOWN_DATE'))
            study_description = sanitize(getattr(first_dataset, 'StudyDescription', 'UNKNOWN_STUDY'))
            series_number = getattr(first_dataset, 'SeriesNumber', None)
            series_description = sanitize(getattr(first_dataset, 'SeriesDescription', 'UNKNOWN_SERIES'))
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
                instance_num = getattr(dataset, 'InstanceNumber', slice_index + 1)
                if format == "DICOM":
                    filename = f"Instance_{instance_num:04d}{projection_suffix}.dcm"
                elif format == "PNG":
                    filename = f"Instance_{instance_num:04d}{projection_suffix}.png"
                else:
                    filename = f"Instance_{instance_num:04d}{projection_suffix}.jpg"
                paths.append(os.path.join(series_dir, filename))
        
        return paths
    
    def export_selected(
        self,
        selected_items: Dict[Tuple[str, str, int], Dataset],
        output_dir: str,
        format: str,
        window_level_option: str = "dataset",
        current_window_center: Optional[float] = None,
        current_window_width: Optional[float] = None,
        include_overlays: bool = False,
        use_rescaled_values: bool = False,
        roi_manager=None,
        overlay_manager=None,
        measurement_tool=None,
        config_manager=None,
        text_annotation_tool=None,
        arrow_annotation_tool=None,
        studies: Optional[Dict[str, Dict[str, List[Dataset]]]] = None,
        export_scale: float = 1.0,
        scale_annotations_with_image: bool = False,
        anonymize: bool = False,
        projection_enabled: bool = False,
        projection_type: str = "aip",
        projection_slice_count: int = 4,
        subwindow_annotation_managers: Optional[List[Dict[str, Any]]] = None
    ) -> Tuple[int, List[Tuple[str, float, float]]]:
        """
        Export selected items based on hierarchical selection.
        
        Returns:
            (exported_count, downgraded_list). downgraded_list is a list of
            (filename, requested_scale, actual_scale) for images exported at
            a lower magnification than requested (PNG/JPG only).
        
        Args:
            selected_items: Dictionary of {(study_uid, series_uid, slice_index): dataset}
            output_dir: Output directory
            format: Export format ("PNG", "JPG", or "DICOM")
            window_level_option: "current" or "dataset"
            current_window_center: Current window center from viewer
            current_window_width: Current window width from viewer
            include_overlays: Whether to include overlays/ROIs (PNG/JPG only)
            use_rescaled_values: Whether to apply rescale slope/intercept (matches viewer setting)
            roi_manager: Optional ROI manager for rendering ROIs
            overlay_manager: Optional overlay manager for rendering overlays
            measurement_tool: Optional measurement tool for rendering measurements
            config_manager: Optional config manager for overlay configuration
            studies: Optional studies dictionary for calculating total_slices {study_uid: {series_uid: [datasets]}}
            export_scale: Scale factor for image dimensions (1.0, 1.5, 2.0, or 4.0)
            scale_annotations_with_image: If True, multiply annotation line/font sizes by export_scale
            anonymize: Whether to anonymize DICOM exports
            projection_enabled: Whether intensity projection (combine slices) is enabled
            projection_type: Type of projection ("aip", "mip", or "minip")
            projection_slice_count: Number of slices to combine (2, 3, 4, 6, or 8)
            subwindow_annotation_managers: Optional list of per-subwindow dicts with keys
                roi_manager, measurement_tool, text_annotation_tool, arrow_annotation_tool.
                When provided, annotations are aggregated from all subwindows for each slice (Option B).
        """
        exported = 0
        downgraded: List[Tuple[str, float, float]] = []  # (filename, requested_scale, actual_scale)
        
        # Create progress dialog
        progress = QProgressDialog("Exporting images...", "Cancel", 0, len(selected_items))
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(0)
        
        # Group by study and series for directory structure
        items_by_study_series: Dict[Tuple[str, str], List[Tuple[int, Dataset]]] = {}
        for (study_uid, series_uid, slice_index), dataset in selected_items.items():
            key = (study_uid, series_uid)
            if key not in items_by_study_series:
                items_by_study_series[key] = []
            items_by_study_series[key].append((slice_index, dataset))
        
        # Sort by slice index within each series
        for key in items_by_study_series:
            items_by_study_series[key].sort(key=lambda x: x[0])
        
        try:
            for (study_uid, series_uid), items in items_by_study_series.items():
                # Get first dataset to extract folder structure info
                first_dataset = items[0][1] if items else None
                if first_dataset is None:
                    continue
                
                # Use anonymized tags for folder structure when anonymize is True (so folder path doesn't leak patient info)
                if anonymize:
                    from utils.dicom_anonymizer import DICOMAnonymizer
                    anonymizer = DICOMAnonymizer()
                    folder_dataset = anonymizer.anonymize_dataset(first_dataset)
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
                    
                    # Generate filename
                    instance_num = getattr(dataset, 'InstanceNumber', slice_index + 1)
                    
                    # Add projection info to filename if enabled
                    projection_suffix = ""
                    if projection_enabled:
                        projection_type_upper = projection_type.upper()
                        projection_suffix = f"_{projection_type_upper}_{projection_slice_count}slices"
                    
                    if format == "DICOM":
                        filename = f"Instance_{instance_num:04d}{projection_suffix}.dcm"
                    elif format == "PNG":
                        filename = f"Instance_{instance_num:04d}{projection_suffix}.png"
                    else:  # JPG
                        filename = f"Instance_{instance_num:04d}{projection_suffix}.jpg"
                    
                    output_path = os.path.join(series_dir, filename)
                    
                    # Calculate total slices for this series
                    total_slices = None
                    if studies and study_uid in studies and series_uid in studies[study_uid]:
                        total_slices = len(studies[study_uid][series_uid])
                    
                    success, downgrade_info = self.export_slice(
                        dataset,
                        output_path,
                        format,
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
                        anonymize=anonymize,
                        projection_enabled=projection_enabled,
                        projection_type=projection_type,
                        projection_slice_count=projection_slice_count,
                        studies=studies,
                        subwindow_annotation_managers=subwindow_annotation_managers
                    )
                    if success:
                        exported += 1
                        if downgrade_info is not None and format in ("PNG", "JPG"):
                            req, act = downgrade_info
                            downgraded.append((os.path.basename(output_path), req, act))
                    
                    progress.setValue(exported)
            
            progress.close()
        except Exception as e:
            progress.close()
            raise e
        
        return (exported, downgraded)
    
    def export_slice(
        self,
        dataset: Dataset,
        output_path: str,
        format: str,
        window_level_option: str = "dataset",
        current_window_center: Optional[float] = None,
        current_window_width: Optional[float] = None,
        include_overlays: bool = False,
        use_rescaled_values: bool = False,
        roi_manager=None,
        overlay_manager=None,
        measurement_tool=None,
        config_manager=None,
        text_annotation_tool=None,
        arrow_annotation_tool=None,
        study_uid: Optional[str] = None,
        series_uid: Optional[str] = None,
        slice_index: Optional[int] = None,
        total_slices: Optional[int] = None,
        export_scale: float = 1.0,
        scale_annotations_with_image: bool = False,
        anonymize: bool = False,
        projection_enabled: bool = False,
        projection_type: str = "aip",
        projection_slice_count: int = 4,
        studies: Optional[Dict[str, Dict[str, List[Dataset]]]] = None,
        subwindow_annotation_managers: Optional[List[Dict[str, Any]]] = None
    ) -> Tuple[bool, Optional[Tuple[float, float]]]:
        """
        Export a single slice or projection image.

        Args:
            dataset: DICOM dataset
            output_path: Output file path
            format: Export format ("PNG", "JPG", or "DICOM")
            window_level_option: "current" or "dataset"
            current_window_center: Current window center from viewer
            current_window_width: Current window width from viewer
            include_overlays: Whether to include overlays/ROIs (PNG/JPG only)
            use_rescaled_values: Whether to apply rescale slope/intercept (matches viewer setting)
            roi_manager: Optional ROI manager for rendering ROIs
            overlay_manager: Optional overlay manager for rendering overlays
            measurement_tool: Optional measurement tool for rendering measurements
            config_manager: Optional config manager for overlay configuration
            study_uid: Optional study UID for ROI lookup
            series_uid: Optional series UID for ROI lookup
            slice_index: Optional slice index for ROI lookup
            total_slices: Optional total number of slices in series (for "Slice X/Y" formatting)
            export_scale: Scale factor for image dimensions (1.0, 1.5, 2.0, or 4.0)
            scale_annotations_with_image: If True, multiply annotation sizes by export_scale
            anonymize: Whether to anonymize DICOM exports
            projection_enabled: Whether intensity projection (combine slices) is enabled
            projection_type: Type of projection ("aip", "mip", or "minip")
            projection_slice_count: Number of slices to combine (2, 3, 4, 6, or 8)
            studies: Optional studies dictionary for gathering slices for projection
            subwindow_annotation_managers: Optional list of per-subwindow annotation managers (Option B aggregate)

        Returns:
            (success, downgrade_info). downgrade_info is (requested_scale, actual_scale) when
            image was exported at lower magnification than requested (PNG/JPG only), else None.
        """
        try:
            if format == "DICOM":
                # Export as DICOM
                if projection_enabled and studies and study_uid and series_uid and slice_index is not None:
                    # Create projection dataset for DICOM export
                    projection_dataset = _er.create_projection_dataset(
                        dataset, studies, study_uid, series_uid, slice_index,
                        projection_type, projection_slice_count, use_rescaled_values
                    )
                    if projection_dataset is None:
                        # Fall back to single slice if projection fails
                        projection_dataset = dataset
                    
                    if anonymize:
                        # Apply anonymization
                        from utils.dicom_anonymizer import DICOMAnonymizer
                        anonymizer = DICOMAnonymizer()
                        anonymized_dataset = anonymizer.anonymize_dataset(projection_dataset)
                        anonymized_dataset.save_as(output_path)
                    else:
                        # Export projection dataset without anonymization
                        projection_dataset.save_as(output_path)
                else:
                    # Export as regular DICOM (no projection)
                    if anonymize:
                        # Apply anonymization
                        from utils.dicom_anonymizer import DICOMAnonymizer
                        anonymizer = DICOMAnonymizer()
                        anonymized_dataset = anonymizer.anonymize_dataset(dataset)
                        anonymized_dataset.save_as(output_path)
                    else:
                        # Export original data without anonymization
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
                downgrade_info: Optional[Tuple[float, float]] = (export_scale, effective_scale) if effective_scale < export_scale else None
                if effective_scale > 1.0:
                    new_width = int(image.width * effective_scale)
                    new_height = int(image.height * effective_scale)
                    image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
                
                # Render overlays and ROIs if requested (on final-size image)
                if include_overlays:
                    image = _er.render_overlays_and_rois(
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
                
                if format == "PNG":
                    image.save(output_path, "PNG")
                elif format == "JPG":
                    image.save(output_path, "JPEG", quality=95)
            
                return (True, downgrade_info)
        except Exception as e:
            print(f"Error exporting slice: {e}")
            return (False, None)
    
