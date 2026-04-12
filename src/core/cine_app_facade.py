"""
Cine playback and frame-slider coordination for ``DICOMViewerApp``.

Groups slice navigator integration, ``CinePlayer`` / ``CineControlsWidget`` updates,
and config persistence for loop defaults. Slots are wired from ``app_signal_wiring``;
callers that refresh context after load use ``update_cine_player_context``.

Inputs:
    - ``DICOMViewerApp`` reference (duck-typed).

Outputs:
    - UI and playback side effects only.

Requirements:
    - ``CinePlayer``, ``CineControlsWidget``, ``slice_navigator``, and study/series state
      on the app match prior ``main.py`` behavior.
"""

from __future__ import annotations

from typing import Any


class CineAppFacade:
    """Cine-related behaviors formerly implemented as methods on ``DICOMViewerApp``."""

    # __weakref__ required so PySide6 signal connections can weak-reference bound methods.
    __slots__ = ("_app", "__weakref__")

    def __init__(self, app: Any) -> None:
        self._app = app

    def update_cine_player_context(self) -> None:
        """Update cine player context and enable/disable controls based on series capability."""
        app = self._app
        app.cine_player.set_series_context(
            app.current_studies,
            app.current_study_uid,
            app.current_series_uid,
        )

        if (
            app.current_studies
            and app.current_study_uid
            and app.current_series_uid
            and app.current_study_uid in app.current_studies
            and app.current_series_uid in app.current_studies[app.current_study_uid]
        ):
            datasets = app.current_studies[app.current_study_uid][app.current_series_uid]
            app.cine_player.set_datasets(datasets)
            app.cine_controls_widget.set_loop_bounds(None, None)

        is_cine_capable = app.cine_player.is_cine_capable(
            app.current_studies,
            app.current_study_uid,
            app.current_series_uid,
        )

        app.cine_controls_widget.set_controls_enabled(is_cine_capable)
        if app.image_viewer is not None:
            app.image_viewer.set_cine_controls_enabled(is_cine_capable)

        if is_cine_capable:
            total_slices = app.slice_navigator.total_slices
            current_slice = app.slice_navigator.get_current_slice()
            app.cine_controls_widget.update_frame_position(current_slice, total_slices)
        else:
            app.cine_controls_widget.update_frame_position(0, 0)

        if not is_cine_capable and app.cine_player.is_playback_active():
            app.cine_player.stop_playback()

    def on_manual_slice_navigation(self, slice_index: int) -> None:
        """Pause cine when the user navigates slices manually (not via cine advance)."""
        app = self._app
        if app.cine_player.is_playback_active() and not app.cine_player.is_cine_advancing():
            app.cine_player.pause_playback()

    def on_cine_frame_advance(self, frame_index: int) -> None:
        """Advance the slice navigator to ``frame_index`` with loop semantics from the player."""
        app = self._app
        loop_enabled = app.cine_player.loop_enabled
        app.slice_navigator.advance_to_frame(frame_index, loop=loop_enabled)

    def on_cine_playback_state_changed(self, is_playing: bool) -> None:
        """Sync cine controls and FPS readout with playback state."""
        app = self._app
        app.cine_controls_widget.update_playback_state(is_playing)
        fps = app.cine_player.get_effective_frame_rate()
        app.cine_controls_widget.update_fps_display(fps)

    def on_cine_play(self) -> None:
        """Start playback using frame rate from the current dataset when available."""
        app = self._app
        if app.current_dataset is not None:
            frame_rate = app.cine_player.get_frame_rate_from_dicom(app.current_dataset)
            app.cine_player.start_playback(frame_rate=frame_rate, dataset=app.current_dataset)
            fps = app.cine_player.get_effective_frame_rate()
            app.cine_controls_widget.update_fps_display(fps)

    def on_cine_pause(self) -> None:
        self._app.cine_player.pause_playback()

    def on_cine_stop(self) -> None:
        self._app.cine_player.stop_playback()

    def on_cine_speed_changed(self, speed_multiplier: float) -> None:
        app = self._app
        app.cine_player.set_speed(speed_multiplier)
        fps = app.cine_player.get_effective_frame_rate()
        app.cine_controls_widget.update_fps_display(fps)

    def on_cine_loop_toggled(self, enabled: bool) -> None:
        app = self._app
        app.cine_player.set_loop(enabled)
        app.cine_controls_widget.set_loop(enabled)
        app.config_manager.set_cine_default_loop(enabled)

    def get_cine_loop_state(self) -> bool:
        """Return whether cine loop is enabled (for image viewer context menu)."""
        return self._app.cine_player.loop_enabled

    def on_cine_loop_start_set(self, frame_index: int) -> None:
        app = self._app
        loop_end = app.cine_player.loop_end_frame
        app.cine_player.set_loop_bounds(frame_index, loop_end)
        app.cine_controls_widget.set_loop_bounds(frame_index, loop_end)

    def on_cine_loop_end_set(self, frame_index: int) -> None:
        app = self._app
        loop_start = app.cine_player.loop_start_frame
        app.cine_player.set_loop_bounds(loop_start, frame_index)
        app.cine_controls_widget.set_loop_bounds(loop_start, frame_index)

    def on_cine_loop_bounds_cleared(self) -> None:
        app = self._app
        app.cine_player.clear_loop_bounds()
        app.cine_controls_widget.set_loop_bounds(None, None)

    def on_frame_slider_changed(self, frame_index: int) -> None:
        """User dragged the frame slider: pause playback and jump to the frame."""
        app = self._app
        if app.cine_player.is_playback_active():
            app.cine_player.pause_playback()
        total_slices = app.slice_navigator.total_slices
        if 0 <= frame_index < total_slices:
            app.slice_navigator.set_current_slice(frame_index)
