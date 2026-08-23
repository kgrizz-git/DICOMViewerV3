"""
Comprehensive unit tests for src/gui/dialog_coordinator.py.

Achieves 100% statement and branch coverage for DialogCoordinator.
"""

from unittest.mock import MagicMock, patch

import pytest
from pydicom.dataset import Dataset
from PySide6.QtCore import QEvent

from gui.dialog_coordinator import DialogCoordinator


@pytest.fixture
def mock_coordinator_setup(qapp):
    """Fixture for DialogCoordinator with mock injected dependencies."""
    config_mgr = MagicMock()
    main_window = MagicMock()
    get_studies = MagicMock(return_value={"study1": {"series1": [Dataset()]}})
    settings_cb = MagicMock()
    overlay_cb = MagicMock()
    tag_history = MagicMock()
    get_histo_cbs = MagicMock(return_value={"cb1": MagicMock()})
    get_subwin_idx = MagicMock(return_value=0)
    undo_mgr = MagicMock()
    ui_refresh_cb = MagicMock()
    tag_export_host = MagicMock()
    manage_wl_cb = MagicMock()
    clear_study_cb = MagicMock()
    clear_mpr_cb = MagicMock()

    coordinator = DialogCoordinator(
        config_manager=config_mgr,
        main_window=main_window,
        get_current_studies=get_studies,
        settings_applied_callback=settings_cb,
        overlay_config_applied_callback=overlay_cb,
        tag_edit_history=tag_history,
        get_histogram_callbacks_for_subwindow=get_histo_cbs,
        get_focused_subwindow_index=get_subwin_idx,
        undo_redo_manager=undo_mgr,
        ui_refresh_callback=ui_refresh_cb,
        tag_export_union_host=tag_export_host,
        manage_wl_presets_callback=manage_wl_cb,
        clear_study_index_callback=clear_study_cb,
        clear_mpr_cache_callback=clear_mpr_cb,
    )
    return coordinator


def test_init_attributes(mock_coordinator_setup) -> None:
    """Test initialization of DialogCoordinator attributes."""
    coord = mock_coordinator_setup
    assert coord.config_manager is not None
    assert coord.main_window is not None
    assert coord.get_current_studies() != {}
    assert coord.histogram_dialogs == {}
    assert coord.tag_viewer_dialog is None
    assert coord.about_this_file_dialog is None


def test_open_settings(mock_coordinator_setup) -> None:
    """Test open_settings with and without settings_applied_callback."""
    coord = mock_coordinator_setup
    with patch("gui.dialog_coordinator.SettingsDialog") as mock_dlg_cls:
        coord.open_settings()
        mock_dlg_cls.assert_called_once()
        mock_dlg_cls.return_value.exec.assert_called_once()

    coord.settings_applied_callback = None
    with patch("gui.dialog_coordinator.SettingsDialog") as mock_dlg_cls:
        coord.open_settings()
        mock_dlg_cls.assert_called_once()


def test_open_overlay_settings(mock_coordinator_setup) -> None:
    """Test open_overlay_settings with and without settings_applied_callback."""
    coord = mock_coordinator_setup
    with patch("gui.dialog_coordinator.OverlaySettingsDialog") as mock_dlg_cls:
        coord.open_overlay_settings()
        mock_dlg_cls.assert_called_once()

    coord.settings_applied_callback = None
    with patch("gui.dialog_coordinator.OverlaySettingsDialog") as mock_dlg_cls:
        coord.open_overlay_settings()
        mock_dlg_cls.assert_called_once()


def test_open_tag_viewer(mock_coordinator_setup) -> None:
    """Test open_tag_viewer creation, signals, history manager, undo/redo callbacks, and visibility update."""
    coord = mock_coordinator_setup
    ds = Dataset()

    # 1. Clear tag viewer filter & privacy mode when tag_viewer_dialog is None (hits 344->exit & 354->exit)
    assert coord.tag_viewer_dialog is None
    coord.clear_tag_viewer_filter()
    coord.apply_privacy_mode(True)

    # 2. Instantiation with None optional callbacks/history (hits 154->157, 157->160, 160->163, 163->168, 171->175)
    coord.tag_edit_history = None
    coord.ui_refresh_callback = None
    coord.tag_edited_callback = None
    coord.undo_redo_callbacks = None

    with patch("gui.dialog_coordinator.TagViewerDialog") as mock_dlg_cls:
        mock_inst = mock_dlg_cls.return_value
        mock_inst.isVisible.return_value = True

        coord.open_tag_viewer(current_dataset=None, privacy_mode=False)
        mock_inst.set_privacy_mode.assert_called_with(False)
        mock_inst.set_dataset.assert_not_called()

        # Re-set callbacks for fully configured instance tests
        coord.tag_viewer_dialog = None
        coord.tag_edit_history = MagicMock()
        coord.ui_refresh_callback = MagicMock()
        coord.tag_edited_callback = MagicMock()
        coord.undo_redo_callbacks = (MagicMock(), MagicMock(), MagicMock(), MagicMock())

        coord.open_tag_viewer(current_dataset=ds, privacy_mode=True)
        mock_inst.set_history_manager.assert_called_once()
        mock_inst.set_privacy_mode.assert_called_with(True)
        mock_inst.set_dataset.assert_called_with(ds)
        mock_inst.show.assert_called()

        # Second call reuses existing persistent instance
        mock_inst.reset_mock()
        coord.open_tag_viewer(current_dataset=ds, privacy_mode=False)
        mock_inst.show.assert_called_once()

        # Update tag viewer when visible vs not visible
        coord.update_tag_viewer(ds)
        mock_inst.set_dataset.assert_called()

        mock_inst.isVisible.return_value = False
        coord.update_tag_viewer(ds)

        # Clear tag viewer filter
        coord.clear_tag_viewer_filter()
        mock_inst.clear_filter.assert_called_once()

        # Apply privacy mode
        coord.apply_privacy_mode(True)
        mock_inst.set_privacy_mode.assert_called_with(True)


def test_open_overlay_config_and_annotation_options(mock_coordinator_setup) -> None:
    """Test open_overlay_config and open_annotation_options with/without callbacks."""
    coord = mock_coordinator_setup

    with patch("gui.dialog_coordinator.OverlayConfigDialog") as mock_dlg_cls:
        coord.open_overlay_config("CT")
        mock_dlg_cls.assert_called_with(
            coord.config_manager, coord.main_window, initial_modality="CT"
        )

    coord.overlay_config_applied_callback = None
    with patch("gui.dialog_coordinator.OverlayConfigDialog") as mock_dlg_cls:
        coord.open_overlay_config()
        mock_dlg_cls.assert_called_once()

    coord.annotation_options_applied_callback = MagicMock()
    with patch("gui.dialog_coordinator.AnnotationOptionsDialog") as mock_dlg_cls:
        coord.open_annotation_options()
        mock_dlg_cls.assert_called_once()

    coord.annotation_options_applied_callback = None
    with patch("gui.dialog_coordinator.AnnotationOptionsDialog") as mock_dlg_cls:
        coord.open_annotation_options()
        mock_dlg_cls.assert_called_once()


def test_simple_dialog_triggers(mock_coordinator_setup) -> None:
    """Test open_quick_start_guide, open_user_documentation_in_browser, open_fusion_technical_doc."""
    coord = mock_coordinator_setup

    with patch("gui.dialog_coordinator.QuickStartGuideDialog") as mock_dlg:
        coord.open_quick_start_guide()
        mock_dlg.return_value.exec.assert_called_once()

    with patch("gui.dialog_coordinator.QDesktopServices.openUrl") as mock_url:
        coord.open_user_documentation_in_browser()
        mock_url.assert_called_once()

    with patch("gui.dialog_coordinator.FusionTechnicalDocDialog") as mock_dlg:
        coord.open_fusion_technical_doc()
        mock_dlg.return_value.exec.assert_called_once()


def test_open_tag_export_and_export_and_deep_anonymizer(mock_coordinator_setup) -> None:
    """Test open_tag_export, open_export, and open_deep_anonymizer_export with loaded studies and empty studies warning."""
    coord = mock_coordinator_setup

    # 1. With loaded studies
    with patch("gui.dialog_coordinator.TagExportDialog") as mock_dlg:
        coord.open_tag_export()
        mock_dlg.return_value.exec.assert_called_once()

    with patch("gui.dialog_coordinator.ExportDialog") as mock_dlg:
        coord.open_export()
        mock_dlg.return_value.exec.assert_called_once()

    with patch("gui.dialog_coordinator.DeepAnonymizerExportDialog") as mock_dlg:
        coord.open_deep_anonymizer_export()
        mock_dlg.return_value.exec.assert_called_once()

    # 2. Empty studies warning dialogs
    coord.get_current_studies.return_value = {}
    with patch("gui.dialog_coordinator.QMessageBox.warning") as mock_warn:
        coord.open_tag_export()
        mock_warn.assert_called_once()

    with patch("gui.dialog_coordinator.QMessageBox.warning") as mock_warn:
        coord.open_export()
        mock_warn.assert_called_once()

    with patch("gui.dialog_coordinator.QMessageBox.warning") as mock_warn:
        coord.open_deep_anonymizer_export()
        mock_warn.assert_called_once()


def test_open_export_screenshots(mock_coordinator_setup) -> None:
    """Test open_export_screenshots with subwindows vs empty subwindows."""
    coord = mock_coordinator_setup

    # 1. Empty subwindows shows warning
    with patch("gui.dialog_coordinator.QMessageBox.warning") as mock_warn:
        coord.open_export_screenshots([])
        mock_warn.assert_called_once()

    # 2. Subwindows present
    subwins = [MagicMock()]
    with patch("gui.dialog_coordinator.ScreenshotExportDialog") as mock_dlg:
        coord.open_export_screenshots(subwins)
        mock_dlg.return_value.exec.assert_called_once()


def test_histogram_management(mock_coordinator_setup) -> None:
    """Test open_histogram, update_histogram_for_subwindow, and update_histogram_window_level_only_for_subwindow."""
    coord = mock_coordinator_setup

    # 1. missing callbacks or focused index return early
    coord.get_focused_subwindow_index = None
    coord.open_histogram()

    coord.get_focused_subwindow_index = MagicMock(return_value=0)
    coord.get_histogram_callbacks_for_subwindow = None
    coord.open_histogram()

    coord.get_histogram_callbacks_for_subwindow = MagicMock(
        return_value={"get_image_data": MagicMock()}
    )

    # 2. Invalid subwindow index < 0 or > 3 returns early
    coord.open_histogram(-1)
    coord.open_histogram(4)
    coord.update_histogram_for_subwindow(-1)
    coord.update_histogram_for_subwindow(5)
    coord.update_histogram_window_level_only_for_subwindow(-1)
    coord.update_histogram_window_level_only_for_subwindow(5)

    # 3. Empty subwindow callbacks returns early
    coord.get_histogram_callbacks_for_subwindow.return_value = {}
    coord.open_histogram(0)

    # 4. Valid histogram dialog creation and updates
    coord.get_histogram_callbacks_for_subwindow.return_value = {
        "get_image_data": MagicMock()
    }
    with patch("gui.dialog_coordinator.HistogramDialog") as mock_dlg_cls:
        mock_dlg_inst = mock_dlg_cls.return_value
        mock_dlg_inst.isVisible.return_value = True

        coord.open_histogram(0)
        mock_dlg_inst.update_histogram.assert_called_once()
        mock_dlg_inst.show.assert_called_once()

        # Call open_histogram(0) a second time when already instantiated (hits 369->380 branch)
        coord.open_histogram(0)
        mock_dlg_cls.assert_called_once()  # No second creation

        coord.update_histogram_for_subwindow(0)
        assert mock_dlg_inst.update_histogram.call_count == 3

        coord.update_histogram_window_level_only_for_subwindow(0)
        mock_dlg_inst.update_window_level_only.assert_called_once()

        # Update when dialog is NOT visible
        mock_dlg_inst.isVisible.return_value = False
        coord.update_histogram_for_subwindow(0)
        coord.update_histogram_window_level_only_for_subwindow(0)


def test_export_roi_statistics(mock_coordinator_setup) -> None:
    """Test open_export_roi_statistics with empty vs populated studies."""
    coord = mock_coordinator_setup
    subwin_mgrs = {0: {"roi_manager": MagicMock(), "crosshair_manager": MagicMock()}}

    # 1. Populated studies
    with patch("gui.dialog_coordinator.ExportROIStatisticsDialog") as mock_dlg:
        coord.open_export_roi_statistics(subwin_mgrs)
        mock_dlg.return_value.exec.assert_called_once()

    # 2. Empty studies shows warning
    coord.get_current_studies.return_value = {}
    with patch("PySide6.QtWidgets.QMessageBox.warning") as mock_warn:
        coord.open_export_roi_statistics(subwin_mgrs)
        mock_warn.assert_called_once()


def test_about_this_file_and_sr_browser(mock_coordinator_setup) -> None:
    """Test open_about_this_file, update_about_this_file, and open_structured_report_browser."""
    coord = mock_coordinator_setup
    ds = Dataset()

    with patch("gui.dialog_coordinator.AboutThisFileDialog") as mock_dlg_cls:
        mock_dlg_inst = mock_dlg_cls.return_value
        mock_dlg_inst.isVisible.return_value = True

        # Open About This File
        coord.open_about_this_file(ds, "/path/file.dcm")
        mock_dlg_inst.update_file_info.assert_called_with(ds, "/path/file.dcm")
        mock_dlg_inst.show.assert_called_once()

        # Open About This File a second time when already instantiated (hits 441->445 branch)
        coord.open_about_this_file(ds, "/path/file.dcm")
        mock_dlg_cls.assert_called_once()  # No second creation

        # Update About This File when visible vs not visible
        coord.update_about_this_file(ds, "/path/file.dcm")
        assert mock_dlg_inst.update_file_info.call_count == 3

        mock_dlg_inst.isVisible.return_value = False
        coord.update_about_this_file(ds, "/path/file.dcm")

    # Open Structured Report Browser
    priv_cb = MagicMock(return_value=False)
    with patch(
        "gui.dialogs.structured_report_browser_dialog.StructuredReportBrowserDialog"
    ) as mock_sr_cls:
        coord.open_structured_report_browser(ds, get_privacy_enabled=priv_cb)
        mock_sr_cls.return_value.show.assert_called_once()


@pytest.mark.qt
def test_structured_report_browser_is_destroyed_on_close(qapp) -> None:
    """
    The SR browser is modeless and uncached, so it must delete itself on close.

    Without ``WA_DeleteOnClose`` the Qt parent keeps every browser alive after
    the user closes it, leaking one per SR opened for the life of the session.
    A real ``QDialog`` subclass is used rather than a mock: a mock would accept
    ``setAttribute`` and prove nothing about the actual lifetime.
    """
    from pydicom.dataset import Dataset
    from PySide6.QtWidgets import QDialog, QWidget
    from qt_widget_scope import widget_scope

    class _FakeSRBrowser(QDialog):
        def __init__(self, parent, dataset, **kwargs):
            super().__init__(parent)

    def _flush() -> None:
        qapp.processEvents()
        qapp.sendPostedEvents(None, QEvent.Type.DeferredDelete.value)
        qapp.processEvents()

    # The parent is itself a top-level widget, so it has to be cleaned up on
    # both the passing and failing path -- otherwise this test leaks exactly
    # the way the code under test used to.
    with widget_scope():
        parent = QWidget()
        coord = DialogCoordinator(
            config_manager=MagicMock(),
            main_window=parent,
            get_current_studies=MagicMock(return_value={}),
        )

        with patch(
            "gui.dialogs.structured_report_browser_dialog.StructuredReportBrowserDialog",
            _FakeSRBrowser,
        ):
            for _ in range(3):
                coord.open_structured_report_browser(
                    Dataset(), get_privacy_enabled=lambda: False
                )
                for browser in parent.findChildren(_FakeSRBrowser):
                    browser.close()
                _flush()

        survivors = parent.findChildren(_FakeSRBrowser)

    assert survivors == [], (
        "closed SR browsers are still alive; WA_DeleteOnClose was not applied"
    )
