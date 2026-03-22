"""Rewrite file_operations_handler.py to use loading_pipeline."""
import ast
import pathlib

src_path = pathlib.Path("src/core/file_operations_handler.py")
src = src_path.read_text(encoding="utf-8")
lines = src.splitlines(keepends=True)

# 0-based: header → lines 0-35 (source lines 1-36, up to end of imports)
header = "".join(lines[:35])

# class definition + __init__ + _check_large_files: lines 36-131
class_def = "".join(lines[36:132])

# _get_first_study_series_by_dicom starts at source line 1669 → 0-based index 1668
tail = "".join(lines[1668:])

new_import = "from core.loading_pipeline import run_load_pipeline, format_source_name\n"

new_open_files = '''
    def open_files(self) -> tuple[list, dict]:
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
        )

'''

new_open_folder = '''
    def open_folder(self) -> tuple[list, dict]:
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
        )

'''

new_open_recent = '''
    def open_recent_file(self, file_path: str) -> tuple[list, dict]:
        """
        Handle open recent file/folder request.

        Args:
            file_path: Path to file or folder to open

        Returns:
            Tuple of (datasets list, studies dict) or (None, None) if cancelled/error
        """
        if not os.path.exists(file_path):
            self.file_dialog.show_error(
                self.main_window, "Error", f"File or folder not found:\\n{file_path}"
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
        )

'''

new_open_paths = '''
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
            )

        return None, None

'''

new_content = (
    header
    + new_import
    + "\n"
    + class_def
    + new_open_files
    + new_open_folder
    + new_open_recent
    + new_open_paths
    + tail
)

src_path.write_text(new_content, encoding="utf-8")

# Verify
ast.parse(new_content)
print("SYNTAX OK")
print(f"Lines: {len(new_content.splitlines())}")
