"""Unit tests for core.mpr_navigator_thumbnail."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import core.mpr_navigator_thumbnail as mpr_navigator_thumbnail
from core.lut_catalog import linear_lut, sigmoid_lut
from core.mpr_session_types import MprDisplayState, MprViewMetadata
from gui.series_navigator_model import reconcile_mpr_specs


def _make_app(**overrides) -> SimpleNamespace:
    defaults = {
        "subwindow_data": {},
        "subwindow_managers": {},
        "series_navigator": _FakeNavigator(),
        "_mpr_controller": _FakeController(),
        "focused_subwindow_index": 0,
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


class _FakeNavigator:
    """Navigator stand-in that applies the real reconcile rules and counts rebuilds."""

    def __init__(self) -> None:
        self.specs: dict[int, dict] = {}
        self.rebuilds = 0
        self.reconcile_calls = 0

    def mpr_tile_stamps(self) -> dict:
        return {k: v.get("stamp") for k, v in self.specs.items()}

    def reconcile_mpr_thumbnails(self, incoming: dict) -> bool:
        self.reconcile_calls += 1
        new = reconcile_mpr_specs(self.specs, incoming)
        if new is None:
            return False
        self.specs = new
        self.rebuilds += 1
        return True


class _FakeController:
    """Public per-view API surface of ``MprController`` used by the tile sync."""

    def __init__(self, views: dict[int, dict] | None = None) -> None:
        # view_id -> {"seq", "pane", "study", "series", "n_slices", "display", "pixels", "pi", "stamp", ...}
        self.views = views or {}
        self.pixel_requests: list[tuple[int, bool | None]] = []
        self.drag_origin = "AbCdEfGhIjKlMnOpQr_-12"

    def all_view_ids(self) -> list[int]:
        return sorted(self.views, key=lambda v: self.views[v]["seq"])

    def attached_view_id(self, idx: int) -> int | None:
        return next((v for v, d in self.views.items() if d.get("pane") == idx), None)

    def get_view_metadata(self, view_id: int):
        view = self.views.get(view_id)
        if view is None:
            return None
        return MprViewMetadata(
            view_id=view_id, session_id=view.get("session", view_id), creation_seq=view["seq"],
            pane_index=view.get("pane"), orientation=view.get("orientation", "Axial"),
            source_study_uid=view.get("study", "study"), source_series_uid=view.get("series", "series"),
            n_slices=view.get("n_slices", 11), slice_index=0, photometric_interpretation=view.get("pi"),
            view_number=view.get("vnum", 1), view_count=view.get("vcount", 1),
            link_group_id=view.get("link"), content_stamp=view.get("stamp", ("s", view_id)),
        )

    def get_view_display_state(self, view_id: int):
        view = self.views.get(view_id)
        return None if view is None else view.get("display", MprDisplayState())

    def get_view_thumbnail_pixels(self, view_id: int, use_rescaled=None):
        self.pixel_requests.append((view_id, use_rescaled))
        return self.views[view_id].get("pixels", "pixels")


class TestGetSubwindowMprPixelArray:
    def test_returns_rescaled_array_for_valid_mpr_subwindow(self, monkeypatch) -> None:
        monkeypatch.setattr(mpr_navigator_thumbnail, "apply_mpr_stack_combine", MagicMock(return_value="raw"))
        result = SimpleNamespace(n_slices=5, slices=["a"], apply_rescale=MagicMock(return_value="scaled"))
        app = _make_app(
            subwindow_data={
                2: {
                    "is_mpr": True,
                    "mpr_result": result,
                    "mpr_slice_index": 1,
                    "mpr_combine_enabled": True,
                    "mpr_combine_mode": "mip",
                    "mpr_combine_slice_count": 6,
                }
            },
            subwindow_managers={2: {"view_state_manager": SimpleNamespace(use_rescaled_values=True)}},
        )

        pixel_array = mpr_navigator_thumbnail.get_subwindow_mpr_pixel_array(app, 2)

        assert pixel_array == "scaled"
        mpr_navigator_thumbnail.apply_mpr_stack_combine.assert_called_once_with(
            result.slices,
            1,
            enabled=True,
            mode="mip",
            n_planes=6,
        )
        result.apply_rescale.assert_called_once_with("raw")

    def test_returns_raw_when_rescale_disabled_and_none_for_invalid_cases(self, monkeypatch) -> None:
        monkeypatch.setattr(mpr_navigator_thumbnail, "apply_mpr_stack_combine", MagicMock(return_value="raw"))
        result = SimpleNamespace(n_slices=3, slices=["a"], apply_rescale=MagicMock(return_value="scaled"))
        app = _make_app(
            subwindow_data={0: {"is_mpr": True, "mpr_result": result, "mpr_slice_index": 1}},
            subwindow_managers={0: {"view_state_manager": SimpleNamespace(use_rescaled_values=False)}},
        )

        assert mpr_navigator_thumbnail.get_subwindow_mpr_pixel_array(app, 0) == "raw"
        assert mpr_navigator_thumbnail.get_subwindow_mpr_pixel_array(app, 1) is None
        assert mpr_navigator_thumbnail.get_subwindow_mpr_pixel_array(app, 0, 99) is None

    def test_returns_none_when_mpr_slice_index_is_explicitly_missing(self, monkeypatch) -> None:
        monkeypatch.setattr(mpr_navigator_thumbnail, "apply_mpr_stack_combine", MagicMock(return_value="raw"))
        result = SimpleNamespace(n_slices=3, slices=["a"], apply_rescale=MagicMock(return_value="scaled"))
        app = _make_app(subwindow_data={0: {"is_mpr": True, "mpr_result": result, "mpr_slice_index": None}})

        assert mpr_navigator_thumbnail.get_subwindow_mpr_pixel_array(app, 0) is None

    def test_returns_none_when_stack_combine_raises(self, monkeypatch) -> None:
        monkeypatch.setattr(mpr_navigator_thumbnail, "apply_mpr_stack_combine", MagicMock(side_effect=RuntimeError("boom")))
        result = SimpleNamespace(n_slices=2, slices=["a"], apply_rescale=MagicMock())
        app = _make_app(subwindow_data={0: {"is_mpr": True, "mpr_result": result, "mpr_slice_index": 0}})

        assert mpr_navigator_thumbnail.get_subwindow_mpr_pixel_array(app, 0) is None


class TestSyncMprNavigatorTiles:
    def test_every_view_gets_a_tile_keyed_by_view_id_in_creation_order(self) -> None:
        # View 9 was created before view 4; one is attached, one detached.
        controller = _FakeController({
            9: {"seq": 1, "pane": None, "study": "s1", "series": "a", "n_slices": 5, "pixels": "p9"},
            4: {"seq": 2, "pane": 2, "study": "s1", "series": "a", "n_slices": 7, "pixels": "p4"},
        })
        app = _make_app(_mpr_controller=controller)

        mpr_navigator_thumbnail.sync_mpr_navigator_tiles(app)

        nav = app.series_navigator
        assert list(nav.specs) == [9, 4]
        assert [(s["pane_index"], s["order"], s["n_slices"]) for s in nav.specs.values()] == [
            (None, 1, 5), (2, 2, 7),
        ]
        assert nav.specs[4]["pixel_array"] == "p4" and nav.specs[9]["pixel_array"] == "p9"
        assert nav.rebuilds == 1
        assert {s["origin"] for s in nav.specs.values()} == {controller.drag_origin}

    def test_tiles_carry_pane_and_label_separately_from_identity(self) -> None:
        controller = _FakeController({
            3: {"seq": 1, "pane": 1, "session": 8, "vnum": 2, "vcount": 2, "link": 5},
        })
        app = _make_app(_mpr_controller=controller)
        mpr_navigator_thumbnail.sync_mpr_navigator_tiles(app)
        spec = app.series_navigator.specs[3]
        assert spec["pane_index"] == 1
        assert spec["tag"] == "S8.2L"
        assert "Window 2" in spec["tooltip"] and "Linked" in spec["tooltip"]

    def test_unchanged_state_requests_no_pixels_and_does_not_rebuild(self) -> None:
        controller = _FakeController({1: {"seq": 1}, 2: {"seq": 2, "pane": 0}})
        app = _make_app(_mpr_controller=controller)
        mpr_navigator_thumbnail.sync_mpr_navigator_tiles(app)
        controller.pixel_requests.clear()

        mpr_navigator_thumbnail.sync_mpr_navigator_tiles(app)
        mpr_navigator_thumbnail.sync_mpr_navigator_tiles(app)

        assert controller.pixel_requests == []
        assert app.series_navigator.rebuilds == 1  # only the first sync changed anything

    def test_moving_a_view_updates_its_pane_without_regenerating_pixels(self) -> None:
        controller = _FakeController({1: {"seq": 1, "pane": None, "pixels": "px"}})
        app = _make_app(_mpr_controller=controller)
        mpr_navigator_thumbnail.sync_mpr_navigator_tiles(app)
        controller.pixel_requests.clear()
        controller.views[1]["pane"] = 3  # attach: same stamp, new pane

        mpr_navigator_thumbnail.sync_mpr_navigator_tiles(app)

        spec = app.series_navigator.specs[1]
        assert spec["pane_index"] == 3 and spec["pixel_array"] == "px"
        assert controller.pixel_requests == []
        assert app.series_navigator.rebuilds == 2  # one rebuild for the one change

    def test_dirty_views_regenerate_only_themselves(self) -> None:
        controller = _FakeController({1: {"seq": 1}, 2: {"seq": 2, "pane": 0}})
        app = _make_app(_mpr_controller=controller)
        mpr_navigator_thumbnail.sync_mpr_navigator_tiles(app)
        controller.pixel_requests.clear()
        controller.views[2]["pixels"] = "fresh"

        mpr_navigator_thumbnail.sync_mpr_navigator_tiles(app, frozenset({2}))

        assert [v for v, _r in controller.pixel_requests] == [2]
        assert app.series_navigator.specs[2]["pixel_array"] == "fresh"

    def test_a_detached_views_changed_stamp_refreshes_its_tile(self) -> None:
        """Seam for linked groups: detached state is not assumed frozen."""
        controller = _FakeController({1: {"seq": 1, "pixels": "old", "stamp": ("s", 1, "slice-3")}})
        app = _make_app(_mpr_controller=controller)
        mpr_navigator_thumbnail.sync_mpr_navigator_tiles(app)
        controller.pixel_requests.clear()
        controller.views[1].update(pixels="new", stamp=("s", 1, "slice-8"))  # e.g. linked scroll

        mpr_navigator_thumbnail.sync_mpr_navigator_tiles(app)

        assert [v for v, _r in controller.pixel_requests] == [1]
        assert app.series_navigator.specs[1]["pixel_array"] == "new"

    def test_discarded_views_are_removed_in_the_same_single_reconcile(self) -> None:
        controller = _FakeController({1: {"seq": 1}, 2: {"seq": 2}, 3: {"seq": 3}})
        app = _make_app(_mpr_controller=controller)
        mpr_navigator_thumbnail.sync_mpr_navigator_tiles(app)
        calls_before = app.series_navigator.reconcile_calls
        del controller.views[1]
        del controller.views[3]

        mpr_navigator_thumbnail.sync_mpr_navigator_tiles(app)

        assert list(app.series_navigator.specs) == [2]
        assert app.series_navigator.reconcile_calls == calls_before + 1

    def test_tile_uses_view_carried_state_and_ignores_focused_pane(self) -> None:
        carried = sigmoid_lut()
        controller = _FakeController({3: {
            "seq": 1, "pi": "MONOCHROME1",
            "display": MprDisplayState(
                window_center=55.0, window_width=555.0, use_rescaled=False, inverted=True, lut=carried
            ),
        }})
        app = _make_app(
            _mpr_controller=controller,
            # Deliberately differing focus state: rescaled pixels, other W/L.
            subwindow_managers={0: {"view_state_manager": SimpleNamespace(use_rescaled_values=True)}},
            window_level_controls=SimpleNamespace(window_center=40.0, window_width=400.0),
        )

        mpr_navigator_thumbnail.sync_mpr_navigator_tiles(app)

        assert controller.pixel_requests == [(3, False)]
        spec = app.series_navigator.specs[3]
        assert (spec["window_center"], spec["window_width"]) == (55.0, 555.0)
        assert spec["photometric_interpretation"] == "MONOCHROME1"
        assert spec["lut"] is carried and spec["image_inverted"] is True

    def test_missing_carried_lut_falls_back_to_linear_and_invalid_wl_is_auto(self) -> None:
        controller = _FakeController({3: {"seq": 1, "display": MprDisplayState(lut=None, window_width=0.0)}})
        app = _make_app(_mpr_controller=controller)

        mpr_navigator_thumbnail.sync_mpr_navigator_tiles(app)

        spec = app.series_navigator.specs[3]
        assert spec["lut"].name == linear_lut().name
        assert (spec["window_center"], spec["window_width"]) == (None, None)

    def test_view_without_pixels_gets_no_tile(self) -> None:
        controller = _FakeController({3: {"seq": 1, "pixels": None}})
        app = _make_app(_mpr_controller=controller)
        mpr_navigator_thumbnail.sync_mpr_navigator_tiles(app)
        assert app.series_navigator.specs == {}

    def test_missing_navigator_or_controller_is_a_no_op(self) -> None:
        mpr_navigator_thumbnail.sync_mpr_navigator_tiles(SimpleNamespace())
        mpr_navigator_thumbnail.sync_mpr_navigator_tiles(
            SimpleNamespace(series_navigator=_FakeNavigator())
        )

    def test_non_integer_dirty_entries_are_ignored(self) -> None:
        controller = _FakeController({1: {"seq": 1}})
        app = _make_app(_mpr_controller=controller)
        mpr_navigator_thumbnail.sync_mpr_navigator_tiles(app, {"x", None, 1.5})
        assert list(app.series_navigator.specs) == [1]


class TestRefreshPaneTile:
    def test_pane_refresh_regenerates_the_attached_view_only(self) -> None:
        controller = _FakeController({1: {"seq": 1}, 2: {"seq": 2, "pane": 0}})
        app = _make_app(_mpr_controller=controller)
        mpr_navigator_thumbnail.sync_mpr_navigator_tiles(app)
        controller.pixel_requests.clear()

        mpr_navigator_thumbnail.refresh_pane_mpr_tile(app, 0)

        assert [v for v, _r in controller.pixel_requests] == [2]

    def test_pane_without_a_view_does_nothing(self) -> None:
        controller = _FakeController({1: {"seq": 1}})
        app = _make_app(_mpr_controller=controller)
        mpr_navigator_thumbnail.refresh_pane_mpr_tile(app, 3)
        assert app.series_navigator.reconcile_calls == 0
