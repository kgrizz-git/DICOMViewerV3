"""Focused QA facade tests for preflight, summaries, and local exports."""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import MagicMock

from PySide6.QtWidgets import QMessageBox

from gui.qa_app_facade import QAAppFacade
from qa.analysis_types import QAResult


def _app(save_path: str = "") -> SimpleNamespace:
    return SimpleNamespace(
        main_window=MagicMock(),
        _prompt_save_path=MagicMock(return_value=save_path),
    )


def _message_box(monkeypatch, response: int) -> MagicMock:
    """Install a modal-message fake while retaining real enum values."""
    box = MagicMock()
    box.windowFlags.return_value = 0
    box.exec.return_value = response
    message_box = MagicMock(return_value=box)
    message_box.Icon = QMessageBox.Icon
    message_box.StandardButton = QMessageBox.StandardButton
    monkeypatch.setattr("gui.qa_app_facade.QMessageBox", message_box)
    return box


def test_preflight_warnings_include_folder_and_modality_context() -> None:
    facade = QAAppFacade(_app())

    warnings = facade.build_preflight_warnings(
        expected_modality="CT",
        use_focused=False,
        folder_path="/synthetic/input",
        datasets=[],
        modality="MR",
    )

    assert len(warnings) == 2
    assert "folder input" in warnings[0]
    assert "targets CT" in warnings[1]


def test_user_confirms_preflight_only_when_yes(monkeypatch) -> None:
    app = _app()
    facade = QAAppFacade(app)
    box = _message_box(monkeypatch, int(QMessageBox.StandardButton.No))

    assert facade.user_confirms_preflight(["Synthetic warning"]) is False
    assert "Synthetic warning" in box.setText.call_args.args[0]
    assert facade.user_confirms_preflight([]) is True


def test_show_result_dialog_includes_failure_details(monkeypatch) -> None:
    facade = QAAppFacade(_app())
    box = _message_box(monkeypatch, int(QMessageBox.StandardButton.Ok))
    result = QAResult(
        success=False,
        analysis_type="acr_ct",
        study_uid="1.2.3",
        series_uid="1.2.4",
        num_images=4,
        pylinac_version="3.0",
        warnings=["Synthetic warning"],
        errors=["Synthetic failure"],
        pylinac_analysis_profile={"vanilla_pylinac": False, "vanilla_equivalent": False},
    )

    facade.show_qa_result_dialog("QA result", result)

    text = box.setText.call_args.args[0]
    assert "Analysis failed." in text
    assert "Synthetic warning" in text
    assert "Synthetic failure" in text
    box.setIcon.assert_called_once_with(QMessageBox.Icon.Warning)


def test_offer_pdf_opens_only_after_confirmation(monkeypatch) -> None:
    facade = QAAppFacade(_app())
    _message_box(monkeypatch, int(QMessageBox.StandardButton.Yes))
    open_path = MagicMock()
    monkeypatch.setattr(QAAppFacade, "open_path_in_system_viewer", open_path)
    result = QAResult(success=True, analysis_type="acr_ct", pdf_report_path="report.pdf")

    facade.offer_open_single_run_pdf(result)

    open_path.assert_called_once_with("report.pdf")


def test_export_qa_results_writes_json_and_updates_status(tmp_path) -> None:
    output = tmp_path / "qa-result.json"
    app = _app(str(output))
    result = QAResult(success=True, analysis_type="acr_ct", metrics={"score": 1})

    QAAppFacade(app).export_qa_results(result, "qa-result", inputs={"synthetic": True})

    assert json.loads(output.read_text(encoding="utf-8"))["run"]["status"] == "success"
    app.main_window.update_status.assert_called_once_with(f"Saved QA JSON: {output}")


def test_export_qa_results_writes_csv_and_updates_status(tmp_path) -> None:
    output = tmp_path / "qa-result.csv"
    app = _app(str(output))
    result = QAResult(success=True, analysis_type="acr_ct", metrics={"score": 1})

    QAAppFacade(app).export_qa_results(result, "qa-result")

    assert "score,1" in output.read_text(encoding="utf-8")
    app.main_window.update_status.assert_called_once_with(f"Saved QA CSV: {output}")
