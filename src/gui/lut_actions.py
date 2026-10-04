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
    - Menu actions that select a built-in or saved LUT, adjust gamma/sigmoid/exp,
      open the curve or color-stop editor, and save or delete a user LUT

Requirements:
    - PySide6
    - core.lut_catalog
    - gui.widgets.lut_transfer_function_widget.lut_samples
"""

from __future__ import annotations

from typing import Any

import numpy as np
from PySide6.QtGui import QAction, QActionGroup, QCursor, QIcon, QImage, QPixmap
from PySide6.QtWidgets import (
    QInputDialog,
    QMenu,
    QMessageBox,
    QToolButton,
    QWidget,
    QWidgetAction,
)

from core.lut_catalog import (
    DISPLAY_COLORMAP_NAMES,
    builtin_grayscale_luts,
    colormap_lut,
)
from core.lut_defaults import default_entry
from core.lut_engine import (
    LookUpTable,
    exponential_transfer,
    gamma_transfer,
    sigmoid_transfer,
)
from gui.lut_library import delete_lut, is_savable, library_store, save_lut, saved_luts
from gui.widgets.lut_transfer_function_widget import (
    LutTransferFunctionWidget,
    lut_samples,
)

_SAVE_TITLE = "Save LUT"
_IMPORT_TITLE = "Import Colormap"

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
        action.setChecked(current is not None and current == lut)
        action.setIcon(swatch_icon(lut))
        action.triggered.connect(lambda _checked=False, built=lut, owner=host: apply_lut_to_host(owner, built))
        group.addAction(action)
        color.addAction(action)
    _add_saved_menu(menu, group, host, current)
    menu.addSeparator()
    adjust = QAction("Adjust Parameters...", menu)
    adjust.setEnabled(_parameter_lut(current))
    adjust.triggered.connect(lambda: _adjust_parameters(host))
    menu.addAction(adjust)
    edit = QAction("Edit Curve...", menu)
    edit.setEnabled(current is None or current.lut_type == "grayscale_ramp")
    edit.triggered.connect(lambda: _edit_curve(host))
    menu.addAction(edit)
    _add_dicom_lut_action(menu, host)
    colors = QAction("Edit Colors...", menu)
    colors.setEnabled(current is not None and current.lut_type == "colormap")
    colors.triggered.connect(lambda: _edit_colors(host))
    menu.addAction(colors)
    importer = QAction("Import Colormap...", menu)
    importer.setEnabled(library_store(host) is not None)
    importer.setToolTip("Add a .csv or .json colormap to the Saved list")
    importer.triggered.connect(lambda: _import_colormap(host))
    menu.addAction(importer)
    _add_default_actions(menu, host, current)
    save = QAction("Save Current As...", menu)
    save.setEnabled(is_savable(current) and library_store(host) is not None)
    save.triggered.connect(lambda: _save_current(host))
    menu.addAction(save)


def _add_default_actions(menu: QMenu, host: Any, current: LookUpTable | None) -> None:
    """Set or clear the default LUT for the shown series' modality."""
    store = library_store(host)
    getter = getattr(_actor(host), "current_modality", None)
    modality = getter() if callable(getter) else ""
    if store is None or not isinstance(modality, str) or not modality:
        return
    if not callable(getattr(store, "get_lut_defaults", None)):
        return
    entry = default_entry(current) if current is not None else None
    if entry is not None and entry["kind"] == "saved":
        # An unsaved custom curve has no library entry to point at yet.
        if entry["name"] not in {lut.name for lut in saved_luts(store)}:
            entry = None
    use = QAction(f"Use as Default for {modality}", menu)
    use.setEnabled(entry is not None)
    use.setToolTip("Series of this modality start with this LUT until you choose another")
    use.triggered.connect(lambda: _set_default(host, store, modality, entry))
    menu.addAction(use)
    clear = QAction(f"Clear Default for {modality}", menu)
    clear.setEnabled(modality in store.get_lut_defaults())
    clear.triggered.connect(lambda: _set_default(host, store, modality, None))
    menu.addAction(clear)


def _set_default(host: Any, store: Any, modality: str, entry: dict[str, Any] | None) -> None:
    """Set or clear a modality default, then redraw so open panes on it follow."""
    store.set_lut_default(modality, entry)
    redraw = getattr(_actor(host), "redisplay_all_panes", None)
    if callable(redraw):
        redraw()


def _add_dicom_lut_action(menu: QMenu, host: Any) -> None:
    """Checkable "From DICOM (VOI LUT)": the file's own LUTs replace window/level.

    Enabled only when the shown dataset embeds a VOI LUT Sequence. The display
    LUT still applies on top, after polarity, as it does for a windowed image.
    """
    state = getattr(_actor(host), "dicom_lut_state", None)
    found = state() if callable(state) else None
    available, enabled = found if isinstance(found, tuple) and len(found) == 2 else (False, False)
    action = QAction("From DICOM (VOI LUT)", menu)
    action.setCheckable(True)
    action.setChecked(bool(enabled))
    action.setEnabled(bool(available) or bool(enabled))
    action.setToolTip("Use the VOI LUT in the file instead of window/level")
    setter = getattr(_actor(host), "set_dicom_lut", None)
    if callable(setter):
        action.toggled.connect(setter)
    menu.addAction(action)


def _add_saved_menu(menu: QMenu, group: QActionGroup, host: Any, current: LookUpTable | None) -> None:
    """Saved LUTs to select, and a matching Delete submenu. Omitted when none are saved."""
    store = library_store(host)
    luts = saved_luts(store)
    if not luts:
        return
    saved = menu.addMenu("Saved")
    remove = menu.addMenu("Delete Saved")
    for lut in luts:
        action = QAction(lut.name, saved)
        action.setCheckable(True)
        action.setChecked(current is not None and current == lut)
        action.setIcon(swatch_icon(lut))
        action.triggered.connect(lambda _checked=False, built=lut, owner=host: apply_lut_to_host(owner, built))
        group.addAction(action)
        saved.addAction(action)
        drop = QAction(lut.name, remove)
        drop.triggered.connect(lambda _checked=False, name=lut.name, owner=store: delete_lut(owner, name))
        remove.addAction(drop)


def attach_view_lut_menu(view_menu: QMenu, host: Any) -> None:
    """Add View → Look-Up Table. The menu is rebuilt each time it opens."""
    lut_menu = view_menu.addMenu("Look-Up &Table")
    lut_menu.aboutToShow.connect(lambda menu=lut_menu, owner=host: populate_lut_menu(menu, owner))
    config = getattr(host, "config_manager", None)
    if config is not None and callable(getattr(config, "get_show_lut_label", None)):
        show = QAction("Show LUT Label", view_menu)
        show.setCheckable(True)
        show.setChecked(config.get_show_lut_label())
        show.setToolTip("Name a non-Linear or DICOM LUT at the top of each pane")
        show.toggled.connect(lambda checked, owner=config: _set_show_lut_label(owner, checked))
        view_menu.addAction(show)


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
    if not isinstance(button, QToolButton):
        return
    menu = button.menu()
    if menu is not None and not button.isVisible():
        menu.popup(QCursor.pos())
        return
    button.showMenu()


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
    img_bytes = strip.tobytes()
    image = QImage(img_bytes, width, height, 3 * width, QImage.Format.Format_RGB888)
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
    """Refresh the button tooltip to the active LUT, then rebuild its menu."""
    current = _current(host)
    if current is not None:
        button.setToolTip(f"{current.name} ({current.source})")
    populate_lut_menu(menu, host)


def _actor(host: Any) -> Any:
    """Return the LUT callback owner: ``host`` itself or its ``image_viewer``."""
    if callable(getattr(host, "apply_series_lut", None)) or callable(getattr(host, "current_series_lut", None)):
        return host
    return getattr(host, "image_viewer", None)


def _current(host: Any) -> LookUpTable | None:
    """Active LUT of the pane's actor, or ``None`` when the pane is unwired."""
    actor = _actor(host)
    getter = getattr(actor, "current_series_lut", None)
    if not callable(getter):
        return None
    lut = getter()
    return lut if isinstance(lut, LookUpTable) else None


def _parent(host: Any) -> QWidget | None:
    """Widget parent for dialogs: ``host`` itself or its viewer."""
    if isinstance(host, QWidget):
        return host
    viewer = getattr(host, "image_viewer", None)
    return viewer if isinstance(viewer, QWidget) else None


def _same_builtin(current: LookUpTable | None, built: LookUpTable) -> bool:
    """True when ``current`` is the same built-in curve kind as ``built`` (parameters may differ)."""
    if current is None or current.lut_type != "grayscale_ramp" or current.control_points is not None:
        return False
    if current.source == "custom":
        return False  # a saved LUT is checked under Saved, not as its built-in kind
    return current.transfer_fn is built.transfer_fn


def _parameter_lut(lut: LookUpTable | None) -> bool:
    """True when ``lut`` exposes an adjustable parameter (gamma, sigmoid, or exponential)."""
    if lut is None or lut.transfer_fn is None:
        return False
    return lut.transfer_fn in (gamma_transfer, sigmoid_transfer, exponential_transfer)


def _select_builtin(host: Any, lut: LookUpTable) -> None:
    """Apply ``lut``; a parameter curve opens its slider dialog first."""
    chosen = lut
    if _parameter_lut(lut):
        from gui.dialogs.lut_parameter_dialog import edit_lut_parameters

        current = _current(host)
        # Only a built-in carries its parameter over; a saved, file, or DICOM LUT
        # keeps its own entry, so choosing the built-in starts from the built-in.
        start = lut
        if current is not None and current.transfer_fn is lut.transfer_fn and current.source == "built_in":
            start = current
        updated = edit_lut_parameters(start, _parent(host))
        if updated is None:
            return
        chosen = updated
    apply_lut_to_host(host, chosen)


def _adjust_parameters(host: Any) -> None:
    """Open the parameter slider for the active parameter LUT and apply the result."""
    current = _current(host)
    if current is None or not _parameter_lut(current):
        return
    from gui.dialogs.lut_parameter_dialog import edit_lut_parameters

    updated = edit_lut_parameters(current, _parent(host))
    if updated is not None:
        apply_lut_to_host(host, updated)


def _edit_curve(host: Any) -> None:
    """Open the curve editor for a grayscale LUT and apply the accepted result."""
    current = _current(host)
    if current is not None and current.lut_type != "grayscale_ramp":
        return
    from gui.dialogs.lut_curve_editor_dialog import edit_lut_curve

    context = getattr(_actor(host), "lut_display_context", None)
    display = context() if callable(context) else {}
    updated = edit_lut_curve(current, _parent(host), display if isinstance(display, dict) else {})
    if updated is not None:
        apply_lut_to_host(host, updated)


def _edit_colors(host: Any) -> None:
    """Open the color-stop editor for the active colormap and apply the result."""
    current = _current(host)
    if current is None or current.lut_type != "colormap":
        return
    from gui.dialogs.lut_color_stops_dialog import edit_color_stops

    updated = edit_color_stops(current, _parent(host))
    if updated is not None:
        apply_lut_to_host(host, updated)


def _save_current(host: Any) -> None:
    """Ask for a name, save the active LUT to the library, and keep it selected."""
    current = _current(host)
    store = library_store(host)
    if not is_savable(current) or store is None or current is None:
        return
    suggested = current.name if current.source == "custom" else f"My {current.name}"
    name, accepted = QInputDialog.getText(_parent(host), _SAVE_TITLE, "Name:", text=suggested)
    if not accepted:
        return
    if not name.strip():
        QMessageBox.warning(_parent(host), _SAVE_TITLE, "Enter a name for the LUT.")
        return
    named = save_lut(store, current, name)
    if named is None:
        QMessageBox.warning(
            _parent(host),
            _SAVE_TITLE,
            "The LUT was not saved. The saved-LUT file may be read-only, or it was "
            "written by a newer version of the viewer and is left unchanged.",
        )
        return
    apply_lut_to_host(host, named)


def _set_show_lut_label(config: Any, enabled: bool) -> None:
    """Persist the toggle and refresh every pane's label."""
    from gui.lut_pane_label import LutPaneLabel

    config.set_show_lut_label(enabled)
    LutPaneLabel.refresh_all()


def _import_colormap(host: Any) -> None:
    """Pick a .csv/.json colormap, save each LUT it holds, and apply the first."""
    from pathlib import Path

    from PySide6.QtWidgets import QFileDialog

    from core.lut_import import import_colormap_file

    store = library_store(host)
    if store is None:
        return
    chosen, _filter = QFileDialog.getOpenFileName(
        _parent(host), _IMPORT_TITLE, "", "Colormaps (*.csv *.json)"
    )
    if not chosen:
        return
    try:
        luts = import_colormap_file(Path(chosen))
    except OSError:
        QMessageBox.warning(_parent(host), _IMPORT_TITLE, "The file could not be read.")
        return
    except ValueError:
        QMessageBox.warning(
            _parent(host),
            _IMPORT_TITLE,
            "The colormap was not imported. Use a .csv of r,g,b or x,r,g,b rows "
            "(0-255, or 0-1 floats), or a .json colormap or saved-LUT file.",
        )
        return
    taken = {lut.name for lut in saved_luts(store)}
    saved = []
    for lut in luts:
        # Never replace an existing saved LUT: an import adds, it does not overwrite.
        name = _unused_name(lut.name, taken)
        named = save_lut(store, lut, name)
        if named is not None:
            taken.add(name)
            saved.append(named)
    if not saved:
        QMessageBox.warning(
            _parent(host),
            _IMPORT_TITLE,
            "The colormap was read but not saved. The saved-LUT file may be read-only, "
            "or it was written by a newer version of the viewer.",
        )
        return
    apply_lut_to_host(host, saved[0])


def _unused_name(name: str, taken: set[str]) -> str:
    """``name``, or ``name (2)``, ``name (3)``, ... when that is already saved."""
    if name not in taken:
        return name
    number = 2
    while f"{name} ({number})" in taken:
        number += 1
    return f"{name} ({number})"
