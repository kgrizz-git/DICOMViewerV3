"""Series navigator MPR tiles: stable view IDs, creation order, batched rebuilds."""

from __future__ import annotations

from unittest.mock import MagicMock

import numpy as np
import pytest
from pydicom.dataset import Dataset

from core.dicom_processor import DICOMProcessor
from gui.series_navigator import SeriesNavigator
from gui.series_navigator_model import compute_study_section_width, reconcile_mpr_specs

_PIXELS = np.zeros((8, 8), dtype=np.float32)


def _spec(view_id: int, *, order: int, pane: int | None = None, pixels=_PIXELS, **extra) -> dict:
    spec = {
        "study_uid": "st", "source_series_uid": "se", "pixel_array": pixels,
        "window_center": 40.0, "window_width": 400.0, "n_slices": 3,
        "photometric_interpretation": None, "image_inverted": False, "lut": None,
        "order": order, "pane_index": pane, "tag": f"S{view_id}", "tooltip": f"tip {view_id}",
        "origin": "AbCdEfGhIjKlMnOpQr_-12",
        "stamp": ("s", view_id),
    }
    spec.update(extra)
    return spec


def _navigator() -> SeriesNavigator:
    nav = SeriesNavigator(DICOMProcessor())
    nav._generate_thumbnail = MagicMock(return_value=None)  # type: ignore[method-assign]
    ds = Dataset()
    ds.SeriesDescription, ds.Modality, ds.SeriesNumber = "Src", "CT", 1
    nav.update_series_list({"st": {"se": [ds]}}, "st", "se")
    return nav


class TestReconcileRules:
    def test_identical_incoming_is_reported_unchanged(self) -> None:
        current = {1: _spec(1, order=1), 2: _spec(2, order=2)}
        assert reconcile_mpr_specs(current, {1: dict(current[1]), 2: dict(current[2])}) is None

    def test_keep_update_reuses_shown_pixels_and_changes_only_metadata(self) -> None:
        current = {1: _spec(1, order=1, pane=None)}
        keep = _spec(1, order=1, pane=2, pixels=None)
        keep.pop("stamp")
        result = reconcile_mpr_specs(current, {1: keep})
        assert result is not None
        assert result[1]["pane_index"] == 2
        assert result[1]["pixel_array"] is current[1]["pixel_array"]  # not regenerated
        assert result[1]["stamp"] == current[1]["stamp"]

    def test_keep_update_without_anything_shown_is_dropped(self) -> None:
        # Nothing to keep and nothing shown: the result equals the (empty) current set.
        assert reconcile_mpr_specs({}, {1: _spec(1, order=1, pixels=None)}) is None
        current = {2: _spec(2, order=1)}
        assert reconcile_mpr_specs(current, {1: _spec(1, order=1, pixels=None)}) == {}

    def test_removed_views_are_removed(self) -> None:
        current = {1: _spec(1, order=1), 2: _spec(2, order=2)}
        result = reconcile_mpr_specs(current, {2: dict(current[2])})
        assert result is not None and list(result) == [2]

    def test_new_pixel_array_object_counts_as_a_change(self) -> None:
        current = {1: _spec(1, order=1)}
        assert reconcile_mpr_specs(current, {1: _spec(1, order=1, pixels=np.zeros((8, 8), np.float32))}) is not None

    def test_key_order_change_counts_as_a_change(self) -> None:
        current = {1: _spec(1, order=1), 2: _spec(2, order=2)}
        assert reconcile_mpr_specs(current, {2: dict(current[2]), 1: dict(current[1])}) is not None


@pytest.mark.qt
class TestNavigatorTiles:
    def test_tiles_are_keyed_by_view_id_with_pane_number_separate(self, qapp) -> None:
        nav = _navigator()
        nav.reconcile_mpr_thumbnails({7: _spec(7, order=1, pane=None), 3: _spec(3, order=2, pane=1)})
        assert set(nav._mpr_thumbnails) == {7, 3}
        assert (nav._mpr_thumbnails[7].view_id, nav._mpr_thumbnails[7].pane_index) == (7, None)
        assert (nav._mpr_thumbnails[3].view_id, nav._mpr_thumbnails[3].pane_index) == (3, 1)
        assert nav._mpr_thumbnails[3].toolTip() == "tip 3" and nav._mpr_thumbnails[3]._tag == "S3"
        assert nav._mpr_thumbnails[3]._origin == "AbCdEfGhIjKlMnOpQr_-12"  # stamped into its drags

    def test_creation_order_wins_over_key_order_and_survives_detach_attach(self, qapp) -> None:
        nav = _navigator()
        nav.reconcile_mpr_thumbnails({
            9: _spec(9, order=1), 2: _spec(2, order=2, pane=0), 5: _spec(5, order=3),
        })
        assert list(nav._mpr_thumbnails) == [9, 2, 5]
        # View 9 attaches to a pane, then view 2 detaches: tiles keep creation order.
        nav.reconcile_mpr_thumbnails({
            9: _spec(9, order=1, pane=1, pixels=None),
            2: _spec(2, order=2, pane=None, pixels=None),
            5: _spec(5, order=3, pixels=None),
        })
        assert list(nav._mpr_thumbnails) == [9, 2, 5]
        assert nav._mpr_thumbnails[9].pane_index == 1 and nav._mpr_thumbnails[2].pane_index is None

    def test_a_whole_transaction_rebuilds_the_navigator_exactly_once(self, qapp) -> None:
        nav = _navigator()
        nav._rebuild_from_cached_studies = MagicMock()  # type: ignore[method-assign]
        # Add three, change one, remove one: one reconcile, one rebuild.
        assert nav.reconcile_mpr_thumbnails({i: _spec(i, order=i) for i in (1, 2, 3)}) is True
        assert nav._rebuild_from_cached_studies.call_count == 1
        assert nav.reconcile_mpr_thumbnails({
            1: _spec(1, order=1, pane=0, pixels=None), 3: _spec(3, order=3, pixels=None),
        }) is True
        assert nav._rebuild_from_cached_studies.call_count == 2
        assert list(nav._mpr_thumbnail_specs) == [1, 3]

    def test_unchanged_reconcile_does_not_rebuild(self, qapp) -> None:
        nav = _navigator()
        nav.reconcile_mpr_thumbnails({1: _spec(1, order=1)})
        nav._rebuild_from_cached_studies = MagicMock()  # type: ignore[method-assign]
        assert nav.reconcile_mpr_thumbnails({1: _spec(1, order=1, pixels=None)}) is False
        nav._rebuild_from_cached_studies.assert_not_called()

    def test_tile_stamps_expose_content_stamps_by_view_id(self, qapp) -> None:
        nav = _navigator()
        nav.reconcile_mpr_thumbnails({4: _spec(4, order=1), 6: _spec(6, order=2)})
        assert nav.mpr_tile_stamps() == {4: ("s", 4), 6: ("s", 6)}

    def test_tile_signals_carry_the_view_id_not_a_pane(self, qapp) -> None:
        nav = _navigator()
        nav.reconcile_mpr_thumbnails({11: _spec(11, order=1, pane=2)})
        clicked: list[int] = []
        cleared: list[int] = []
        duplicated: list[int] = []
        nav.mpr_thumbnail_clicked.connect(clicked.append)
        nav.mpr_thumbnail_clear_requested.connect(cleared.append)
        nav.mpr_thumbnail_duplicate_requested.connect(duplicated.append)
        tile = nav._mpr_thumbnails[11]

        tile.clicked.emit(11)
        menu = tile.build_context_menu()
        menu.actions()[0].trigger()
        menu.actions()[1].trigger()

        assert (clicked, duplicated, cleared) == ([11], [11], [11])

    def test_width_counts_every_tile_after_its_source_series(self, qapp) -> None:
        nav = _navigator()
        nav.reconcile_mpr_thumbnails({i: _spec(i, order=i) for i in (1, 2, 3)})
        single = compute_study_section_width(
            [(1, "se", Dataset())], "st", show_instances_separately=False,
            multiframe_info_map={}, mpr_thumbnail_specs={},
        )
        with_three = compute_study_section_width(
            [(1, "se", Dataset())], "st", show_instances_separately=False,
            multiframe_info_map={}, mpr_thumbnail_specs=nav._mpr_thumbnail_specs,
        )
        assert with_three == single + 3 * (5 + 68)
