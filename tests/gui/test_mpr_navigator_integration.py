"""Real controller + real tile sync + real navigator: tiles follow views, one rebuild per transaction."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from mpr_lifecycle_harness import (
    _add_detached_view,
    _light_display,
    _make_controller,
    _make_result,
    _seed_mpr_pane,
)
from pydicom.dataset import Dataset

from core.dicom_processor import DICOMProcessor
from core.mpr_navigator_thumbnail import sync_mpr_navigator_tiles
from gui.series_navigator import SeriesNavigator


def _wired(qapp):
    ctrl, app = _make_controller()
    nav = SeriesNavigator(DICOMProcessor())
    nav._generate_thumbnail = MagicMock(return_value=None)  # type: ignore[method-assign]
    ds = Dataset()
    ds.SeriesDescription, ds.Modality, ds.SeriesNumber = "Src", "CT", 1
    # Harness sources are "ST"/"SE": show a matching series so tiles have a section.
    nav.update_series_list({"ST": {"SE": [ds]}}, "ST", "SE")
    app.series_navigator = nav
    ctrl.mpr_tiles_changed.connect(lambda dirty: sync_mpr_navigator_tiles(app, dirty))
    nav._rebuild_from_cached_studies = MagicMock(wraps=nav._rebuild_from_cached_studies)  # type: ignore[method-assign]
    return ctrl, app, nav


@pytest.mark.qt
class TestTilesFollowViews:
    def test_detach_attach_duplicate_clear_keep_one_tile_per_view_by_id(self, qapp) -> None:
        ctrl, app, nav = _wired(qapp)
        _seed_mpr_pane(app, 0, _make_result(), study="ST")
        view = ctrl.attached_view_id(0)

        with _light_display(ctrl):
            ctrl.detach_mpr_from_subwindow(0)
            assert list(nav._mpr_thumbnails) == [view]
            assert nav._mpr_thumbnails[view].pane_index is None
            ctrl.move_view(view, 1)
            assert nav._mpr_thumbnails[view].pane_index == 1
            ctrl.duplicate_view(view, 0)
        duplicate = ctrl.attached_view_id(0)
        assert list(nav._mpr_thumbnails) == [view, duplicate]  # creation order
        assert nav._mpr_thumbnails[duplicate]._tag == "S1.2"
        assert nav._mpr_thumbnails[view]._tag == "S1.1"

        ctrl.clear_mpr(1)
        assert list(nav._mpr_thumbnails) == [duplicate]

    def test_each_transaction_rebuilds_the_navigator_exactly_once(self, qapp) -> None:
        ctrl, app, nav = _wired(qapp)
        _seed_mpr_pane(app, 0, _make_result(), study="ST")
        _seed_mpr_pane(app, 1, _make_result(), study="ST")
        mover = ctrl.attached_view_id(0)
        nav._rebuild_from_cached_studies.reset_mock()

        with _light_display(ctrl):
            # relocate-over-occupied: cleared + detached + activated signals, ONE rebuild.
            ctrl.relocate_mpr_subwindow(0, 1)
        assert nav._rebuild_from_cached_studies.call_count == 1
        assert nav._mpr_thumbnails[mover].pane_index == 1

        nav._rebuild_from_cached_studies.reset_mock()
        ctrl.release_all_mpr()
        assert nav._rebuild_from_cached_studies.call_count == 1
        assert nav._mpr_thumbnails == {} or not nav._mpr_thumbnail_specs

    def test_a_transaction_that_changes_nothing_visible_does_not_rebuild(self, qapp) -> None:
        ctrl, app, nav = _wired(qapp)
        _add_detached_view(ctrl, _make_result(), "ST", "SE")
        sync_mpr_navigator_tiles(app)
        nav._rebuild_from_cached_studies.reset_mock()
        sync_mpr_navigator_tiles(app)
        ctrl.detach_view_for_pane_reset(1)  # no view in pane 1: nothing announced, nothing rebuilt
        assert nav._rebuild_from_cached_studies.call_count == 0


@pytest.mark.qt
class TestLinkedTiles:
    def test_linked_duplicate_and_unlink_through_the_tile_menus(self, qapp) -> None:
        from main_mixin_delegation_support import _stub_for

        ctrl, app, nav = _wired(qapp)
        stub = _stub_for("MPRNavigationMixin", _mpr_controller=ctrl)
        nav.mpr_thumbnail_unlink_requested.connect(stub._on_mpr_unlink_requested)
        _seed_mpr_pane(app, 0, _make_result(), study="ST")
        source = ctrl.attached_view_id(0)

        with _light_display(ctrl):
            assert ctrl.duplicate_view(source, 1, linked=True) is True
        duplicate = ctrl.attached_view_id(1)

        assert [nav._mpr_thumbnails[v]._tag for v in (source, duplicate)] == ["S1.1L", "S1.2L"]
        assert all(nav._mpr_thumbnails[v]._linked for v in (source, duplicate))
        assert "Linked scrolling" in nav._mpr_thumbnails[duplicate].toolTip()

        menu = nav._mpr_thumbnails[duplicate].build_context_menu()
        unlink = next(a for a in menu.actions() if a.text() == "Unlink View")
        assert unlink.isEnabled()
        unlink.trigger()  # tile → navigator signal → app handler → controller

        assert ctrl._registry.get_view(source).link_group_id is None
        assert [nav._mpr_thumbnails[v]._tag for v in (source, duplicate)] == ["S1.1", "S1.2"]
        assert not any(nav._mpr_thumbnails[v]._linked for v in (source, duplicate))
        assert next(
            a for a in nav._mpr_thumbnails[duplicate].build_context_menu().actions() if a.text() == "Unlink View"
        ).isEnabled() is False

    def test_a_detached_linked_tile_shows_its_dormant_position_after_the_debounced_refresh(self, qapp) -> None:
        ctrl, app, nav = _wired(qapp)
        _seed_mpr_pane(app, 0, _make_result(n_slices=12), study="ST")
        source = ctrl.attached_view_id(0)
        with _light_display(ctrl):
            ctrl.duplicate_view(source, 1, linked=True)
        duplicate = ctrl.attached_view_id(1)
        ctrl.detach_mpr_from_subwindow(1)
        assert "slice 2 of 12" in nav._mpr_thumbnails[duplicate].toolTip()  # seeded at index 1

        ctrl.set_pane_slice(0, 8)
        assert "slice 2 of 12" in nav._mpr_thumbnails[duplicate].toolTip()  # debounced: not yet
        nav._rebuild_from_cached_studies.reset_mock()
        ctrl.flush_tile_refresh()

        assert "slice 9 of 12" in nav._mpr_thumbnails[duplicate].toolTip()
        assert nav._rebuild_from_cached_studies.call_count == 1  # one rebuild for the whole burst
