"""Round-two coverage for QAAppFacade orchestration paths."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from PySide6.QtCore import Qt, QUrl
from PySide6.QtWidgets import QMessageBox

import gui.qa_app_facade as facade_module
from gui.qa_app_facade import QAAppFacade
from qa.analysis_types import (
    CTBatchResult,
    LcRunConfig,
    MRIBatchResult,
    QARequest,
    QAResult,
)

pytestmark = pytest.mark.qt


class FakeSignal:
    def __init__(self) -> None:
        self._callbacks = []

    def connect(self, callback) -> None:
        self._callbacks.append(callback)

    def emit(self, *args) -> None:
        for callback in self._callbacks:
            callback(*args)


class FakeProgress:
    def __init__(self, *_args) -> None:
        self.canceled = FakeSignal()
        self.closed = False
        self.value = None
        self.label = None

    def setWindowTitle(self, _title) -> None:
        return None

    def setWindowModality(self, _modality) -> None:
        return None

    def setWindowFlags(self, flags):
        return flags

    def windowFlags(self):
        return Qt.WindowType.Widget
    def show(self) -> None:
        return None

    def activateWindow(self) -> None:
        return None

    def raise_(self) -> None:
        return None

    def close(self) -> None:
        self.closed = True

    def setValue(self, value) -> None:
        self.value = value

    def setLabelText(self, label) -> None:
        self.label = label


class FakeWorker:
    def __init__(self, *_args, **_kwargs) -> None:
        self.result_ready = FakeSignal()
        self.batch_result_ready = FakeSignal()
        self.series_completed = FakeSignal()
        self.finished = FakeSignal()
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


def _result(**kwargs) -> QAResult:
    values = {"success": True, "analysis_type": "acr_ct", "num_images": 3}
    values.update(kwargs)
    return QAResult(**values)


def _batch_result() -> CTBatchResult:
    return CTBatchResult(
        run_results=[_result(series_uid="synthetic-series")],
        run_labels=["Synthetic series"],
    )


def test_preflight_cancel_stops_ct_flow_before_options(qapp, monkeypatch) -> None:
    app = _app()
    app._resolve_focused_series_ordered_paths = MagicMock(
        return_value=("study", "series", "MR", ["synthetic.dcm"], [])
    )
    app.config_manager = MagicMock()
    app.config_manager.get_acr_qa_vanilla_pylinac.return_value = False
    facade = QAAppFacade(app)
    confirms = MagicMock(return_value=False)
    monkeypatch.setattr(QAAppFacade, "user_confirms_preflight", confirms)
    class FakeChoice:
        def __init__(self, _parent) -> None:
            self._focused = None

        def setWindowTitle(self, _title) -> None:
            return None

        def setText(self, _text) -> None:
            return None

        def addButton(self, text, _role=None):
            button = SimpleNamespace(text=lambda: text)
            if text == "Use Focused Series":
                self._focused = button
            return button

        def setWindowFlags(self, flags):
            return flags

        def windowFlags(self):
            return Qt.WindowType.Widget

        def activateWindow(self) -> None:
            return None

        def raise_(self) -> None:
            return None

        def exec(self) -> int:
            return 0

        def clickedButton(self):
            return self._focused

        def button(self, _button):
            return None

    class FakeMessageBox:
        StandardButton = QMessageBox.StandardButton
        ButtonRole = QMessageBox.ButtonRole

        def __new__(cls, parent):
            return FakeChoice(parent)

    monkeypatch.setattr(facade_module, "QMessageBox", FakeMessageBox)
    prompt = MagicMock()
    monkeypatch.setattr(facade_module, "prompt_acr_ct_options", prompt)

    facade.open_acr_ct_phantom_analysis()

    prompt.assert_not_called()
    assert app._qa_worker is None


def test_result_summary_success_and_pdf_decline_are_user_visible(qapp, monkeypatch) -> None:
    app = _app()
    facade = QAAppFacade(app)
    box = MagicMock()
    box.windowFlags.return_value = 0
    box.exec.return_value = int(QMessageBox.StandardButton.No)
    monkeypatch.setattr(facade_module, "QMessageBox", MagicMock(return_value=box, Icon=QMessageBox.Icon, StandardButton=QMessageBox.StandardButton))
    result = _result(
        pdf_report_path="synthetic-report.pdf",
        pylinac_version="synthetic-version",
        pylinac_analysis_profile={"vanilla_pylinac": True},
    )

    facade.show_qa_result_dialog("Synthetic QA", result)
    facade.offer_open_single_run_pdf(result)

    assert "Completed successfully." in box.setText.call_args_list[0].args[0]
    assert "PDF: synthetic-report.pdf" in box.setText.call_args_list[0].args[0]
    assert box.exec.call_count == 2


@pytest.mark.parametrize("chosen_path, expected_path", [("report", "report"), ("", None)])
def test_json_export_adds_extension_or_honors_cancel(qapp, tmp_path: Path, chosen_path, expected_path) -> None:
    output = str(tmp_path / chosen_path) if chosen_path else ""
    app = _app(output)
    result = _result(metrics={"synthetic_metric": 2})

    QAAppFacade(app).export_qa_json(result, "synthetic")

    if expected_path:
        saved = tmp_path / expected_path
        assert json.loads(saved.read_text(encoding="utf-8"))["run"]["status"] == "success"
        app.main_window.update_status.assert_called_once_with(f"Saved QA JSON: {saved}")
    else:
        app.main_window.update_status.assert_not_called()


def test_ct_batch_worker_callbacks_update_progress_and_show_dialog(qapp, monkeypatch) -> None:
    app = _app()
    facade = QAAppFacade(app)
    progress = FakeProgress()
    worker = FakeWorker()
    monkeypatch.setattr(facade_module, "QProgressDialog", lambda *args: progress)
    monkeypatch.setattr(facade_module, "QACTBatchWorker", lambda *args, **kwargs: worker)
    show_dialog = MagicMock()
    monkeypatch.setattr(QAAppFacade, "show_ct_batch_result_dialog", show_dialog)

    facade.start_ct_batch_worker([QARequest("acr_ct")], ["Synthetic series"])
    worker.series_completed.emit(1, 1, _result())
    worker.batch_result_ready.emit(_batch_result())

    assert progress.value == 1
    assert progress.label.endswith("1 of 1)...")
    show_dialog.assert_called_once_with(worker, _batch_result())
    assert worker.started is True


def test_ct_batch_dialog_wires_exports_and_cleans_temp_dir(qapp, monkeypatch) -> None:
    app = _app()
    facade = QAAppFacade(app)
    worker = FakeWorker()
    dialog = MagicMock()
    monkeypatch.setattr(facade_module, "create_ct_batch_result_dialog", MagicMock(return_value=dialog))
    export_xlsx = MagicMock()
    export_json = MagicMock()
    monkeypatch.setattr(QAAppFacade, "export_ct_batch_xlsx", export_xlsx)
    monkeypatch.setattr(QAAppFacade, "export_ct_batch_json", export_json)
    batch = _batch_result()

    facade.show_ct_batch_result_dialog(worker, batch)

    factory = facade_module.create_ct_batch_result_dialog
    kwargs = factory.call_args.kwargs
    kwargs["on_save_xlsx_clicked"]()
    kwargs["on_save_json_clicked"]()
    kwargs["on_destroyed"]()
    export_xlsx.assert_called_once_with(batch)
    export_json.assert_called_once_with(batch)
    assert app._ct_batch_result_dialog is None
    worker.image_temp_dir.cleanup.assert_called_once()


def test_ct_batch_json_and_xlsx_exports_report_synthetic_paths(qapp, monkeypatch, tmp_path: Path) -> None:
    json_path = tmp_path / "batch.json"
    xlsx_path = tmp_path / "batch.xlsx"
    app = _app(str(json_path))
    facade = QAAppFacade(app)
    batch = _batch_result()

    facade.export_ct_batch_json(batch)
    assert json.loads(json_path.read_text(encoding="utf-8"))[0]["run"]["status"] == "success"

    workbook = MagicMock()
    monkeypatch.setattr(facade_module, "build_qa_workbook", MagicMock(return_value=workbook))
    app._prompt_save_path.return_value = str(xlsx_path)
    facade.export_ct_batch_xlsx(batch)

    workbook.save.assert_called_once_with(str(xlsx_path))
    assert app.main_window.update_status.call_args.args[0].endswith(str(xlsx_path))


def test_open_path_missing_is_safe_and_existing_path_uses_deferred_qt_open(qapp, monkeypatch, tmp_path: Path) -> None:
    app = _app()
    facade = QAAppFacade(app)
    warning = MagicMock()
    monkeypatch.setattr(facade_module.QMessageBox, "warning", warning)
    facade.open_path_in_system_viewer(str(tmp_path / "missing.pdf"))
    warning.assert_called_once()

    existing = tmp_path / "synthetic.pdf"
    existing.write_text("synthetic", encoding="utf-8")
    scheduled = {}
    monkeypatch.setattr(facade_module.QTimer, "singleShot", lambda _ms, callback: scheduled.setdefault("callback", callback))
    opened = MagicMock(return_value=True)
    monkeypatch.setattr(facade_module.QDesktopServices, "openUrl", opened)
    facade.open_path_in_system_viewer(str(existing))
    scheduled["callback"]()
    opened.assert_called_once_with(QUrl.fromLocalFile(str(existing)))


def test_mri_compare_dialog_wires_open_and_json_export(qapp, monkeypatch, tmp_path: Path) -> None:
    app = _app(str(tmp_path / "compare.json"))
    facade = QAAppFacade(app)
    dialog = MagicMock()
    monkeypatch.setattr(facade_module, "create_mri_compare_result_dialog", MagicMock(return_value=dialog))
    open_path = MagicMock()
    monkeypatch.setattr(QAAppFacade, "open_path_in_system_viewer", open_path)
    run_config = LcRunConfig("Synthetic run", "rose", 1.0, 2.0)
    batch = MRIBatchResult([_result(analysis_type="acr_mri_large")], [run_config])

    facade.show_mri_compare_result_dialog(batch, json_inputs={"synthetic": True})
    kwargs = facade_module.create_mri_compare_result_dialog.call_args.kwargs
    kwargs["on_open_pdf"]("synthetic.pdf")
    kwargs["on_save_json_clicked"]()

    open_path.assert_called_once_with("synthetic.pdf")
    assert app._mri_compare_result_dialog is dialog
    assert (tmp_path / "compare.json").exists()
    assert json.loads((tmp_path / "compare.json").read_text(encoding="utf-8"))["compare_mode"] is True


def test_worker_result_callback_uses_controlled_fake_and_cleans_temp_dir(qapp, monkeypatch) -> None:
    app = _app()
    facade = QAAppFacade(app)
    progress = FakeProgress()
    worker = FakeWorker()
    image_dir = MagicMock()
    monkeypatch.setattr(facade_module, "QProgressDialog", lambda *args: progress)
    monkeypatch.setattr(facade_module, "QAAnalysisWorker", lambda request: worker)
    show_dialog = MagicMock()
    offer_pdf = MagicMock()
    export_results = MagicMock()
    monkeypatch.setattr(QAAppFacade, "show_qa_result_dialog", show_dialog)
    monkeypatch.setattr(QAAppFacade, "offer_open_single_run_pdf", offer_pdf)
    monkeypatch.setattr(QAAppFacade, "export_qa_results", export_results)

    facade.start_qa_worker(
        QARequest("acr_ct"),
        progress_title="Synthetic",
        progress_label="Synthetic run",
        result_dialog_title="Synthetic result",
        json_default_stem="synthetic",
        analyzed_image_temp_dir=image_dir,
    )
    worker.result_ready.emit(_result())

    show_dialog.assert_called_once()
    offer_pdf.assert_called_once()
    export_results.assert_called_once()
    image_dir.cleanup.assert_called_once()
