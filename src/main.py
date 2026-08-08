"""
DICOM Viewer V3 - Main Application Entry Point

This module is the main entry point for the DICOM viewer application.
It initializes the application, creates the main window, and sets up
the application event loop.

Inputs:
    - Command line arguments (optional)
    
Outputs:
    - Running DICOM viewer application
    
Requirements:
    - PySide6 for application framework
    - pydicom for DICOM file handling
    - PIL/Pillow for image processing
    - numpy for array operations
    - openpyxl for Excel export (tag export feature)
    - All other application modules
"""

import time as _time

_PERF_STARTUP_T0 = _time.perf_counter()

import logging
import sys
from collections.abc import Callable
from typing import cast

if "--decoder-fixture-smoke" in sys.argv or "--decoder-fixture-child" in sys.argv:
    from core.decoder_fixture_smoke import main as _decoder_fixture_smoke_main

    raise SystemExit(_decoder_fixture_smoke_main(sys.argv[1:]))

from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QMessageBox,
)

from gui.cine_player import CinePlayer
from gui.window_slot_map_widget import WindowSlotMapPopupDialog, WindowSlotMapWidget
from utils.debug_flags import PERF_LOG
from utils.log_sanitizer import sanitized_format_exc
from utils.privacy import (
    install_privacy_filter,
    install_privacy_streams,
    log_structural_event,
)

_logger = logging.getLogger(__name__)

# Import handler classes
from core.cine_app_facade import CineAppFacade
from core.customization_handlers import CustomizationHandlers
from core.privacy_controller import PrivacyController
from core.session_reset_controller import (
    finalize_for_application_quit as session_reset_finalize_for_application_quit,
)

# Import slice sync components
from core.study_index import LocalStudyIndexService
from gui.dialog_coordinator import DialogCoordinator
from gui.dialogs.disclaimer_dialog import DisclaimerDialog
from gui.file_operations_handler import FileOperationsHandler
from gui.file_series_loading_coordinator import (
    FileSeriesLoadingCoordinator,
)

# Import fusion components (FusionProcessor lazy-imported at point of use)
from gui.keyboard_event_handler import KeyboardEventHandler
from gui.main_app_key_event_filter import (
    dispatch_app_key_event,
)
from gui.mouse_mode_handler import MouseModeHandler
from gui.tag_export_union_host import TagExportUnionHost
from main_app_display_settings import DisplayProjectionMixin, SettingsLayoutMixin
from main_app_initialization import InitializationMixin
from main_app_subwindow_management import MPRNavigationMixin, SubwindowManagementMixin
from main_app_tag_roi import ROIWorkflowMixin, TagEditingMixin
from main_app_ui_and_files import FileOperationsMixin, UIHandlersMixin
from qa.worker import QAAnalysisWorker, QABatchWorker, QACTBatchWorker

_PERF_IMPORTS_DONE = _time.perf_counter()


class DICOMViewerApp(
    QObject,
    InitializationMixin,
    SubwindowManagementMixin,
    MPRNavigationMixin,
    UIHandlersMixin,
    FileOperationsMixin,
    DisplayProjectionMixin,
    SettingsLayoutMixin,
    TagEditingMixin,
    ROIWorkflowMixin,
):
    """
    Main application class for DICOM Viewer.

    Coordinates all components and handles application logic.
    """

    #: Emitted when background tag-export union finishes (generation, merged dict).
    tag_export_union_ready = Signal(int, object)

    app: QApplication

    # Set in __init__ (real objects in _initialize_handlers); placeholders use cast(object, None)
    # so the checker accepts definite assignment before coordinator construction runs.
    _file_series_coordinator: FileSeriesLoadingCoordinator
    file_operations_handler: FileOperationsHandler
    dialog_coordinator: DialogCoordinator
    _privacy_controller: PrivacyController
    _customization_handlers: CustomizationHandlers
    mouse_mode_handler: MouseModeHandler
    cine_player: CinePlayer
    cine_app_facade: CineAppFacade
    keyboard_event_handler: KeyboardEventHandler

    # Lazily created UI / background workers (Optional avoids Pyright
    # reportUninitializedInstanceVariable on first use).
    _window_slot_map_dialog: WindowSlotMapPopupDialog | None = None
    _window_slot_map_widget_popup: WindowSlotMapWidget | None = None
    _qa_worker: QAAnalysisWorker | None = None
    _qa_batch_worker: QABatchWorker | None = None
    _mri_compare_result_dialog: QDialog | None = None
    _qa_ct_batch_worker: QACTBatchWorker | None = None
    _ct_batch_result_dialog: QDialog | None = None
    _histogram_wl_update_timer: QTimer | None = None
    _histogram_update_timer: QTimer | None = None
    study_index_service: LocalStudyIndexService
    tag_export_union_host: TagExportUnionHost

    def __init__(self):
        """
        Initialize the DICOM Viewer application.

        Initialization order is significant and must be preserved:

        1. _init_core_managers()
           QApplication + all data managers (config, DICOM, history, undo/redo).
           No widgets are created yet; Qt must exist first.

        2. _init_main_window_and_layout()
           MainWindow, FileDialog, and MultiWindowLayout.
           Requires Step 1: widgets need config_manager and QApplication.

        3. _init_controllers_and_tools()
           MetadataController and ROIMeasurementController.
           Requires Step 2: theme must be applied before metadata panel is shown.

        4. _init_view_widgets()
           Remaining shared view widgets (navigators, fusion, overlays, etc.).
           Requires Step 1 for config; Step 3 for privacy flag propagation.

        5. _post_init_subwindows_and_handlers()
           UI assembly, per-subwindow manager creation, handler init, signal
           wiring, and final interaction setup.
           Must be last: all managers, widgets, and controllers must be ready.
        """
        # Initialize QObject first (must be the very first statement)
        super().__init__()

        # Typed placeholders; real instances are assigned in _initialize_handlers()
        # (invoked from __init__ via _post_init_subwindows_and_handlers).
        self._file_series_coordinator = cast(
            FileSeriesLoadingCoordinator, cast(object, None)
        )
        self.file_operations_handler = cast(FileOperationsHandler, cast(object, None))
        self.dialog_coordinator = cast(DialogCoordinator, cast(object, None))
        self._privacy_controller = cast(PrivacyController, cast(object, None))
        self._customization_handlers = cast(CustomizationHandlers, cast(object, None))
        self.mouse_mode_handler = cast(MouseModeHandler, cast(object, None))
        self.cine_player = cast(CinePlayer, cast(object, None))
        self.cine_app_facade = cast(CineAppFacade, cast(object, None))
        self.keyboard_event_handler = cast(KeyboardEventHandler, cast(object, None))
        self.study_index_service = cast(LocalStudyIndexService, cast(object, None))

        # Step 1 – Core application and data managers
        self._init_core_managers()

        # Step 2 – Main window, file dialog, and layout skeleton
        self._init_main_window_and_layout()

        # Step 3 – Feature controllers (MetadataController, ROIMeasurementController)
        self._init_controllers_and_tools()

        # Step 4 – Remaining shared view widgets
        self._init_view_widgets()

        # Step 5 – Subwindow lifecycle, handlers, signals, and post-init interaction
        self._post_init_subwindows_and_handlers()

    def _log_startup_perf(self) -> None:
        """Emit startup timing metrics when ``DICOM_PERF_LOG=1`` (see ``PERF_LOG``)."""
        if not PERF_LOG:
            return
        log_structural_event(
            _logger,
            logging.INFO,
            "performance.startup",
            metrics={
                "import_ms": (_PERF_IMPORTS_DONE - _PERF_STARTUP_T0) * 1000,
                "app_init_ms": (_time.perf_counter() - _PERF_IMPORTS_DONE) * 1000,
                "total_ms": (_time.perf_counter() - _PERF_STARTUP_T0) * 1000,
            },
        )

    def _on_app_about_to_quit(self) -> None:
        """Reset view–slot mapping and dissolve slice sync groups when the application is exiting."""
        session_reset_finalize_for_application_quit(self)

    def _restart_single_shot_timer(
        self,
        attr_name: str,
        interval_ms: int,
        on_timeout: Callable[..., None],
    ) -> None:
        """Create (once), stop, and restart a single-shot QTimer with the given interval and slot."""
        timer = getattr(self, attr_name, None)
        if timer is None:
            timer = QTimer(self)
            timer.setSingleShot(True)
            timer.setInterval(interval_ms)
            timer.timeout.connect(on_timeout)
            setattr(self, attr_name, timer)
        timer.stop()
        timer.start()

    def eventFilter(self, obj, event) -> bool:
        """Filter key events: layout shortcut focus gating and ``KeyboardEventHandler`` (see ``main_app_key_event_filter``)."""
        dispatched = dispatch_app_key_event(self, event)
        if dispatched is not None:
            return dispatched
        return super().eventFilter(obj, event)

    def run(self) -> int:
        """
        Run the application.

        Returns:
            Exit code
        """
        # Show disclaimer dialog before showing main window
        if not DisclaimerDialog.show_disclaimer(self.config_manager, self.main_window, force_show=False):
            # User cancelled, exit application
            return 0

        # Show window maximized (full-screen) and bring it to the foreground.
        # activateWindow() + raise_() ensure the window appears on top of other
        # open applications regardless of how the process was launched.
        self.main_window.showMaximized()
        self.main_window.activateWindow()
        self.main_window.raise_()

        # Set keyboard focus after window is shown
        # Use QTimer to ensure window is fully visible before setting focus
        QTimer.singleShot(100, self._set_initial_keyboard_focus)
        QTimer.singleShot(800, self._warn_if_privacy_off)

        return self.app.exec()

    def _set_initial_keyboard_focus(self) -> None:
        """Set keyboard focus to the focused subwindow after window is shown."""
        if self.image_viewer:
            self.image_viewer.setFocus()

    def _warn_if_privacy_off(self) -> None:
        """Show a warning toast on startup when privacy mode is disabled."""
        if not self.config_manager.get_privacy_view():
            self.main_window.show_toast_message(
                "Privacy mode is OFF — patient identifiers are visible",
                timeout_ms=7000,
                severity="warning",
            )

def exception_hook(exctype, value, tb):
    """Global exception handler to catch unhandled exceptions."""
    _ = (value, tb)
    log_structural_event(
        _logger,
        logging.CRITICAL,
        "application.unhandled",
        error=exctype,
    )

    # Try to show error dialog if QApplication exists
    try:
        if QApplication.instance():
            QMessageBox.critical(
                None,
                "Fatal Error",
                "An unexpected error occurred. Details were withheld to protect "
                "private data. The application may be unstable.",
            )
    except Exception:
        pass  # If Qt is not available, just print


def install_application_privacy_boundaries() -> None:
    """Install idempotent fail-closed process boundaries for application startup.

    Keeping this explicit makes importing :mod:`main` inert for tests and
    embedded callers while ensuring the executable entry point protects logs
    and process streams before application construction can load user data.
    """

    root_logger = logging.getLogger()
    if not root_logger.handlers:
        logging.basicConfig(
            level=logging.INFO if PERF_LOG else logging.WARNING,
            format="%(message)s",
        )
    install_privacy_filter(root_logger)
    install_privacy_streams()


def main():
    """Main entry point."""
    install_application_privacy_boundaries()

    # Install global exception hook
    sys.excepthook = exception_hook

    try:
        app = DICOMViewerApp()
        return app.run()
    except Exception as e:
        log_structural_event(
            _logger,
            logging.CRITICAL,
            "application.startup",
            error=e,
        )
        _logger.debug("%s", sanitized_format_exc())
        return 1


if __name__ == "__main__":
    sys.exit(main())
