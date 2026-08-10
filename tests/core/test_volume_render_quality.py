"""Tests for the VTK-free first-paint quality policy."""

from core.volume_render_quality import (
    AUTO_REFINE_BUDGET_MS,
    HUGE_VOLUME_BYTES,
    LARGE_VOLUME_BYTES,
    auto_detail_cap_index,
    estimate_volume_megabytes,
    should_auto_refine,
)


def test_estimate_volume_megabytes_uses_float32_input_size() -> None:
    assert estimate_volume_megabytes((256, 256, 256)) == 64.0


def test_auto_detail_cap_boundaries() -> None:
    assert auto_detail_cap_index(None, mode_count=4) == 3
    assert auto_detail_cap_index(LARGE_VOLUME_BYTES - 1, mode_count=4) == 3
    assert auto_detail_cap_index(LARGE_VOLUME_BYTES, mode_count=4) == 1
    assert auto_detail_cap_index(HUGE_VOLUME_BYTES, mode_count=4) == 0


def test_auto_refine_requires_a_responsive_non_fallback_preview() -> None:
    assert should_auto_refine(
        preview_elapsed_ms=AUTO_REFINE_BUDGET_MS, gpu_fallback_used=False
    ) is True
    assert should_auto_refine(
        preview_elapsed_ms=AUTO_REFINE_BUDGET_MS + 0.1, gpu_fallback_used=False
    ) is False
    assert should_auto_refine(preview_elapsed_ms=1.0, gpu_fallback_used=True) is False
