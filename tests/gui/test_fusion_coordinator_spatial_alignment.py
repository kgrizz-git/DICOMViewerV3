"""
Regression tests for FusionCoordinator._update_spatial_alignment cache writes.

Covers missing pixel spacing and missing ImagePositionPatient so the alignment
cache still receives the documented fallback scale/offset tuples, while
user-modified offsets are not overwritten.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

from gui.fusion_coordinator import FusionCoordinator


def _make_coordinator(
    *,
    studies: dict,
    study_uid: str = "study-1",
    base_uid: str = "base-1",
    overlay_uid: str = "overlay-1",
    user_modified_offset: bool = False,
) -> tuple[FusionCoordinator, MagicMock, MagicMock]:
    """Build a coordinator with fake handler/controls for spatial-alignment tests."""
    fusion_handler = MagicMock()
    fusion_handler.base_series_uid = base_uid
    fusion_handler.overlay_series_uid = overlay_uid
    fusion_handler.get_alignment.return_value = None

    fusion_controls = MagicMock()
    fusion_controls.has_user_modified_offset.return_value = user_modified_offset
    fusion_controls.status_label = None

    coordinator = FusionCoordinator(
        fusion_handler=fusion_handler,
        fusion_processor=MagicMock(),
        fusion_controls=fusion_controls,
        get_current_studies=lambda: studies,
        get_current_study_uid=lambda: study_uid,
        get_current_series_uid=lambda: base_uid,
        get_current_slice_index=lambda: 0,
        request_display_update=MagicMock(),
    )
    # Avoid exercising the full resampling-status path in these unit tests.
    coordinator._update_resampling_status = MagicMock()  # type: ignore[method-assign]
    return coordinator, fusion_handler, fusion_controls


def test_missing_pixel_spacing_caches_identity_scale_and_zero_offset() -> None:
    base_ds = SimpleNamespace()
    overlay_ds = SimpleNamespace()
    studies = {"study-1": {"base-1": [base_ds], "overlay-1": [overlay_ds]}}
    coordinator, fusion_handler, fusion_controls = _make_coordinator(studies=studies)

    fusion_handler.get_pixel_spacing_with_source.side_effect = [
        (None, None),
        (None, None),
    ]

    coordinator._update_spatial_alignment()

    fusion_handler.set_alignment.assert_called_once_with(
        "base-1",
        "overlay-1",
        (1.0, 1.0),
        (0.0, 0.0),
    )
    fusion_controls.set_scaling_factors.assert_called_once_with(1.0, 1.0)
    fusion_controls.set_calculated_offset.assert_called_once_with(0.0, 0.0)
    fusion_handler.calculate_translation_offset.assert_not_called()


def test_missing_image_position_caches_zero_offset() -> None:
    base_ds = SimpleNamespace()
    overlay_ds = SimpleNamespace()
    studies = {"study-1": {"base-1": [base_ds], "overlay-1": [overlay_ds]}}
    coordinator, fusion_handler, fusion_controls = _make_coordinator(studies=studies)

    base_spacing = (1.0, 1.0)
    overlay_spacing = (2.0, 2.0)
    fusion_handler.get_pixel_spacing_with_source.side_effect = [
        (base_spacing, "PixelSpacing"),
        (overlay_spacing, "PixelSpacing"),
    ]
    fusion_handler.calculate_translation_offset.return_value = None

    coordinator._update_spatial_alignment()

    fusion_handler.set_alignment.assert_called_once_with(
        "base-1",
        "overlay-1",
        (2.0, 2.0),
        (0.0, 0.0),
    )
    fusion_controls.set_scaling_factors.assert_called_once_with(2.0, 2.0)
    fusion_controls.set_calculated_offset.assert_called_once_with(0.0, 0.0)


def test_user_modified_offset_is_not_overwritten_when_spacing_missing() -> None:
    base_ds = SimpleNamespace()
    overlay_ds = SimpleNamespace()
    studies = {"study-1": {"base-1": [base_ds], "overlay-1": [overlay_ds]}}
    coordinator, fusion_handler, fusion_controls = _make_coordinator(
        studies=studies,
        user_modified_offset=True,
    )
    fusion_handler.get_pixel_spacing_with_source.side_effect = [
        (None, None),
        (None, None),
    ]

    coordinator._update_spatial_alignment()

    fusion_handler.set_alignment.assert_called_once_with(
        "base-1",
        "overlay-1",
        (1.0, 1.0),
        (0.0, 0.0),
    )
    fusion_controls.set_calculated_offset.assert_not_called()


def test_cached_alignment_skips_recalculation() -> None:
    studies = {"study-1": {"base-1": [SimpleNamespace()], "overlay-1": [SimpleNamespace()]}}
    coordinator, fusion_handler, fusion_controls = _make_coordinator(studies=studies)
    fusion_handler.get_alignment.return_value = {
        "scale": (1.5, 1.5),
        "offset": (3.0, 4.0),
    }

    coordinator._update_spatial_alignment()

    fusion_controls.set_scaling_factors.assert_called_once_with(1.5, 1.5)
    fusion_controls.set_calculated_offset.assert_called_once_with(3.0, 4.0)
    fusion_handler.set_alignment.assert_not_called()
    fusion_handler.get_pixel_spacing_with_source.assert_not_called()
