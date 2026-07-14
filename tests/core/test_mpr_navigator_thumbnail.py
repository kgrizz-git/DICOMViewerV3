"""Unit tests for core.mpr_navigator_thumbnail."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import core.mpr_navigator_thumbnail as mpr_navigator_thumbnail


def _make_app(**overrides) -> SimpleNamespace:
    defaults = {
        "subwindow_data": {},
        "subwindow_managers": {},
        "series_navigator": SimpleNamespace(
            set_mpr_thumbnail=MagicMock(),
            clear_mpr_thumbnail=MagicMock(),
        ),
        "window_level_controls": SimpleNamespace(window_center="40", window_width="400"),
        "_mpr_controller": SimpleNamespace(
            has_detached_mpr=MagicMock(return_value=False),
            get_detached_mpr_thumbnail_pixels=MagicMock(return_value=None),
        ),
        "focused_subwindow_index": 0,
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


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
        )


class TestFloatingMprThumbnail:
    def test_clears_when_no_detached_mpr_exists(self) -> None:
        app = _make_app()

        mpr_navigator_thumbnail.update_floating_mpr_navigator_thumbnail(app)

        app.series_navigator.clear_mpr_thumbnail.assert_called_once_with(-1)

    def test_sets_floating_thumbnail_with_payload_and_wl(self) -> None:
        payload = {
            "current_study_uid": "study",
            "current_series_uid": "series",
            "mpr_result": SimpleNamespace(n_slices=11),
        }
        app = _make_app(
            _mpr_controller=SimpleNamespace(
                has_detached_mpr=MagicMock(return_value=True),
                get_detached_mpr_thumbnail_pixels=MagicMock(return_value="pixels"),
                _detached_mpr_payload=payload,
            ),
            subwindow_managers={0: {"view_state_manager": SimpleNamespace(use_rescaled_values=False)}},
        )

        mpr_navigator_thumbnail.update_floating_mpr_navigator_thumbnail(app)

        app._mpr_controller.get_detached_mpr_thumbnail_pixels.assert_called_once_with(False)
        app.series_navigator.set_mpr_thumbnail.assert_called_once_with(
            -1,
            "pixels",
            "study",
            "series",
            40.0,
            400.0,
            11,
        )

    def test_skips_when_floating_pixels_missing_or_payload_invalid(self) -> None:
        app = _make_app(
            _mpr_controller=SimpleNamespace(
                has_detached_mpr=MagicMock(return_value=True),
                get_detached_mpr_thumbnail_pixels=MagicMock(side_effect=[None, "pixels"]),
                _detached_mpr_payload="not-a-dict",
            ),
            window_level_controls=SimpleNamespace(window_center=None, window_width="bad"),
        )

        mpr_navigator_thumbnail.update_floating_mpr_navigator_thumbnail(app)
        app.series_navigator.set_mpr_thumbnail.assert_not_called()

        mpr_navigator_thumbnail.update_floating_mpr_navigator_thumbnail(app)
        app.series_navigator.set_mpr_thumbnail.assert_called_once_with(
            -1,
            "pixels",
            "",
            "",
            None,
            None,
            None,
        )


def test_clear_and_detach_helpers_delegate() -> None:
    app = _make_app()

    mpr_navigator_thumbnail.clear_mpr_navigator_thumbnail(app, 3)
    app.series_navigator.clear_mpr_thumbnail.assert_called_once_with(3)

    app.series_navigator.clear_mpr_thumbnail.reset_mock()
    app._mpr_controller = SimpleNamespace(
        has_detached_mpr=MagicMock(return_value=False),
        get_detached_mpr_thumbnail_pixels=MagicMock(return_value=None),
    )
    mpr_navigator_thumbnail.on_mpr_detached(app, 2)

    app.series_navigator.clear_mpr_thumbnail.assert_any_call(2)
    app.series_navigator.clear_mpr_thumbnail.assert_any_call(-1)
