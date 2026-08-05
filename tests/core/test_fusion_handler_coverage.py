"""Focused coverage tests for FusionHandler state and interpolation paths."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import numpy as np
from pydicom.dataset import Dataset

from core import fusion_handler as fusion_module
from core.fusion_handler import FusionHandler, OverlayMatchResult


def _slice(location: float, pixels: np.ndarray | None = None) -> SimpleNamespace:
    data = SimpleNamespace(SliceLocation=location)
    if pixels is not None:
        data.pixel_array = pixels
    return data


def test_series_setters_invalidate_relevant_caches_and_tracking() -> None:
    handler = FusionHandler()
    handler.base_series_uid = "old-base"
    handler.overlay_series_uid = "old-overlay"
    handler.set_alignment("old-base", "other", (1.0, 1.0), (0.0, 0.0))
    handler.set_alignment("other", "old-overlay", (1.0, 1.0), (0.0, 0.0))
    handler._slice_location_cache["cached"] = [(0, 1.0)]
    handler._resampling_decision_cache = (True, "cached")
    handler._resampling_decision_cache_key = ("old-base", "old-overlay")
    handler._actual_resampling_mode_used = True
    handler._resampling_failure_reason = "old failure"

    handler.set_base_series("new-base")
    handler.set_overlay_series("new-overlay")

    assert handler.base_series_uid == "new-base"
    assert handler.overlay_series_uid == "new-overlay"
    assert handler._alignment_cache == {}
    assert handler._slice_location_cache == {}
    assert handler._resampling_decision_cache is None
    assert handler._resampling_decision_cache_key is None
    assert handler.get_actual_resampling_mode_used() is None
    assert handler.get_resampling_failure_reason() is None


def test_duplicate_locations_and_available_series_are_classified_and_sorted() -> None:
    handler = FusionHandler()
    assert handler.has_duplicate_locations([]) == (False, 0)
    assert handler.has_duplicate_locations([_slice(1.0)]) == (False, 0)
    assert handler.has_duplicate_locations(
        [_slice(1.0), _slice(1.005), _slice(2.0)]
    ) == (
        True,
        1,
    )

    first = SimpleNamespace(
        SeriesNumber="10", Modality="CT", SeriesDescription="Anatomy"
    )
    second = SimpleNamespace(SeriesNumber="2", Modality="PT", SeriesDescription="PET")
    unnamed = SimpleNamespace()
    studies = {
        "study": {
            "late": [first],
            "early": [second],
            "empty": [],
            "uid-only": [unnamed],
        }
    }

    assert handler.get_available_series_for_fusion({}, "study") == []
    assert handler.get_available_series_for_fusion(studies, "study") == [
        ("early", "S2 - PT - PET"),
        ("late", "S10 - CT - Anatomy"),
        ("uid-only", "uid-only"),
    ]


def test_resampling_mode_uses_cached_compatibility_but_honors_user_choice() -> None:
    handler = FusionHandler()
    handler.set_base_series("base")
    handler.set_overlay_series("overlay")
    handler.image_resampler = MagicMock()
    handler.image_resampler.needs_resampling.return_value = (False, "matching geometry")
    base = [_slice(0.0)]
    overlay = [_slice(0.0)]

    handler.resampling_mode = "fast"
    assert handler._should_use_3d_resampling(base, overlay) == (
        False,
        "User selected Fast Mode (2D)",
    )
    assert handler._should_use_3d_resampling(base, overlay) == (
        False,
        "User selected Fast Mode (2D)",
    )
    handler.image_resampler.needs_resampling.assert_called_once_with(overlay, base)

    handler.set_resampling_mode("high_accuracy")
    assert handler._should_use_3d_resampling(base, overlay) == (
        True,
        "User selected High Accuracy Mode (3D)",
    )
    assert handler.image_resampler.needs_resampling.call_count == 2

    handler.set_resampling_mode("unexpected")
    assert handler._should_use_3d_resampling(base, overlay) == (
        True,
        "Defaulting to High Accuracy Mode (3D)",
    )


def test_interpolate_returns_none_before_resampling_outside_overlay_stack() -> None:
    handler = FusionHandler()
    handler.image_resampler = MagicMock()

    result = handler.interpolate_overlay_slice(
        0,
        [_slice(-1.0)],
        [_slice(0.0, np.array([[1]], dtype=np.uint16))],
    )

    assert result is None
    assert handler._last_overlay_match_result is OverlayMatchResult.below_stack
    handler.image_resampler.get_resampled_slice.assert_not_called()


def test_interpolate_uses_successful_3d_resampling() -> None:
    handler = FusionHandler()
    handler.set_base_series("base")
    handler.set_overlay_series("overlay")
    handler.resampling_mode = "high_accuracy"
    handler.image_resampler = MagicMock()
    handler.image_resampler.needs_resampling.return_value = (True, "different geometry")
    handler.image_resampler.get_resampled_slice.return_value = np.array(
        [[5]], dtype=np.int16
    )

    result = handler.interpolate_overlay_slice(
        0,
        [_slice(0.0)],
        [_slice(0.0, np.array([[1]], dtype=np.uint16))],
    )

    assert result is not None
    assert result.dtype == np.float32
    assert np.array_equal(result, np.array([[5]], dtype=np.float32))
    assert handler.get_actual_resampling_mode_used() is True
    assert handler.get_resampling_failure_reason() is None
    handler.image_resampler.get_resampled_slice.assert_called_once()


def test_interpolate_falls_back_to_exact_2d_when_3d_returns_none(monkeypatch) -> None:
    handler = FusionHandler()
    handler.resampling_mode = "high_accuracy"
    handler.image_resampler = MagicMock()
    handler.image_resampler.needs_resampling.return_value = (True, "different geometry")
    handler.image_resampler.get_resampled_slice.return_value = None
    monkeypatch.setattr(
        fusion_module.DICOMProcessor,
        "get_rescale_parameters",
        lambda _dataset: (None, None, None),
    )

    result = handler.interpolate_overlay_slice(
        0,
        [_slice(0.0)],
        [_slice(0.0, np.array([[7]], dtype=np.uint16))],
    )

    assert np.array_equal(result, np.array([[7]], dtype=np.float32))
    assert handler.get_actual_resampling_mode_used() is False
    assert handler.get_resampling_failure_reason() == "3D resampling returned None"


def test_interpolate_blends_2d_slices_and_rejects_shape_mismatch(monkeypatch) -> None:
    handler = FusionHandler()
    handler.resampling_mode = "fast"
    handler.image_resampler = MagicMock()
    handler.image_resampler.needs_resampling.return_value = (False, "matching geometry")
    monkeypatch.setattr(
        fusion_module.DICOMProcessor,
        "get_rescale_parameters",
        lambda _dataset: (None, None, None),
    )
    base = [_slice(5.0)]
    lower = _slice(0.0, np.array([[0]], dtype=np.uint16))
    upper = _slice(10.0, np.array([[10]], dtype=np.uint16))

    result = handler.interpolate_overlay_slice(0, base, [lower, upper])

    assert np.array_equal(result, np.array([[5]], dtype=np.float32))
    mismatched = _slice(10.0, np.array([[10, 11]], dtype=np.uint16))
    fallback = handler.interpolate_overlay_slice(0, base, [lower, mismatched])
    assert np.array_equal(fallback, np.array([[0]], dtype=np.float32))


def test_calculate_translation_offset() -> None:
    handler = FusionHandler()
    base = Dataset()
    base.ImagePositionPatient = [10.0, 20.0, 30.0]
    base.ImageOrientationPatient = [1.0, 0.0, 0.0, 0.0, 1.0, 0.0]
    overlay = Dataset()
    overlay.ImagePositionPatient = [18.0, 26.0, 99.0]

    assert handler.calculate_translation_offset(
        base, overlay, (2.0, 4.0), (2.0, 4.0)
    ) == (
        2.0,
        3.0,
    )


def test_alignment_guards() -> None:
    handler = FusionHandler()
    assert handler.get_alignment(None, "overlay") is None
    handler.set_alignment("same", "same", None, None)
    assert handler.get_alignment("same", "same") is None


def test_get_resampling_status() -> None:
    handler = FusionHandler()
    assert handler.get_resampling_status([], [_slice(0.0)]) == (
        "Disabled",
        "No datasets available",
    )
    handler.image_resampler = MagicMock()
    handler.image_resampler.needs_resampling.return_value = (
        True,
        "orientation differs",
    )
    handler.resampling_mode = "high_accuracy"
    handler._actual_resampling_mode_used = False
    handler._resampling_failure_reason = "3D failed"
    assert handler.get_resampling_status([_slice(0.0)], [_slice(0.0)]) == (
        "2D Mode (3D Failed)",
        "3D failed, using 2D fallback",
    )
