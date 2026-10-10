"""Target-window chooser for "Duplicate into Window…" on an MPR tile.

Lists the existing, currently visible panes (hidden panes in 1×1 / 3-pane
layouts are not offered). The pane that already shows the source view is
listed but disabled: duplicating a view into its own window is meaningless.
The choice is made from public layout/controller APIs only and calls the
controller's ``duplicate_view``; the menu itself never mutates state.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import QMenu, QWidget


@dataclass(frozen=True)
class PaneChoice:
    """One selectable window in the chooser."""

    pane_index: int
    label: str
    enabled: bool


def pane_choices(app: Any, source_view_id: int) -> list[PaneChoice]:
    """Visible, existing panes for duplicating *source_view_id* (empty if it is gone)."""
    meta = app._mpr_controller.get_view_metadata(source_view_id)
    if meta is None:
        return []
    choices: list[PaneChoice] = []
    for idx, pane in enumerate(app.multi_window_layout.get_all_subwindows()):
        if pane is None or getattr(pane, "image_viewer", None) is None or pane.isHidden():
            continue
        is_source = idx == meta.pane_index
        label = f"Window {idx + 1}" + (" (shows this view)" if is_source else "")
        choices.append(PaneChoice(idx, label, enabled=not is_source))
    return choices


def build_target_menu(
    parent: QWidget | None, choices: list[PaneChoice], on_choose: Callable[[int], None]
) -> QMenu:
    """Menu with one action per choice; enabled actions call ``on_choose(pane_index)``."""
    menu = QMenu(parent)
    for choice in choices:
        action = menu.addAction(choice.label)
        action.setEnabled(choice.enabled)
        action.triggered.connect(lambda _checked=False, idx=choice.pane_index: on_choose(idx))
    return menu


def show_duplicate_target_menu(
    app: Any, source_view_id: int, linked: bool = False
) -> QMenu | None:
    """Pop up the chooser at the cursor. Returns the menu, or None when nothing is offered.

    ``linked=True`` is the "Duplicate Linked into Window…" variant: the chosen
    duplicate also joins the source's link group.
    """
    choices = pane_choices(app, source_view_id)
    if not any(c.enabled for c in choices):
        toast = getattr(app.main_window, "show_toast_message", None)
        if callable(toast):
            toast("No other window is available to duplicate this MPR into.", timeout_ms=3500)
        return None
    menu = build_target_menu(
        app.main_window,
        choices,
        lambda idx: app._mpr_controller.duplicate_view(source_view_id, idx, linked=linked),
    )
    # Popup menus are transient: delete on close instead of piling up under the
    # main window for the rest of the session.
    menu.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
    menu.popup(QCursor.pos())
    return menu


__all__ = ["PaneChoice", "build_target_menu", "pane_choices", "show_duplicate_target_menu"]
