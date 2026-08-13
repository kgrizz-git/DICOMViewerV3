"""Follow-up coverage for deterministic dialog action preconditions and wrappers."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from PySide6.QtWidgets import QDialog, QMessageBox

from gui.actions import dialog_actions


def _app(**overrides):
    """Build a minimal synthetic application double for action handlers."""
    app = SimpleNamespace(main_window=object())
    for key, value in overrides.items():
        setattr(app, key, value)
    return app


@pytest.mark.qt
@pytest.mark.parametrize(
    "blocker",
    [
        "The focused window is an MPR view.",
        "Cine export is not available.",
        "The focused window has no multi-frame cine series to export.",
    ],
)
def test_cine_export_reports_blocker_without_opening_export_dialog(
    qapp, monkeypatch, blocker
):
    info = MagicMock()
    monkeypatch.setattr(dialog_actions, "describe_focused_cine_export_blocker", lambda app: blocker)
    monkeypatch.setattr(QMessageBox, "information", info)
    app = _app(get_focused_subwindow_index=MagicMock(), subwindow_data={})

    dialog_actions.open_export_cine_video(app)

    info.assert_called_once_with(app.main_window, "Export Cine", blocker)


@pytest.mark.qt
@pytest.mark.parametrize(
    ("studies", "message"),
    [
        ({}, "Series data is not available."),
        ({"study": {"series": []}}, "Not enough frames to export."),
    ],
)
def test_cine_export_rejects_missing_or_single_frame_series(
    qapp, monkeypatch, studies, message
):
    warning = MagicMock()
    info = MagicMock()
    monkeypatch.setattr(dialog_actions.QMessageBox, "warning", warning)
    monkeypatch.setattr(dialog_actions.QMessageBox, "information", info)
    cine_player = SimpleNamespace(
        is_cine_capable=MagicMock(return_value=True),
        get_effective_frame_rate=MagicMock(),
    )
    app = _app(
        get_focused_subwindow_index=MagicMock(return_value=0),
        subwindow_data={0: {"current_study_uid": "study", "current_series_uid": "series"}},
        current_studies=studies,
        cine_player=cine_player,
    )
    monkeypatch.setattr(dialog_actions, "CineExportDialog", MagicMock())

    dialog_actions.open_export_cine_video(app)

    box = warning if message.startswith("Series") else info
    box.assert_called_once_with(app.main_window, "Export Cine", message)
    dialog_actions.CineExportDialog.assert_not_called()


@pytest.mark.qt
def test_cine_export_returns_when_options_dialog_is_cancelled(qapp, monkeypatch):
    dialog = MagicMock()
    dialog.exec.return_value = QDialog.DialogCode.Rejected
    dialog_factory = MagicMock(return_value=dialog)
    monkeypatch.setattr(dialog_actions, "CineExportDialog", dialog_factory)
    monkeypatch.setattr(dialog_actions, "QMessageBox", MagicMock())
    series = [object(), object()]
    app = _app(
        main_window=object(),
        get_focused_subwindow_index=MagicMock(return_value=0),
        subwindow_data={0: {"current_study_uid": "study", "current_series_uid": "series"}},
        current_studies={"study": {"series": series}},
        cine_player=SimpleNamespace(
            is_cine_capable=MagicMock(return_value=True),
            get_effective_frame_rate=MagicMock(return_value=24.0),
            loop_start_frame=0,
            loop_end_frame=1,
        ),
    )

    dialog_actions.open_export_cine_video(app)

    dialog_factory.assert_called_once_with(
        app.main_window, default_fps=24.0, total_frames=2, loop_start=0, loop_end=1
    )
    dialog.exec.assert_called_once_with()
    dialog.build_options.assert_not_called()


@pytest.mark.qt
def test_structured_report_browser_returns_for_negative_subwindow(qapp):
    app = _app(get_focused_subwindow_index=MagicMock(return_value=-1))

    dialog_actions.open_structured_report_browser(app)


@pytest.mark.qt
def test_study_index_search_skips_dismissed_warning_and_opens_dialog(qapp, monkeypatch):
    search = MagicMock()
    search_factory = MagicMock(return_value=search)
    monkeypatch.setattr(dialog_actions, "StudyIndexSearchDialog", search_factory)
    config = SimpleNamespace(get_study_index_passphrase_warning_dismissed=MagicMock(return_value=True))
    app = _app(
        config_manager=config,
        study_index_service=object(),
        main_window=SimpleNamespace(),
    )

    dialog_actions.open_study_index_search(app)

    search_factory.assert_called_once()
    search.exec.assert_called_once_with()
    config.get_study_index_passphrase_warning_dismissed.assert_called_once_with()


def test_remaining_dialog_action_wrappers_delegate_to_synthetic_facades():
    qa = SimpleNamespace(
        open_acr_ct_phantom_analysis=MagicMock(),
        open_acr_ct_batch_analysis=MagicMock(),
        open_acr_mri_phantom_analysis=MagicMock(),
        open_nuclear_qc_analysis=MagicMock(),
        open_path_in_system_viewer=MagicMock(),
    )
    app = _app(_qa_app_facade=qa)

    dialog_actions.open_acr_ct_phantom_analysis(app)
    dialog_actions.open_acr_ct_batch_analysis(app)
    dialog_actions.open_acr_mri_phantom_analysis(app)
    dialog_actions.open_nuclear_qc_analysis(app)
    dialog_actions.open_path_in_system_viewer(app, "synthetic/report.pdf")

    qa.open_acr_ct_phantom_analysis.assert_called_once_with()
    qa.open_acr_ct_batch_analysis.assert_called_once_with()
    qa.open_acr_mri_phantom_analysis.assert_called_once_with()
    qa.open_nuclear_qc_analysis.assert_called_once_with()
    qa.open_path_in_system_viewer.assert_called_once_with("synthetic/report.pdf")


def test_slice_sync_and_deep_anonymizer_actions_delegate(monkeypatch):
    sync = MagicMock()
    anonymizer = MagicMock()
    app = _app(
        config_manager=SimpleNamespace(get_slice_sync_groups=MagicMock(return_value=[])),
        dialog_coordinator=SimpleNamespace(open_deep_anonymizer_export=anonymizer),
        _qa_app_facade=SimpleNamespace(),
        _on_slice_sync_groups_changed=MagicMock(),
    )
    dialog_actions.open_deep_anonymizer_export(app)
    assert app.dialog_coordinator.open_deep_anonymizer_export is anonymizer
    anonymizer.assert_called_once_with()

    monkey_dialog = SimpleNamespace(groups_changed=SimpleNamespace(connect=sync), exec=MagicMock())
    # The real dialog is patched only for this wrapper, keeping the test synthetic.
    monkeypatch.setattr(dialog_actions, "SliceSyncDialog", MagicMock(return_value=monkey_dialog))
    dialog_actions.open_slice_sync_dialog(app)

    app.config_manager.get_slice_sync_groups.assert_called_once_with()
    sync.assert_called_once_with(app._on_slice_sync_groups_changed)
    monkey_dialog.exec.assert_called_once_with()
