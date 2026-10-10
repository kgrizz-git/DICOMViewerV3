"""Unit tests for core.mpr_navigator_thumbnail."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import core.mpr_navigator_thumbnail as mpr_navigator_thumbnail
from core.lut_catalog import linear_lut, sigmoid_lut
from core.mpr_session_types import MprDisplayState, MprViewMetadata


def _make_app(**overrides) -> SimpleNamespace:
    defaults = {
        "subwindow_data": {},
        "subwindow_managers": {},
        "series_navigator": SimpleNamespace(
            set_mpr_thumbnail=MagicMock(),
            clear_mpr_thumbnail=MagicMock(),
            mpr_thumbnail_keys=MagicMock(return_value=[]),
        ),
        "window_level_controls": SimpleNamespace(window_center="40", window_width="400"),
        "_mpr_controller": _FakeController(),
        "focused_subwindow_index": 0,
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


class _FakeController:
    """Public per-view API surface of ``MprController`` used by the tile sync."""

    def __init__(self, views: dict[int, dict] | None = None) -> None:
        # view_id -> {"seq", "study", "series", "n_slices", "display", "pixels", "pi"}
        self.views = views or {}
        self.pixel_requests: list[tuple[int, bool | None]] = []

    def detached_view_ids(self) -> list[int]:
        return sorted(self.views, key=lambda v: self.views[v]["seq"])

    def get_view_metadata(self, view_id: int):
        view = self.views.get(view_id)
        if view is None:
            return None
        return MprViewMetadata(
            view_id=view_id, session_id=view_id, creation_seq=view["seq"], pane_index=None,
            orientation="Axial", source_study_uid=view.get("study", "study"),
            source_series_uid=view.get("series", "series"), n_slices=view.get("n_slices", 11),
            slice_index=0, photometric_interpretation=view.get("pi"),
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


class TestThumbnailHelpers:
    def test_thumbnail_pixel_array_uses_middle_slice(self, monkeypatch) -> None:
        getter = MagicMock(return_value="pixels")
        monkeypatch.setattr(mpr_navigator_thumbnail, "get_subwindow_mpr_pixel_array", getter)
        app = _make_app(subwindow_data={0: {"mpr_result": SimpleNamespace(n_slices=7)}})

        assert mpr_navigator_thumbnail.get_subwindow_mpr_thumbnail_pixel_array(app, 0) == "pixels"
        getter.assert_called_once_with(app, 0, 3)

    def test_thumbnail_pixel_array_returns_none_without_valid_slice_count(self) -> None:
        assert mpr_navigator_thumbnail.get_subwindow_mpr_thumbnail_pixel_array(
            _make_app(subwindow_data={0: {"mpr_result": None}}), 0
        ) is None
        assert mpr_navigator_thumbnail.get_subwindow_mpr_thumbnail_pixel_array(
            _make_app(subwindow_data={0: {"mpr_result": SimpleNamespace(n_slices=0)}}), 0
        ) is None


class TestUpdateMprNavigatorThumbnail:
    def test_clears_thumbnail_for_non_mpr_or_missing_result(self) -> None:
        app = _make_app(subwindow_data={1: {"is_mpr": False}})

        mpr_navigator_thumbnail.update_mpr_navigator_thumbnail(app, 1)

        app.series_navigator.clear_mpr_thumbnail.assert_called_once_with(1)

    def test_sets_thumbnail_with_window_level_and_slice_count(self, monkeypatch) -> None:
        monkeypatch.setattr(
            mpr_navigator_thumbnail,
            "get_subwindow_mpr_thumbnail_pixel_array",
            MagicMock(return_value="pixels"),
        )
        app = _make_app(
            subwindow_data={
                0: {
                    "is_mpr": True,
                    "mpr_result": SimpleNamespace(n_slices=9),
                    "current_study_uid": "study",
                    "current_series_uid": "series",
                }
            }
        )

        mpr_navigator_thumbnail.update_mpr_navigator_thumbnail(app, 0)

        app.series_navigator.set_mpr_thumbnail.assert_called_once_with(
            0,
            "pixels",
            "study",
            "series",
            40.0,
            400.0,
            9,
            None,
            image_inverted=False,
            lut=linear_lut(),
            order=None,
        )

    def test_skips_set_when_pixels_missing_and_tolerates_bad_window_level(self, monkeypatch) -> None:
        monkeypatch.setattr(
            mpr_navigator_thumbnail,
            "get_subwindow_mpr_thumbnail_pixel_array",
            MagicMock(side_effect=[None, "pixels"]),
        )
        app = _make_app(
            subwindow_data={0: {"is_mpr": True, "mpr_result": SimpleNamespace(n_slices="bad")}},
            window_level_controls=SimpleNamespace(window_center="bad", window_width=0),
        )

        mpr_navigator_thumbnail.update_mpr_navigator_thumbnail(app, 0)
        app.series_navigator.set_mpr_thumbnail.assert_not_called()

        mpr_navigator_thumbnail.update_mpr_navigator_thumbnail(app, 0)
        app.series_navigator.set_mpr_thumbnail.assert_called_once_with(
            0,
            "pixels",
            "",
            "",
            None,
            None,
            None,
            None,
            image_inverted=False,
            lut=linear_lut(),
            order=None,
        )


class TestFloatingMprThumbnail:
    def test_no_detached_views_shows_nothing_and_clears_stale_detached_tiles(self) -> None:
        app = _make_app()
        app.series_navigator.mpr_thumbnail_keys.return_value = [2, -3, -1]

        mpr_navigator_thumbnail.update_floating_mpr_navigator_thumbnail(app)

        app.series_navigator.set_mpr_thumbnail.assert_not_called()
        # Pane tiles (>= 0) are never touched by the detached sync.
        assert [c.args for c in app.series_navigator.clear_mpr_thumbnail.call_args_list] == [(-3,), (-1,)]

    def test_each_detached_view_gets_its_own_exact_id_tile_in_creation_order(self) -> None:
        # View 9 was created before view 4: creation order, not key order, rules.
        controller = _FakeController({
            9: {"seq": 1, "study": "s1", "series": "a", "n_slices": 5, "pixels": "p9"},
            4: {"seq": 2, "study": "s1", "series": "a", "n_slices": 7, "pixels": "p4"},
        })
        app = _make_app(_mpr_controller=controller)

        mpr_navigator_thumbnail.update_floating_mpr_navigator_thumbnail(app)

        calls = app.series_navigator.set_mpr_thumbnail.call_args_list
        assert [(c.args[0], c.args[1], c.args[6], c.kwargs["order"]) for c in calls] == [
            (-9, "p9", 5, 1),
            (-4, "p4", 7, 2),
        ]

    def test_existing_detached_tiles_are_left_alone_and_removed_when_no_longer_detached(self) -> None:
        controller = _FakeController({4: {"seq": 2}, 5: {"seq": 3}})
        app = _make_app(_mpr_controller=controller)
        app.series_navigator.mpr_thumbnail_keys.return_value = [-4, -8, 0]

        mpr_navigator_thumbnail.update_floating_mpr_navigator_thumbnail(app)

        # -4 already shown (frozen state): untouched. -5 missing: added. -8 stale: removed.
        assert [c.args[0] for c in app.series_navigator.set_mpr_thumbnail.call_args_list] == [-5]
        assert [c.args for c in app.series_navigator.clear_mpr_thumbnail.call_args_list] == [(-8,)]

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

        mpr_navigator_thumbnail.update_floating_mpr_navigator_thumbnail(app)

        assert controller.pixel_requests == [(3, False)]
        args, kwargs = app.series_navigator.set_mpr_thumbnail.call_args
        assert (args[4], args[5], args[7]) == (55.0, 555.0, "MONOCHROME1")
        assert kwargs["lut"] is carried
        assert kwargs["image_inverted"] is True

    def test_missing_carried_lut_falls_back_to_linear_and_invalid_wl_is_auto(self) -> None:
        controller = _FakeController({3: {"seq": 1, "display": MprDisplayState(lut=None, window_width=0.0)}})
        app = _make_app(_mpr_controller=controller)

        mpr_navigator_thumbnail.update_floating_mpr_navigator_thumbnail(app)

        args, kwargs = app.series_navigator.set_mpr_thumbnail.call_args
        assert kwargs["lut"].name == linear_lut().name
        assert (args[4], args[5]) == (None, None)

    def test_view_without_pixels_gets_no_tile(self) -> None:
        controller = _FakeController({3: {"seq": 1, "pixels": None}})
        app = _make_app(_mpr_controller=controller)

        mpr_navigator_thumbnail.update_floating_mpr_navigator_thumbnail(app)

        app.series_navigator.set_mpr_thumbnail.assert_not_called()


def test_clear_and_detach_helpers_delegate() -> None:
    app = _make_app()

    mpr_navigator_thumbnail.clear_mpr_navigator_thumbnail(app, 3)
    app.series_navigator.clear_mpr_thumbnail.assert_called_once_with(3)

    app.series_navigator.clear_mpr_thumbnail.reset_mock()
    app._mpr_controller = _FakeController({6: {"seq": 1}})
    mpr_navigator_thumbnail.on_mpr_detached(app, 2)

    # The former pane's tile goes; the newly detached view gets its exact-ID tile.
    app.series_navigator.clear_mpr_thumbnail.assert_called_once_with(2)
    assert app.series_navigator.set_mpr_thumbnail.call_args.args[0] == -6


class TestAttachedTileOrder:
    def test_attached_tile_carries_the_views_creation_sequence(self, monkeypatch) -> None:
        monkeypatch.setattr(
            mpr_navigator_thumbnail, "get_subwindow_mpr_thumbnail_pixel_array",
            MagicMock(return_value="pixels"),
        )
        meta = MprViewMetadata(
            view_id=5, session_id=5, creation_seq=17, pane_index=0, orientation="Axial",
            source_study_uid="study", source_series_uid="series", n_slices=9, slice_index=0,
        )
        controller = SimpleNamespace(get_pane_view_metadata=MagicMock(return_value=meta))
        app = _make_app(
            _mpr_controller=controller,
            subwindow_data={0: {"is_mpr": True, "mpr_result": SimpleNamespace(n_slices=9)}},
        )

        mpr_navigator_thumbnail.update_mpr_navigator_thumbnail(app, 0)

        assert app.series_navigator.set_mpr_thumbnail.call_args.kwargs["order"] == 17

    def test_non_integer_order_is_ignored(self, monkeypatch) -> None:
        monkeypatch.setattr(
            mpr_navigator_thumbnail, "get_subwindow_mpr_thumbnail_pixel_array",
            MagicMock(return_value="pixels"),
        )
        app = _make_app(
            _mpr_controller=MagicMock(),  # MagicMock metadata is never a real sequence number
            subwindow_data={0: {"is_mpr": True, "mpr_result": SimpleNamespace(n_slices=9)}},
        )
        mpr_navigator_thumbnail.update_mpr_navigator_thumbnail(app, 0)
        assert app.series_navigator.set_mpr_thumbnail.call_args.kwargs["order"] is None


class TestAttachedThumbnailPaneWindowLevel:
    def test_attached_tile_uses_pane_not_toolbar(self, monkeypatch) -> None:
        monkeypatch.setattr(
            mpr_navigator_thumbnail,
            "get_subwindow_mpr_thumbnail_pixel_array",
            MagicMock(return_value="pixels"),
        )
        app = _make_app(
            subwindow_data={
                0: {
                    "is_mpr": True,
                    "mpr_result": SimpleNamespace(n_slices=9),
                    "current_study_uid": "study",
                    "current_series_uid": "series",
                }
            },
            subwindow_managers={
                0: {
                    "view_state_manager": SimpleNamespace(
                        current_window_center=60.0,
                        current_window_width=600.0,
                        series_defaults={},
                        current_series_identifier="series-id",
                    )
                }
            },
            window_level_controls=SimpleNamespace(window_center=40.0, window_width=400.0),
        )

        mpr_navigator_thumbnail.update_mpr_navigator_thumbnail(app, 0)

        _args, _kwargs = app.series_navigator.set_mpr_thumbnail.call_args
        assert (_args[4], _args[5]) == (60.0, 600.0)
