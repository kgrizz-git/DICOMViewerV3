"""Bounded follow-up coverage for QAAppFacade's remaining orchestration branches."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from pydicom.dataset import Dataset
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QMessageBox

import gui.qa_app_facade as facade_module
from gui.qa_app_facade import QAAppFacade
from qa.analysis_types import (
    LcRunConfig,
    MRIBatchResult,
    MRICompareRequest,
    PlanarUniformityOptions,
    QARequest,
)

pytestmark = pytest.mark.qt


class _Signal:
    def __init__(self) -> None:
        self.callbacks = []

    def connect(self, callback) -> None:
        self.callbacks.append(callback)

    def emit(self, *args) -> None:
        for callback in self.callbacks:
            callback(*args)


class _Progress:
    def __init__(self, *_args) -> None:
        self.canceled = _Signal()
        self.closed = False

    def setWindowTitle(self, _value) -> None:
        pass

    def setWindowModality(self, _value) -> None:
        pass

    def setWindowFlags(self, value):
        return value

    def windowFlags(self):
        return Qt.WindowType.Widget

    def show(self) -> None:
        pass

    def activateWindow(self) -> None:
        pass

    def raise_(self) -> None:
        pass

    def close(self) -> None:
        self.closed = True


class _Worker:
    def __init__(self, *_args, **_kwargs) -> None:
        self.batch_result_ready = _Signal()
        self.finished = _Signal()
        self.started = False

    def start(self) -> None:
        self.started = True


class _Choice:
    def __init__(self, clicked_text: str | None) -> None:
        self.clicked_text = clicked_text
        self.buttons = []

    def setWindowTitle(self, _value) -> None:
        pass

    def setText(self, _value) -> None:
        pass

    def setIcon(self, _value) -> None:
        pass

    def addButton(self, text, _role=None):
        button = SimpleNamespace(text=lambda: text)
        self.buttons.append(button)
        return button

    def setWindowFlags(self, value):
        return value

    def windowFlags(self):
        return Qt.WindowType.Widget

    def activateWindow(self) -> None:
        pass

    def raise_(self) -> None:
        pass

    def exec(self) -> int:
        return 0

    def clickedButton(self):
        return next(
            (button for button in self.buttons if button.text() == self.clicked_text),
            None,
        )

    def button(self, _standard_button):
        return next((button for button in self.buttons if button.text() == "Cancel"), None)


class _RetryBox(_Choice):
    def __init__(self, choose_tolerance: bool) -> None:
        super().__init__("Choose tolerance…" if choose_tolerance else None)
        self.clicked = None

    def addButton(self, text, role=None):
        button = super().addButton(text, role)
        if text == self.clicked_text:
            self.clicked = button
        return button

    def clickedButton(self):
        return self.clicked


class _ChoiceBox(_Choice):
    ButtonRole = QMessageBox.ButtonRole
    StandardButton = QMessageBox.StandardButton


def _app() -> SimpleNamespace:
    return SimpleNamespace(
        main_window=MagicMock(),
        _prompt_save_path=MagicMock(return_value=""),
        _qa_worker=None,
        _qa_batch_worker=None,
        _mri_compare_result_dialog=None,
        _ct_batch_result_dialog=None,
    )


def _mri_options(compare_request=None):
    return (2, False, 1, 0.0, "method", 0.001, 1.0, compare_request, False, True)


def _compare_request() -> MRICompareRequest:
    return MRICompareRequest([LcRunConfig("Synthetic", "rose", 0.001, 1.0)])


def _fake_message_box(box):
    def factory(*_args):
        return box

    factory.Icon = QMessageBox.Icon
    factory.ButtonRole = QMessageBox.ButtonRole
    factory.StandardButton = QMessageBox.StandardButton
    return factory


def test_build_preflight_warnings_covers_missing_and_duplicate_geometry(qapp) -> None:
    facade = QAAppFacade(_app())
    missing = facade.build_preflight_warnings("CT", True, None, [Dataset(), Dataset()], "CT")
    duplicate = Dataset()
    duplicate.ImagePositionPatient = [0, 0, 1]
    duplicate.ImageOrientationPatient = [1, 0, 0, 0, 1, 0]
    duplicate_warnings = facade.build_preflight_warnings(
        "CT", True, None, [duplicate, duplicate], "CT"
    )

    assert "missing or invalid" in missing[0]
    assert any("Duplicate or near-duplicate" in warning for warning in duplicate_warnings)


def test_offer_extent_retry_choose_tolerance_starts_one_relaxed_attempt(qapp, monkeypatch) -> None:
    app = _app()
    facade = QAAppFacade(app)
    retry_box = _RetryBox(choose_tolerance=True)
    monkeypatch.setattr(facade_module, "QMessageBox", _fake_message_box(retry_box))
    monkeypatch.setattr(facade_module.QInputDialog, "getDouble", lambda *_args: (1.5, True))
    start = MagicMock()
    monkeypatch.setattr(QAAppFacade, "start_qa_worker", start)
    request = QARequest("acr_ct", qa_attempt=1, vanilla_pylinac=False)

    facade.offer_extent_retry(
        request,
        {"synthetic": True},
        progress_title="title",
        progress_label="label",
        result_dialog_title="result",
        json_default_stem="stem",
    )

    retried_request = start.call_args.args[0]
    assert retried_request.scan_extent_tolerance_mm == 1.5
    assert retried_request.qa_attempt == 2
    assert start.call_args.kwargs["allow_extent_retry"] is False
    assert start.call_args.kwargs["json_inputs"]["parent_attempt_outcome"] == "failed_strict_extent"


def test_offer_extent_retry_close_does_not_start_worker(qapp, monkeypatch) -> None:
    app = _app()
    facade = QAAppFacade(app)
    monkeypatch.setattr(facade_module, "QMessageBox", _fake_message_box(_RetryBox(False)))
    start = MagicMock()
    monkeypatch.setattr(QAAppFacade, "start_qa_worker", start)

    facade.offer_extent_retry(
        QARequest("acr_ct"), None, progress_title="t", progress_label="l",
        result_dialog_title="r", json_default_stem="s"
    )

    start.assert_not_called()


def test_open_acr_ct_focused_dialog_options_and_worker_request(qapp, monkeypatch) -> None:
    app = _app()
    app._resolve_focused_series_ordered_paths = MagicMock(
        return_value=("study", "series", "CT", ["synthetic.dcm"], [])
    )
    app.config_manager = MagicMock()
    app.config_manager.get_acr_qa_vanilla_pylinac.return_value = False
    app.file_dialog = MagicMock()
    choice = _Choice("Use Focused Series")
    monkeypatch.setattr(facade_module, "QMessageBox", lambda *_args: choice)
    facade_module.QMessageBox.ButtonRole = QMessageBox.ButtonRole
    facade_module.QMessageBox.StandardButton = QMessageBox.StandardButton
    monkeypatch.setattr(facade_module, "prompt_acr_ct_options", lambda *_args, **_kwargs: (1.0, 2, True, True))
    monkeypatch.setattr(QAAppFacade, "user_confirms_preflight", lambda *_args: True)
    start = MagicMock()
    monkeypatch.setattr(QAAppFacade, "start_qa_worker", start)

    QAAppFacade(app).open_acr_ct_phantom_analysis()

    request = start.call_args.args[0]
    assert request.dicom_paths == ["synthetic.dcm"]
    assert request.origin_slice == 2
    assert request.vanilla_pylinac is True
    app.config_manager.set_acr_qa_vanilla_pylinac.assert_called_once_with(True)


def test_open_acr_mri_compare_uses_fake_options_and_batch_worker(qapp, monkeypatch) -> None:
    app = _app()
    app._resolve_focused_series_ordered_paths = MagicMock(
        return_value=("study", "series", "MR", ["synthetic.dcm"], [])
    )
    app.config_manager = MagicMock()
    app.config_manager.get_acr_qa_vanilla_pylinac.return_value = False
    choice = _Choice("Use Focused Series")
    monkeypatch.setattr(facade_module, "QMessageBox", lambda *_args: choice)
    facade_module.QMessageBox.ButtonRole = QMessageBox.ButtonRole
    facade_module.QMessageBox.StandardButton = QMessageBox.StandardButton
    compare = _compare_request()
    monkeypatch.setattr(facade_module, "prompt_acr_mri_options", lambda *_args, **_kwargs: _mri_options(compare))
    monkeypatch.setattr(QAAppFacade, "user_confirms_preflight", lambda *_args: True)
    start = MagicMock()
    monkeypatch.setattr(QAAppFacade, "start_mri_batch_worker", start)

    QAAppFacade(app).open_acr_mri_phantom_analysis()

    request = start.call_args.args[0]
    assert request.analysis_type == "acr_mri_large"
    assert start.call_args.args[1] is compare
    assert request.low_contrast_method == "method"


def test_open_nuclear_file_flow_extracts_identity_and_routes_options(qapp, monkeypatch) -> None:
    app = _app()
    app._resolve_focused_series_ordered_paths = MagicMock(return_value=("", "", "", [], []))
    app.file_dialog = MagicMock()
    app.file_dialog.open_files.return_value = ["synthetic.nm"]
    app.config_manager = MagicMock()
    monkeypatch.setattr(QAAppFacade, "_read_identity", staticmethod(lambda _path: ("study", "series", "NM")))
    monkeypatch.setattr(QAAppFacade, "user_confirms_preflight", lambda *_args: True)
    monkeypatch.setattr(facade_module, "prompt_nuclear_options", lambda *_args: PlanarUniformityOptions())
    start = MagicMock()
    monkeypatch.setattr(QAAppFacade, "start_qa_worker", start)

    QAAppFacade(app).open_nuclear_qc_analysis()

    request = start.call_args.args[0]
    assert request.analysis_type == "nuclear_planar_uniformity"
    assert request.study_uid == "study"
    assert request.dicom_paths == ["synthetic.nm"]


def test_read_identity_returns_empty_tuple_for_synthetic_decode_failure(qapp, monkeypatch) -> None:
    monkeypatch.setattr("pydicom.dcmread", MagicMock(side_effect=ValueError("synthetic failure")))

    assert QAAppFacade._read_identity("synthetic.nm") == ("", "", "")


def test_mri_batch_completion_shows_dialog_and_cancel_ignores_late_result(qapp, monkeypatch) -> None:
    app = _app()
    facade = QAAppFacade(app)
    progress = _Progress()
    worker = _Worker()
    monkeypatch.setattr(facade_module, "QProgressDialog", lambda *args: progress)
    monkeypatch.setattr(facade_module, "QABatchWorker", lambda *args, **kwargs: worker)
    show = MagicMock()
    monkeypatch.setattr(QAAppFacade, "show_mri_compare_result_dialog", show)
    base = QARequest("acr_mri_large")
    batch = MRIBatchResult([MagicMock()], _compare_request().run_configs)

    facade.start_mri_batch_worker(base, _compare_request(), json_inputs={"synthetic": True})
    worker.batch_result_ready.emit(batch)
    show.assert_called_once_with(batch, json_inputs={"synthetic": True})
    assert worker.started is True

    show.reset_mock()
    progress.canceled.emit()
    worker.batch_result_ready.emit(batch)
    show.assert_not_called()
    assert app.main_window.update_status.call_args_list[-2].args == (
        "QA batch analysis cancelled (best-effort).",
    )
    assert app.main_window.update_status.call_args_list[-1].args == (
        "Ignored late QA batch result after cancellation.",
    )
