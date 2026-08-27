"""Unit tests for VTK/Qt-free volume render-status formatting."""

from __future__ import annotations

from types import SimpleNamespace

from gui.volume.render_status import memory_guard_status_lines


def test_memory_guard_status_is_empty_for_native_resolution() -> None:
    renderer = SimpleNamespace(_downsample_factor=1)

    assert memory_guard_status_lines(renderer) == []


def test_memory_guard_status_discloses_downsampling_and_peak_budget() -> None:
    renderer = SimpleNamespace(
        _downsample_factor=2,
        _source_dimensions=(512, 512, 800),
        _estimated_peak_bytes=1_500 * 1024 * 1024,
        _memory_budget_bytes=2_560 * 1024 * 1024,
    )

    assert memory_guard_status_lines(renderer) == [
        "Memory guard: 2× downsampled from 512×512×800",
        "Predicted peak: ~1500 MB / 2560 MB budget",
    ]


def test_memory_guard_status_tolerates_missing_or_malformed_optional_metadata() -> None:
    renderer = SimpleNamespace(
        _downsample_factor=3,
        _source_dimensions=(512, 512),
        _estimated_peak_bytes="not an integer",
        _memory_budget_bytes=None,
    )

    assert memory_guard_status_lines(renderer) == ["Memory guard: 3× downsampled"]
