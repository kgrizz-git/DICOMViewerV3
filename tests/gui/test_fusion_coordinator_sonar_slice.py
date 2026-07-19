"""
Characterize FusionCoordinator contracts for the Sonar S3776 first slice.

Covers handle_fusion_enabled_changed, _update_base_display,
sync_ui_from_handler_state, _update_resampling_status, and
_auto_detect_fusion_candidates.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from gui.fusion_coordinator import FusionCoordinator


def _make_coordinator(
    *,
    studies: dict | None = None,
    study_uid: str = "study-1",
    base_uid: str = "base-1",
    overlay_uid: str = "overlay-1",
    check_notification_shown=None,
    mark_notification_shown=None,
) -> tuple[FusionCoordinator, MagicMock, MagicMock]:
    fusion_handler = MagicMock()
    fusion_handler.fusion_enabled = False
    fusion_handler.base_series_uid = base_uid
    fusion_handler.overlay_series_uid = overlay_uid
    fusion_handler.opacity = 0.4
    fusion_handler.threshold = 0.1
    fusion_handler.colormap = "Hot"
    fusion_handler.overlay_window = 100.0
    fusion_handler.overlay_level = 50.0
    fusion_handler.resampling_mode = "accurate"
    fusion_handler.interpolation_method = "linear"

    fusion_controls = MagicMock()
    fusion_controls._updating = False
    fusion_controls.opacity_slider = MagicMock()
    fusion_controls.opacity_value_label = MagicMock()
    fusion_controls.threshold_slider = MagicMock()
    fusion_controls.threshold_value_label = MagicMock()
    fusion_controls.colormap_combo = MagicMock()
    fusion_controls.colormap_combo.findText.return_value = 1
    fusion_controls.overlay_series_combo = MagicMock()
    fusion_controls.overlay_series_combo.count.return_value = 1
    fusion_controls.overlay_series_combo.itemData.return_value = overlay_uid

    coordinator = FusionCoordinator(
        fusion_handler=fusion_handler,
        fusion_processor=MagicMock(),
        fusion_controls=fusion_controls,
        get_current_studies=lambda: studies if studies is not None else {},
        get_current_study_uid=lambda: study_uid,
        get_current_series_uid=lambda: base_uid,
        get_current_slice_index=lambda: 0,
        request_display_update=MagicMock(),
        check_notification_shown=check_notification_shown,
        mark_notification_shown=mark_notification_shown,
    )
    return coordinator, fusion_handler, fusion_controls


def test_fusion_enabled_prompts_when_overlay_missing() -> None:
    coord, handler, _controls = _make_coordinator(overlay_uid="")
    with patch.object(coord, "_append_status") as status:
        coord.handle_fusion_enabled_changed(True)
    assert handler.fusion_enabled is True
    status.assert_called_once_with("Please select overlay series", severity="info")
    coord.request_display_update.assert_not_called()


def test_fusion_enabled_checks_frame_of_reference_and_updates() -> None:
    base_ds = SimpleNamespace(Modality="CT")
    overlay_ds = SimpleNamespace(Modality="PT")
    studies = {"study-1": {"base-1": [base_ds], "overlay-1": [overlay_ds]}}
    coord, handler, _controls = _make_coordinator(studies=studies)
    handler.check_frame_of_reference_match.return_value = True

    with (
        patch.object(coord, "_update_spatial_alignment") as align,
        patch.object(coord, "_update_resampling_status") as resampling,
        patch.object(coord, "_append_status") as status,
    ):
        coord.handle_fusion_enabled_changed(True)

    align.assert_called_once()
    resampling.assert_called_once()
    status.assert_called_once_with("Aligned (Frame of Reference)", severity="info")
    coord.request_display_update.assert_called_once()


def test_fusion_disabled_appends_disabled_status() -> None:
    coord, handler, _controls = _make_coordinator()
    with patch.object(coord, "_append_status") as status:
        coord.handle_fusion_enabled_changed(False)
    assert handler.fusion_enabled is False
    status.assert_called_once_with("Disabled", severity="info")
    coord.request_display_update.assert_called_once()


def test_update_base_display_formats_series_metadata() -> None:
    ds = SimpleNamespace(SeriesNumber=3, SeriesDescription="Axial", Modality="CT")
    studies = {"study-1": {"base-1": [ds]}}
    coord, _handler, controls = _make_coordinator(studies=studies)

    coord._update_base_display("base-1")

    controls.set_base_display.assert_called_once_with("S3 - CT - Axial")


def test_update_base_display_falls_back_when_series_missing() -> None:
    coord, _handler, controls = _make_coordinator(studies={"study-1": {}})
    coord._update_base_display("missing-series-uid-abcdefgh")
    controls.set_base_display.assert_called_once_with("missing-series-uid-a")


def test_sync_ui_from_handler_state_writes_controls() -> None:
    coord, handler, controls = _make_coordinator()
    with patch.object(coord, "_update_base_display") as base_display:
        coord.sync_ui_from_handler_state()

    controls.set_fusion_enabled.assert_called_once_with(False)
    controls.opacity_slider.setValue.assert_called_once_with(40)
    controls.threshold_slider.setValue.assert_called_once_with(10)
    controls.colormap_combo.setCurrentIndex.assert_called_once_with(1)
    controls.set_overlay_window_level.assert_called_once_with(100.0, 50.0)
    controls.set_resampling_mode.assert_called_once_with("accurate")
    controls.set_interpolation_method.assert_called_once_with("linear")
    base_display.assert_called_once_with(handler.base_series_uid)
    controls.overlay_series_combo.setCurrentIndex.assert_called_once_with(0)
    assert controls._updating is False


def test_update_resampling_status_enables_offsets_for_2d() -> None:
    base_ds = SimpleNamespace()
    overlay_ds = SimpleNamespace()
    studies = {"study-1": {"base-1": [base_ds], "overlay-1": [overlay_ds]}}
    coord, handler, controls = _make_coordinator(studies=studies)
    handler.get_resampling_status.return_value = ("2D", "aligned")
    handler._should_use_3d_resampling.return_value = (False, None)
    handler.get_actual_resampling_mode_used.return_value = False
    handler.resampling_mode = "fast"
    handler.image_resampler.needs_resampling.return_value = (False, None)

    with patch.object(coord, "_append_status"):
        coord._update_resampling_status()

    controls.set_offset_controls_enabled.assert_called_once_with(True)
    controls.set_offset_status_text.assert_called_once_with(False)
    controls.set_resampling_status.assert_called_once_with("2D", "aligned", False, "")


def test_update_resampling_status_warns_on_3d_fallback() -> None:
    base_ds = SimpleNamespace()
    overlay_ds = SimpleNamespace()
    studies = {"study-1": {"base-1": [base_ds], "overlay-1": [overlay_ds]}}
    coord, handler, controls = _make_coordinator(studies=studies)
    handler.get_resampling_status.return_value = ("2D", "fallback")
    handler._should_use_3d_resampling.return_value = (True, None)
    handler.get_actual_resampling_mode_used.return_value = False
    handler.get_resampling_failure_reason.return_value = "timeout"

    with patch.object(coord, "_append_status") as status:
        coord._update_resampling_status()

    status.assert_called_once()
    assert "3D resampling failed" in status.call_args[0][0]
    assert handler.resampling_mode == "fast"
    controls.set_resampling_mode.assert_called_once_with("fast")
    args = controls.set_resampling_status.call_args[0]
    assert args[2] is True
    assert "timeout" in args[3]


def test_auto_detect_suggests_compatible_pet_ct_pair() -> None:
    pet = SimpleNamespace(Modality="PT")
    ct = SimpleNamespace(Modality="CT")
    studies = {
        "study-1": {
            "pet-1": [pet],
            "ct-1": [ct],
        }
    }
    mark = MagicMock()
    coord, handler, _controls = _make_coordinator(
        studies=studies,
        check_notification_shown=MagicMock(return_value=False),
        mark_notification_shown=mark,
    )
    handler.check_frame_of_reference_match.return_value = True
    series_list = [("pet-1", "PET"), ("ct-1", "CT")]

    with patch.object(coord, "_suggest_fusion") as suggest:
        coord._auto_detect_fusion_candidates(studies, "study-1", series_list)

    suggest.assert_called_once_with("ct-1", "CT", "pet-1", "PET")
    mark.assert_called_once_with("study-1")


def test_auto_detect_skips_when_already_notified() -> None:
    studies = {"study-1": {"a": [SimpleNamespace(Modality="PT")]}}
    coord, _handler, _controls = _make_coordinator(
        studies=studies,
        check_notification_shown=MagicMock(return_value=True),
    )
    with patch.object(coord, "_suggest_fusion") as suggest:
        coord._auto_detect_fusion_candidates(
            studies, "study-1", [("a", "PET"), ("b", "CT")]
        )
    suggest.assert_not_called()


def test_finish_overlay_load_warns_on_duplicate_locations() -> None:
    ds = SimpleNamespace()
    studies = {"study-1": {"overlay-1": [ds]}}
    coord, handler, controls = _make_coordinator(studies=studies)
    handler.has_duplicate_locations.return_value = (True, 2)
    handler.fusion_enabled = False

    with (
        patch.object(coord, "_update_resampling_status") as resampling,
        patch.object(coord, "_update_spatial_alignment") as align,
        patch.object(coord, "_append_status") as status,
        patch(
            "core.dicom_processor.DICOMProcessor.get_rescale_parameters",
            return_value=(None, None, None),
        ),
        patch(
            "core.dicom_processor.DICOMProcessor.get_series_pixel_value_range",
            return_value=(0.0, 100.0),
        ),
        patch(
            "core.dicom_processor.DICOMProcessor.get_window_level_from_dataset",
            return_value=(40.0, 80.0, False),
        ),
    ):
        coord._finish_overlay_series_load()

    status.assert_called()
    assert "same location" in status.call_args[0][0]
    assert handler.overlay_window == 80.0
    assert handler.overlay_level == 40.0
    controls.set_overlay_window_level.assert_called_once_with(80.0, 40.0)
    resampling.assert_called_once()
    align.assert_called_once()


def test_finish_overlay_load_noop_without_overlay_uid() -> None:
    coord, handler, _controls = _make_coordinator(overlay_uid="")
    with (
        patch.object(coord, "_update_resampling_status") as resampling,
        patch.object(coord, "_update_spatial_alignment") as align,
    ):
        coord._finish_overlay_series_load()
    resampling.assert_not_called()
    align.assert_not_called()
    handler.has_duplicate_locations.assert_not_called()


def test_get_fused_image_returns_none_when_disabled() -> None:
    from PIL import Image

    coord, handler, _controls = _make_coordinator()
    handler.fusion_enabled = False
    result = coord.get_fused_image(Image.new("L", (4, 4)), [SimpleNamespace()], 0)
    assert result is None


def test_get_fused_image_blends_when_overlay_available() -> None:
    import numpy as np
    from PIL import Image

    ds = SimpleNamespace()
    studies = {"study-1": {"overlay-1": [ds]}}
    coord, handler, controls = _make_coordinator(studies=studies)
    handler.fusion_enabled = True
    handler._should_use_3d_resampling.return_value = (False, None)
    handler.interpolate_overlay_slice.return_value = np.ones((4, 4), dtype=np.float32)
    handler.get_actual_resampling_mode_used.return_value = False
    handler.get_pixel_spacing.return_value = (1.0, 1.0)
    handler.find_matching_slice.return_value = (0, None)
    controls.get_overlay_window_level.return_value = (100.0, 50.0)
    controls.get_translation_offset.return_value = (1.0, 2.0)
    fused_pil = Image.new("RGB", (4, 4))
    coord.fusion_processor.create_fusion_image.return_value = np.zeros(
        (4, 4, 3), dtype=np.uint8
    )
    coord.fusion_processor.convert_array_to_pil_image.return_value = fused_pil

    result = coord.get_fused_image(Image.new("L", (4, 4)), [ds], 0)

    assert result is fused_pil
    coord.fusion_processor.create_fusion_image.assert_called_once()
    call_kwargs = coord.fusion_processor.create_fusion_image.call_args.kwargs
    assert call_kwargs["translation_offset"] == (1.0, 2.0)
    assert call_kwargs["skip_2d_resize"] is False


def test_get_fused_image_sets_coverage_hint_when_no_overlay() -> None:
    from PIL import Image

    from core.fusion_handler import OverlayMatchResult

    ds = SimpleNamespace()
    studies = {"study-1": {"overlay-1": [ds]}}
    coord, handler, controls = _make_coordinator(studies=studies)
    handler.fusion_enabled = True
    handler._should_use_3d_resampling.return_value = (False, None)
    handler.interpolate_overlay_slice.return_value = None
    handler._last_overlay_match_result = OverlayMatchResult.above_stack

    result = coord.get_fused_image(Image.new("L", (4, 4)), [ds], 0)

    assert result is None
    controls.set_status.assert_called()
    assert "outside overlay" in controls.set_status.call_args[0][0]


def test_spatial_alignment_calculates_and_caches_offset() -> None:
    base_ds = SimpleNamespace()
    overlay_ds = SimpleNamespace()
    studies = {"study-1": {"base-1": [base_ds], "overlay-1": [overlay_ds]}}
    coord, handler, controls = _make_coordinator(studies=studies)
    handler.get_alignment.return_value = None
    handler.get_pixel_spacing_with_source.side_effect = [
        ((1.0, 1.0), "PixelSpacing"),
        ((2.0, 2.0), "PixelSpacing"),
    ]
    handler.calculate_translation_offset.return_value = (5.0, -3.0)
    controls.has_user_modified_offset.return_value = False

    with patch.object(coord, "_update_resampling_status"):
        coord._update_spatial_alignment()

    controls.set_scaling_factors.assert_called_once_with(2.0, 2.0)
    controls.set_calculated_offset.assert_called_once_with(5.0, -3.0)
    handler.set_alignment.assert_called_once_with(
        "base-1", "overlay-1", (2.0, 2.0), (5.0, -3.0)
    )
