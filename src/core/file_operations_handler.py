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
from typing import Callable, Optional, Tuple
from PySide6.QtWidgets import QApplication
from core.dicom_loader import DICOMLoader, should_skip_path_for_dicom
from core.dicom_organizer import DICOMOrganizer
from core.loading_progress_manager import LoadingProgressManager
from gui.dialogs.file_dialog import FileDialog
from utils.config_manager import ConfigManager
from gui.main_window import MainWindow


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
        clear_data_callback: Callable,
        load_first_slice_callback: Callable,
        update_status_callback: Callable
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
        """
        self.dicom_loader = dicom_loader
        self.dicom_organizer = dicom_organizer
        self.file_dialog = file_dialog
        self.config_manager = config_manager
        self.main_window = main_window
        self.clear_data_callback = clear_data_callback
        self.load_first_slice_callback = load_first_slice_callback
        self.update_status_callback = update_status_callback

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
    
    def _format_source_name(self, file_paths: list[str]) -> str:
        """
        Format source name for status display.
        
        Args:
            file_paths: List of file paths
            
        Returns:
            Formatted source name string
        """
        if len(file_paths) == 1:
            return os.path.basename(file_paths[0])
        elif len(file_paths) > 1:
            return os.path.basename(file_paths[0]) + "..."
        return ""
    
    def _format_final_status(
        self,
        num_studies: int,
        num_series: int,
        num_files: int,
        source_name: str,
        num_processed: Optional[int] = None,
        non_dicom_count: int = 0,
        duplicate_count: int = 0,
        extension_skipped_count: int = 0,
    ) -> str:
        """
        Format final status message with loaded counts and optional skipped breakdown.

        Args:
            num_studies: Number of studies in the batch
            num_series: Number of series in the batch
            num_files: Number of files loaded in the batch
            source_name: Name of source (folder or file)
            num_processed: Unused; kept for call-site compatibility
            non_dicom_count: Number of files that failed to load (attempted but not DICOM or errors)
            duplicate_count: Number of duplicate files not added
            extension_skipped_count: Number of files skipped by extension (not attempted)

        Returns:
            Formatted status message
        """
        study_text = f"{num_studies} study" if num_studies == 1 else f"{num_studies} studies"
        series_text = f"{num_series} series"
        file_text = f"{num_files} file" + ("s" if num_files != 1 else "")

        main = f"{study_text}, {series_text}, {file_text} loaded from {source_name}"

        total_non_dicom = extension_skipped_count + non_dicom_count
        if total_non_dicom > 0 or duplicate_count > 0:
            parts = []
            if total_non_dicom > 0:
                parts.append(f"{total_non_dicom} non-DICOM")
            if duplicate_count > 0:
                parts.append(f"{duplicate_count} duplicate" + ("s" if duplicate_count != 1 else ""))
            main += " (" + ", ".join(parts) + " skipped)"

        return main

    @staticmethod
    def _batch_counts_from_merge_result(merge_result) -> tuple[int, int, int]:
        """
        Compute batch-only study/series/file counts from a MergeResult.

        Used so the status bar reflects only the current batch actually loaded
        (e.g. after cancel or when duplicates are skipped).

        Args:
            merge_result: MergeResult from DICOMOrganizer.merge_batch()

        Returns:
            Tuple of (num_studies, num_series, num_files) for the batch.
        """
        combined = merge_result.new_series + merge_result.appended_series
        num_studies = len({s[0] for s in combined})
        num_series = len(combined)
        num_files = merge_result.added_file_count
        return (num_studies, num_series, num_files)

    def open_files(self) -> tuple[list, dict]:
        """
        Handle open files request.
        
        Returns:
            Tuple of (datasets list, studies dict) or (None, None) if cancelled/error
        """
        file_paths = self.file_dialog.open_files(self.main_window)
        if not file_paths:
            return None, None

        # Skip known non-DICOM extensions so they are not attempted or counted as failed
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

        # Add first file to recent files (representing this file selection)
        if file_paths:
            self.config_manager.add_recent_file(file_paths[0])
            self.main_window.update_recent_menu()
        
        # Determine source directory for dedup/disambiguation
        source_dir = os.path.dirname(os.path.abspath(file_paths[0]))
        
        # Format source name for status display
        source_name = self._format_source_name(file_paths)
        
        try:
            # Reset loading manager state (cancellation flag, animation, dialog)
            self._loading_manager.reset()
            self.dicom_loader.reset_cancellation()
            
            # Create progress dialog first so the UI is responsive immediately
            progress_dialog = self._loading_manager.create_progress_dialog(self.main_window,
                len(file_paths),
                f"Loading files from {source_name}..."
            )
            progress_dialog.setValue(0)
            QApplication.processEvents()

            # Check for large files and show warning (now that the progress dialog is visible)
            self._check_large_files(file_paths)
            
            # Track if we've actually started loading files (to avoid false cancellation on dialog creation)
            # Use list to allow modification in nested function
            loading_started = [False]
            
            # Create progress callback
            def progress_callback(current: int, total: int, filename: str) -> None:
                # Mark that loading has started once we get a real progress update with a filename
                if current > 0 and filename:
                    loading_started[0] = True
                
                # Update progress dialog
                if self._loading_manager.get_dialog():
                    self._loading_manager.get_dialog().setValue(current)
                    if filename:
                        # Update dialog label with current filename
                        if filename.startswith("Deferring"):
                            self._loading_manager.get_dialog().setLabelText(filename)
                        else:
                            self._loading_manager.get_dialog().setLabelText(f"Loading file {current}/{total}: {filename}...")
                    else:
                        self._loading_manager.get_dialog().setLabelText(f"Loaded {current} file(s). Organizing into studies/series...")
                    
                    # Manually check if Cancel button was clicked (only after loading has actually started)
                    # This prevents false cancellation when dialog is first shown
                    if not self._loading_manager.is_cancelled() and loading_started[0] and self._loading_manager.was_dialog_cancelled():
                        self._loading_manager.on_cancel_loading()
                
                # Check for explicit user cancellation
                if self._loading_manager.is_cancelled():
                    # Already handled by _on_cancel_loading
                    pass
                
                QApplication.processEvents()
            
            # Load files
            datasets = self.dicom_loader.load_files(file_paths, progress_callback=progress_callback)
            
            # Close progress dialog
            self._loading_manager.close_progress_dialog()
            
            # Check for cancellation (use explicit user cancellation flag)
            was_cancelled = self._loading_manager.is_cancelled()
            if was_cancelled:
                num_loaded = len(datasets) if datasets else 0
                if num_loaded > 0:
                    # Show cancellation message but keep partial data
                    self.update_status_callback(f"Loading cancelled. {num_loaded} file(s) loaded successfully.")
                    # Continue with organization and display of partial data
                else:
                    # No files loaded, return None
                    self.update_status_callback("Loading cancelled.")
                    self.dicom_loader.reset_cancellation()
                    return None, None
            
            # Stop animation after loading completes
            self._loading_manager.stop_animated_loading()
            
            if not datasets:
                # Check if there were specific errors
                failed = self.dicom_loader.get_failed_files()
                if failed:
                    error_msg = "No DICOM files could be loaded.\n\nErrors:\n"
                    for path, error in failed[:5]:  # Show first 5
                        error_msg += f"\n{os.path.basename(path)}: {error}"
                    if len(failed) > 5:
                        error_msg += f"\n... and {len(failed) - 5} more"
                else:
                    error_msg = "No DICOM files could be loaded."
                
                self.file_dialog.show_error(
                    self.main_window,
                    "Error",
                    error_msg
                )
                return None, None
            
            # Validate datasets before processing
            # Multi-frame detection kept for potential future use, but no filtering
            validated_datasets = []
            validated_paths = []
            
            for ds, path in zip(datasets, file_paths):
                validated_datasets.append(ds)
                validated_paths.append(path)
            
            # Update datasets and paths to validated ones
            datasets = validated_datasets
            file_paths = validated_paths
            
            if not datasets:
                self.file_dialog.show_error(
                    self.main_window,
                    "No Valid Files",
                    "All selected files were skipped due to safety checks. No files to display."
                )
                return None, None
            
            # Show warnings for failed files
            failed = self.dicom_loader.get_failed_files()
            if failed:
                warning_msg = f"Warning: {len(failed)} file(s) could not be loaded:\n"
                for path, error in failed[:5]:  # Show first 5
                    warning_msg += f"\n{os.path.basename(path)}: {error}"
                if len(failed) > 5:
                    warning_msg += f"\n... and {len(failed) - 5} more"
                
                self.file_dialog.show_warning(self.main_window, "Loading Warnings", warning_msg)
            
            # Check if we have a large number of datasets and suggest memory management
            if len(datasets) > 100:
                # Force garbage collection before expensive organize step
                import time
                gc_start = time.time()
                gc.collect()
                gc_time = time.time() - gc_start
                # print(f"[ORGANIZE DEBUG] Pre-organize GC: {gc_time:.3f}s")
                QApplication.processEvents()
            
            # Merge into existing organizer state (additive)
            try:
                import time
                organize_start = time.time()
                # print(f"[ORGANIZE DEBUG] Starting merge_batch of {len(datasets)} datasets...")
                merge_result = self.dicom_organizer.merge_batch(datasets, file_paths, source_dir)
                organize_time = time.time() - organize_start
                # print(f"[ORGANIZE DEBUG] merge_batch completed in {organize_time:.2f}s")
            except MemoryError as e:
                self.file_dialog.show_error(
                    self.main_window,
                    "Memory Error",
                    f"Out of memory while organizing DICOM files. "
                    f"Try closing other applications or loading fewer files.\n\nError: {str(e)}"
                )
                return None, None
            except Exception as e:
                self.file_dialog.show_error(
                    self.main_window,
                    "Error",
                    f"Error organizing DICOM files: {str(e)}"
                )
                return None, None
            
            # Update UI with additive load result
            try:
                self.load_first_slice_callback(merge_result)
            except MemoryError as e:
                self.file_dialog.show_error(
                    self.main_window,
                    "Memory Error",
                    f"Out of memory while displaying image. "
                    f"Try closing other applications.\n\nError: {str(e)}"
                )
                return None, None
            except Exception as e:
                self.file_dialog.show_error(
                    self.main_window,
                    "Error",
                    f"Error displaying first slice: {str(e)}"
                )
                return None, None
            
            # Format and display final status (batch-only counts + processed/non-DICOM/duplicate)
            num_studies, num_series, num_files = self._batch_counts_from_merge_result(merge_result)
            extension_skipped = self.dicom_loader.get_extension_skipped_count()
            num_processed = self.dicom_loader.get_attempted_file_count() + extension_skipped
            non_dicom_count = len(self.dicom_loader.get_failed_files())
            duplicate_count = merge_result.skipped_file_count
            final_status = self._format_final_status(
                num_studies, num_series, num_files, source_name,
                num_processed=num_processed,
                non_dicom_count=non_dicom_count,
                duplicate_count=duplicate_count,
                extension_skipped_count=extension_skipped,
            )

            # Check for compression errors and append guidance if needed
            failed = self.dicom_loader.get_failed_files()
            compression_errors = [f for f in failed if "Compressed DICOM" in f[1] or "pylibjpeg" in f[1].lower()]
            if compression_errors:
                compression_count = len(compression_errors)
                final_status += f". {compression_count} compressed file(s) require pylibjpeg: pip install pylibjpeg pyjpegls"

            self.update_status_callback(final_status)
            QApplication.processEvents()

            # Reset cancellation flag
            self.dicom_loader.reset_cancellation()

            return datasets, self.dicom_organizer.studies

        except SystemExit:
            self._loading_manager.stop_animated_loading()
            self._loading_manager.close_progress_dialog()
            self.dicom_loader.reset_cancellation()
            raise  # Don't catch system exit
        except KeyboardInterrupt:
            self._loading_manager.stop_animated_loading()
            self._loading_manager.close_progress_dialog()
            self.dicom_loader.reset_cancellation()
            raise  # Don't catch Ctrl+C
        except MemoryError as e:
            self._loading_manager.stop_animated_loading()
            self._loading_manager.close_progress_dialog()
            self.dicom_loader.reset_cancellation()
            self.file_dialog.show_error(
                self.main_window,
                "Memory Error",
                f"Out of memory while loading files. "
                f"Try closing other applications or use a system with more memory.\n\nError: {str(e)}"
            )
            return None, None
        except BaseException as e:
            self._loading_manager.stop_animated_loading()
            self._loading_manager.close_progress_dialog()
            self.dicom_loader.reset_cancellation()
            # Catch everything else including C extension errors that make it to Python
            error_type = type(e).__name__
            error_msg = f"A critical error occurred during file loading.\n\n"
            error_msg += f"Error: {error_type}: {str(e)}\n\n"
            error_msg += f"This may be due to corrupted or unsupported DICOM files."
            
            print(f"Critical error in open_files: {error_type}: {e}")
            import traceback
            traceback.print_exc()
            
            self.file_dialog.show_error(
                self.main_window,
                "Critical Error",
                error_msg
            )
            return None, None
    
    def open_folder(self) -> tuple[list, dict]:
        """
        Handle open folder request.
        
        Returns:
            Tuple of (datasets list, studies dict) or (None, None) if cancelled/error
        """
        folder_path = self.file_dialog.open_folder(self.main_window)
        if not folder_path:
            return None, None
        
        # Add folder to recent files
        self.config_manager.add_recent_file(folder_path)
        self.main_window.update_recent_menu()
        
        # Source directory for dedup/disambiguation
        source_dir = folder_path
        
        # Format source name for status display
        source_name = os.path.basename(folder_path)
        
        try:
            # Reset loading manager state (cancellation flag, animation, dialog)
            self._loading_manager.reset()
            self.dicom_loader.reset_cancellation()
            
            # Create progress dialog immediately so the UI is responsive (use placeholder count)
            progress_dialog = self._loading_manager.create_progress_dialog(self.main_window,
                100,  # Placeholder – updated after folder scan below
                f"Loading files from {source_name}..."
            )
            progress_dialog.setValue(0)
            QApplication.processEvents()

            # Scan folder once: update dialog count and check for large files (dialog is now visible)
            try:
                from pathlib import Path
                folder_path_obj = Path(folder_path)
                scanned_files = [str(p) for p in folder_path_obj.rglob('*') if p.is_file()]
                if scanned_files:
                    progress_dialog.setMaximum(len(scanned_files))
                    self._check_large_files(scanned_files)
            except Exception:
                pass

            # Track if we've actually started loading files (to avoid false cancellation on dialog creation)
            loading_started = [False]
            
            # Create progress callback with throttling for UI updates
            last_progress_update = [0]  # Use list to allow modification in nested function
            last_label_update = [0]
            progress_update_interval = 0.1  # Update progress bar every 100ms
            label_update_interval = 0.5  # Update label text every 500ms
            
            def progress_callback(current: int, total: int, filename: str) -> None:
                import time
                current_time = time.time()
                
                # Mark that loading has started once we get a real progress update with a filename
                if current > 0 and filename:
                    loading_started[0] = True
                
                # Update progress dialog with throttling
                if self._loading_manager.get_dialog():
                    # Always update maximum if needed (infrequent operation)
                    if total > self._loading_manager.get_dialog().maximum():
                        self._loading_manager.get_dialog().setMaximum(total)
                    
                    # Throttle progress bar updates (every 100ms)
                    if current_time - last_progress_update[0] >= progress_update_interval:
                        self._loading_manager.get_dialog().setValue(current)
                        last_progress_update[0] = current_time
                    
                    # Throttle label text updates (every 500ms) - this is more expensive
                    if current_time - last_label_update[0] >= label_update_interval:
                        if filename:
                            self._loading_manager.get_dialog().setLabelText(f"Loading file {current}/{total}: {filename}...")
                        else:
                            self._loading_manager.get_dialog().setLabelText(f"Loaded {current} file(s). Organizing into studies/series...")
                        last_label_update[0] = current_time
                    
                    # Manually check if Cancel button was clicked (only after loading has actually started)
                    # This prevents false cancellation when dialog is first shown
                    if not self._loading_manager.is_cancelled() and loading_started[0] and self._loading_manager.was_dialog_cancelled():
                        self._loading_manager.on_cancel_loading()
                
                # Check for explicit user cancellation
                if self._loading_manager.is_cancelled():
                    # Already handled by _on_cancel_loading
                    pass
                
                # Throttle processEvents - only call every 50ms
                if current_time - last_progress_update[0] >= 0.05:
                    QApplication.processEvents()
            
            # Load folder (recursive)
            datasets = self.dicom_loader.load_directory(folder_path, recursive=True, progress_callback=progress_callback)
            
            # Close progress dialog
            self._loading_manager.close_progress_dialog()
            
            # Check for cancellation (use explicit user cancellation flag)
            was_cancelled = self._loading_manager.is_cancelled()
            if was_cancelled:
                num_loaded = len(datasets) if datasets else 0
                if num_loaded > 0:
                    # Show cancellation message but keep partial data
                    self.update_status_callback(f"Loading cancelled. {num_loaded} file(s) loaded successfully.")
                    # Continue with organization and display of partial data
                else:
                    # No files loaded, return None
                    self.update_status_callback("Loading cancelled.")
                    self.dicom_loader.reset_cancellation()
                    return None, None
            
            if not datasets:
                # Check if there were specific errors
                failed = self.dicom_loader.get_failed_files()
                if failed:
                    error_msg = f"No DICOM files found in folder.\n\n{len(failed)} file(s) could not be loaded."
                else:
                    error_msg = "No DICOM files found in folder."
                
                self.file_dialog.show_error(
                    self.main_window,
                    "Error",
                    error_msg
                )
                return None, None
            
            # Show warnings
            failed = self.dicom_loader.get_failed_files()
            if failed:
                warning_msg = f"Warning: {len(failed)} file(s) could not be loaded."
                self.file_dialog.show_warning(self.main_window, "Loading Warnings", warning_msg)
            
            # Check if we have a large number of datasets and suggest memory management
            if len(datasets) > 100:
                # Force garbage collection before expensive organize step
                gc.collect()
                QApplication.processEvents()
            
            # Merge into existing organizer state (additive)
            # Extract file paths from datasets for path-based dedup
            folder_file_paths = [getattr(ds, 'filename', None) for ds in datasets]
            try:
                merge_result = self.dicom_organizer.merge_batch(datasets, folder_file_paths, source_dir)
            except MemoryError as e:
                self.file_dialog.show_error(
                    self.main_window,
                    "Memory Error",
                    f"Out of memory while organizing DICOM files. "
                    f"Try closing other applications or loading fewer files.\n\nError: {str(e)}"
                )
                return None, None
            except Exception as e:
                self.file_dialog.show_error(
                    self.main_window,
                    "Error",
                    f"Error organizing DICOM files: {str(e)}"
                )
                return None, None
            
            # Update UI with additive load result
            try:
                self.load_first_slice_callback(merge_result)
            except MemoryError as e:
                self.file_dialog.show_error(
                    self.main_window,
                    "Memory Error",
                    f"Out of memory while displaying image. "
                    f"Try closing other applications.\n\nError: {str(e)}"
                )
                return None, None
            except Exception as e:
                self.file_dialog.show_error(
                    self.main_window,
                    "Error",
                    f"Error displaying first slice: {str(e)}"
                )
                return None, None
            
            # Format and display final status (batch-only counts + processed/non-DICOM/duplicate)
            num_studies, num_series, num_files = self._batch_counts_from_merge_result(merge_result)
            extension_skipped = self.dicom_loader.get_extension_skipped_count()
            num_processed = self.dicom_loader.get_attempted_file_count() + extension_skipped
            non_dicom_count = len(self.dicom_loader.get_failed_files())
            duplicate_count = merge_result.skipped_file_count
            final_status = self._format_final_status(
                num_studies, num_series, num_files, source_name,
                num_processed=num_processed,
                non_dicom_count=non_dicom_count,
                duplicate_count=duplicate_count,
                extension_skipped_count=extension_skipped,
            )
            self.update_status_callback(final_status)
            QApplication.processEvents()

            # Reset cancellation flag
            self.dicom_loader.reset_cancellation()

            return datasets, self.dicom_organizer.studies

        except SystemExit:
            self._loading_manager.close_progress_dialog()
            self.dicom_loader.reset_cancellation()
            raise  # Don't catch system exit
        except KeyboardInterrupt:
            self._loading_manager.close_progress_dialog()
            self.dicom_loader.reset_cancellation()
            raise  # Don't catch Ctrl+C
        except MemoryError as e:
            self._loading_manager.close_progress_dialog()
            self.dicom_loader.reset_cancellation()
            self.file_dialog.show_error(
                self.main_window,
                "Memory Error",
                f"Out of memory while loading folder. "
                f"Try closing other applications or use a system with more memory.\n\nError: {str(e)}"
            )
            return None, None
        except BaseException as e:
            self._loading_manager.close_progress_dialog()
            self.dicom_loader.reset_cancellation()
            # Catch everything else including C extension errors that make it to Python
            error_type = type(e).__name__
            error_msg = f"A critical error occurred during folder loading.\n\n"
            error_msg += f"Error: {error_type}: {str(e)}\n\n"
            error_msg += f"This may be due to corrupted or unsupported DICOM files."
            
            print(f"Critical error in open_folder: {error_type}: {e}")
            import traceback
            traceback.print_exc()
            
            self.file_dialog.show_error(
                self.main_window,
                "Critical Error",
                error_msg
            )
            return None, None
    
    def open_recent_file(self, file_path: str) -> tuple[list, dict]:
        """
        Handle open recent file/folder request.
        
        Args:
            file_path: Path to file or folder to open
            
        Returns:
            Tuple of (datasets list, studies dict) or (None, None) if cancelled/error
        """
        # Check if path exists
        if not os.path.exists(file_path):
            self.file_dialog.show_error(
                self.main_window,
                "Error",
                f"File or folder not found:\n{file_path}"
            )
            # Remove from recent files if it doesn't exist
            recent_files = self.config_manager.get_recent_files()
            if file_path in recent_files:
                recent_files.remove(file_path)
                self.config_manager.config["recent_files"] = recent_files
                self.config_manager.save_config()
                self.main_window.update_recent_menu()
            return None, None
        
        # Determine if it's a file or folder
        if os.path.isfile(file_path):
            if should_skip_path_for_dicom(file_path):
                self.file_dialog.show_warning(
                    self.main_window,
                    "File skipped",
                    "This file type is not attempted as DICOM (e.g. document, image, script).",
                )
                return None, None

            # Open as file
            source_name = os.path.basename(file_path)
            # Source directory for dedup/disambiguation
            source_dir = os.path.dirname(os.path.abspath(file_path))

            # Check for large file and show warning
            self._check_large_files([file_path])
            
            try:
                # Reset cancellation flags
                self._loading_manager.reset()
                self.dicom_loader.reset_cancellation()
                self.dicom_loader.set_extension_skipped_count(0)  # Single file, no extension filter applied

                # Create progress dialog
                progress_dialog = self._loading_manager.create_progress_dialog(self.main_window,
                    1,
                    f"Loading {source_name}..."
                )
                progress_dialog.setValue(0)
                QApplication.processEvents()
                
                # Track if we've actually started loading files (to avoid false cancellation on dialog creation)
                loading_started = [False]
                
                # Create progress callback
                def progress_callback(current: int, total: int, filename: str) -> None:
                    # Mark that loading has started once we get a real progress update with a filename
                    if current > 0 and filename:
                        loading_started[0] = True
                    
                    # Update progress dialog
                    if self._loading_manager.get_dialog():
                        self._loading_manager.get_dialog().setValue(current)
                        if filename:
                            if filename.startswith("Deferring"):
                                self._loading_manager.get_dialog().setLabelText(filename)
                            else:
                                self._loading_manager.get_dialog().setLabelText(filename.rstrip('.'))
                        else:
                            self._loading_manager.get_dialog().setLabelText(f"Loaded {current} file(s). Organizing into studies/series...")
                        
                        # Manually check if Cancel button was clicked (only after loading has actually started)
                        # This prevents false cancellation when dialog is first shown
                        if not self._loading_manager.is_cancelled() and loading_started[0] and self._loading_manager.was_dialog_cancelled():
                            self._loading_manager.on_cancel_loading()
                    
                    # Check for explicit user cancellation
                    if self._loading_manager.is_cancelled():
                        # Already handled by _on_cancel_loading
                        pass
                        
                    QApplication.processEvents()
                
                datasets = self.dicom_loader.load_files([file_path], progress_callback=progress_callback)
                
                # Close progress dialog
                self._loading_manager.close_progress_dialog()
                
                # Check for cancellation (use explicit user cancellation flag)
                was_cancelled = self._loading_manager.is_cancelled()
                if was_cancelled:
                    num_loaded = len(datasets) if datasets else 0
                    if num_loaded > 0:
                        # Show cancellation message but keep partial data
                        self.update_status_callback(f"Loading cancelled. {num_loaded} file(s) loaded successfully.")
                        # Continue with organization and display of partial data
                    else:
                        # No files loaded, return None
                        self.update_status_callback("Loading cancelled.")
                        self.dicom_loader.reset_cancellation()
                        return None, None
                
                # Stop animation after loading completes
                self._loading_manager.stop_animated_loading()
                
                if not datasets:
                    # Check if there were specific errors
                    failed = self.dicom_loader.get_failed_files()
                    if failed:
                        error_msg = "No DICOM files could be loaded.\n\nErrors:\n"
                        for path, error in failed[:5]:  # Show first 5
                            error_msg += f"\n{os.path.basename(path)}: {error}"
                        if len(failed) > 5:
                            error_msg += f"\n... and {len(failed) - 5} more"
                    else:
                        error_msg = "No DICOM files could be loaded."
                    
                    self.file_dialog.show_error(
                        self.main_window,
                        "Error",
                        error_msg
                    )
                    return None, None
                
                # Check if we have a large number of datasets and suggest memory management
                if len(datasets) > 100:
                    # Force garbage collection before expensive organize step
                    gc.collect()
                    QApplication.processEvents()
                
                # Merge into existing organizer state (additive)
                try:
                    merge_result = self.dicom_organizer.merge_batch(datasets, [file_path], source_dir)
                except MemoryError as e:
                    self.file_dialog.show_error(
                        self.main_window,
                        "Memory Error",
                        f"Out of memory while organizing DICOM files. "
                        f"Try closing other applications or loading fewer files.\n\nError: {str(e)}"
                    )
                    return None, None
                except Exception as e:
                    self.file_dialog.show_error(
                        self.main_window,
                        "Error",
                        f"Error organizing DICOM files: {str(e)}"
                    )
                    return None, None
                
                # Update UI with additive load result
                try:
                    self.load_first_slice_callback(merge_result)
                except MemoryError as e:
                    self.file_dialog.show_error(
                        self.main_window,
                        "Memory Error",
                        f"Out of memory while displaying image. "
                        f"Try closing other applications.\n\nError: {str(e)}"
                    )
                    return None, None
                except Exception as e:
                    self.file_dialog.show_error(
                        self.main_window,
                        "Error",
                        f"Error displaying first slice: {str(e)}"
                    )
                    return None, None
                
                # Format and display final status (batch-only counts + processed/non-DICOM/duplicate)
                num_studies, num_series, num_files = self._batch_counts_from_merge_result(merge_result)
                extension_skipped = self.dicom_loader.get_extension_skipped_count()
                num_processed = self.dicom_loader.get_attempted_file_count() + extension_skipped
                non_dicom_count = len(self.dicom_loader.get_failed_files())
                duplicate_count = merge_result.skipped_file_count
                final_status = self._format_final_status(
                    num_studies, num_series, num_files, source_name,
                    num_processed=num_processed,
                    non_dicom_count=non_dicom_count,
                    duplicate_count=duplicate_count,
                    extension_skipped_count=extension_skipped,
                )

                # Check for compression errors and append guidance if needed
                failed = self.dicom_loader.get_failed_files()
                compression_errors = [f for f in failed if "Compressed DICOM" in f[1] or "pylibjpeg" in f[1].lower()]
                if compression_errors:
                    compression_count = len(compression_errors)
                    final_status += f". {compression_count} compressed file(s) require pylibjpeg: pip install pylibjpeg pyjpegls"
                
                self.update_status_callback(final_status)
                QApplication.processEvents()
                
                # Reset cancellation flag
                self.dicom_loader.reset_cancellation()
                
                return datasets, self.dicom_organizer.studies
                
            except MemoryError as e:
                self._loading_manager.close_progress_dialog()
                self.dicom_loader.reset_cancellation()
                self.file_dialog.show_error(
                    self.main_window,
                    "Memory Error",
                    f"Out of memory while loading file. "
                    f"Try closing other applications or use a system with more memory.\n\nError: {str(e)}"
                )
                return None, None
            except Exception as e:
                self._loading_manager.close_progress_dialog()
                self.dicom_loader.reset_cancellation()
                error_type = type(e).__name__
                error_msg = f"Error loading file: {str(e)}"
                if error_type not in error_msg:
                    error_msg = f"{error_type}: {error_msg}"
                self.file_dialog.show_error(
                    self.main_window,
                    "Error",
                    error_msg
                )
                return None, None
        else:
            # Open as folder
            source_name = os.path.basename(file_path)
            # Source directory for dedup/disambiguation
            source_dir = file_path
            
            # Check for large files in folder before loading
            try:
                from pathlib import Path
                folder_path_obj = Path(file_path)
                file_paths = [str(p) for p in folder_path_obj.rglob('*') if p.is_file()]
                if file_paths:
                    self._check_large_files(file_paths)
            except Exception:
                # If we can't check files, continue without warning
                pass
            
            try:
                # Reset cancellation flags
                self._loading_manager.reset()
                self.dicom_loader.reset_cancellation()
                
                # Estimate total files for progress dialog
                try:
                    from pathlib import Path
                    folder_path_obj = Path(file_path)
                    estimated_total = len([str(p) for p in folder_path_obj.rglob('*') if p.is_file()])
                except Exception:
                    estimated_total = 100  # Fallback estimate
                
                # Create progress dialog
                progress_dialog = self._loading_manager.create_progress_dialog(self.main_window,
                    estimated_total,
                    f"Loading files from {source_name}..."
                )
                progress_dialog.setValue(0)
                QApplication.processEvents()
                
                # Track if we've actually started loading files (to avoid false cancellation on dialog creation)
                loading_started = [False]
                
                # Create progress callback
                def progress_callback(current: int, total: int, filename: str) -> None:
                    # Mark that loading has started once we get a real progress update with a filename
                    if current > 0 and filename:
                        loading_started[0] = True
                    
                    # Update progress dialog
                    if self._loading_manager.get_dialog():
                        # Update maximum if total changed
                        if total > self._loading_manager.get_dialog().maximum():
                            self._loading_manager.get_dialog().setMaximum(total)
                        self._loading_manager.get_dialog().setValue(current)
                        if filename:
                            self._loading_manager.get_dialog().setLabelText(f"Loading file {current}/{total}: {filename}...")
                        else:
                            self._loading_manager.get_dialog().setLabelText(f"Loaded {current} file(s). Organizing into studies/series...")
                        
                        # Manually check if Cancel button was clicked (only after loading has actually started)
                        # This prevents false cancellation when dialog is first shown
                        if not self._loading_manager.is_cancelled() and loading_started[0] and self._loading_manager.was_dialog_cancelled():
                            self._loading_manager.on_cancel_loading()
                
                # Check for explicit user cancellation
                if self._loading_manager.is_cancelled():
                    # Already handled by _on_cancel_loading
                    pass
                
                QApplication.processEvents()
                
                datasets = self.dicom_loader.load_directory(file_path, recursive=True, progress_callback=progress_callback)
                
                # Close progress dialog
                self._loading_manager.close_progress_dialog()
                
                # Check for cancellation (use explicit user cancellation flag)
                was_cancelled = self._loading_manager.is_cancelled()
                if was_cancelled:
                    num_loaded = len(datasets) if datasets else 0
                    if num_loaded > 0:
                        # Show cancellation message but keep partial data
                        self.update_status_callback(f"Loading cancelled. {num_loaded} file(s) loaded successfully.")
                        # Continue with organization and display of partial data
                    else:
                        # No files loaded, return None
                        self.update_status_callback("Loading cancelled.")
                        self.dicom_loader.reset_cancellation()
                        return None, None
                
                if not datasets:
                    # Check if there were specific errors
                    failed = self.dicom_loader.get_failed_files()
                    if failed:
                        error_msg = f"No DICOM files found in folder.\n\n{len(failed)} file(s) could not be loaded."
                    else:
                        error_msg = "No DICOM files found in folder."
                    
                    self.file_dialog.show_error(
                        self.main_window,
                        "Error",
                        error_msg
                    )
                    return None, None
                
                # Check if we have a large number of datasets and suggest memory management
                if len(datasets) > 100:
                    # Force garbage collection before expensive organize step
                    import time
                    gc_start = time.time()
                    gc.collect()
                    gc_time = time.time() - gc_start
                    # print(f"[ORGANIZE DEBUG] Pre-organize GC: {gc_time:.3f}s")
                    QApplication.processEvents()
                
                # Merge into existing organizer state (additive)
                # Extract file paths from datasets for path-based dedup
                folder_file_paths = [getattr(ds, 'filename', None) for ds in datasets]
                try:
                    import time
                    organize_start = time.time()
                    # print(f"[ORGANIZE DEBUG] Starting merge_batch of {len(datasets)} datasets...")
                    merge_result = self.dicom_organizer.merge_batch(datasets, folder_file_paths, source_dir)
                    organize_time = time.time() - organize_start
                    # print(f"[ORGANIZE DEBUG] merge_batch completed in {organize_time:.2f}s")
                except MemoryError as e:
                    self.file_dialog.show_error(
                        self.main_window,
                        "Memory Error",
                        f"Out of memory while organizing DICOM files. "
                        f"Try closing other applications or loading fewer files.\n\nError: {str(e)}"
                    )
                    return None, None
                except Exception as e:
                    self.file_dialog.show_error(
                        self.main_window,
                        "Error",
                        f"Error organizing DICOM files: {str(e)}"
                    )
                    return None, None
                
                # Update UI with additive load result
                try:
                    self.load_first_slice_callback(merge_result)
                except MemoryError as e:
                    self.file_dialog.show_error(
                        self.main_window,
                        "Memory Error",
                        f"Out of memory while displaying image. "
                        f"Try closing other applications.\n\nError: {str(e)}"
                    )
                    return None, None
                except Exception as e:
                    self.file_dialog.show_error(
                        self.main_window,
                        "Error",
                        f"Error displaying first slice: {str(e)}"
                    )
                    return None, None
                
                # Format and display final status (batch-only counts + processed/non-DICOM/duplicate)
                num_studies, num_series, num_files = self._batch_counts_from_merge_result(merge_result)
                extension_skipped = self.dicom_loader.get_extension_skipped_count()
                num_processed = self.dicom_loader.get_attempted_file_count() + extension_skipped
                non_dicom_count = len(self.dicom_loader.get_failed_files())
                duplicate_count = merge_result.skipped_file_count
                final_status = self._format_final_status(
                    num_studies, num_series, num_files, source_name,
                    num_processed=num_processed,
                    non_dicom_count=non_dicom_count,
                    duplicate_count=duplicate_count,
                    extension_skipped_count=extension_skipped,
                )
                self.update_status_callback(final_status)
                QApplication.processEvents()
                
                # Reset cancellation flag
                self.dicom_loader.reset_cancellation()
                
                return datasets, self.dicom_organizer.studies
                
            except MemoryError as e:
                self._loading_manager.close_progress_dialog()
                self.dicom_loader.reset_cancellation()
                self.file_dialog.show_error(
                    self.main_window,
                    "Memory Error",
                    f"Out of memory while loading folder. "
                    f"Try closing other applications or use a system with more memory.\n\nError: {str(e)}"
                )
                return None, None
            except Exception as e:
                self._loading_manager.close_progress_dialog()
                self.dicom_loader.reset_cancellation()
                error_type = type(e).__name__
                error_msg = f"Error loading folder: {str(e)}"
                if error_type not in error_msg:
                    error_msg = f"{error_type}: {error_msg}"
                self.file_dialog.show_error(
                    self.main_window,
                    "Error",
                    error_msg
                )
                return None, None
    
    def open_paths(self, paths: list[str]) -> tuple[list, dict]:
        """
        Handle open files/folders from drag-and-drop or direct paths.
        
        Args:
            paths: List of file or folder paths to open
            
        Returns:
            Tuple of (datasets list, studies dict) or (None, None) if cancelled/error
        """
        if not paths:
            return None, None
        
        # Separate files and folders
        files = []
        folders = []
        
        for path in paths:
            if not os.path.exists(path):
                continue
            if os.path.isfile(path):
                files.append(path)
            elif os.path.isdir(path):
                folders.append(path)
        
        # Priority: process folders first (if any), then files
        if folders:
            # Process first folder (prioritize folders)
            folder_path = folders[0]
            
            # Add folder to recent files
            self.config_manager.add_recent_file(folder_path)
            self.main_window.update_recent_menu()
            
            # Source directory for dedup/disambiguation
            source_dir = folder_path
            
            # Format source name for status display
            source_name = os.path.basename(folder_path)
            
            # Check for large files in folder before loading
            try:
                from pathlib import Path
                folder_path_obj = Path(folder_path)
                file_paths = [str(p) for p in folder_path_obj.rglob('*') if p.is_file()]
                if file_paths:
                    self._check_large_files(file_paths)
            except Exception:
                # If we can't check files, continue without warning
                pass
            
            try:
                # Reset cancellation flags
                self._loading_manager.reset()
                self.dicom_loader.reset_cancellation()
                
                # Estimate total files for progress dialog
                try:
                    from pathlib import Path
                    folder_path_obj = Path(folder_path)
                    estimated_total = len([str(p) for p in folder_path_obj.rglob('*') if p.is_file()])
                except Exception:
                    estimated_total = 100  # Fallback estimate
                
                # Create progress dialog
                progress_dialog = self._loading_manager.create_progress_dialog(self.main_window,
                    estimated_total,
                    f"Loading files from {source_name}..."
                )
                progress_dialog.setValue(0)
                QApplication.processEvents()
                
                # Track if we've actually started loading files (to avoid false cancellation on dialog creation)
                loading_started = [False]
                
                # Create progress callback
                def progress_callback(current: int, total: int, filename: str) -> None:
                    # Mark that loading has started once we get a real progress update with a filename
                    if current > 0 and filename:
                        loading_started[0] = True
                    
                    # Update progress dialog
                    if self._loading_manager.get_dialog():
                        # Update maximum if total changed
                        if total > self._loading_manager.get_dialog().maximum():
                            self._loading_manager.get_dialog().setMaximum(total)
                        self._loading_manager.get_dialog().setValue(current)
                        if filename:
                            self._loading_manager.get_dialog().setLabelText(f"Loading file {current}/{total}: {filename}...")
                        else:
                            self._loading_manager.get_dialog().setLabelText(f"Loaded {current} file(s). Organizing into studies/series...")
                        
                        # Manually check if Cancel button was clicked (only after loading has actually started)
                        # This prevents false cancellation when dialog is first shown
                        if not self._loading_manager.is_cancelled() and loading_started[0] and self._loading_manager.was_dialog_cancelled():
                            self._loading_manager.on_cancel_loading()
                
                # Check for explicit user cancellation
                if self._loading_manager.is_cancelled():
                    # Already handled by _on_cancel_loading
                    pass
                
                QApplication.processEvents()
                
                # Load folder (recursive)
                datasets = self.dicom_loader.load_directory(folder_path, recursive=True, progress_callback=progress_callback)
                
                # Close progress dialog
                self._loading_manager.close_progress_dialog()
                
                # Check for cancellation (use explicit user cancellation flag)
                was_cancelled = self._loading_manager.is_cancelled()
                if was_cancelled:
                    num_loaded = len(datasets) if datasets else 0
                    if num_loaded > 0:
                        # Show cancellation message but keep partial data
                        self.update_status_callback(f"Loading cancelled. {num_loaded} file(s) loaded successfully.")
                        # Continue with organization and display of partial data
                    else:
                        # No files loaded, return None
                        self.update_status_callback("Loading cancelled.")
                        self.dicom_loader.reset_cancellation()
                        return None, None
                
                if not datasets:
                    # Check if there were specific errors
                    failed = self.dicom_loader.get_failed_files()
                    if failed:
                        error_msg = f"No DICOM files found in folder.\n\n{len(failed)} file(s) could not be loaded."
                    else:
                        error_msg = "No DICOM files found in folder."
                    
                    self.file_dialog.show_error(
                        self.main_window,
                        "Error",
                        error_msg
                    )
                    return None, None
                
                # Show warnings
                failed = self.dicom_loader.get_failed_files()
                if failed:
                    warning_msg = f"Warning: {len(failed)} file(s) could not be loaded."
                    self.file_dialog.show_warning(self.main_window, "Loading Warnings", warning_msg)
                
                # Merge into existing organizer state (additive)
                # Extract file paths from datasets for path-based dedup
                folder_file_paths = [getattr(ds, 'filename', None) for ds in datasets]
                try:
                    merge_result = self.dicom_organizer.merge_batch(datasets, folder_file_paths, source_dir)
                except MemoryError as e:
                    self.file_dialog.show_error(
                        self.main_window,
                        "Memory Error",
                        f"Out of memory while organizing DICOM files. "
                        f"Try closing other applications or loading fewer files.\n\nError: {str(e)}"
                    )
                    return None, None
                except Exception as e:
                    self.file_dialog.show_error(
                        self.main_window,
                        "Error",
                        f"Error organizing DICOM files: {str(e)}"
                    )
                    return None, None
                
                # Update UI with additive load result
                try:
                    self.load_first_slice_callback(merge_result)
                except MemoryError as e:
                    self.file_dialog.show_error(
                        self.main_window,
                        "Memory Error",
                        f"Out of memory while displaying image. "
                        f"Try closing other applications.\n\nError: {str(e)}"
                    )
                    return None, None
                except Exception as e:
                    self.file_dialog.show_error(
                        self.main_window,
                        "Error",
                        f"Error displaying first slice: {str(e)}"
                    )
                    return None, None
                
                # Format and display final status (batch-only counts + processed/non-DICOM/duplicate)
                num_studies, num_series, num_files = self._batch_counts_from_merge_result(merge_result)
                extension_skipped = self.dicom_loader.get_extension_skipped_count()
                num_processed = self.dicom_loader.get_attempted_file_count() + extension_skipped
                non_dicom_count = len(self.dicom_loader.get_failed_files())
                duplicate_count = merge_result.skipped_file_count
                final_status = self._format_final_status(
                    num_studies, num_series, num_files, source_name,
                    num_processed=num_processed,
                    non_dicom_count=non_dicom_count,
                    duplicate_count=duplicate_count,
                    extension_skipped_count=extension_skipped,
                )
                self.update_status_callback(final_status)
                QApplication.processEvents()
                
                # Reset cancellation flag
                self.dicom_loader.reset_cancellation()
                
                return datasets, self.dicom_organizer.studies
            
            except SystemExit:
                self._loading_manager.close_progress_dialog()
                self.dicom_loader.reset_cancellation()
                raise  # Don't catch system exit
            except KeyboardInterrupt:
                self._loading_manager.close_progress_dialog()
                self.dicom_loader.reset_cancellation()
                raise  # Don't catch Ctrl+C
            except MemoryError as e:
                self._loading_manager.close_progress_dialog()
                self.dicom_loader.reset_cancellation()
                self.file_dialog.show_error(
                    self.main_window,
                    "Memory Error",
                    f"Out of memory while loading folder. "
                    f"Try closing other applications or use a system with more memory.\n\nError: {str(e)}"
                )
                return None, None
            except BaseException as e:
                self._loading_manager.close_progress_dialog()
                self.dicom_loader.reset_cancellation()
                # Catch everything else including C extension errors that make it to Python
                error_type = type(e).__name__
                error_msg = f"A critical error occurred during folder loading.\n\n"
                error_msg += f"Error: {error_type}: {str(e)}\n\n"
                error_msg += f"This may be due to corrupted or unsupported DICOM files."
                
                print(f"Critical error in open_paths (folder): {error_type}: {e}")
                import traceback
                traceback.print_exc()
                
                self.file_dialog.show_error(
                    self.main_window,
                    "Critical Error",
                    error_msg
                )
                return None, None
        
        elif files:
            # Skip known non-DICOM extensions
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

            # Process all files together
            # Add first file to recent files (representing this file selection)
            if files:
                self.config_manager.add_recent_file(files[0])
                self.main_window.update_recent_menu()

            # Source directory for dedup/disambiguation (parent of first file)
            source_dir = os.path.dirname(os.path.abspath(files[0])) if files else ""

            # Format source name for status display
            source_name = self._format_source_name(files)

            # Check for large files and show warning
            self._check_large_files(files)

            try:
                # Reset cancellation flags
                self._loading_manager.reset()
                self.dicom_loader.reset_cancellation()

                # Create progress dialog
                progress_dialog = self._loading_manager.create_progress_dialog(self.main_window,
                    len(files),
                    f"Loading files from {source_name}..."
                )
                progress_dialog.setValue(0)
                QApplication.processEvents()
                
                # Track if we've actually started loading files (to avoid false cancellation on dialog creation)
                loading_started = [False]
                
                # Create progress callback
                def progress_callback(current: int, total: int, filename: str) -> None:
                    # Mark that loading has started once we get a real progress update with a filename
                    if current > 0 and filename:
                        loading_started[0] = True
                    
                    # Update progress dialog
                    if self._loading_manager.get_dialog():
                        self._loading_manager.get_dialog().setValue(current)
                        if filename:
                            if filename.startswith("Deferring"):
                                self._loading_manager.get_dialog().setLabelText(filename)
                            else:
                                self._loading_manager.get_dialog().setLabelText(f"Loading file {current}/{total}: {filename}...")
                        else:
                            self._loading_manager.get_dialog().setLabelText(f"Loaded {current} file(s). Organizing into studies/series...")
                        
                        # Manually check if Cancel button was clicked (only after loading has actually started)
                        # This prevents false cancellation when dialog is first shown
                        if not self._loading_manager.is_cancelled() and loading_started[0] and self._loading_manager.was_dialog_cancelled():
                            self._loading_manager.on_cancel_loading()
                    
                    # Check for explicit user cancellation
                    if self._loading_manager.is_cancelled():
                        # Already handled by _on_cancel_loading
                        pass
                        
                    QApplication.processEvents()
                
                # Load files
                datasets = self.dicom_loader.load_files(files, progress_callback=progress_callback)
                
                # Close progress dialog
                self._loading_manager.close_progress_dialog()
                
                # Check for cancellation (use explicit user cancellation flag)
                was_cancelled = self._loading_manager.is_cancelled()
                if was_cancelled:
                    num_loaded = len(datasets) if datasets else 0
                    if num_loaded > 0:
                        # Show cancellation message but keep partial data
                        self.update_status_callback(f"Loading cancelled. {num_loaded} file(s) loaded successfully.")
                        # Continue with organization and display of partial data
                    else:
                        # No files loaded, return None
                        self.update_status_callback("Loading cancelled.")
                        self.dicom_loader.reset_cancellation()
                        return None, None
                
                if not datasets:
                    # Check if there were specific errors
                    failed = self.dicom_loader.get_failed_files()
                    if failed:
                        error_msg = "No DICOM files could be loaded.\n\nErrors:\n"
                        for path, error in failed[:5]:  # Show first 5
                            error_msg += f"\n{os.path.basename(path)}: {error}"
                        if len(failed) > 5:
                            error_msg += f"\n... and {len(failed) - 5} more"
                    else:
                        error_msg = "No DICOM files could be loaded."
                    
                    self.file_dialog.show_error(
                        self.main_window,
                        "Error",
                        error_msg
                    )
                    return None, None
                
                # Validate datasets before processing
                # Multi-frame detection kept for potential future use, but no filtering
                validated_datasets = []
                validated_paths = []
                
                for ds, path in zip(datasets, files):
                    validated_datasets.append(ds)
                    validated_paths.append(path)
                
                # Update datasets and paths to validated ones
                datasets = validated_datasets
                files = validated_paths
                
                if not datasets:
                    self.file_dialog.show_error(
                        self.main_window,
                        "No Valid Files",
                        "All selected files were skipped due to safety checks. No files to display."
                    )
                    return None, None
                
                # Show warnings for failed files
                failed = self.dicom_loader.get_failed_files()
                if failed:
                    warning_msg = f"Warning: {len(failed)} file(s) could not be loaded:\n"
                    for path, error in failed[:5]:  # Show first 5
                        warning_msg += f"\n{os.path.basename(path)}: {error}"
                    if len(failed) > 5:
                        warning_msg += f"\n... and {len(failed) - 5} more"
                    
                    self.file_dialog.show_warning(self.main_window, "Loading Warnings", warning_msg)
                
                # Check if we have a large number of datasets and suggest memory management
                if len(datasets) > 100:
                    # Force garbage collection before expensive organize step
                    gc.collect()
                    QApplication.processEvents()
                
                # Merge into existing organizer state (additive)
                try:
                    merge_result = self.dicom_organizer.merge_batch(datasets, files, source_dir)
                except MemoryError as e:
                    self.file_dialog.show_error(
                        self.main_window,
                        "Memory Error",
                        f"Out of memory while organizing DICOM files. "
                        f"Try closing other applications or loading fewer files.\n\nError: {str(e)}"
                    )
                    return None, None
                except Exception as e:
                    self.file_dialog.show_error(
                        self.main_window,
                        "Error",
                        f"Error organizing DICOM files: {str(e)}"
                    )
                    return None, None
                
                # Update UI with additive load result
                try:
                    self.load_first_slice_callback(merge_result)
                except MemoryError as e:
                    self.file_dialog.show_error(
                        self.main_window,
                        "Memory Error",
                        f"Out of memory while displaying image. "
                        f"Try closing other applications.\n\nError: {str(e)}"
                    )
                    return None, None
                except Exception as e:
                    self.file_dialog.show_error(
                        self.main_window,
                        "Error",
                        f"Error displaying first slice: {str(e)}"
                    )
                    return None, None
                
                # Format and display final status (batch-only counts + processed/non-DICOM/duplicate)
                num_studies, num_series, num_files = self._batch_counts_from_merge_result(merge_result)
                extension_skipped = self.dicom_loader.get_extension_skipped_count()
                num_processed = self.dicom_loader.get_attempted_file_count() + extension_skipped
                non_dicom_count = len(self.dicom_loader.get_failed_files())
                duplicate_count = merge_result.skipped_file_count
                final_status = self._format_final_status(
                    num_studies, num_series, num_files, source_name,
                    num_processed=num_processed,
                    non_dicom_count=non_dicom_count,
                    duplicate_count=duplicate_count,
                    extension_skipped_count=extension_skipped,
                )

                # Check for compression errors and append guidance if needed
                failed = self.dicom_loader.get_failed_files()
                compression_errors = [f for f in failed if "Compressed DICOM" in f[1] or "pylibjpeg" in f[1].lower()]
                if compression_errors:
                    compression_count = len(compression_errors)
                    final_status += f". {compression_count} compressed file(s) require pylibjpeg: pip install pylibjpeg pyjpegls"
                
                self.update_status_callback(final_status)
                QApplication.processEvents()
                
                # Reset cancellation flag
                self.dicom_loader.reset_cancellation()
                
                return datasets, self.dicom_organizer.studies
            
            except SystemExit:
                self._loading_manager.close_progress_dialog()
                self.dicom_loader.reset_cancellation()
                raise  # Don't catch system exit
            except KeyboardInterrupt:
                self._loading_manager.close_progress_dialog()
                self.dicom_loader.reset_cancellation()
                raise  # Don't catch Ctrl+C
            except MemoryError as e:
                self._loading_manager.close_progress_dialog()
                self.dicom_loader.reset_cancellation()
                self.file_dialog.show_error(
                    self.main_window,
                    "Memory Error",
                    f"Out of memory while loading files. "
                    f"Try closing other applications or use a system with more memory.\n\nError: {str(e)}"
                )
                return None, None
            except BaseException as e:
                self._loading_manager.close_progress_dialog()
                self.dicom_loader.reset_cancellation()
                # Catch everything else including C extension errors that make it to Python
                error_type = type(e).__name__
                error_msg = f"A critical error occurred during file loading.\n\n"
                error_msg += f"Error: {error_type}: {str(e)}\n\n"
                error_msg += f"This may be due to corrupted or unsupported DICOM files."
                
                print(f"Critical error in open_paths (files): {error_type}: {e}")
                import traceback
                traceback.print_exc()
                
                self.file_dialog.show_error(
                    self.main_window,
                    "Critical Error",
                    error_msg
                )
                return None, None
        
        # No valid files or folders
        return None, None
    
    def _get_first_study_series_by_dicom(self, studies: dict) -> Optional[Tuple[str, str]]:
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

    def load_first_slice(self, studies: dict) -> dict:
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

