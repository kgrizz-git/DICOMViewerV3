"""Tests for propagating in-window slice/frame slider display settings."""

from __future__ import annotations

from types import SimpleNamespace

from gui.subwindow_image_viewer_sync import (
    apply_initial_image_viewer_display_state,
    set_slice_slider_options_all,
)


class _Viewer:
    def __init__(self) -> None:
        self.slider_options: tuple[str, str] | None = None
        self.slider_enabled: bool | None = None

    def set_privacy_view_state(self, enabled: bool) -> None:
        pass

    def set_slice_sync_enabled_state(self, enabled: bool) -> None:
        pass

    def set_smooth_when_zoomed_state(self, enabled: bool) -> None:
        pass

    def set_scale_markers_state(self, enabled: bool) -> None:
        pass

    def set_direction_labels_state(self, enabled: bool) -> None:
        pass

    def set_slice_slider_options(self, placement: str, direction: str) -> None:
        self.slider_options = (placement, direction)

    def set_slice_slider_enabled(self, enabled: bool) -> None:
        self.slider_enabled = enabled

    def set_scale_markers_color_state(self, rgb: tuple[int, int, int]) -> None:
        pass

    def set_direction_labels_color_state(self, rgb: tuple[int, int, int]) -> None:
        pass

    def set_direction_label_size_state(self, size: int) -> None:
        pass

    def set_scale_markers_tick_intervals_state(self, major_mm: int, minor_mm: int) -> None:
        pass


class _Config:
    def get_slice_sync_enabled(self) -> bool:
        return False

    def get_smooth_image_when_zoomed(self) -> bool:
        return True

    def get_show_scale_markers(self) -> bool:
        return False

    def get_show_direction_labels(self) -> bool:
        return True

    def get_show_slice_slider(self) -> bool:
        return True

    def get_slice_slider_placement(self) -> str:
        return "right"

    def get_slice_slider_direction(self) -> str:
        return "first_at_end"

    def get_scale_markers_color(self) -> tuple[int, int, int]:
        return (255, 255, 255)

    def get_direction_labels_color(self) -> tuple[int, int, int]:
        return (255, 255, 0)

    def get_direction_label_size(self) -> int:
        return 10

    def get_scale_markers_major_tick_interval_mm(self) -> int:
        return 10

    def get_scale_markers_minor_tick_interval_mm(self) -> int:
        return 1


def _app_with_viewers(*viewers: _Viewer) -> SimpleNamespace:
    return SimpleNamespace(
        privacy_view_enabled=False,
        config_manager=_Config(),
        multi_window_layout=SimpleNamespace(
            get_all_subwindows=lambda: [SimpleNamespace(image_viewer=v) for v in viewers]
        ),
    )


def test_initial_display_state_applies_slider_options_and_enabled_state() -> None:
    viewer = _Viewer()

    apply_initial_image_viewer_display_state(_app_with_viewers(viewer))

    assert viewer.slider_options == ("right", "first_at_end")
    assert viewer.slider_enabled is True


def test_set_slice_slider_options_all_updates_each_viewer() -> None:
    first = _Viewer()
    second = _Viewer()

    set_slice_slider_options_all(_app_with_viewers(first, second), "top", "first_at_start")

    assert first.slider_options == ("top", "first_at_start")
    assert second.slider_options == ("top", "first_at_start")
