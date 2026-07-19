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
