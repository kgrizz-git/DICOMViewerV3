"""Tests for VolumeRenderControlState model."""

from __future__ import annotations

from core.volume_render_control_state import VolumeRenderControlState, default_state


def test_default_state_values() -> None:
    s = default_state()
    assert s.preset_name == ""
    assert s.opacity_percent == 100.0
    assert s.contrast_depth == 50
    assert s.window == 2000.0
    assert s.level == 0.0
    assert s.threshold == 0
    assert s.background_name == "Black"
    assert s.quality_mode == "Normal"
    assert s.render_method == "Auto"


def test_to_preset_record() -> None:
    s = VolumeRenderControlState(
        preset_name="My CT",
        is_user_preset=True,
        base_preset_name="CT Bone",
        opacity_percent=42.5,
        window=3000.0,
        level=500.0,
        threshold=-100,
    )
    rec = s.to_preset_record()
    assert rec["name"] == "My CT"
    assert rec["base_preset"] == "CT Bone"
    assert rec["opacity"] == 42.5
    assert rec["window"] == 3000.0
    assert rec["level"] == 500.0
    assert rec["threshold"] == -100


def test_to_preset_record_builtin_uses_preset_name_as_base() -> None:
    s = VolumeRenderControlState(preset_name="CT Bone", is_user_preset=False)
    rec = s.to_preset_record()
    assert rec["base_preset"] == "CT Bone"
    assert rec["name"] == ""
