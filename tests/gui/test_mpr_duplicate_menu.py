"""Duplicate-into-window chooser and the tile → navigator → app → controller chain."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import numpy as np
import pytest
from main_mixin_delegation_support import _stub_for
from PySide6.QtWidgets import QMenu, QWidget

from gui.mpr_duplicate_menu import (
    PaneChoice,
    build_target_menu,
    pane_choices,
    show_duplicate_target_menu,
)


def _pane(*, hidden: bool = False, viewer: object | None = object()) -> SimpleNamespace:
    return SimpleNamespace(isHidden=lambda: hidden, image_viewer=viewer)


def _app(panes, source_pane: int | None = 0) -> SimpleNamespace:
    controller = MagicMock()
    controller.get_view_metadata.return_value = (
        None if source_pane == -1 else SimpleNamespace(view_id=5, pane_index=source_pane)
    )
    return SimpleNamespace(
        _mpr_controller=controller,
        multi_window_layout=SimpleNamespace(get_all_subwindows=lambda: panes),
        main_window=SimpleNamespace(show_toast_message=MagicMock()),
    )


class TestPaneChoices:
    def test_lists_visible_existing_panes_and_disables_the_sources_own(self) -> None:
        app = _app([_pane(), _pane(), _pane(hidden=True), _pane()], source_pane=1)
        assert pane_choices(app, 5) == [
            PaneChoice(0, "Window 1", True),
            PaneChoice(1, "Window 2 (shows this view)", False),
            PaneChoice(3, "Window 4", True),  # pane 2 is hidden by the layout
        ]

    def test_a_detached_source_has_no_disabled_pane(self) -> None:
        app = _app([_pane(), _pane()], source_pane=None)
        assert all(c.enabled for c in pane_choices(app, 5))

    def test_panes_without_a_viewer_are_not_offered(self) -> None:
        app = _app([_pane(viewer=None), _pane(), None], source_pane=None)
        assert [c.pane_index for c in pane_choices(app, 5)] == [1]

    def test_unknown_source_view_offers_nothing(self) -> None:
        assert pane_choices(_app([_pane()], source_pane=-1), 5) == []


@pytest.mark.qt
class TestTargetMenu:
    def test_enabled_actions_choose_their_pane_and_disabled_ones_do_nothing(self, qapp) -> None:
        chosen: list[int] = []
        menu = build_target_menu(
            None, [PaneChoice(0, "Window 1", True), PaneChoice(1, "Window 2 (shows this view)", False)],
            chosen.append,
        )
        first, second = menu.actions()
        assert (first.isEnabled(), second.isEnabled()) == (True, False)
        second.trigger()
        assert chosen == []
        first.trigger()
        assert chosen == [0]

    def test_nothing_available_toasts_and_shows_no_menu(self, qapp) -> None:
        app = _app([_pane()], source_pane=0)  # the only pane is the source's
        assert show_duplicate_target_menu(app, 5) is None
        app.main_window.show_toast_message.assert_called_once()
        app._mpr_controller.duplicate_view.assert_not_called()


@pytest.mark.qt
def test_tile_context_menu_to_controller_duplicate_chain(qapp, monkeypatch) -> None:
    """Right-click action on a real tile → chooser → controller.duplicate_view(view, pane)."""
    from gui.series_navigator import SeriesNavigator

    popped: list[QMenu] = []
    monkeypatch.setattr(QMenu, "popup", lambda self, _pos=None, _action=None: popped.append(self))

    class _Window(QWidget):
        show_toast_message = MagicMock()

    app = _app([_pane(), _pane(), _pane()], source_pane=2)
    app.main_window = _Window()  # the chooser menu is parented to the real main window
    stub = _stub_for(
        "MPRNavigationMixin", _mpr_controller=app._mpr_controller,
        multi_window_layout=app.multi_window_layout, main_window=app.main_window,
    )
    nav = SeriesNavigator(MagicMock())
    nav._rebuild_from_cached_studies = MagicMock()  # type: ignore[method-assign]
    nav.reconcile_mpr_thumbnails({
        5: {
            "study_uid": "st", "source_series_uid": "se", "pixel_array": np.zeros((4, 4), np.float32),
            "order": 1, "pane_index": 2, "tag": "S1", "tooltip": "",
        }
    })
    nav.mpr_thumbnail_duplicate_requested.connect(stub._on_mpr_duplicate_requested)
    tile = nav._create_mpr_thumbnail_widget(5, 2, nav)

    menu = tile.build_context_menu()
    assert menu.actions()[0].text() == "Duplicate into Window…"
    menu.actions()[0].trigger()  # the explicit context-menu action

    assert len(popped) == 1
    chooser = popped[0]
    texts = [a.text() for a in chooser.actions()]
    assert texts == ["Window 1", "Window 2", "Window 3 (shows this view)"]
    assert [a.isEnabled() for a in chooser.actions()] == [True, True, False]
    chooser.actions()[1].trigger()  # pick Window 2
    app._mpr_controller.duplicate_view.assert_called_once_with(5, 1)
