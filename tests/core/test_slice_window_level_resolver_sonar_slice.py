"""
Characterization tests for series-transition W/L helpers (Sonar S3776 slice).

Covers study/series membership checks extracted from
``resolve_window_level_for_series_transition``.
"""

from __future__ import annotations

from core.slice_window_level_resolver import _series_in_current_studies


def test_series_in_current_studies_membership() -> None:
    studies = {"study1": {"series_a": [object()]}}
    assert _series_in_current_studies(studies, "study1", "series_a") is True
    assert _series_in_current_studies(studies, "study1", "missing") is False
    assert _series_in_current_studies(studies, "missing", "series_a") is False
    assert _series_in_current_studies({}, "study1", "series_a") is False
    assert _series_in_current_studies(studies, "", "series_a") is False
