"""
File Operations Handler

This module handles all file-related operations including opening files, folders,
and recent files, as well as loading the first slice.

Inputs:
    - File paths (single or multiple)
    - Folder paths
    - Recent file paths
    
Outputs:
    - Loaded DICOM datasets
    - Organized studies/series
    - First slice displayed
    
Requirements:
    - DICOMLoader for loading files
    - DICOMOrganizer for organizing
    - FileDialog for user dialogs
    - ConfigManager for configuration
    - LoadingProgressManager for animated status, progress dialog and cancellation
"""

import os
import gc
from typing import Any, Callable, Optional, Tuple
from PySide6.QtWidgets import QApplication
from core.dicom_loader import DICOMLoader, should_skip_path_for_dicom
from core.dicom_organizer import DICOMOrganizer
from core.loading_progress_manager import LoadingProgressManager
from gui.dialogs.file_dialog import FileDialog
from utils.config_manager import ConfigManager
from gui.main_window import MainWindow

from core.loading_pipeline import run_load_pipeline, format_source_name

class FileOperationsHandler:
    """
    Handles file operations including opening files, folders, and recent files.
    
    Responsibilities:
    - Open single or multiple DICOM files
    - Open folders (recursive)
    - Open recent files/folders
    - Load and organize DICOM datasets
    - Display first slice after loading
    - Clear existing data when opening new files
    """
    
    def __init__(
        self,
        dicom_loader: DICOMLoader,
        dicom_organizer: DICOMOrganizer,
        file_dialog: FileDialog,
        config_manager: ConfigManager,
        main_window: MainWindow,
        clear_data_callback: Callable[..., None],
        load_first_slice_callback: Callable[..., None],
        update_status_callback: Callable[..., None],
        on_load_success_callback: Optional[Callable[..., None]] = None,
    ):
        """
        Initialize the file operations handler.
        
        Args:
            dicom_loader: DICOM loader instance
            dicom_organizer: DICOM organizer instance
            file_dialog: File dialog instance
            config_manager: Configuration manager
            main_window: Main window for dialogs
            clear_data_callback: Callback to clear existing data (ROIs, measurements, etc.)
            load_first_slice_callback: Callback to load and display first slice
            update_status_callback: Callback to update status bar
            on_load_success_callback: Optional hook after successful load
                ``(datasets, studies, merge_result, source_dir, merge_paths)``.
        """
        self.dicom_loader = dicom_loader
        self.dicom_organizer = dicom_organizer
        self.file_dialog = file_dialog
        self.config_manager = config_manager
        self.main_window = main_window
        self.clear_data_callback = clear_data_callback
        self.load_first_slice_callback = load_first_slice_callback
        self.update_status_callback = update_status_callback
        self._on_load_success_callback = on_load_success_callback

        # Centralised loading progress infrastructure (animated dots, progress dialog, cancellation).
        self._loading_manager = LoadingProgressManager(
            update_status_callback=update_status_callback,
            cancel_loader_callback=dicom_loader.cancel,
        )
    
    def _check_large_files(self, file_paths: list[str], threshold_mb: float = 25.0) -> None:
        """
        Check for large files and show warning if any exceed the threshold.
        
        Args:
            file_paths: List of file paths to check
            threshold_mb: Size threshold in MB (default 25 MB)
        """
        threshold_bytes = threshold_mb * 1024 * 1024
        large_files = []
        
        for file_path in file_paths:
            if os.path.isfile(file_path):
                try:
                    file_size = os.path.getsize(file_path)
                    if file_size > threshold_bytes:
                        filename = os.path.basename(file_path)
                        size_mb = file_size / (1024 * 1024)
                        large_files.append((filename, size_mb))
                except (OSError, ValueError):
                    # Skip files that can't be checked (permissions, etc.)
                    continue
        
        if large_files:
            warning_msg = (
                f"Warning: {len(large_files)} large file(s) detected (>25 MB).\n"
                f"Loading may cause temporary unresponsiveness.\n"
                f"Please be patient during loading.\n\n"
                f"Files:\n"
            )
            # Show first 5 files
            for filename, size_mb in large_files[:5]:
                warning_msg += f"{filename} ({size_mb:.1f} MB)\n"
            
            if len(large_files) > 5:
                warning_msg += f"\n... and {len(large_files) - 5} more"
            
            self.file_dialog.show_warning(
                self.main_window,
                "Large File Warning",
                warning_msg
            )
            QApplication.processEvents()
    

    def open_files(self) -> tuple[list[Any] | None, dict[str, Any] | None]:
        """
        Handle open files request.

        Returns:
            Tuple of (datasets list, studies dict) or (None, None) if cancelled/error
        """
        file_paths = self.file_dialog.open_files(self.main_window)
        if not file_paths:
            return None, None

        original_count = len(file_paths)
        file_paths = [p for p in file_paths if not should_skip_path_for_dicom(p)]
        self.dicom_loader.set_extension_skipped_count(max(0, original_count - len(file_paths)))
        if not file_paths:
            self.file_dialog.show_warning(
                self.main_window,
                "No DICOM files to load",
                "All selected files were skipped by type (e.g. documents, images, scripts).",
            )
            return None, None

        self.config_manager.add_recent_file(file_paths[0])
        self.main_window.update_recent_menu()
        source_dir = os.path.dirname(os.path.abspath(file_paths[0]))
        source_name = format_source_name(file_paths)
        self._check_large_files(file_paths)

        captured = list(file_paths)

        def loader_fn(cb):
            return self.dicom_loader.load_files(captured, progress_callback=cb)

        return run_load_pipeline(
            loader_fn=loader_fn,
            source_dir=source_dir,
            source_name=source_name,
            file_paths_for_merge=file_paths,
            loader=self.dicom_loader,
            organizer=self.dicom_organizer,
            loading_manager=self._loading_manager,
            progress_max=len(file_paths),
            main_window=self.main_window,
            file_dialog=self.file_dialog,
            load_first_slice_callback=self.load_first_slice_callback,
            update_status_callback=self.update_status_callback,
            check_compression_errors=True,
            on_load_success=self._on_load_success_callback,
        )


    def open_folder(self) -> tuple[list[Any] | None, dict[str, Any] | None]:
        """
        Handle open folder request.

        Returns:
            Tuple of (datasets list, studies dict) or (None, None) if cancelled/error
        """
        folder_path = self.file_dialog.open_folder(self.main_window)
        if not folder_path:
            return None, None

        self.config_manager.add_recent_file(folder_path)
        self.main_window.update_recent_menu()
        source_dir = folder_path
        source_name = os.path.basename(folder_path)

        estimated_total = 100
        try:
            from pathlib import Path
            scanned = [str(p) for p in Path(folder_path).rglob("*") if p.is_file()]
            if scanned:
                estimated_total = len(scanned)
                self._check_large_files(scanned)
        except Exception:
            pass

        def loader_fn(cb):
            return self.dicom_loader.load_directory(
                folder_path, recursive=True, progress_callback=cb
            )

        return run_load_pipeline(
            loader_fn=loader_fn,
            source_dir=source_dir,
            source_name=source_name,
            file_paths_for_merge=None,
            loader=self.dicom_loader,
            organizer=self.dicom_organizer,
            loading_manager=self._loading_manager,
            progress_max=estimated_total,
            main_window=self.main_window,
            file_dialog=self.file_dialog,
            load_first_slice_callback=self.load_first_slice_callback,
            update_status_callback=self.update_status_callback,
            check_compression_errors=False,
            on_load_success=self._on_load_success_callback,
        )


    def open_recent_file(self, file_path: str) -> tuple[list[Any] | None, dict[str, Any] | None]:
        """
        Handle open recent file/folder request.

        Args:
            file_path: Path to file or folder to open

        Returns:
            Tuple of (datasets list, studies dict) or (None, None) if cancelled/error
        """
        if not os.path.exists(file_path):
            self.file_dialog.show_error(
                self.main_window, "Error", f"File or folder not found:\n{file_path}"
            )
            recent_files = self.config_manager.get_recent_files()
            if file_path in recent_files:
                recent_files.remove(file_path)
                self.config_manager.config["recent_files"] = recent_files
                self.config_manager.save_config()
                self.main_window.update_recent_menu()
            return None, None

        if os.path.isfile(file_path):
            if should_skip_path_for_dicom(file_path):
                self.file_dialog.show_warning(
                    self.main_window,
                    "File skipped",
                    "This file type is not attempted as DICOM (e.g. document, image, script).",
                )
                return None, None

            source_name = os.path.basename(file_path)
            source_dir = os.path.dirname(os.path.abspath(file_path))
            self.dicom_loader.set_extension_skipped_count(0)
            self._check_large_files([file_path])

            def loader_fn(cb):
                return self.dicom_loader.load_files([file_path], progress_callback=cb)

            return run_load_pipeline(
                loader_fn=loader_fn,
                source_dir=source_dir,
                source_name=source_name,
                file_paths_for_merge=[file_path],
                loader=self.dicom_loader,
                organizer=self.dicom_organizer,
                loading_manager=self._loading_manager,
                progress_max=1,
                progress_label=f"Loading {source_name}...",
                main_window=self.main_window,
                file_dialog=self.file_dialog,
                load_first_slice_callback=self.load_first_slice_callback,
                update_status_callback=self.update_status_callback,
                check_compression_errors=True,
                on_load_success=self._on_load_success_callback,
            )

        # Open as folder
        source_name = os.path.basename(file_path)
        source_dir = file_path

        estimated_total = 100
        try:
            from pathlib import Path
            scanned = [str(p) for p in Path(file_path).rglob("*") if p.is_file()]
            if scanned:
                estimated_total = len(scanned)
                self._check_large_files(scanned)
        except Exception:
            pass

        def loader_fn(cb):  # noqa: F811
            return self.dicom_loader.load_directory(
                file_path, recursive=True, progress_callback=cb
            )

        return run_load_pipeline(
            loader_fn=loader_fn,
            source_dir=source_dir,
            source_name=source_name,
            file_paths_for_merge=None,
            loader=self.dicom_loader,
            organizer=self.dicom_organizer,
            loading_manager=self._loading_manager,
            progress_max=estimated_total,
            main_window=self.main_window,
            file_dialog=self.file_dialog,
            load_first_slice_callback=self.load_first_slice_callback,
            update_status_callback=self.update_status_callback,
            check_compression_errors=False,
            on_load_success=self._on_load_success_callback,
        )


    def open_paths(self, paths: list[str]) -> tuple[list[Any] | None, dict[str, Any] | None]:
        """
        Handle open files/folders from drag-and-drop or direct paths.

        Args:
            paths: List of file or folder paths to open

        Returns:
            Tuple of (datasets list, studies dict) or (None, None) if cancelled/error
        """
        if not paths:
            return None, None

        files = []
        folders = []
        for path in paths:
            if not os.path.exists(path):
                continue
            if os.path.isfile(path):
                files.append(path)
            elif os.path.isdir(path):
                folders.append(path)

        if folders:
            folder_path = folders[0]
            self.config_manager.add_recent_file(folder_path)
            self.main_window.update_recent_menu()
            source_dir = folder_path
            source_name = os.path.basename(folder_path)

            estimated_total = 100
            try:
                from pathlib import Path
                scanned = [str(p) for p in Path(folder_path).rglob("*") if p.is_file()]
                if scanned:
                    estimated_total = len(scanned)
                    self._check_large_files(scanned)
            except Exception:
                pass

            def loader_fn(cb):
                return self.dicom_loader.load_directory(
                    folder_path, recursive=True, progress_callback=cb
                )

            return run_load_pipeline(
                loader_fn=loader_fn,
                source_dir=source_dir,
                source_name=source_name,
                file_paths_for_merge=None,
                loader=self.dicom_loader,
                organizer=self.dicom_organizer,
                loading_manager=self._loading_manager,
                progress_max=estimated_total,
                main_window=self.main_window,
                file_dialog=self.file_dialog,
                load_first_slice_callback=self.load_first_slice_callback,
                update_status_callback=self.update_status_callback,
                check_compression_errors=False,
                on_load_success=self._on_load_success_callback,
            )

        if files:
            original_count = len(files)
            files = [p for p in files if not should_skip_path_for_dicom(p)]
            self.dicom_loader.set_extension_skipped_count(max(0, original_count - len(files)))
            if not files:
                self.file_dialog.show_warning(
                    self.main_window,
                    "No DICOM files to load",
                    "All dropped/selected files were skipped by type (e.g. documents, images, scripts).",
                )
                return None, None

            self.config_manager.add_recent_file(files[0])
            self.main_window.update_recent_menu()
            source_dir = os.path.dirname(os.path.abspath(files[0]))
            source_name = format_source_name(files)
            self._check_large_files(files)

            captured = list(files)

            def loader_fn(cb):  # noqa: F811
                return self.dicom_loader.load_files(captured, progress_callback=cb)

            return run_load_pipeline(
                loader_fn=loader_fn,
                source_dir=source_dir,
                source_name=source_name,
                file_paths_for_merge=files,
                loader=self.dicom_loader,
                organizer=self.dicom_organizer,
                loading_manager=self._loading_manager,
                progress_max=len(files),
                main_window=self.main_window,
                file_dialog=self.file_dialog,
                load_first_slice_callback=self.load_first_slice_callback,
                update_status_callback=self.update_status_callback,
                check_compression_errors=True,
                on_load_success=self._on_load_success_callback,
            )

        return None, None

    def _get_first_study_series_by_dicom(
        self, studies: dict[str, Any]
    ) -> Optional[Tuple[str, str]]:
        """
        Return (study_uid, series_uid) for the first study/series using the same
        logic as the series navigator: first study in dict iteration order, then
        series with lowest SeriesNumber in that study. So the auto-loaded series
        is always from the first study shown in the navigator.

        Args:
            studies: Dictionary of organized studies/series (study_uid -> series_key -> [datasets]).

        Returns:
            (study_uid, series_uid) or None if no studies/series.
        """
        if not studies:
            return None
        for study_uid in studies.keys():
            series_dict = studies[study_uid]
            if not series_dict:
                continue
            series_list = []
            for series_uid, datasets in series_dict.items():
                if not datasets:
                    continue
                sn = getattr(datasets[0], 'SeriesNumber', None)
                try:
                    sn = int(sn) if sn is not None else 0
                except (ValueError, TypeError):
                    sn = 0
                series_list.append((sn, series_uid, datasets))
            series_list.sort(key=lambda x: x[0])
            if not series_list:
                continue
            return (study_uid, series_list[0][1])
        return None

    def load_first_slice(self, studies: dict[str, Any]) -> dict[str, Any] | None:
        """
        Load and return information about the first slice.
        First study/series uses the same order as the series navigator (first study, lowest SeriesNumber).

        Args:
            studies: Dictionary of organized studies/series

        Returns:
            Dictionary with first slice information: study_uid, series_uid, slice_index, dataset
            or None if no studies available
        """
        if not studies:
            return None
        pair = self._get_first_study_series_by_dicom(studies)
        if not pair:
            return None
        study_uid, series_uid = pair
        datasets = studies[study_uid][series_uid]
        if not datasets:
            return None
        return {
            'study_uid': study_uid,
            'series_uid': series_uid,
            'slice_index': 0,
            'dataset': datasets[0],
            'total_slices': len(datasets)
        }

