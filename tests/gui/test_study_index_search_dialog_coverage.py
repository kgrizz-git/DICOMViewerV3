"""Behavioral coverage for the study-index search dialog.

The existing sorting/state suites cover the normal query contract.  These tests
exercise the dialog's user-facing guards and failure paths while replacing only
the modal/file-picker calls that would otherwise block a headless test.
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock

import pytest

pytest.importorskip("PySide6", reason="PySide6 not installed")

from PySide6.QtCore import QModelIndex
from PySide6.QtWidgets import QDialog, QFileDialog, QMessageBox

from core.study_index.index_service import MissingStudyRecord
from gui.dialogs.study_index_search_dialog import (
    StudyIndexSearchDialog,
    _AboutStudyIndexDialog,
    _format_indexed_at_display,
    _MissingStudiesDialog,
    _StudyIndexGroupedModel,
)
from utils.config.study_index_config import STUDY_INDEX_BROWSER_COLUMN_IDS_DEFAULT


class Config:
    def __init__(self, privacy: bool = False) -> None:
        self.privacy = privacy
        self.saved_orders: list[list[str]] = []

    def get_study_index_browser_column_order(self) -> list[str]:
        return list(STUDY_INDEX_BROWSER_COLUMN_IDS_DEFAULT)

    def get_study_index_db_path(self) -> str:
        return "/synthetic/index.sqlite"

    def get_privacy_view(self) -> bool:
        return self.privacy

    def set_study_index_browser_column_order(self, order: list[str]) -> None:
        self.saved_orders.append(order)

    def get_last_path(self) -> str:
        return "/synthetic"


class Service:
    def __init__(self, batches: list[list[dict]] | None = None) -> None:
        self.batches = batches or [[]]
        self.calls: list[dict] = []
        self.error: Exception | None = None
        self.file_paths: list[str] = []
        self.deleted: list[tuple[str, str]] = []
        self.relocated: list[tuple[str, str, str]] = []
        self.relocate_result = 2

    def is_backend_available(self) -> bool:
        return True

    def search_grouped_studies(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return self.batches[len(self.calls) - 1] if len(self.calls) <= len(self.batches) else []

    def get_file_paths_for_study(self, uid: str, root: str) -> list[str]:
        return list(self.file_paths)

    def delete_grouped_study(self, uid: str, root: str) -> int:
        self.deleted.append((uid, root))
        return 3

    def relocate_study(self, uid: str, old: str, new: str) -> int:
        self.relocated.append((uid, old, new))
        return self.relocate_result

    def start_index_folder(self, folder, on_finished, on_failed) -> None:
        on_finished(4)

    def row_count(self) -> int:
        return 12

    def db_file_size_bytes(self) -> int:
        return 1024

    def db_last_modified(self) -> float:
        return datetime(2024, 1, 2).timestamp()

    def move_database(self, dest: str) -> str:
        return dest

    def export_entries(self) -> list[dict]:
        return [{"study_uid": "1.2.3", "file_path": "/x.dcm"}]

    def import_entries(self, rows: list[dict]) -> tuple[int, int]:
        return len(rows), 1


def row(uid: str = "1.2.3", **changes) -> dict:
    value = {
        "study_uid": uid,
        "study_root_path": "/missing/study",
        "patient_name": "Doe^Jane",
        "patient_id": "P1",
        "study_date": "20240115",
        "instance_count": 4,
        "series_count": 2,
        "accession_number": "A1",
        "study_description": "Head CT",
        "modalities": "CT",
        "open_file_path": "/missing/sample.dcm",
        "indexed_at": 1700000000.0,
    }
    value.update(changes)
    return value


def dialog(qapp, service=None, config=None, opened=None):
    service = service or Service()
    if opened is None:
        opened = []
    result = StudyIndexSearchDialog(
        service, config or Config(), opened.append
    )
    return result, service, opened


def messages(monkeypatch, name: str) -> list[str]:
    result: list[str] = []
    monkeypatch.setattr(
        QMessageBox,
        name,
        staticmethod(lambda _parent, _title, text: result.append(text)),
    )
    return result


def test_model_guards_and_display_branches() -> None:
    assert _format_indexed_at_display(float("nan")) == ""
    assert _format_indexed_at_display("bad") == ""
    assert _format_indexed_at_display(1e999) == ""
    model = _StudyIndexGroupedModel(["patient_name", "instance_count"])
    model.set_rows([{"patient_name": None, "instance_count": 2.9}])
    assert model.data(QModelIndex()) is None
    assert model.data(model.index(0, 0)) == ""
    assert model.data(model.index(0, 1)) == "2"
    assert model.rowCount(model.index(0, 0)) == 0
    assert model.columnCount(model.index(0, 0)) == 0
    model.append_rows([])
    assert model.open_path_for_row(9) == ""
    assert model.group_row_snapshot(9) == {}


def test_date_filter_strictness_and_formatting(qapp) -> None:
    dlg, _, _ = dialog(qapp)
    try:
        dlg._date_from.setText("01152024")
        dlg._date_to.setText("99/99/9999")
        assert dlg._effective_date_filters(strict=True)[2].startswith("Study date to")
        assert dlg._effective_date_filters(strict=False) == ("20240115", "", None)
    finally:
        dlg.deleteLater()


def test_browse_backend_date_and_query_errors(monkeypatch, qapp) -> None:
    service = Service([ [row()]])
    dlg, _, _ = dialog(qapp, service=service)
    try:
        service.is_backend_available = lambda: False  # type: ignore[method-assign]
        warning = messages(monkeypatch, "warning")
        dlg._run_browse(reset=True)
        assert service.calls == []
        assert "sqlcipher3" in warning[0]

        service.is_backend_available = lambda: True  # type: ignore[method-assign]
        dlg._date_from.setText("13/40/2024")
        dlg._run_browse(reset=True, strict_dates=True)
        assert len(service.calls) == 0
        assert "Study date from" in warning[-1]

        service.error = ValueError("bad filter")
        dlg._run_browse(reset=True)
        assert "Search parameters are invalid" in warning[-1]

        critical = messages(monkeypatch, "critical")
        service.error = RuntimeError("query failed")
        dlg._run_browse(reset=True)
        assert "Query failed" in critical[0]
    finally:
        dlg.deleteLater()


def test_browse_pagination_and_clear_reset(qapp) -> None:
    service = Service([[row()], [row("4.5.6")]])
    dlg, _, _ = dialog(qapp, service=service)
    try:
        dlg._patient_name.setText("Jane")
        dlg._run_browse(reset=True)
        assert dlg._model.rowCount() == 1
        assert dlg._offset == 1
        dlg._on_load_more()
        assert dlg._model.rowCount() == 2
        assert service.calls[-1]["offset"] == 1
        dlg._patient_name.setText("stale")
        dlg._on_clear_filters_clicked()
        assert dlg._patient_name.text() == ""
        assert service.calls[-1]["offset"] == 0
    finally:
        dlg.deleteLater()


def test_selection_and_open_row_guards(monkeypatch, qapp, tmp_path) -> None:
    dlg, service, opened = dialog(qapp)
    try:
        info = messages(monkeypatch, "information")
        dlg._open_selected_file()
        assert info == ["Select a row first."]
        warning = messages(monkeypatch, "warning")
        dlg._model.set_rows([row(study_uid="", study_root_path="")])
        dlg._open_row(0)
        assert "missing study UID" in warning[0]

        root = tmp_path / "study"
        root.mkdir()
        dlg._model.set_rows([row(study_root_path=str(root))])
        dlg._open_row(0)
        assert opened == [[str(root)]]
        assert dlg.result() == QDialog.DialogCode.Accepted
    finally:
        dlg.deleteLater()


def test_open_row_file_errors_and_partial_missing(monkeypatch, qapp, tmp_path) -> None:
    service = Service()
    opened: list[list[str]] = []
    dlg, _, _ = dialog(qapp, service=service, opened=opened)
    try:
        service.get_file_paths_for_study = MagicMock(side_effect=RuntimeError("db"))  # type: ignore[method-assign]
        critical = messages(monkeypatch, "critical")
        dlg._model.set_rows([row()])
        dlg._open_row(0)
        assert "Failed to retrieve file list" in critical[0]

        existing = tmp_path / "present.dcm"
        existing.write_bytes(b"dcm")
        service.get_file_paths_for_study = lambda _uid, _root: [str(existing), "/gone.dcm"]  # type: ignore[method-assign]
        warning = messages(monkeypatch, "warning")
        dlg._open_row(0)
        assert "1 of 2" in warning[0]
        assert opened == [[str(existing)]]
    finally:
        dlg.deleteLater()


def test_open_row_missing_files_can_load_sample_or_cancel(monkeypatch, qapp, tmp_path) -> None:
    sample = tmp_path / "sample.dcm"
    sample.write_bytes(b"dcm")
    service = Service()
    service.file_paths = []
    opened: list[list[str]] = []
    dlg, _, _ = dialog(qapp, service=service, opened=opened)
    try:
        buttons = []
        original_add_button = QMessageBox.addButton

        def capture_button(box, *args):
            button = original_add_button(box, *args)
            buttons.append(button)
            return button

        monkeypatch.setattr(QMessageBox, "addButton", capture_button)
        monkeypatch.setattr(QMessageBox, "exec", lambda _box: 0)
        monkeypatch.setattr(QMessageBox, "clickedButton", lambda _box: buttons[0])
        dlg._model.set_rows([row(open_file_path=str(sample))])
        dlg._open_row(0)
        assert opened == [[str(sample)]]

        buttons.clear()
        opened.clear()
        dlg._model.set_rows([row(open_file_path="")])
        monkeypatch.setattr(QMessageBox, "clickedButton", lambda _box: None)
        dlg._open_row(0)
        assert opened == []
    finally:
        dlg.deleteLater()


def test_relocate_and_reopen_success_and_guards(monkeypatch, qapp) -> None:
    service = Service()
    dlg, _, opened = dialog(qapp, service=service)
    try:
        service.is_backend_available = lambda: False  # type: ignore[method-assign]
        messages(monkeypatch, "warning")
        assert dlg._relocate_and_reopen("1.2.3", "/old") is False
        service.is_backend_available = lambda: True  # type: ignore[method-assign]
        monkeypatch.setattr(QFileDialog, "getExistingDirectory", lambda *_a: "/new")
        service.relocate_result = 0
        warning = messages(monkeypatch, "warning")
        assert dlg._relocate_and_reopen("1.2.3", "/old") is False
        assert "No relocated files" in warning[-1]
        service.relocate_result = 2
        dlg._run_browse = MagicMock()  # type: ignore[method-assign]
        assert dlg._relocate_and_reopen("1.2.3", "/old") is True
        assert opened == [["/new"]]
        assert service.relocated[-1] == ("1.2.3", "/old", "/new")
    finally:
        dlg.deleteLater()


def test_remove_guards_confirmation_privacy_and_errors(monkeypatch, qapp) -> None:
    service = Service()
    dlg, _, _ = dialog(qapp, service=service, config=Config(privacy=True))
    try:
        info = messages(monkeypatch, "information")
        dlg._on_remove_from_index_clicked()
        assert "Select a study row first" in info[0]
        warning = messages(monkeypatch, "warning")
        dlg._model.set_rows([row(study_uid="", study_root_path="")])
        dlg._remove_studies_at_rows([0])
        assert "missing a study UID" in warning[0]

        dlg._model.set_rows([row(patient_name="Secret")])
        prompts: list[str] = []
        monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda _p, _t, text: (prompts.append(text), QMessageBox.StandardButton.No)[1]))
        dlg._remove_studies_at_rows([0])
        assert "***" in prompts[0] and "Secret" not in prompts[0]

        monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *_a: QMessageBox.StandardButton.Yes))
        service.delete_grouped_study = MagicMock(side_effect=RuntimeError("locked"))  # type: ignore[method-assign]
        critical = messages(monkeypatch, "critical")
        dlg._remove_studies_at_rows([0])
        assert "Remove failed" in critical[0]
    finally:
        dlg.deleteLater()


def test_missing_studies_dialog_guards_and_success(monkeypatch, qapp) -> None:
    record = MissingStudyRecord("1.2.3", "/old", "Pat", "20200101", "CT", 1, 2)
    service = Service()
    changed: list[bool] = []
    dlg = _MissingStudiesDialog([record], service, privacy=False, on_changed=lambda: changed.append(True))
    try:
        info = messages(monkeypatch, "information")
        dlg._relocate_selected()
        dlg._remove_selected()
        assert info == ["Select a study first.", "Select a study first."]
        dlg._table.selectRow(0)
        monkeypatch.setattr(QFileDialog, "getExistingDirectory", lambda *_a: "/new")
        monkeypatch.setattr(QMessageBox, "information", staticmethod(lambda *_a: None))
        dlg._relocate_selected()
        assert service.relocated == [("1.2.3", "/old", "/new")]
        assert changed == [True]
        assert dlg._table.rowCount() == 0
    finally:
        dlg.deleteLater()


def test_missing_studies_remove_all_declined_and_empty(monkeypatch, qapp) -> None:
    record = MissingStudyRecord("1.2.3", "/old", "Pat", "20200101", "CT", 1, 2)
    changed: list[bool] = []
    dlg = _MissingStudiesDialog([record], Service(), privacy=True, on_changed=lambda: changed.append(True))
    try:
        monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *_a: QMessageBox.StandardButton.No))
        dlg._remove_all()
        assert dlg._table.rowCount() == 1 and changed == []
        dlg._records = []
        dlg._populate()
        dlg._remove_all()
        assert dlg._table.rowCount() == 0
    finally:
        dlg.deleteLater()


def test_missing_studies_error_paths(monkeypatch, qapp) -> None:
    record = MissingStudyRecord("1.2.3", "/old", "Pat", "20200101", "CT", 1, 2)
    service = Service()
    dlg = _MissingStudiesDialog([record], service, privacy=False, on_changed=lambda: None)
    try:
        dlg._table.selectRow(0)
        monkeypatch.setattr(QFileDialog, "getExistingDirectory", lambda *_a: "/new")
        service.relocate_study = MagicMock(side_effect=RuntimeError("io"))  # type: ignore[method-assign]
        critical = messages(monkeypatch, "critical")
        dlg._relocate_selected()
        assert "Relocate failed" in critical[0]
        monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *_a: QMessageBox.StandardButton.Yes))
        service.delete_grouped_study = MagicMock(side_effect=RuntimeError("lock"))  # type: ignore[method-assign]
        dlg._remove_selected()
        assert "Remove failed" in critical[-1]
    finally:
        dlg.deleteLater()


def test_about_refresh_move_export_import(monkeypatch, qapp, tmp_path) -> None:
    service = Service()
    changed: list[bool] = []
    dlg = _AboutStudyIndexDialog(service, Config(), on_changed=lambda: changed.append(True))
    try:
        assert dlg._rows_value.text() == "12"
        monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *_a: (str(tmp_path / "db.sqlite"), ""))
        monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *_a: QMessageBox.StandardButton.Yes))
        monkeypatch.setattr(QMessageBox, "information", staticmethod(lambda *_a: None))
        dlg._move_index()
        assert changed == [True]

        export = tmp_path / "export.csv"
        monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *_a: (str(export), ""))
        dlg._export_index()
        assert export.exists()

        source = tmp_path / "import.csv"
        source.write_text("study_uid,file_path\n1.2.3,/x.dcm\n", encoding="utf-8")
        monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *_a: (str(source), ""))
        dlg._import_index()
        assert changed == [True, True]
    finally:
        dlg.deleteLater()


def test_about_import_and_export_errors(monkeypatch, qapp) -> None:
    service = Service()
    dlg = _AboutStudyIndexDialog(service, Config(), on_changed=lambda: None)
    try:
        monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *_a: ("/dest.csv", ""))
        service.export_entries = MagicMock(side_effect=RuntimeError("io"))  # type: ignore[method-assign]
        critical = messages(monkeypatch, "critical")
        dlg._export_index()
        assert "Export failed" in critical[0]
        monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *_a: ("/bad.csv", ""))
        monkeypatch.setattr("gui.dialogs.study_index_search_dialog.read_entries_csv", MagicMock(side_effect=RuntimeError("parse")))
        dlg._import_index()
        assert "Import failed" in critical[-1]
    finally:
        dlg.deleteLater()


def test_backend_and_about_guards(monkeypatch, qapp) -> None:
    service = Service()
    service.is_backend_available = lambda: False  # type: ignore[method-assign]
    dlg, _, _ = dialog(qapp, service=service)
    try:
        warning = messages(monkeypatch, "warning")
        dlg._show_about_index()
        assert "sqlcipher3" in warning[0]
        dlg._check_indexed_studies()
        assert len(warning) == 2
    finally:
        dlg.deleteLater()


def test_missing_study_and_location_guards(monkeypatch, qapp) -> None:
    dlg, _, _ = dialog(qapp)
    try:
        info = messages(monkeypatch, "information")
        dlg._show_missing_studies([])
        assert "All indexed studies were found" in info[0]
        monkeypatch.setattr(
            "gui.dialogs.study_index_search_dialog.open_study_index_location",
            lambda _config: False,
        )
        dlg._on_open_index_location()
        assert "Could not open the index location" in info[-1]
    finally:
        dlg.deleteLater()
