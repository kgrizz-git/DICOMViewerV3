"""Focused state-machine tests for 3D volume first-paint helpers."""

from types import SimpleNamespace

import pytest
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QLabel

from core.volume_render_quality import GpuFallbackOutcome
from gui.volume.first_paint import (
    cancel_pending_refine,
    check_interactive_gpu_fallback,
    refine_detail,
    run_first_preview,
    set_render_feedback,
)


class _RenderWindow:
    def __init__(self) -> None:
        self.render_count = 0

    def Render(self) -> None:
        self.render_count += 1


class _Renderer:
    def __init__(self, *, fallback: bool = False) -> None:
        self.fallback = fallback
        self.fallback_calls = 0
        self.restores = 0

    def check_gpu_fallback(self, _window, *, probe_quality=None) -> GpuFallbackOutcome:
        assert probe_quality == "Fast"
        self.fallback_calls += 1
        return (
            GpuFallbackOutcome.FELL_BACK
            if self.fallback
            else GpuFallbackOutcome.GPU_OK_VISIBLE
        )

    def restore_target_quality(self) -> None:
        self.restores += 1


def _widget(renderer: _Renderer, window: _RenderWindow):
    feedback = QLabel()
    timer = QTimer()
    timer.setSingleShot(True)
    return SimpleNamespace(
        _cleaned_up=False,
        _initialized=True,
        _vtk_render_window=window,
        _first_paint_pending=True,
        _first_paint_complete=False,
        _auto_refine_suppressed=False,
        _renderer=renderer,
        _render_feedback_label=feedback,
        _refine_timer=timer,
        _update_render_status=lambda: None,
    )


@pytest.mark.qt
def test_responsive_preview_schedules_refinement_and_restores_target(qapp) -> None:
    renderer = _Renderer()
    window = _RenderWindow()
    widget = _widget(renderer, window)

    run_first_preview(widget)

    assert window.render_count == 1
    assert renderer.fallback_calls == 1
    assert widget._refine_timer.isActive() is True
    assert "refining" in widget._render_feedback_label.text().lower()

    refine_detail(widget)
    assert window.render_count == 2
    assert renderer.restores == 1


@pytest.mark.qt
def test_slow_or_cpu_fallback_preview_suppresses_refinement(monkeypatch, qapp) -> None:
    renderer = _Renderer(fallback=True)
    window = _RenderWindow()
    widget = _widget(renderer, window)

    run_first_preview(widget)

    assert widget._auto_refine_suppressed is True
    assert widget._refine_timer.isActive() is False
    assert "may be slow" in widget._render_feedback_label.text()

    set_render_feedback(widget, "Queued")
    widget._refine_timer.start()
    cancel_pending_refine(widget)
    assert widget._refine_timer.isActive() is False


@pytest.mark.qt
def test_expected_blank_preview_refines_without_hardware_warning(qapp) -> None:
    class _ExpectedBlankRenderer(_Renderer):
        def check_gpu_fallback(self, _window, *, probe_quality=None) -> GpuFallbackOutcome:
            assert probe_quality == "Fast"
            self.fallback_calls += 1
            return GpuFallbackOutcome.EXPECTED_BLANK

    renderer = _ExpectedBlankRenderer()
    window = _RenderWindow()
    widget = _widget(renderer, window)

    run_first_preview(widget)

    assert widget._auto_refine_suppressed is False
    assert widget._refine_timer.isActive() is True
    assert "nothing is visible" in widget._render_feedback_label.text().lower()

    refine_detail(widget)
    assert "nothing is visible" in widget._render_feedback_label.text().lower()


@pytest.mark.qt
def test_slow_expected_blank_preview_keeps_preset_guidance(monkeypatch, qapp) -> None:
    class _ExpectedBlankRenderer(_Renderer):
        def check_gpu_fallback(self, _window, *, probe_quality=None) -> GpuFallbackOutcome:
            assert probe_quality == "Fast"
            return GpuFallbackOutcome.EXPECTED_BLANK

    monkeypatch.setattr("gui.volume.first_paint.should_auto_refine", lambda **_kwargs: False)
    widget = _widget(_ExpectedBlankRenderer(), _RenderWindow())

    run_first_preview(widget)

    assert widget._auto_refine_suppressed is True
    assert "nothing is visible" in widget._render_feedback_label.text().lower()


def test_interactive_gpu_fallback_updates_status_only_after_cpu_fallback() -> None:
    calls: list[object] = []

    class _FallbackRenderer:
        def check_gpu_fallback(self, window) -> GpuFallbackOutcome:
            calls.append(window)
            return GpuFallbackOutcome.FELL_BACK

    window = object()
    widget = SimpleNamespace(
        _first_paint_complete=True,
        _vtk_render_window=window,
        _renderer=_FallbackRenderer(),
        _update_render_status=lambda: calls.append("status"),
    )

    check_interactive_gpu_fallback(widget)

    assert calls == [window, "status"]


@pytest.mark.qt
def test_visible_interactive_render_clears_expected_blank_guidance(qapp) -> None:
    class _VisibleRenderer:
        def check_gpu_fallback(self, _window) -> GpuFallbackOutcome:
            return GpuFallbackOutcome.GPU_OK_VISIBLE

    feedback = QLabel("Nothing is visible with this preset")
    widget = SimpleNamespace(
        _first_paint_complete=True,
        _vtk_render_window=object(),
        _renderer=_VisibleRenderer(),
        _expected_blank_guidance=True,
        _render_feedback_label=feedback,
        _update_render_status=lambda: None,
    )

    check_interactive_gpu_fallback(widget)

    assert widget._expected_blank_guidance is False
    assert feedback.text() == ""
