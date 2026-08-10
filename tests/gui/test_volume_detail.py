"""Unit tests for 3D volume Detail control helpers."""

from __future__ import annotations

from types import SimpleNamespace

from core.volume_renderer import BUILTIN_PRESETS
from gui.volume.detail import apply_auto_detail


class _CheckBox:
    def isChecked(self) -> bool:
        return True


class _Slider:
    def __init__(self) -> None:
        self.value = -1

    def blockSignals(self, _blocked: bool) -> None:
        pass

    def setValue(self, value: int) -> None:
        self.value = value


class _Caption:
    def setText(self, _text: str) -> None:
        pass


class _RefineTimer:
    def isActive(self) -> bool:
        return False


class _Renderer:
    def __init__(self) -> None:
        self.quality_calls: list[tuple[str, bool]] = []

    def set_quality_mode(self, name: str, *, apply: bool = True) -> None:
        self.quality_calls.append((name, apply))


def test_builtin_preset_keeps_fast_detail_after_suppressed_auto_refine() -> None:
    """A later Auto preset update retains Fast mapper detail after a slow preview."""
    renderer = _Renderer()
    widget = SimpleNamespace(
        _detail_auto_cb=_CheckBox(),
        _refine_timer=_RefineTimer(),
        _renderer=renderer,
        _auto_detail_capped=False,
        _auto_refine_suppressed=True,
        _detail_slider=_Slider(),
        _detail_caption=_Caption(),
        _update_overlay_text=lambda: None,
    )

    apply_auto_detail(widget, BUILTIN_PRESETS[0])

    assert widget._detail_slider.value >= 0
    assert renderer.quality_calls[-1][1] is False
