"""Focused state-machine tests for 3D volume first-paint helpers."""

from types import SimpleNamespace

import pytest
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QLabel

from gui.volume.first_paint import (
    cancel_pending_refine,
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

    def check_gpu_fallback(self, _window, *, probe_quality=None) -> bool:
        assert probe_quality == "Fast"
        self.fallback_calls += 1
        return self.fallback

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
