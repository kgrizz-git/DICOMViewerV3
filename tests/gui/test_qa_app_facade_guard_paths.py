"""Additional deterministic coverage for QAAppFacade guard and callback paths."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import ANY, MagicMock

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QMessageBox

import gui.qa_app_facade as facade_module
from gui.qa_app_facade import QAAppFacade
from qa.analysis_types import (
    CTBatchResult,
    LcRunConfig,
    MRIBatchResult,
    PlanarUniformityOptions,
    QARequest,
    QAResult,
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
        self.result_ready = _Signal()
        self.batch_result_ready = _Signal()
        self.series_completed = _Signal()
        self.finished = _Signal()
        self.image_temp_dir = MagicMock()
        self.started = False
        self.cancelled = False

    def start(self) -> None:
        self.started = True

    def cancel(self) -> None:
        self.cancelled = True


def _app(save_path: str = "") -> SimpleNamespace:
    return SimpleNamespace(
        main_window=MagicMock(),
        _prompt_save_path=MagicMock(return_value=save_path),
        _qa_worker=None,
        _qa_batch_worker=None,
        _qa_ct_batch_worker=None,
        _ct_batch_result_dialog=None,
        _mri_compare_result_dialog=None,
    )


def _result(**overrides) -> QAResult:
    values = {"success": True, "analysis_type": "acr_ct", "num_images": 2}
    values.update(overrides)
    return QAResult(**values)


def _choice(clicked_text: str):
    class Choice:
        def __init__(self) -> None:
            self.buttons = []

        def setWindowTitle(self, _value) -> None:
            pass

        def setText(self, _value) -> None:
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
            return next((b for b in self.buttons if b.text() == clicked_text), None)

        def button(self, _standard_button):
            return next((b for b in self.buttons if b.text() == "Cancel"), None)

    return Choice()


def test_result_dialog_routes_nuclear_results_to_nuclear_summary(monkeypatch) -> None:
    app = _app()
    shown = MagicMock()
    monkeypatch.setattr(
        "gui.dialogs.nuclear_result_dialog.show_nuclear_result_dialog", shown
    )

    QAAppFacade(app).show_qa_result_dialog(
        "Synthetic nuclear", _result(analysis_type="nuclear_planar_uniformity")
    )

    shown.assert_called_once_with(app.main_window, "Synthetic nuclear", ANY)


def test_single_worker_cancel_ignores_late_result_and_cleans_image_dir(qapp, monkeypatch) -> None:
    app = _app()
    progress = _Progress()
    worker = _Worker()
    image_dir = MagicMock()
    monkeypatch.setattr(facade_module, "QProgressDialog", lambda *args: progress)
    monkeypatch.setattr(facade_module, "QAAnalysisWorker", lambda _request: worker)
    show = MagicMock()
    monkeypatch.setattr(QAAppFacade, "show_qa_result_dialog", show)

    QAAppFacade(app).start_qa_worker(
        QARequest("acr_ct"),
        progress_title="Synthetic",
        progress_label="Synthetic",
        result_dialog_title="Synthetic",
        json_default_stem="synthetic",
        analyzed_image_temp_dir=image_dir,
    )
    progress.canceled.emit()
    worker.result_ready.emit(_result())

    show.assert_not_called()
    image_dir.cleanup.assert_called_once()
    assert app.main_window.update_status.call_args_list == [
        (("QA analysis cancelled (best-effort).",), {}),
        (("Ignored late QA result after cancellation.",), {}),
    ]


def test_single_worker_nuclear_callback_uses_dedicated_dialog(monkeypatch) -> None:
    app = _app()
    progress = _Progress()
    worker = _Worker()
    monkeypatch.setattr(facade_module, "QProgressDialog", lambda *args: progress)
    monkeypatch.setattr(facade_module, "QAAnalysisWorker", lambda _request: worker)
    nuclear = MagicMock()
    monkeypatch.setattr(
        "gui.dialogs.nuclear_result_dialog.show_nuclear_result_dialog", nuclear
    )

    QAAppFacade(app).start_qa_worker(
        QARequest("nuclear_planar_uniformity"),
        progress_title="Nuclear",
        progress_label="Synthetic",
        result_dialog_title="Nuclear",
        json_default_stem="nuclear",
        json_inputs={"synthetic": True},
    )
    result = _result(analysis_type="nuclear_planar_uniformity")
    worker.result_ready.emit(result)

    nuclear.assert_called_once()
    assert nuclear.call_args.args[:3] == (app.main_window, "Nuclear", result)
    assert nuclear.call_args.kwargs["inputs"] == {"synthetic": True}


def test_single_worker_extent_failure_offers_relaxed_retry(monkeypatch) -> None:
    app = _app()
    progress = _Progress()
    worker = _Worker()
    monkeypatch.setattr(facade_module, "QProgressDialog", lambda *args: progress)
    monkeypatch.setattr(facade_module, "QAAnalysisWorker", lambda _request: worker)
    monkeypatch.setattr(QAAppFacade, "show_qa_result_dialog", MagicMock())
    monkeypatch.setattr(QAAppFacade, "offer_open_single_run_pdf", MagicMock())
    monkeypatch.setattr(QAAppFacade, "export_qa_results", MagicMock())
    retry = MagicMock()
    monkeypatch.setattr(QAAppFacade, "offer_extent_retry", retry)

    request = QARequest("acr_ct", vanilla_pylinac=False, qa_attempt=1)
    QAAppFacade(app).start_qa_worker(
        request,
        progress_title="Synthetic",
        progress_label="Synthetic",
        result_dialog_title="Synthetic",
        json_default_stem="synthetic",
    )
    worker.result_ready.emit(
        _result(success=False, errors=["physical scan extent is insufficient"])
    )

    retry.assert_called_once_with(
        request,
        None,
        progress_title="Synthetic",
        progress_label="Synthetic",
        result_dialog_title="Synthetic",
        json_default_stem="synthetic",
    )


def test_empty_batch_guards_clean_up_or_skip_dialog(monkeypatch) -> None:
    app = _app()
    worker = _Worker()
    facade = QAAppFacade(app)
    facade.show_ct_batch_result_dialog(worker, CTBatchResult())
    worker.image_temp_dir.cleanup.assert_called_once()

    facade.show_mri_compare_result_dialog(MRIBatchResult())
    monkeypatch.setattr(facade_module, "create_ct_batch_result_dialog", MagicMock())
    previous_dialog = MagicMock()
    app._ct_batch_result_dialog = previous_dialog
    facade.show_ct_batch_result_dialog(worker, CTBatchResult([_result()], ["one"]))
    previous_dialog.close.assert_called_once()


def test_batch_xlsx_export_adds_extension_and_reports_status(monkeypatch, tmp_path: Path) -> None:
    output = tmp_path / "batch-without-extension"
    workbook = MagicMock()
    monkeypatch.setattr(
        "gui.qa_ct_batch_export.build_qa_workbook",
        lambda *args, **kwargs: workbook,
    )
    app = _app(str(output))
    batch = CTBatchResult([_result()], ["Synthetic series"])

    QAAppFacade(app).export_ct_batch_xlsx(batch)

    workbook.save.assert_called_once_with(str(output) + ".xlsx")
    app.main_window.update_status.assert_called_once_with(
        f"Saved QA batch XLSX: {output}.xlsx"
    )


def test_compare_json_cancel_does_not_write_or_update_status(tmp_path: Path) -> None:
    app = _app("")
    batch = MRIBatchResult(
        [_result(analysis_type="acr_mri_large")],
        [LcRunConfig("Synthetic", "rose", 1.0, 1.0)],
    )

    QAAppFacade(app).export_mri_compare_json(batch)

    app.main_window.update_status.assert_not_called()
    assert not list(tmp_path.iterdir())


def test_ct_folder_flow_builds_folder_request(monkeypatch) -> None:
    app = _app()
    app._resolve_focused_series_ordered_paths = MagicMock(return_value=("", "", "", [], []))
    app.file_dialog = MagicMock()
    app.file_dialog.open_folder.return_value = "/synthetic/folder"
    app.config_manager = MagicMock()
    app.config_manager.get_acr_qa_vanilla_pylinac.return_value = False
    monkeypatch.setattr(facade_module, "prompt_acr_ct_options", lambda *_args, **_kwargs: (0.0, None, False))
    monkeypatch.setattr(QAAppFacade, "user_confirms_preflight", lambda *_args: True)
    start = MagicMock()
    monkeypatch.setattr(QAAppFacade, "start_qa_worker", start)

    QAAppFacade(app).open_acr_ct_phantom_analysis()

    request = start.call_args.args[0]
    assert request.folder_path == "/synthetic/folder"
    assert request.dicom_paths == []
    assert request.modality == "CT"


def test_mri_single_run_routes_to_single_worker(monkeypatch) -> None:
    app = _app()
    app._resolve_focused_series_ordered_paths = MagicMock(
        return_value=("study", "series", "MR", ["synthetic.dcm"], [])
    )
    app.config_manager = MagicMock()
    app.config_manager.get_acr_qa_vanilla_pylinac.return_value = False
    choice = _choice("Use Focused Series")
    monkeypatch.setattr(facade_module, "QMessageBox", lambda *_args: choice)
    facade_module.QMessageBox.ButtonRole = QMessageBox.ButtonRole
    facade_module.QMessageBox.StandardButton = QMessageBox.StandardButton
    monkeypatch.setattr(facade_module, "prompt_acr_mri_options", lambda *_args, **_kwargs: (1, False, 1, 0.0, "rose", 0.001, 1.0, None, False))
    monkeypatch.setattr(QAAppFacade, "user_confirms_preflight", lambda *_args: True)
    start = MagicMock()
    monkeypatch.setattr(QAAppFacade, "start_qa_worker", start)

    QAAppFacade(app).open_acr_mri_phantom_analysis()

    assert start.call_args.args[0].analysis_type == "acr_mri_large"
    assert start.call_args.kwargs["json_default_stem"] == "qa-acr-mri"


def test_nuclear_focused_image_routes_selected_class(monkeypatch) -> None:
    app = _app()
    app._resolve_focused_series_ordered_paths = MagicMock(
        return_value=("study", "series", "NM", ["synthetic.nm"], [])
    )
    app.file_dialog = MagicMock()
    choice = _choice("Use Focused Image")
    monkeypatch.setattr(facade_module, "QMessageBox", lambda *_args: choice)
    facade_module.QMessageBox.ButtonRole = QMessageBox.ButtonRole
    facade_module.QMessageBox.StandardButton = QMessageBox.StandardButton
    monkeypatch.setattr(
        facade_module,
        "prompt_nuclear_options",
        lambda *_args: PlanarUniformityOptions(),
    )
    monkeypatch.setattr(QAAppFacade, "user_confirms_preflight", lambda *_args: True)
    start = MagicMock()
    monkeypatch.setattr(QAAppFacade, "start_qa_worker", start)

    QAAppFacade(app).open_nuclear_qc_analysis()

    request = start.call_args.args[0]
    assert request.dicom_paths == ["synthetic.nm"]
    assert request.nuclear_options is not None
    app.file_dialog.open_files.assert_not_called()
