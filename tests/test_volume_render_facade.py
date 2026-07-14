"""
Unit tests for core.volume_render_facade (backward-compatible re-exports of
core.volume_render_eligibility).
"""

from __future__ import annotations

import core.volume_render_eligibility as eligibility
from core.volume_render_facade import (
    _MIN_SLICES_FOR_VOLUME,
    MIN_SLICES_FOR_VOLUME,
    can_launch_3d_volume_render,
    get_datasets_for_subwindow,
    series_has_volume_geometry,
)


def test_reexports_match_source_module():
    assert MIN_SLICES_FOR_VOLUME is eligibility.MIN_SLICES_FOR_VOLUME
    assert _MIN_SLICES_FOR_VOLUME == eligibility.MIN_SLICES_FOR_VOLUME
    assert can_launch_3d_volume_render is eligibility.can_launch_3d_volume_render
    assert get_datasets_for_subwindow is eligibility.get_datasets_for_subwindow
    assert series_has_volume_geometry is eligibility.series_has_volume_geometry
