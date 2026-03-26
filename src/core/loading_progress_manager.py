"""
Loading Progress Manager

Manages the animated loading-dots timer, progress dialog, and cancellation
state that are shared by all file-open operations (open_files, open_folder,
open_recent_file, open_paths).

Inputs:
    - update_status_callback: Callable[[str], None]
        Posts messages to the main-window status bar.
    - cancel_loader_callback: Optional[Callable[[], None]]
        Called when the user cancels a load (e.g. dicom_loader.cancel).

Outputs:
    - Animated "Loading..." status bar messages while files are loading.
    - A QProgressDialog with Cancel button / Escape-key support.
    - A boolean is_cancelled flag that open methods can query.

Requirements:
    - PySide6 (QTimer, QProgressDialog, QObject, QEvent)
"""

from typing import Callable, Optional

from PySide6.QtCore import QEvent, QObject, Qt, QTimer
from PySide6.QtWidgets import QApplication, QProgressDialog, QWidget


class ProgressDialogEventFilter(QObject):
    """
    Event filter for a QProgressDialog.

    Intercepts the Escape key so that pressing Escape triggers the application's
    own cancel callback instead of relying on QDialog's built-in close behaviour,
    which can fire the ``canceled`` signal unexpectedly in some compiled builds.
    """

    def __init__(self, cancel_callback: Callable[[], None]) -> None:
        """
        Args:
            cancel_callback: Zero-argument callable invoked when Escape is pressed.
        """
        super().__init__()
        self._cancel_callback = cancel_callback

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:  # type: ignore[override]
        """Intercept Escape key presses and forward to the cancel callback."""
        if event.type() == QEvent.Type.KeyPress:
            if event.key() == Qt.Key.Key_Escape:  # pyright: ignore[reportAttributeAccessIssue]
                self._cancel_callback()
                return True
        return False


class LoadingProgressManager:
    """
    Centralises all loading-progress infrastructure used by FileOperationsHandler.

    Owns:
        - Animated loading-dots QTimer and state.
        - QProgressDialog and its ProgressDialogEventFilter.
        - User-cancellation flag.

    FileOperationsHandler creates **one** instance in its ``__init__`` and calls
    ``reset()`` at the start of each file-open operation.

    Public API
    ----------
    start_animated_loading(base_message)
        Begin the animated "Loading..." dots in the status bar.
    stop_animated_loading()
        Stop the dots animation.
    create_progress_dialog(parent, total_files, message) -> QProgressDialog
        Build and show a new progress dialog (closes any existing one first).
    close_progress_dialog()
        Safely close and clean up the progress dialog.
    on_cancel_loading()
        Mark the load as cancelled; stop animation; invoke loader cancel.
    is_cancelled() -> bool
        True if the user has cancelled the current operation.
    was_dialog_cancelled() -> bool
        True if the progress dialog's Cancel button was clicked.
    get_dialog() -> Optional[QProgressDialog]
        Return the current progress dialog (may be None).
    reset()
        Clear all state ready for the next operation.
    """

    def __init__(
        self,
        update_status_callback: Callable[[str], None],
        cancel_loader_callback: Optional[Callable[[], None]] = None,
    ) -> None:
        """
        Args:
            update_status_callback: Posts status-bar messages.
            cancel_loader_callback: Called inside on_cancel_loading to cancel the
                underlying loader (e.g. ``dicom_loader.cancel``).  May be None.
        """
        self._update_status_callback = update_status_callback
        self._cancel_loader_callback = cancel_loader_callback

        # Animated dots state
        self._loading_timer: Optional[QTimer] = None
        self._loading_base_message: str = ""
        self._loading_dot_state: int = 0

        # Progress dialog state
        self._progress_dialog: Optional[QProgressDialog] = None
        self._progress_event_filter: Optional[ProgressDialogEventFilter] = None

        # Cancellation flag
        self._user_cancelled: bool = False

    # ------------------------------------------------------------------
    # Animated loading dots
    # ------------------------------------------------------------------

    def start_animated_loading(self, base_message: str) -> None:
        """
        Start the animated loading-dots status bar message.

        Stops any existing animation first, then immediately shows the first
        frame and starts a 500 ms repeating timer.

        Args:
            base_message: Text prefix; dots (``...``, ``..``, ``.``) are appended.
        """
        self.stop_animated_loading()
        self._loading_base_message = base_message
        self._loading_dot_state = 0

        def _update_dots() -> None:
            """Cycle through three dot counts and post to the status bar."""
            dots = ["...", "..", "."][self._loading_dot_state % 3]
            self._update_status_callback(f"{self._loading_base_message}{dots}")
            self._loading_dot_state += 1
            QApplication.processEvents()

        _update_dots()
        self._loading_timer = QTimer()
        self._loading_timer.timeout.connect(_update_dots)
        self._loading_timer.start(500)

    def stop_animated_loading(self) -> None:
        """Stop the animated loading-dots timer and reset related state."""
        if self._loading_timer is not None:
            self._loading_timer.stop()
            self._loading_timer = None
        self._loading_base_message = ""
        self._loading_dot_state = 0

    # ------------------------------------------------------------------
    # Progress dialog
    # ------------------------------------------------------------------

    def create_progress_dialog(
        self, parent: QWidget | None, total_files: int, message: str
    ) -> QProgressDialog:
        """
        Create and return a new QProgressDialog.

        Closes any existing dialog first.  The dialog is modal with no minimum
        display duration (shown immediately).  An event filter is installed to
        intercept the Escape key.

        Args:
            parent: Parent widget for the dialog.
            total_files: Maximum value for the progress bar (clamped to ≥ 1).
            message: Initial label text.

        Returns:
            The new QProgressDialog instance (also stored in ``self._progress_dialog``).
        """
        self.close_progress_dialog()

        if total_files <= 0:
            total_files = 1

        progress = QProgressDialog(message, "Cancel", 0, total_files, parent)
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(0)
        progress.setWindowTitle("Loading DICOM Files")

        # We intentionally do NOT connect progress.canceled to on_cancel_loading;
        # the signal can fire spuriously in compiled builds.  Instead, callers
        # check was_dialog_cancelled() inside their progress callback.
        self._progress_event_filter = ProgressDialogEventFilter(self.on_cancel_loading)
        progress.installEventFilter(self._progress_event_filter)

        self._progress_dialog = progress
        return progress

    def close_progress_dialog(self) -> None:
        """Safely close and clean up the current progress dialog."""
        if self._progress_dialog is not None:
            if self._progress_event_filter is not None:
                self._progress_dialog.removeEventFilter(self._progress_event_filter)
            self._progress_dialog.close()
            self._progress_dialog = None
            self._progress_event_filter = None

    def get_dialog(self) -> Optional[QProgressDialog]:
        """Return the active QProgressDialog, or None if none is open."""
        return self._progress_dialog

    # ------------------------------------------------------------------
    # Cancellation
    # ------------------------------------------------------------------

    def on_cancel_loading(self) -> None:
        """
        Handle a cancellation request.

        Sets the cancellation flag, invokes the loader cancel callback (if any),
        posts "Cancelling…" to the status bar, and stops the animation timer.
        """
        self._user_cancelled = True
        if self._cancel_loader_callback is not None:
            self._cancel_loader_callback()
        self._update_status_callback("Cancelling...")
        self.stop_animated_loading()

    def is_cancelled(self) -> bool:
        """Return True if the user has cancelled the current loading operation."""
        return self._user_cancelled

    def was_dialog_cancelled(self) -> bool:
        """Return True if the progress dialog's Cancel button has been clicked."""
        return (
            self._progress_dialog is not None
            and self._progress_dialog.wasCanceled()
        )

    # ------------------------------------------------------------------
    # Reset
    # ------------------------------------------------------------------

    def reset(self) -> None:
        """
        Reset all state ready for a new loading operation.

        Stops the animation timer, closes any open progress dialog, and clears
        the user-cancellation flag.
        """
        self._user_cancelled = False
        self.stop_animated_loading()
        self.close_progress_dialog()
