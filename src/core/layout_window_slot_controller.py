"""
Layout changes, subwindow manager wiring, and window-slot map UI.

Bodies moved from ``DICOMViewerApp`` for multi-window layout handling,
viewport signal connects, swap/expand, and the window-slot map popup.
``DICOMViewerApp`` keeps stable slot names as thin delegates.

Inputs:
    ``app``: ``DICOMViewerApp`` instance.

Outputs:
    Mutates layout, navigators, dialogs, and config (popup position).

Requirements:
    PySide6; ``app._subwindow_lifecycle_controller`` for delegated lifecycle work.
"""

from __future__ import annotations

# pyright: reportImportCycles=false

from typing import TYPE_CHECKING, Any, Dict

from PySide6.QtCore import QPoint, Qt, QTimer
from PySide6.QtGui import QCursor

from gui.image_viewer import ImageViewer
from gui.sub_window_container import SubWindowContainer
from gui.window_slot_map_widget import WindowSlotMapPopupDialog

if TYPE_CHECKING:  # pragma: no cover
    from main import DICOMViewerApp


def on_layout_changed(app: "DICOMViewerApp", layout_mode: str) -> None:
    """Handle layout mode change from multi-window layout."""
    app._subwindow_lifecycle_controller.on_layout_changed(layout_mode)
    QTimer.singleShot(0, app._slice_location_line_coordinator.refresh_all)
    refresh_window_slot_map_widgets(app)


def on_main_window_layout_changed(app: "DICOMViewerApp", layout_mode: str) -> None:
    """Handle layout mode change from main window menu."""
    app._subwindow_lifecycle_controller.on_main_window_layout_changed(layout_mode)
    QTimer.singleShot(0, app._slice_location_line_coordinator.refresh_all)


def capture_subwindow_view_states(app: "DICOMViewerApp") -> Dict[int, Dict[str, Any]]:
    """Capture view state for all subwindows before layout change."""
    return app._subwindow_lifecycle_controller.capture_subwindow_view_states()


def restore_subwindow_views(
    app: "DICOMViewerApp", view_states: Dict[int, Dict[str, Any]]
) -> None:
    """Restore subwindow views after layout change."""
    app._subwindow_lifecycle_controller.restore_subwindow_views(view_states)


def ensure_all_subwindows_have_managers(app: "DICOMViewerApp") -> None:
    """Ensure all visible subwindows have managers."""
    app._subwindow_lifecycle_controller.ensure_all_subwindows_have_managers()


def connect_all_subwindow_transform_signals(app: "DICOMViewerApp") -> None:
    """Connect transform/zoom signals for all subwindows."""
    app._subwindow_lifecycle_controller.connect_all_subwindow_transform_signals()


def connect_all_subwindow_context_menu_signals(app: "DICOMViewerApp") -> None:
    """Connect context menu signals for all subwindows."""
    app._subwindow_lifecycle_controller.connect_all_subwindow_context_menu_signals()


def on_layout_change_requested(app: "DICOMViewerApp", layout_mode: str) -> None:
    """Handle layout change request from image viewer context menu."""
    app._subwindow_lifecycle_controller.on_layout_change_requested(layout_mode)


def on_expand_to_1x1_requested(app: "DICOMViewerApp") -> None:
    """Handle double-click: expand to 1x1 or, if already in 1x1, revert to last used layout (or 2x2)."""
    sender = app.sender()
    if not isinstance(sender, SubWindowContainer):
        return
    if app.multi_window_layout.get_layout_mode() == "1x1":
        # Already in 1x1: revert to last layout before 1x1 (or 2x2)
        app.multi_window_layout.set_layout(app.multi_window_layout.get_revert_layout())
    else:
        app.multi_window_layout.set_focused_subwindow(sender)
        app.multi_window_layout.set_layout("1x1")


def on_swap_view_requested(app: "DICOMViewerApp", other_index: int) -> None:
    """Handle Swap with View X from context menu: swap slot positions in all layouts; focus stays unchanged."""
    sender = app.sender()
    if not isinstance(sender, ImageViewer) or sender.subwindow_index is None:
        return
    if other_index < 0 or other_index >= 4 or other_index == sender.subwindow_index:
        return
    app.multi_window_layout.swap_views(sender.subwindow_index, other_index)
    # Resize images in visible panes so any view that was last in a smaller
    # layout (e.g. 2x2) fits the current window.
    app._subwindow_lifecycle_controller.schedule_viewport_resized()
    if app.multi_window_layout.get_layout_mode() != "2x2":
        app.main_window.update_status("Slot order updated; switch to 2x2 to see positions.")
    # Navigator dots are keyed by grid slot; slot_to_view changed, so refresh assignments.
    app.series_navigator.set_subwindow_assignments(app._get_subwindow_assignments())
    refresh_window_slot_map_widgets(app)


def refresh_window_slot_map_widgets(app: "DICOMViewerApp") -> None:
    """Refresh the embedded and popup window-slot map widgets, if present.

    ``cell_clicked`` uses ``app._on_window_slot_map_cell_clicked`` (not a
    ``partial``) so ``Qt.ConnectionType.UniqueConnection`` is a legal Qt slot
    connection (QObject member); see Qt warning about partials/lambdas.
    """
    widget = getattr(app.main_window, "window_slot_map_widget", None)
    if widget is not None:
        try:
            # UniqueConnection requires a QObject member slot; use app's thin wrapper.
            widget.cell_clicked.connect(
                app._on_window_slot_map_cell_clicked,
                Qt.ConnectionType.UniqueConnection,
            )
        except Exception:
            pass
        try:
            widget.refresh()
        except Exception:
            pass
    popup_widget = getattr(app, "_window_slot_map_widget_popup", None)
    if popup_widget is not None:
        try:
            popup_widget.cell_clicked.connect(
                app._on_window_slot_map_cell_clicked,
                Qt.ConnectionType.UniqueConnection,
            )
        except Exception:
            pass
        try:
            popup_widget.refresh()
        except Exception:
            pass


def on_window_slot_map_cell_clicked(app: "DICOMViewerApp", slot: int) -> None:
    """Focus the subwindow in grid slot *slot* (0–3); 1×2 / 2×1 re-arrange via layout."""
    try:
        stv = app.multi_window_layout.get_slot_to_view()
    except Exception:
        return
    if slot < 0 or slot >= len(stv):
        return
    view_idx = int(stv[slot])
    subwindows = app.multi_window_layout.get_all_subwindows()
    if view_idx < 0 or view_idx >= len(subwindows):
        return
    sub = subwindows[view_idx]
    if sub is None:
        return
    app.multi_window_layout.set_focused_subwindow(sub)


def on_window_slot_map_popup_requested(app: "DICOMViewerApp") -> None:
    """Show or hide a small popup with the window-slot map near the cursor (toggle)."""
    base_widget = getattr(app.main_window, "window_slot_map_widget", None)
    if base_widget is None:
        return

    # If dialog already exists and is visible, treat this as a toggle and close it.
    if hasattr(app, "_window_slot_map_dialog") and app._window_slot_map_dialog is not None:
        dlg = app._window_slot_map_dialog
        if dlg.isVisible():
            dlg.close()
            return

    # Lazily create draggable popup dialog
    if not hasattr(app, "_window_slot_map_dialog") or app._window_slot_map_dialog is None:

        def on_position_changed(x: int, y: int) -> None:
            try:
                app.config_manager.set_layout_map_popup_position(x, y)
            except Exception:
                pass

        dlg = WindowSlotMapPopupDialog(
            app.main_window,
            boundary_widget=app.main_window,
            on_position_changed=on_position_changed,
        )
        app._window_slot_map_dialog = dlg
    else:
        dlg = app._window_slot_map_dialog

    widget = dlg.get_map_widget()
    if widget is None:
        return
    app._window_slot_map_widget_popup = widget

    # Configure callbacks to mirror the main thumbnail (including thumbnails)
    try:
        widget.set_callbacks(
            get_slot_to_view=app.multi_window_layout.get_slot_to_view,
            get_layout_mode=app.multi_window_layout.get_layout_mode,
            get_focused_view_index=app.get_focused_subwindow_index,
            get_thumbnail_for_view=app._get_thumbnail_for_view,
        )
    except Exception:
        pass
    try:
        widget.cell_clicked.connect(
            app._on_window_slot_map_cell_clicked,
            Qt.ConnectionType.UniqueConnection,
        )
    except Exception:
        pass

    widget.refresh()

    # Restore saved position if valid and within main window; otherwise place near cursor
    saved = app.config_manager.get_layout_map_popup_position()
    boundary = app.main_window.frameGeometry()
    if saved is not None:
        x, y = saved
        # Clamp so popup stays within main window
        w, h = dlg.width(), dlg.height()
        x = max(boundary.left(), min(x, boundary.right() - w))
        y = max(boundary.top(), min(y, boundary.bottom() - h))
        dlg.move(x, y)
    else:
        global_pos = QCursor.pos()
        dlg.move(global_pos + QPoint(16, 16))

    dlg.show()
    dlg.raise_()
