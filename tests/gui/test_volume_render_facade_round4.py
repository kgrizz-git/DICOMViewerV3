"""Round-4 tests for gui.volume_render_facade (lightweight fakes)."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

from gui.volume_render_facade import VolumeRenderFacade

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class _FakeApp:
    """Minimal app stub consumed by VolumeRenderFacade."""

    def __init__(
        self,
        *,
        subwindow_data: dict[int, dict] | None = None,
        focused_idx: int = 0,
        main_window: Any = None,
    ) -> None:
        self.subwindow_data: dict[int, dict] = subwindow_data or {}
        self._focused_idx = focused_idx
        self.main_window = main_window or MagicMock()
        self.config_manager = None

    def get_focused_subwindow_index(self) -> int:
        return self._focused_idx


class _FakeDialog:
    """Stub for VolumeRenderDialog with minimal lifecycle surface."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self._visible = True
        self._shown = False
        self.raise_called = False
        self.destroyed = MagicMock()

    def show(self) -> None:
        self._shown = True

    def isVisible(self) -> bool:
        return self._visible

    def raise_(self) -> None:
        self.raise_called = True

    def activateWindow(self) -> None:
        pass

    def close(self) -> bool:
        self._visible = False
        return True

    def hide(self) -> None:
        self._visible = False


class _NonCloseableDialog(_FakeDialog):
    """Dialog whose close() returns False (e.g. user cancelled)."""

    def close(self) -> bool:
        return False


class _RuntimeErrorDialog(_FakeDialog):
    """Dialog that raises RuntimeError on close (already deleted by Qt)."""

    def close(self) -> bool:
        raise RuntimeError("wrapped C/C++ object deleted")


# ---------------------------------------------------------------------------
# _get_series_description  (static, lines 138-153)
# ---------------------------------------------------------------------------

class TestGetSeriesDescription:
    def test_empty_datasets_returns_empty(self) -> None:
        assert VolumeRenderFacade._get_series_description([]) == ""

    def test_no_dicom_attrs_returns_unknown(self) -> None:
        assert VolumeRenderFacade._get_series_description([object()]) == "Unknown"

    def test_series_description_only(self) -> None:
        ds = MagicMock(spec=["SeriesDescription"])
        ds.SeriesDescription = "CT Head"
        assert VolumeRenderFacade._get_series_description([ds]) == "CT Head"

    def test_modality_only(self) -> None:
        ds = MagicMock(spec=["Modality"])
        ds.Modality = "CT"
        assert VolumeRenderFacade._get_series_description([ds]) == "CT"

    def test_both_description_and_modality(self) -> None:
        ds = MagicMock(spec=["SeriesDescription", "Modality"])
        ds.SeriesDescription = "CT Head"
        ds.Modality = "CT"
        assert VolumeRenderFacade._get_series_description([ds]) == "CT Head - CT"

    def test_empty_string_attrs_count_as_false(self) -> None:
        ds = MagicMock(spec=["SeriesDescription", "Modality"])
        ds.SeriesDescription = ""
        ds.Modality = ""
        assert VolumeRenderFacade._get_series_description([ds]) == "Unknown"


# ---------------------------------------------------------------------------
# _get_series_key  (lines 102-109)
# ---------------------------------------------------------------------------

class TestGetSeriesKey:
    def test_returns_combined_key(self) -> None:
        app = _FakeApp(subwindow_data={0: {"study_uid": "SU1", "series_uid": "SE1"}})
        facade = VolumeRenderFacade(app)
        assert facade._get_series_key(0) == "SU1|SE1"

    def test_returns_none_when_no_study_uid(self) -> None:
        app = _FakeApp(subwindow_data={0: {"series_uid": "SE1"}})
        facade = VolumeRenderFacade(app)
        assert facade._get_series_key(0) is None

    def test_returns_none_when_no_series_uid(self) -> None:
        app = _FakeApp(subwindow_data={0: {"study_uid": "SU1"}})
        facade = VolumeRenderFacade(app)
        assert facade._get_series_key(0) is None

    def test_returns_none_when_idx_missing(self) -> None:
        app = _FakeApp()
        facade = VolumeRenderFacade(app)
        assert facade._get_series_key(99) is None

    def test_returns_none_when_data_empty(self) -> None:
        app = _FakeApp(subwindow_data={0: {}})
        facade = VolumeRenderFacade(app)
        assert facade._get_series_key(0) is None


# ---------------------------------------------------------------------------
# launch_3d_view — guard / delegation branches (lines 34-100)
# ---------------------------------------------------------------------------

class TestLaunch3dView:
    @patch("gui.volume_render_facade.can_launch_3d_volume_render", return_value=(False, "vtk not installed"))
    @patch("gui.volume_render_facade.QMessageBox")
    def test_vtk_missing_shows_warning(self, mock_qbox, mock_eligible) -> None:
        facade = VolumeRenderFacade(_FakeApp())
        facade.launch_3d_view(subwindow_idx=0)
        mock_qbox.warning.assert_called_once()
        mock_qbox.information.assert_not_called()

    @patch("gui.volume_render_facade.can_launch_3d_volume_render", return_value=(False, "Requires at least 3 slices"))
    @patch("gui.volume_render_facade.QMessageBox")
    def test_ineligible_non_vtk_shows_information(self, mock_qbox, mock_eligible) -> None:
        facade = VolumeRenderFacade(_FakeApp())
        facade.launch_3d_view(subwindow_idx=0)
        mock_qbox.information.assert_called_once()
        mock_qbox.warning.assert_not_called()

    @patch("gui.volume_render_facade.can_launch_3d_volume_render", return_value=(True, "ok"))
    @patch("gui.volume_render_facade.get_datasets_for_subwindow", return_value=["d1", "d2", "d3"])
    @patch("gui.volume_render_facade.VolumeRenderDialog")
    def test_success_with_explicit_idx(self, mock_dlg_cls, mock_get, mock_eligible) -> None:
        app = _FakeApp(subwindow_data={5: {"study_uid": "SU", "series_uid": "SE"}})
        facade = VolumeRenderFacade(app)
        facade.launch_3d_view(subwindow_idx=5)
        mock_get.assert_called_once_with(app, 5)
        mock_dlg_cls.assert_called_once()
        assert len(facade._alive) == 1

    @patch("gui.volume_render_facade.can_launch_3d_volume_render", return_value=(True, "ok"))
    @patch("gui.volume_render_facade.get_datasets_for_subwindow", return_value=["d1", "d2", "d3"])
    @patch("gui.volume_render_facade.VolumeRenderDialog")
    def test_success_with_focused_idx(self, mock_dlg_cls, mock_get, mock_eligible) -> None:
        app = _FakeApp(focused_idx=3, subwindow_data={3: {"study_uid": "SU", "series_uid": "SE"}})
        facade = VolumeRenderFacade(app)
        facade.launch_3d_view()  # subwindow_idx is None → use focused
        mock_get.assert_called_once_with(app, 3)

    @patch("gui.volume_render_facade.can_launch_3d_volume_render", return_value=(True, "ok"))
    @patch("gui.volume_render_facade.get_datasets_for_subwindow", return_value=["d1", "d2", "d3"])
    @patch("gui.volume_render_facade.VolumeRenderDialog")
    def test_dialog_registered_with_series_key(self, mock_dlg_cls, mock_get, mock_eligible) -> None:
        app = _FakeApp(subwindow_data={0: {"study_uid": "SU", "series_uid": "SE"}})
        facade = VolumeRenderFacade(app)
        facade.launch_3d_view(subwindow_idx=0)
        assert "SU|SE" in facade._open_dialogs
        assert facade._open_dialogs["SU|SE"] is mock_dlg_cls.return_value

    @patch("gui.volume_render_facade.can_launch_3d_volume_render", return_value=(True, "ok"))
    @patch("gui.volume_render_facade.get_datasets_for_subwindow", return_value=["d1", "d2", "d3"])
    @patch("gui.volume_render_facade.VolumeRenderDialog")
    def test_no_series_key_skips_open_dialogs_registration(self, mock_dlg_cls, mock_get, mock_eligible) -> None:
        app = _FakeApp(subwindow_data={0: {}})
        facade = VolumeRenderFacade(app)
        facade.launch_3d_view(subwindow_idx=0)
        assert facade._open_dialogs == {}
        assert len(facade._alive) == 1

    @patch("gui.volume_render_facade.can_launch_3d_volume_render", return_value=(True, "ok"))
    @patch("gui.volume_render_facade.get_datasets_for_subwindow", return_value=["d1", "d2", "d3"])
    @patch("gui.volume_render_facade.VolumeRenderDialog")
    def test_duplicate_visible_dialog_raises_and_returns(self, mock_dlg_cls, mock_get, mock_eligible) -> None:
        app = _FakeApp(subwindow_data={0: {"study_uid": "SU", "series_uid": "SE"}})
        facade = VolumeRenderFacade(app)
        existing = _FakeDialog()
        facade._open_dialogs["SU|SE"] = existing
        facade.launch_3d_view(subwindow_idx=0)
        assert existing.raise_called is True
        assert facade._open_dialogs["SU|SE"] is existing
        mock_dlg_cls.assert_not_called()

    @patch("gui.volume_render_facade.can_launch_3d_volume_render", return_value=(True, "ok"))
    @patch("gui.volume_render_facade.get_datasets_for_subwindow", return_value=["d1", "d2", "d3"])
    @patch("gui.volume_render_facade.VolumeRenderDialog")
    def test_duplicate_hidden_dialog_replaced(self, mock_dlg_cls, mock_get, mock_eligible) -> None:
        app = _FakeApp(subwindow_data={0: {"study_uid": "SU", "series_uid": "SE"}})
        facade = VolumeRenderFacade(app)
        hidden = _FakeDialog()
        hidden._visible = False
        facade._open_dialogs["SU|SE"] = hidden
        facade.launch_3d_view(subwindow_idx=0)
        mock_dlg_cls.assert_called_once()
        assert facade._open_dialogs["SU|SE"] is mock_dlg_cls.return_value

    @patch("gui.volume_render_facade.can_launch_3d_volume_render", return_value=(True, "ok"))
    @patch("gui.volume_render_facade.get_datasets_for_subwindow", return_value=["d1", "d2", "d3"])
    @patch("gui.volume_render_facade.VolumeRenderDialog")
    def test_series_description_passed_to_dialog(self, mock_dlg_cls, mock_get, mock_eligible) -> None:
        ds = MagicMock(spec=["SeriesDescription", "Modality"])
        ds.SeriesDescription = "CT Head"
        ds.Modality = "CT"
        mock_get.return_value = [ds]
        app = _FakeApp(subwindow_data={0: {"study_uid": "SU", "series_uid": "SE"}})
        facade = VolumeRenderFacade(app)
        facade.launch_3d_view(subwindow_idx=0)
        _, kwargs = mock_dlg_cls.call_args
        assert kwargs.get("series_description") == "CT Head - CT"

    @patch("gui.volume_render_facade.can_launch_3d_volume_render", return_value=(True, "ok"))
    @patch("gui.volume_render_facade.get_datasets_for_subwindow", return_value=["d1", "d2", "d3"])
    @patch("gui.volume_render_facade.VolumeRenderDialog")
    def test_config_manager_passed_through(self, mock_dlg_cls, mock_get, mock_eligible) -> None:
        cm = MagicMock()
        app = _FakeApp(subwindow_data={0: {"study_uid": "SU", "series_uid": "SE"}})
        app.config_manager = cm
        facade = VolumeRenderFacade(app)
        facade.launch_3d_view(subwindow_idx=0)
        _, kwargs = mock_dlg_cls.call_args
        assert kwargs.get("config_manager") is cm

    @patch("gui.volume_render_facade.can_launch_3d_volume_render", return_value=(True, "ok"))
    @patch("gui.volume_render_facade.get_datasets_for_subwindow", return_value=["d1", "d2", "d3"])
    @patch("gui.volume_render_facade.VolumeRenderDialog")
    def test_config_manager_absent_defaults_to_none(self, mock_dlg_cls, mock_get, mock_eligible) -> None:
        app = _FakeApp(subwindow_data={0: {"study_uid": "SU", "series_uid": "SE"}})
        del app.config_manager
        facade = VolumeRenderFacade(app)
        facade.launch_3d_view(subwindow_idx=0)
        _, kwargs = mock_dlg_cls.call_args
        assert kwargs.get("config_manager") is None

    @patch("gui.volume_render_facade.can_launch_3d_volume_render", return_value=(True, "ok"))
    @patch("gui.volume_render_facade.get_datasets_for_subwindow", return_value=["d1", "d2", "d3"])
    @patch("gui.volume_render_facade.VolumeRenderDialog")
    def test_multiframe_datasets_trigger_synthesis(self, mock_dlg_cls, mock_get, mock_eligible) -> None:
        ds = MagicMock(spec=["_original_dataset", "_frame_index"])
        ds._original_dataset = MagicMock()
        ds._frame_index = 0
        mock_get.return_value = [ds]
        app = _FakeApp(subwindow_data={0: {"study_uid": "SU", "series_uid": "SE"}})
        facade = VolumeRenderFacade(app)
        with patch("core.volume_render_eligibility.synthesize_frame_geometry") as mock_synth:
            facade.launch_3d_view(subwindow_idx=0)
            mock_synth.assert_called_once_with([ds])

    @patch("gui.volume_render_facade.can_launch_3d_volume_render", return_value=(True, "ok"))
    @patch("gui.volume_render_facade.get_datasets_for_subwindow", return_value=["d1", "d2", "d3"])
    @patch("gui.volume_render_facade.VolumeRenderDialog")
    def test_non_multiframe_skips_synthesis(self, mock_dlg_cls, mock_get, mock_eligible) -> None:
        app = _FakeApp(subwindow_data={0: {"study_uid": "SU", "series_uid": "SE"}})
        facade = VolumeRenderFacade(app)
        with patch("core.volume_render_eligibility.synthesize_frame_geometry") as mock_synth:
            facade.launch_3d_view(subwindow_idx=0)
            mock_synth.assert_not_called()

    @patch("gui.volume_render_facade.can_launch_3d_volume_render", return_value=(True, "ok"))
    @patch("gui.volume_render_facade.get_datasets_for_subwindow", return_value=["d1", "d2", "d3"])
    @patch("gui.volume_render_facade.VolumeRenderDialog")
    def test_dialog_shown_on_launch(self, mock_dlg_cls, mock_get, mock_eligible) -> None:
        app = _FakeApp(subwindow_data={0: {}})
        facade = VolumeRenderFacade(app)
        facade.launch_3d_view(subwindow_idx=0)
        mock_dlg_cls.return_value.show.assert_called_once()

    @patch("gui.volume_render_facade.can_launch_3d_volume_render", return_value=(True, "ok"))
    @patch("gui.volume_render_facade.get_datasets_for_subwindow", return_value=["d1", "d2", "d3"])
    @patch("gui.volume_render_facade.VolumeRenderDialog")
    def test_on_destroyed_removes_from_alive_and_open_dialogs(self, mock_dlg_cls, mock_get, mock_eligible) -> None:
        app = _FakeApp(subwindow_data={0: {"study_uid": "SU", "series_uid": "SE"}})
        facade = VolumeRenderFacade(app)
        facade.launch_3d_view(subwindow_idx=0)
        dialog = mock_dlg_cls.return_value
        # Capture the callback connected to dialog.destroyed.connect
        on_destroyed_cb = dialog.destroyed.connect.call_args[0][0]
        on_destroyed_cb()
        assert dialog not in facade._alive
        assert "SU|SE" not in facade._open_dialogs

    @patch("gui.volume_render_facade.can_launch_3d_volume_render", return_value=(True, "ok"))
    @patch("gui.volume_render_facade.get_datasets_for_subwindow", return_value=["d1", "d2", "d3"])
    @patch("gui.volume_render_facade.VolumeRenderDialog")
    def test_on_destroyed_no_series_key_only_removes_from_alive(self, mock_dlg_cls, mock_get, mock_eligible) -> None:
        app = _FakeApp(subwindow_data={0: {}})
        facade = VolumeRenderFacade(app)
        facade.launch_3d_view(subwindow_idx=0)
        dialog = mock_dlg_cls.return_value
        on_destroyed_cb = dialog.destroyed.connect.call_args[0][0]
        on_destroyed_cb()
        assert dialog not in facade._alive

    @patch("gui.volume_render_facade.can_launch_3d_volume_render", return_value=(True, "ok"))
    @patch("gui.volume_render_facade.get_datasets_for_subwindow", return_value=["d1", "d2", "d3"])
    @patch("gui.volume_render_facade.VolumeRenderDialog")
    def test_on_destroyed_already_removed_is_swallowed(self, mock_dlg_cls, mock_get, mock_eligible) -> None:
        app = _FakeApp(subwindow_data={0: {"study_uid": "SU", "series_uid": "SE"}})
        facade = VolumeRenderFacade(app)
        facade.launch_3d_view(subwindow_idx=0)
        dialog = mock_dlg_cls.return_value
        on_destroyed_cb = dialog.destroyed.connect.call_args[0][0]
        # Remove manually first to test the ValueError catch
        facade._alive.remove(dialog)
        facade._open_dialogs.pop("SU|SE", None)
        on_destroyed_cb()
        assert dialog not in facade._alive


# ---------------------------------------------------------------------------
# close_all_dialogs  (lines 111-136)
# ---------------------------------------------------------------------------

class TestCloseAllDialogs:
    def test_clears_alive_and_open_dialogs(self, qapp) -> None:
        facade = VolumeRenderFacade(_FakeApp())
        d1, d2 = _FakeDialog(), _FakeDialog()
        facade._alive = [d1, d2]
        facade._open_dialogs = {"k1": d1, "k2": d2}
        facade.close_all_dialogs()
        assert facade._alive == []
        assert facade._open_dialogs == {}

    def test_close_returns_false_falls_through_to_hide(self, qapp) -> None:
        facade = VolumeRenderFacade(_FakeApp())
        d = _NonCloseableDialog()
        facade._alive = [d]
        facade.close_all_dialogs()
        assert d._visible is False

    def test_runtime_error_on_close_is_swallowed(self, qapp) -> None:
        facade = VolumeRenderFacade(_FakeApp())
        d = _RuntimeErrorDialog()
        facade._alive = [d]
        facade.close_all_dialogs()
        assert facade._alive == []

    def test_process_events_called_when_app_exists(self, qapp) -> None:
        facade = VolumeRenderFacade(_FakeApp())
        events_called = []
        original_pe = qapp.processEvents

        def tracking_pe(*a, **kw):
            events_called.append(True)
            return original_pe(*a, **kw)

        with (
            patch.object(qapp, "processEvents", side_effect=tracking_pe),
            patch("gui.volume_render_facade.QApplication") as mock_qa,
        ):
            mock_qa.instance.return_value = qapp
            mock_qa.topLevelWidgets.return_value = []
            facade.close_all_dialogs()
        assert events_called

    def test_no_process_events_when_app_is_none(self, qapp) -> None:
        facade = VolumeRenderFacade(_FakeApp())
        with patch("gui.volume_render_facade.QApplication") as mock_qa:
            mock_qa.instance.return_value = None
            facade.close_all_dialogs()
            assert facade._alive == []
            assert facade._open_dialogs == {}

    def test_sweeps_untracked_volume_render_dialogs(self, qapp) -> None:
        from gui.dialogs.volume_render_dialog import VolumeRenderDialog

        facade = VolumeRenderFacade(_FakeApp())

        class _FakeVRD(VolumeRenderDialog):
            def __init__(self) -> None:
                from PySide6.QtWidgets import QDialog

                QDialog.__init__(self, None)
                self.closed = False

            def closeEvent(self, event: Any) -> None:
                self.closed = True
                event.accept()

        vrd = _FakeVRD()
        vrd.show()
        qapp.processEvents()
        try:
            facade.close_all_dialogs()
            qapp.processEvents()
            assert vrd.closed is True
        finally:
            if vrd.isVisible():
                vrd.close()
            qapp.processEvents()

    def test_tracked_top_level_vrd_not_doubled(self, qapp) -> None:
        """Branch 121->120: tracked VRD is also a top-level widget → not appended again."""
        from gui.dialogs.volume_render_dialog import VolumeRenderDialog

        facade = VolumeRenderFacade(_FakeApp())

        class _TrackedVRD(VolumeRenderDialog):
            def __init__(self) -> None:
                from PySide6.QtWidgets import QDialog

                QDialog.__init__(self, None)
                self.closed = False

            def closeEvent(self, event: Any) -> None:
                self.closed = True
                event.accept()

        vrd = _TrackedVRD()
        vrd.show()
        qapp.processEvents()
        facade._alive.append(vrd)
        facade._open_dialogs["SU|SE"] = vrd
        try:
            facade.close_all_dialogs()
            qapp.processEvents()
            assert vrd.closed is True
            assert facade._alive == []
        finally:
            if vrd.isVisible():
                vrd.close()
            qapp.processEvents()
