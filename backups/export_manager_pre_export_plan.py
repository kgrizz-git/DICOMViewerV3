"""
Export Manager – core export execution for DICOM images.

This module provides the ExportManager class that performs export of selected
slices to JPEG, PNG, or DICOM with window/level, overlays, ROIs, measurements,
and projection support. Used by the Export dialog (gui.dialogs.export_dialog).

Purpose:
    - Execute export_selected and export_slice with progress and folder structure
    - Handle photometric interpretation, projection, anonymization, overlay rendering

Inputs:
    - selected_items or single dataset, output path, format, window/level, options

Outputs:
    - Exported files on disk

Requirements:
    - PySide6 (QProgressDialog, Qt)
    - PIL/Pillow, pydicom, numpy
    - core.dicom_processor, core.dicom_parser, utils.dicom_utils
"""

import copy
import os
from typing import Optional, List, Dict, Tuple

import numpy as np
import pydicom.uid
from PIL import Image, ImageDraw, ImageFont
from pydicom.dataset import Dataset
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QProgressDialog

from core.dicom_parser import DICOMParser
from core.dicom_processor import DICOMProcessor
from utils.dicom_utils import get_slice_thickness


class ExportManager:
    """
    Manages export operations.
    """
    
    def __init__(self):
        """Initialize the export manager."""
        pass
    
    @staticmethod
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
            print(f"[EXPORT] Error processing image by PhotometricInterpretation: {e}")
            import traceback
            traceback.print_exc()
            # Return original image on error
            return image
    
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
        studies: Optional[Dict[str, Dict[str, List[Dataset]]]] = None,
        export_at_display_resolution: bool = False,
        current_zoom: Optional[float] = None,
        initial_fit_zoom: float = 1.0,
        anonymize: bool = False,
        projection_enabled: bool = False,
        projection_type: str = "aip",
        projection_slice_count: int = 4
    ) -> int:
        """
        Export selected items based on hierarchical selection.
        
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
            export_at_display_resolution: Whether to export at displayed resolution (apply zoom)
            current_zoom: Optional current zoom level from viewer
            anonymize: Whether to anonymize DICOM exports
            projection_enabled: Whether intensity projection (combine slices) is enabled
            projection_type: Type of projection ("aip", "mip", or "minip")
            projection_slice_count: Number of slices to combine (2, 3, 4, 6, or 8)
            
        Returns:
            Number of files exported
        """
        exported = 0
        
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
                
                # Extract DICOM tags for folder structure: Patient ID / Study Date - Study Description / Series Number - Series Description
                patient_id = getattr(first_dataset, 'PatientID', 'UNKNOWN_PATIENT')
                study_date = getattr(first_dataset, 'StudyDate', 'UNKNOWN_DATE')
                study_description = getattr(first_dataset, 'StudyDescription', 'UNKNOWN_STUDY')
                series_number = getattr(first_dataset, 'SeriesNumber', None)
                series_description = getattr(first_dataset, 'SeriesDescription', 'UNKNOWN_SERIES')
                
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
                    
                    if self.export_slice(
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
                        study_uid,
                        series_uid,
                        slice_index,
                        total_slices,
                        export_at_display_resolution,
                        current_zoom,
                        initial_fit_zoom,
                        anonymize=anonymize,
                        projection_enabled=projection_enabled,
                        projection_type=projection_type,
                        projection_slice_count=projection_slice_count,
                        studies=studies
                    ):
                        exported += 1
                    
                    progress.setValue(exported)
            
            progress.close()
        except Exception as e:
            progress.close()
            raise e
        
        return exported
    
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
        study_uid: Optional[str] = None,
        series_uid: Optional[str] = None,
        slice_index: Optional[int] = None,
        total_slices: Optional[int] = None,
        export_at_display_resolution: bool = False,
        current_zoom: Optional[float] = None,
        initial_fit_zoom: float = 1.0,
        anonymize: bool = False,
        projection_enabled: bool = False,
        projection_type: str = "aip",
        projection_slice_count: int = 4,
        studies: Optional[Dict[str, Dict[str, List[Dataset]]]] = None
    ) -> bool:
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
            export_at_display_resolution: Whether to export at displayed resolution (apply zoom)
            current_zoom: Optional current zoom level from viewer
            anonymize: Whether to anonymize DICOM exports
            projection_enabled: Whether intensity projection (combine slices) is enabled
            projection_type: Type of projection ("aip", "mip", or "minip")
            projection_slice_count: Number of slices to combine (2, 3, 4, 6, or 8)
            studies: Optional studies dictionary for gathering slices for projection
            
        Returns:
            True if successful
        """
        try:
            if format == "DICOM":
                # Export as DICOM
                if projection_enabled and studies and study_uid and series_uid and slice_index is not None:
                    # Create projection dataset for DICOM export
                    projection_dataset = self._create_projection_dataset(
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
                    image = self._create_projection_for_export(
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
                    return False
                
                # Handle PhotometricInterpretation (MONOCHROME1 inversion, YBR conversion, etc.)
                # Only apply for non-projection images (projections are already processed)
                # Note: Fallback single-slice images need photometric processing even if projection was enabled
                if not is_projection_image:
                    image = ExportManager.process_image_by_photometric_interpretation(image, dataset)
                
                # Apply display resolution scaling BEFORE rendering overlays
                # This ensures font size is calculated based on magnified dimensions
                zoom_factor = 1.0
                if export_at_display_resolution and current_zoom and current_zoom > 1.0:
                    zoom_factor = current_zoom
                    new_width = int(image.width * zoom_factor)
                    new_height = int(image.height * zoom_factor)
                    image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
                
                # Render overlays and ROIs if requested (now on magnified image)
                # Font size will be calculated based on magnified dimensions
                if include_overlays:
                    image = self._render_overlays_and_rois(
                        image,
                        dataset,
                        roi_manager,
                        overlay_manager,
                        measurement_tool,
                        config_manager,
                        study_uid,
                        series_uid,
                        slice_index,
                        total_slices,
                        zoom_factor,  # Pass zoom factor to scale ROI/measurement coordinates
                        projection_enabled=projection_enabled,
                        projection_type=projection_type,
                        projection_slice_count=projection_slice_count,
                        studies=studies,
                        export_at_display_resolution=export_at_display_resolution,
                        initial_fit_zoom=initial_fit_zoom
                    )
                
                if format == "PNG":
                    image.save(output_path, "PNG")
                elif format == "JPG":
                    image.save(output_path, "JPEG", quality=95)
            
            return True
        except Exception as e:
            print(f"Error exporting slice: {e}")
            return False
    
    def _create_projection_for_export(
        self,
        dataset: Dataset,
        studies: Dict[str, Dict[str, List[Dataset]]],
        study_uid: str,
        series_uid: str,
        slice_index: int,
        projection_type: str,
        projection_slice_count: int,
        window_center: Optional[float],
        window_width: Optional[float],
        use_rescaled_values: bool
    ) -> Optional[Image.Image]:
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
                rescale_slope = getattr(dataset, 'RescaleSlope', None)
                rescale_intercept = getattr(dataset, 'RescaleIntercept', None)
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
            print(f"Error creating projection for export: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def _create_projection_dataset(
        self,
        dataset: Dataset,
        studies: Dict[str, Dict[str, List[Dataset]]],
        study_uid: str,
        series_uid: str,
        slice_index: int,
        projection_type: str,
        projection_slice_count: int,
        use_rescaled_values: bool
    ) -> Optional[Dataset]:
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
                original_dtype = original_pixel_array.dtype
                bits_stored = getattr(dataset, 'BitsStored', 16)
                bits_allocated = getattr(dataset, 'BitsAllocated', 16)
                pixel_representation = getattr(dataset, 'PixelRepresentation', 0)  # 0=unsigned, 1=signed
                
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
            print(f"Error creating projection dataset: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def _render_overlays_and_rois(
        self,
        image: Image.Image,
        dataset: Dataset,
        roi_manager,
        overlay_manager,
        measurement_tool,
        config_manager,
        study_uid: Optional[str],
        series_uid: Optional[str],
        slice_index: Optional[int],
        total_slices: Optional[int] = None,
        zoom_factor: float = 1.0,
        projection_enabled: bool = False,
        projection_type: str = "aip",
        projection_slice_count: int = 4,
        studies: Optional[Dict[str, Dict[str, List[Dataset]]]] = None,
        export_at_display_resolution: bool = False,
        initial_fit_zoom: float = 1.0
    ) -> Image.Image:
        """
        Render overlays, ROIs, and measurements onto a PIL Image.
        
        Args:
            image: PIL Image to draw on
            dataset: DICOM dataset
            roi_manager: ROI manager instance
            overlay_manager: Overlay manager instance
            measurement_tool: Measurement tool instance
            config_manager: Config manager instance
            study_uid: Study UID for ROI lookup
            series_uid: Series UID for ROI lookup
            slice_index: Slice index for ROI lookup
            total_slices: Optional total number of slices in series (for "Slice X/Y" formatting)
            zoom_factor: Factor to scale ROI/measurement coordinates by (default 1.0)
            projection_enabled: Whether intensity projection is enabled
            projection_type: Type of projection ("aip", "mip", or "minip")
            projection_slice_count: Number of slices to combine
            studies: Optional studies dictionary for calculating projection thickness
            
        Returns:
            PIL Image with overlays, ROIs, and measurements rendered
        """
        # Convert to RGB if grayscale (needed for drawing colored ROIs)
        if image.mode == 'L':
            image = image.convert('RGB')
        
        draw = ImageDraw.Draw(image)
        width, height = image.size
        
        # Draw ROIs (scale coordinates by zoom_factor)
        if roi_manager and study_uid and series_uid and slice_index is not None:
            # Get ROI colors from config
            roi_line_color = (255, 0, 0)  # Default red
            roi_font_color = (255, 255, 0)  # Default yellow
            roi_line_thickness = 2
            roi_font_size = 6
            
            if config_manager:
                roi_line_color = config_manager.get_roi_line_color()
                roi_font_color = config_manager.get_roi_font_color()
                roi_line_thickness = config_manager.get_roi_line_thickness()
                roi_font_size = config_manager.get_roi_font_size()
            
            rois = roi_manager.get_rois_for_slice(study_uid, series_uid, slice_index)
            for roi in rois:
                bounds = roi.get_bounds()
                # Convert QRectF coordinates to integers and scale by zoom
                x1 = int(max(0, min(bounds.left() * zoom_factor, width)))
                y1 = int(max(0, min(bounds.top() * zoom_factor, height)))
                x2 = int(max(0, min(bounds.right() * zoom_factor, width)))
                y2 = int(max(0, min(bounds.bottom() * zoom_factor, height)))
                
                scaled_thickness = max(1, int(roi_line_thickness * zoom_factor))
                
                if roi.shape_type == "rectangle":
                    draw.rectangle([x1, y1, x2, y2], outline=roi_line_color, width=scaled_thickness)
                elif roi.shape_type == "ellipse":
                    draw.ellipse([x1, y1, x2, y2], outline=roi_line_color, width=scaled_thickness)
                
                # Draw ROI statistics text if available and visible
                if roi.statistics and roi.statistics_overlay_visible:
                    # Try to get a font for ROI statistics
                    roi_font = None
                    font_paths = [
                        "arial.ttf",
                        "Arial.ttf",
                        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
                        "/System/Library/Fonts/Helvetica.ttc",
                        "C:/Windows/Fonts/arial.ttf"
                    ]
                    scaled_font_size = max(8, int(roi_font_size * zoom_factor))
                    for font_path in font_paths:
                        try:
                            roi_font = ImageFont.truetype(font_path, scaled_font_size)
                            break
                        except:
                            continue
                    
                    if roi_font is None:
                        try:
                            roi_font = ImageFont.load_default()
                        except:
                            pass
                    
                    if roi_font:
                        # Format statistics text
                        stats_lines = []
                        if "mean" in roi.visible_statistics and "mean" in roi.statistics:
                            stats_lines.append(f"Mean: {roi.statistics['mean']:.2f}")
                        if "std" in roi.visible_statistics and "std" in roi.statistics:
                            stats_lines.append(f"Std Dev: {roi.statistics['std']:.2f}")
                        if "min" in roi.visible_statistics and "min" in roi.statistics:
                            stats_lines.append(f"Min: {roi.statistics['min']:.2f}")
                        if "max" in roi.visible_statistics and "max" in roi.statistics:
                            stats_lines.append(f"Max: {roi.statistics['max']:.2f}")
                        if "area" in roi.visible_statistics and "area" in roi.statistics:
                            stats_lines.append(f"Area: {roi.statistics['area']:.2f}")
                        if "count" in roi.visible_statistics and "count" in roi.statistics:
                            stats_lines.append(f"Count: {int(roi.statistics['count'])}")
                        
                        if stats_lines:
                            stats_text = "\n".join(stats_lines)
                            # Position text at top-right of ROI bounds with offset
                            text_x = int(x2 + 5 * zoom_factor)
                            text_y = int(y1 + 5 * zoom_factor)
                            draw.text((text_x, text_y), stats_text, fill=roi_font_color, font=roi_font)
        
        # Draw measurements (scale coordinates by zoom_factor)
        if measurement_tool and study_uid and series_uid and slice_index is not None:
            # Get measurement colors from config
            measurement_line_color = (0, 255, 0)  # Default green
            measurement_font_color = (0, 255, 0)  # Default green
            measurement_line_thickness = 2
            measurement_font_size = 6
            
            if config_manager:
                measurement_line_color = config_manager.get_measurement_line_color()
                measurement_font_color = config_manager.get_measurement_font_color()
                measurement_line_thickness = config_manager.get_measurement_line_thickness()
                measurement_font_size = config_manager.get_measurement_font_size()
            
            measurements = measurement_tool.measurements.get((study_uid, series_uid, slice_index), [])
            for measurement in measurements:
                # Scale measurement coordinates
                start_x = int(measurement.start_point.x() * zoom_factor)
                start_y = int(measurement.start_point.y() * zoom_factor)
                end_x = int((measurement.start_point.x() + measurement.end_relative.x()) * zoom_factor)
                end_y = int((measurement.start_point.y() + measurement.end_relative.y()) * zoom_factor)
                
                # Draw measurement line with config color and thickness
                scaled_thickness = max(2, int(measurement_line_thickness * zoom_factor))
                draw.line([(start_x, start_y), (end_x, end_y)], fill=measurement_line_color, width=scaled_thickness)
                
                # Draw text label at midpoint
                mid_x = int((start_x + end_x) / 2)
                mid_y = int((start_y + end_y) / 2)
                
                # Try to get a font for measurement text
                measurement_font = None
                font_paths = [
                    "arial.ttf",
                    "Arial.ttf",
                    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
                    "/System/Library/Fonts/Helvetica.ttc",
                    "C:/Windows/Fonts/arial.ttf"
                ]
                scaled_font_size = max(10, int(measurement_font_size * zoom_factor))
                for font_path in font_paths:
                    try:
                        measurement_font = ImageFont.truetype(font_path, scaled_font_size)
                        break
                    except:
                        continue
                
                if measurement_font is None:
                    try:
                        measurement_font = ImageFont.load_default()
                    except:
                        pass
                
                # Draw measurement text with config color
                if measurement_font:
                    draw.text((mid_x, mid_y), measurement.distance_formatted, fill=measurement_font_color, font=measurement_font)
        
        # Draw overlay text
        if overlay_manager and config_manager:
            parser = DICOMParser(dataset)
            modality = overlay_manager._get_modality(parser)
            corner_tags = config_manager.get_overlay_tags(modality)
            
            # Get base font size from overlay manager
            base_font_size = overlay_manager.font_size
            font_color = overlay_manager.font_color
            
            # Calculate font size
            # The viewer uses ItemIgnoresTransformations flag, which keeps font size constant
            # regardless of zoom level. When exporting at display resolution with zoom,
            # we scale the font by the ratio of current zoom to initial fit zoom.
            
            # If exporting at display resolution, scale by the zoom ratio
            if export_at_display_resolution:
                # Scale by the ratio of current zoom to initial fit zoom
                # This maintains the relative font size as seen in the viewer
                zoom_ratio = zoom_factor / initial_fit_zoom if initial_fit_zoom > 0 else zoom_factor
                base_font_with_scaling = base_font_size * zoom_ratio
            else:
                base_font_with_scaling = base_font_size
            
            # Apply minimal scaling based on ORIGINAL (unzoomed) image size for very small/large images
            image_min_dimension = min(width, height)
            
            # If image was zoomed for export, use original dimensions for scaling decision
            if zoom_factor > 1.0:
                image_min_dimension = int(image_min_dimension / zoom_factor)
            
            if image_min_dimension < 256:
                # Very small images: scale up slightly for readability
                scale_factor = image_min_dimension / 256.0
                font_size = max(8, int(base_font_with_scaling * scale_factor))
            elif image_min_dimension > 2048:
                # Very large images: scale up to maintain visibility
                scale_factor = image_min_dimension / 1024.0
                font_size = int(base_font_with_scaling * scale_factor)
            else:
                # Normal size images (256-2048): use appropriately scaled font size
                font_size = int(base_font_with_scaling)
            
            # Clamp font size to reasonable bounds for readability
            font_size = max(8, min(72, font_size))
            
            # Use user's selected font color with minimal safety check
            if isinstance(font_color, (list, tuple)) and len(font_color) >= 3:
                r, g, b = font_color[0], font_color[1], font_color[2]
                # Only override if color is pure black (which would be invisible)
                if r == 0 and g == 0 and b == 0:
                    text_color = (255, 255, 255)  # Use white instead of pure black
                else:
                    text_color = (r, g, b)
            else:
                text_color = (255, 255, 0)  # Default to bright yellow only if not specified
            
            # Try to load a font, fallback to default
            # Use bold variant to match viewer appearance (viewer uses setBold(True))
            font = None
            # Try common font paths - prioritize bold variants to match viewer
            font_paths = [
                "arialbd.ttf",  # Arial Bold (Windows)
                "Arial Bold.ttf",  # Arial Bold (macOS)
                "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",  # Linux bold
                "/System/Library/Fonts/Helvetica.ttc",  # macOS fallback
                "arial.ttf",  # Regular Arial fallback
                "Arial.ttf",
                "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
                "C:/Windows/Fonts/arialbd.ttf",  # Windows Arial Bold explicit path
                "C:/Windows/Fonts/arial.ttf"
            ]
            for font_path in font_paths:
                try:
                    font = ImageFont.truetype(font_path, font_size)
                    break
                except:
                    continue
            
            # If no font loaded, try default
            if font is None:
                try:
                    font = ImageFont.load_default()
                except:
                    pass
            
            margin = 10
            
            # Calculate projection information for overlay rendering
            projection_start_slice = None
            projection_end_slice = None
            projection_total_thickness = None
            
            if projection_enabled and studies and study_uid and series_uid and slice_index is not None:
                if study_uid in studies and series_uid in studies[study_uid]:
                    series_datasets = studies[study_uid][series_uid]
                    total_series_slices = len(series_datasets)
                    
                    # Calculate projection slice range
                    projection_start_slice = max(0, slice_index)
                    projection_end_slice = min(total_series_slices - 1, slice_index + projection_slice_count - 1)
                    
                    # Calculate total slice thickness
                    total_thickness = 0.0
                    thickness_count = 0
                    for i in range(projection_start_slice, projection_end_slice + 1):
                        if 0 <= i < len(series_datasets):
                            slice_dataset = series_datasets[i]
                            thickness = get_slice_thickness(slice_dataset)
                            if thickness is not None:
                                total_thickness += thickness
                                thickness_count += 1
                    
                    if thickness_count > 0:
                        projection_total_thickness = total_thickness
            
            # Draw text for each corner
            corners = [
                ("upper_left", margin, margin, "left", False),
                ("upper_right", width - margin, margin, "right", False),
                ("lower_left", margin, height - margin, "left", True),
                ("lower_right", width - margin, height - margin, "right", True)
            ]
            
            for corner_name, x, y, align, is_bottom in corners:
                tags = corner_tags.get(corner_name, [])
                if not tags:
                    continue
                
                # Use overlay_manager's _get_corner_text() method for consistent formatting
                # This handles "Slice X/Y" formatting, projection info, and other edge cases
                text = overlay_manager._get_corner_text(
                    parser, tags, total_slices,
                    projection_enabled=projection_enabled,
                    projection_start_slice=projection_start_slice,
                    projection_end_slice=projection_end_slice,
                    projection_total_thickness=projection_total_thickness,
                    projection_type=projection_type
                )
                
                if not text:
                    continue
                
                if not font:
                    continue
                
                # Calculate text bounding box to get dimensions
                bbox = draw.textbbox((0, 0), text, font=font)
                text_width = bbox[2] - bbox[0]
                text_height = bbox[3] - bbox[1]
                
                # Adjust y-position for bottom corners to prevent clipping
                if is_bottom:
                    y = y - text_height
                
                # Draw text - handle right alignment by drawing each line separately
                if align == "right":
                    lines = text.split('\n')
                    current_y = y
                    for line in lines:
                        if line.strip():  # Only draw non-empty lines
                            line_bbox = draw.textbbox((0, 0), line, font=font)
                            line_width = line_bbox[2] - line_bbox[0]
                            line_height = line_bbox[3] - line_bbox[1]
                            # Position each line so it ends at x (the right edge position)
                            line_x = x - line_width
                            draw.text((line_x, current_y), line, fill=text_color, font=font)
                            current_y += line_height
                        else:
                            # For empty lines, just advance by a line height
                            empty_bbox = draw.textbbox((0, 0), "A", font=font)
                            empty_height = empty_bbox[3] - empty_bbox[1]
                            current_y += empty_height
                else:
                    # Left alignment - draw normally
                    draw.text((x, y), text, fill=text_color, font=font)
        
        return image
