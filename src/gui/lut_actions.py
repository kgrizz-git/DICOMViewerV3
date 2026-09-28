"""
Apply a per-pane LUT and build the Look-Up Table menus.

Each image viewer receives ``apply_series_lut`` and ``current_series_lut``
from the subwindow factory. The View menu and toolbar use the focused viewer
(``main_window.image_viewer``). Built-in curves are replaced, never mutated.

Bare ``L`` opens this menu when focus is in the image, navigator, or a side
panel. ``Ctrl+Shift+L`` stays on overlay tag configuration. The 3D view's
patient-left camera is key ``3``, not ``L``.

Inputs:
    - A host widget (the image viewer, or the main window that holds one)
    - A ``QMenu`` or toolbar to fill

Outputs:
    - Menu actions that select a LUT, adjust gamma/sigmoid/exp, or open the editor

Requirements:
    - PySide6
    - core.lut_catalog
    - gui.widgets.lut_transfer_function_widget.lut_samples
"""

from __future__ import annotations

from typing import Any

import numpy as np
from PySide6.QtGui import QAction, QActionGroup, QCursor, QIcon, QImage, QPixmap
from PySide6.QtWidgets import QMenu, QToolButton, QWidget, QWidgetAction

from core.lut_catalog import (
    DISPLAY_COLORMAP_NAMES,
    builtin_grayscale_luts,
    colormap_lut,
)
from core.lut_engine import (
    LookUpTable,
    exponential_transfer,
    gamma_transfer,
    sigmoid_transfer,
)
from gui.widgets.lut_transfer_function_widget import (
    LutTransferFunctionWidget,
    lut_samples,
)


def apply_lut_to_host(host: Any, lut: LookUpTable) -> None:
    """Store ``lut`` on the pane behind ``host`` and redisplay that pane."""
    actor = _actor(host)
    apply = getattr(actor, "apply_series_lut", None)
    if callable(apply):
        apply(lut)


def populate_lut_menu(menu: QMenu, host: Any) -> None:
    """Fill ``menu`` with grayscale curves, colormaps, parameter adjust, and the editor."""
    _clear_lut_menu(menu)
    current = _current(host)
    if current is not None:
        info = QAction(f"{current.name} — {current.source}", menu)
        info.setEnabled(False)
        menu.addAction(info)
        preview = LutTransferFunctionWidget(menu)
        preview.setMinimumSize(180, 64)
        context = getattr(_actor(host), "lut_display_context", None)
        display = context() if callable(context) else {}
        if not isinstance(display, dict):
            display = {}
        preview.set_lut(
            current,
            window_center=display.get("window_center"),
            window_width=display.get("window_width"),
            photometric_interpretation=display.get("photometric"),
            image_inverted=bool(display.get("image_inverted", False)),
        )
        preview_action = QWidgetAction(menu)
        preview_action.setDefaultWidget(preview)
        menu.addAction(preview_action)
    group = QActionGroup(menu)
    group.setExclusive(True)
    gray = menu.addMenu("Grayscale")
    for lut in builtin_grayscale_luts().values():
        action = QAction(lut.name, gray)
        action.setCheckable(True)
        action.setChecked(_same_builtin(current, lut))
        action.setIcon(swatch_icon(lut))
        action.triggered.connect(lambda _checked=False, built=lut, owner=host: _select_builtin(owner, built))
        group.addAction(action)
        gray.addAction(action)
    color = menu.addMenu("Color")
    for name in DISPLAY_COLORMAP_NAMES:
        lut = colormap_lut(name)
        action = QAction(name, color)
        action.setCheckable(True)
        action.setChecked(current is not None and current.lut_type == "colormap" and current.name == name)
        action.setIcon(swatch_icon(lut))
        action.triggered.connect(lambda _checked=False, built=lut, owner=host: apply_lut_to_host(owner, built))
        group.addAction(action)
        color.addAction(action)
    menu.addSeparator()
    adjust = QAction("Adjust Parameters...", menu)
    adjust.setEnabled(_parameter_lut(current))
    adjust.triggered.connect(lambda: _adjust_parameters(host))
    menu.addAction(adjust)
    edit = QAction("Edit Curve...", menu)
    edit.setEnabled(current is None or current.lut_type == "grayscale_ramp")
    edit.triggered.connect(lambda: _edit_curve(host))
    menu.addAction(edit)


def attach_view_lut_menu(view_menu: QMenu, host: Any) -> None:
    """Add View → Look-Up Table. The menu is rebuilt each time it opens."""
    lut_menu = view_menu.addMenu("Look-Up &Table")
    lut_menu.aboutToShow.connect(lambda menu=lut_menu, owner=host: populate_lut_menu(menu, owner))


def attach_context_lut_menu(context_menu: QMenu, viewer: Any) -> None:
    """Add the image context-menu Look-Up Table submenu."""
    lut_menu = context_menu.addMenu("Look-Up Table")
    lut_menu.aboutToShow.connect(lambda menu=lut_menu, owner=viewer: populate_lut_menu(menu, owner))


def show_lut_toolbar_menu(host: Any) -> None:
    """Open the toolbar Look-Up Table menu. Bound to bare ``L``.

    Fullscreen hides the toolbar. A hidden button would pin ``showMenu`` to
    the window corner, so the menu opens at the pointer instead.
    """
    button = getattr(host, "lut_toolbar_button", None)
    if button is None:
        return
    menu_getter = getattr(button, "menu", None)
    menu = menu_getter() if callable(menu_getter) else None
    if menu is not None and not button.isVisible():
        menu.popup(QCursor.pos())
        return
    show_menu = getattr(button, "showMenu", None)
    if callable(show_menu):
        show_menu()


def attach_toolbar_lut_button(toolbar: Any, host: Any) -> QToolButton:
    """Toolbar button whose menu is the same Look-Up Table list."""
    button = QToolButton(toolbar)
    button.setText("LUT")
    button.setToolTip("Look-Up Table for the focused pane  (L)")
    button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
    menu = QMenu(button)
    menu.aboutToShow.connect(lambda host_menu=menu, owner=host: _show_toolbar_menu(button, host_menu, owner))
    button.setMenu(menu)
    toolbar.addWidget(button)
    return button


def swatch_icon(lut: LookUpTable) -> QIcon:
    """A short gradient icon. Sampling goes through the transfer widget."""
    samples = lut_samples(lut)
    if samples.ndim == 1:
        column = np.asarray(samples, dtype=np.uint8)
        rgb = np.stack((column, column, column), axis=-1)
    else:
        rgb = np.asarray(samples, dtype=np.uint8)
    strip = np.ascontiguousarray(np.repeat(rgb.reshape(1, -1, 3), 10, axis=0))
    height, width, _channels = strip.shape
    image = QImage(strip.tobytes(), width, height, 3 * width, QImage.Format.Format_RGB888)
    return QIcon(QPixmap.fromImage(image.copy()))


def _clear_lut_menu(menu: QMenu) -> None:
    """Remove the previous entries.

    ``QMenu.clear`` deletes actions and leaves submenus and the exclusive
    action group parented to the menu. Each open would otherwise keep another
    Grayscale menu, Color menu, and group.
    """
    menu.clear()
    for child in list(menu.children()):
        if isinstance(child, (QMenu, QActionGroup)):
            child.deleteLater()


def _show_toolbar_menu(button: QToolButton, menu: QMenu, host: Any) -> None:
    current = _current(host)
    if current is not None:
        button.setToolTip(f"{current.name} ({current.source})")
    populate_lut_menu(menu, host)


def _actor(host: Any) -> Any:
    if callable(getattr(host, "apply_series_lut", None)) or callable(getattr(host, "current_series_lut", None)):
        return host
    return getattr(host, "image_viewer", None)


def _current(host: Any) -> LookUpTable | None:
    actor = _actor(host)
    getter = getattr(actor, "current_series_lut", None)
    if not callable(getter):
        return None
    lut = getter()
    return lut if isinstance(lut, LookUpTable) else None


def _parent(host: Any) -> QWidget | None:
    if isinstance(host, QWidget):
        return host
    viewer = getattr(host, "image_viewer", None)
    return viewer if isinstance(viewer, QWidget) else None


def _same_builtin(current: LookUpTable | None, built: LookUpTable) -> bool:
    if current is None or current.lut_type != "grayscale_ramp" or current.control_points is not None:
        return False
    return current.transfer_fn is built.transfer_fn


def _parameter_lut(lut: LookUpTable | None) -> bool:
    if lut is None or lut.transfer_fn is None:
        return False
    return lut.transfer_fn in (gamma_transfer, sigmoid_transfer, exponential_transfer)


def _select_builtin(host: Any, lut: LookUpTable) -> None:
    chosen = lut
    if _parameter_lut(lut):
        from gui.dialogs.lut_parameter_dialog import edit_lut_parameters

        current = _current(host)
        start = current if current is not None and current.transfer_fn is lut.transfer_fn else lut
        updated = edit_lut_parameters(start, _parent(host))
        if updated is None:
            return
        chosen = updated
    apply_lut_to_host(host, chosen)


def _adjust_parameters(host: Any) -> None:
    current = _current(host)
    if current is None or not _parameter_lut(current):
        return
    from gui.dialogs.lut_parameter_dialog import edit_lut_parameters

    updated = edit_lut_parameters(current, _parent(host))
    if updated is not None:
        apply_lut_to_host(host, updated)


def _edit_curve(host: Any) -> None:
    current = _current(host)
    if current is not None and current.lut_type != "grayscale_ramp":
        return
    from gui.dialogs.lut_curve_editor_dialog import edit_lut_curve

    context = getattr(_actor(host), "lut_display_context", None)
    display = context() if callable(context) else {}
    updated = edit_lut_curve(current, _parent(host), display if isinstance(display, dict) else {})
    if updated is not None:
        apply_lut_to_host(host, updated)
