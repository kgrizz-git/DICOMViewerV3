"""
Tests for ``core.privacy_controller`` — privacy mode propagation.

Pure-Python tests; no Qt or DICOM files required.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from core.privacy_controller import PrivacyController

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_controller(
    *,
    subwindow_managers=None,
    all_subwindows=None,
    focused_idx=0,
    subwindow_data=None,
):
    if subwindow_managers is None:
        subwindow_managers = {}
    if all_subwindows is None:
        all_subwindows = []
    if subwindow_data is None:
        subwindow_data = {}

    config_manager = MagicMock()
    metadata_controller = MagicMock()
    overlay_manager = MagicMock()
    dialog_coordinator = MagicMock()

    ctrl = PrivacyController(
        config_manager=config_manager,
        metadata_controller=metadata_controller,
        overlay_manager=overlay_manager,
        dialog_coordinator=dialog_coordinator,
        get_subwindow_managers=lambda: subwindow_managers,
        get_all_subwindows=lambda: all_subwindows,
        get_focused_subwindow_index=lambda: focused_idx,
        get_subwindow_data=lambda: subwindow_data,
    )
    return ctrl, metadata_controller, overlay_manager, dialog_coordinator


# ---------------------------------------------------------------------------
# Tests — apply_privacy propagation
# ---------------------------------------------------------------------------

class TestApplyPrivacy:
    def test_propagates_to_metadata_controller(self):
        ctrl, meta, overlay, dialog = _make_controller()
        ctrl.apply_privacy(True)
        meta.set_privacy_mode.assert_called_once_with(True)

    def test_propagates_false_to_metadata_controller(self):
        ctrl, meta, overlay, _ = _make_controller()
        ctrl.apply_privacy(False)
        meta.set_privacy_mode.assert_called_once_with(False)

    def test_propagates_to_overlay_manager(self):
        ctrl, _, overlay, _ = _make_controller()
        ctrl.apply_privacy(True)
        overlay.set_privacy_mode.assert_called_once_with(True)

    def test_propagates_to_dialog_coordinator(self):
        ctrl, _, _, dialog = _make_controller()
        ctrl.apply_privacy(True)
        dialog.apply_privacy_mode.assert_called_once_with(True)

    def test_propagates_to_per_subwindow_overlay_managers(self):
        per_overlay = MagicMock()
        managers = {0: {"overlay_manager": per_overlay}}
        ctrl, _, _, _ = _make_controller(subwindow_managers=managers)
        ctrl.apply_privacy(True)
        per_overlay.set_privacy_mode.assert_called_once_with(True)

    def test_propagates_to_image_viewer_on_subwindow(self):
        subwindow = MagicMock()
        subwindow.image_viewer = MagicMock()
        ctrl, _, _, _ = _make_controller(
            all_subwindows=[subwindow],
            subwindow_data={0: object()},
        )
        ctrl.apply_privacy(True)
        subwindow.image_viewer.set_privacy_view_state.assert_called_once_with(True)

    def test_subwindow_without_image_viewer_is_skipped(self):
        """apply_privacy should not crash if image_viewer is None."""
        subwindow = MagicMock()
        subwindow.image_viewer = None
        ctrl, _, _, _ = _make_controller(all_subwindows=[subwindow])
        ctrl.apply_privacy(True)  # should not raise

    def test_none_subwindow_is_skipped(self):
        ctrl, _, _, _ = _make_controller(all_subwindows=[None])
        ctrl.apply_privacy(True)  # should not raise

    def test_metadata_controller_without_set_privacy_mode_is_skipped(self):
        """Controller tolerates missing set_privacy_mode attribute."""
        config = MagicMock()
        meta = object()  # no set_privacy_mode
        overlay = MagicMock()
        ctrl = PrivacyController(
            config_manager=config,
            metadata_controller=meta,
            overlay_manager=overlay,
            get_subwindow_managers=lambda: {},
            get_all_subwindows=lambda: [],
            get_focused_subwindow_index=lambda: 0,
            get_subwindow_data=lambda: {},
        )
        ctrl.apply_privacy(True)  # should not raise


# ---------------------------------------------------------------------------
# Tests — refresh_overlays
# ---------------------------------------------------------------------------

class TestRefreshOverlays:
    def test_refresh_calls_display_slice_for_loaded_subwindow(self):
        """refresh_overlays calls slice_display_manager.display_slice for a loaded subwindow."""
        sdm = MagicMock()
        sdm.current_dataset = MagicMock()
        sdm.current_studies = [MagicMock()]
        sdm.current_study_uid = "uid-1"
        sdm.current_series_uid = "uid-2"
        sdm.current_slice_index = 0

        subwindow = MagicMock()
        subwindow.image_viewer = MagicMock()

        managers = {0: {"slice_display_manager": sdm}}
        ctrl, _, _, _ = _make_controller(
            all_subwindows=[subwindow],
            subwindow_managers=managers,
            subwindow_data={0: object()},
            focused_idx=0,
        )
        ctrl.refresh_overlays()

        sdm.display_slice.assert_called_once()
        _, kwargs = sdm.display_slice.call_args
        assert kwargs.get("update_metadata") is True  # focused subwindow

    def test_refresh_skips_subwindow_without_loaded_data(self):
        """Subwindow with no entry in subwindow_data is skipped."""
        sdm = MagicMock()
        subwindow = MagicMock()
        subwindow.image_viewer = MagicMock()

        managers = {0: {"slice_display_manager": sdm}}
        ctrl, _, _, _ = _make_controller(
            all_subwindows=[subwindow],
            subwindow_managers=managers,
            subwindow_data={},  # empty — subwindow 0 not loaded
        )
        ctrl.refresh_overlays()

        sdm.display_slice.assert_not_called()

    def test_refresh_sets_update_metadata_false_for_non_focused(self):
        """Non-focused subwindow refresh uses update_metadata=False."""
        sdm = MagicMock()
        sdm.current_dataset = MagicMock()
        sdm.current_studies = []
        sdm.current_study_uid = "uid"
        sdm.current_series_uid = "sid"
        sdm.current_slice_index = 0

        subwindow = MagicMock()
        subwindow.image_viewer = MagicMock()

        managers = {0: {"slice_display_manager": sdm}}
        ctrl, _, _, _ = _make_controller(
            all_subwindows=[subwindow],
            subwindow_managers=managers,
            subwindow_data={0: object()},
            focused_idx=99,  # focus is elsewhere
        )
        ctrl.refresh_overlays()

        _, kwargs = sdm.display_slice.call_args
        assert kwargs.get("update_metadata") is False

    def test_refresh_skips_sdm_with_none_current_dataset(self):
        """If slice_display_manager.current_dataset is None, skip that subwindow."""
        sdm = MagicMock()
        sdm.current_dataset = None  # no data

        subwindow = MagicMock()
        subwindow.image_viewer = MagicMock()

        managers = {0: {"slice_display_manager": sdm}}
        ctrl, _, _, _ = _make_controller(
            all_subwindows=[subwindow],
            subwindow_managers=managers,
            subwindow_data={0: object()},
        )
        ctrl.refresh_overlays()

        sdm.display_slice.assert_not_called()

    def test_refresh_falls_back_to_overlay_manager_on_exception(self):
        """If display_slice raises, falls back to overlay_manager.create_overlay_items."""
        sdm = MagicMock()
        sdm.current_dataset = MagicMock()
        sdm.current_studies = []
        sdm.current_study_uid = "u"
        sdm.current_series_uid = "s"
        sdm.current_slice_index = 0
        sdm.display_slice.side_effect = RuntimeError("display fail")
        sdm.get_multiframe_overlay_context.return_value = None

        overlay_mgr = MagicMock()
        subwindow = MagicMock()
        subwindow.image_viewer = MagicMock()
        subwindow.image_viewer.scene = MagicMock()

        managers = {0: {"slice_display_manager": sdm, "overlay_manager": overlay_mgr}}
        ctrl, _, _, _ = _make_controller(
            all_subwindows=[subwindow],
            subwindow_managers=managers,
            subwindow_data={0: object()},
        )

        with patch("core.dicom_parser.DICOMParser"):
            ctrl.refresh_overlays()

        overlay_mgr.create_overlay_items.assert_called_once()
