"""View-menu actions for 3D viewer windows: keep in front and show/hide."""

from __future__ import annotations

from typing import Any

from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMenu


def attach_3d_window_menu_actions(view_menu: QMenu, main_window: Any) -> None:
    """Add "Show 3D Viewer" and "Keep 3D Viewer in Front" to the View menu."""
    show_action = QAction("Show 3D Viewer", main_window)
    show_action.setCheckable(True)
    show_action.setEnabled(False)
    show_action.setToolTip("Show or hide the 3D viewer window you used most recently.")
    view_menu.addAction(show_action)
    main_window.show_3d_viewer_action = show_action

    keep_action = QAction("Keep 3D Viewer in Front", main_window)
    keep_action.setCheckable(True)
    keep_action.setChecked(main_window.config_manager.get_keep_3d_viewer_in_front())
    keep_action.setToolTip(
        "Keeps 3D viewer windows above the main window while this app is active. "
        "Currently applies on macOS and Linux only."
    )
    view_menu.addAction(keep_action)
    main_window.keep_3d_viewer_in_front_action = keep_action


def wire_3d_window_menu_actions(app: Any) -> None:
    """Connect the View-menu 3D window actions to the volume render facade."""
    window = app.main_window
    show_action = getattr(window, "show_3d_viewer_action", None)
    keep_action = getattr(window, "keep_3d_viewer_in_front_action", None)
    if show_action is None or keep_action is None:
        return
    facade = app._volume_render_facade

    def _idx() -> int:
        return app.get_focused_subwindow_index()

    def _sync() -> None:
        show_action.setEnabled(facade.has_open_dialog())
        show_action.setChecked(facade.target_is_shown(_idx()))

    def _on_keep_toggled(checked: bool) -> None:
        window.config_manager.set_keep_3d_viewer_in_front(checked)
        facade.refresh_stay_on_top()

    show_action.triggered.connect(lambda _c=False: (facade.toggle_dialog_visibility(_idx()), _sync()))
    keep_action.toggled.connect(_on_keep_toggled)
    view_menu = getattr(window, "view_menu", None)
    if view_menu is not None:
        view_menu.aboutToShow.connect(_sync)
