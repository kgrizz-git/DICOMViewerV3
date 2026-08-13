"""Focused state and query-contract tests for the Study Index browser dialog."""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6", reason="PySide6 not installed")

from PySide6.QtWidgets import QMessageBox

from gui.dialogs.study_index_search_dialog import (
    StudyIndexSearchDialog,
    _StudyIndexGroupedModel,
)
from utils.config.study_index_config import STUDY_INDEX_BROWSER_COLUMN_IDS_DEFAULT


class _FakeConfig:
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


class _FakeService:
    def __init__(self, batches: list[list[dict]] | None = None) -> None:
        self.batches = list(batches or [[]])
        self.calls: list[dict] = []
        self.error: Exception | None = None

    def is_backend_available(self) -> bool:
        return True

    def search_grouped_studies(self, **kwargs):
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        if len(self.calls) <= len(self.batches):
            return self.batches[len(self.calls) - 1]
        return []


def _row(uid: str = "1.2.3") -> dict:
    return {
        "study_uid": uid,
        "study_root_path": "/synthetic/study",
        "patient_name": "Doe^Jane",
        "study_date": "20240115",
        "instance_count": 4,
    }


def _dialog(qapp, *, service=None, config=None):
    service = service or _FakeService()
    config = config or _FakeConfig()
    dialog = StudyIndexSearchDialog(
        service=service,  # type: ignore[arg-type]
        config_manager=config,  # type: ignore[arg-type]
        open_paths_callback=lambda _paths: None,
    )
    return dialog, service


def test_model_formats_grouped_values_and_bounds() -> None:
    model = _StudyIndexGroupedModel(
        ["patient_name", "study_date", "instance_count", "open_file_path"]
    )
    model.set_rows(
        [
            {
                "patient_name": "b'Doe^Jane'",
                "study_date": "20240115",
                "instance_count": 4.9,
                "open_file_path": " /synthetic/file.dcm ",
            }
        ]
    )

    assert model.data(model.index(0, 0)) == "Doe^Jane"
    assert model.data(model.index(0, 1)) == "01/15/2024"
    assert model.data(model.index(0, 2)) == "4"
    assert model.open_path_for_row(0) == "/synthetic/file.dcm"
    assert model.open_path_for_row(-1) == ""
    assert model.group_row_snapshot(0)["study_date"] == "20240115"
    assert model.group_row_snapshot(5) == {}


def test_date_filters_accept_compact_and_formatted_values(qapp) -> None:
    dialog, _service = _dialog(qapp)
    try:
        dialog._date_from.setText("01152024")
        dialog._date_to.setText("20241231")
        assert dialog._date_from.text() == "01/15/2024"
        assert dialog._effective_date_filters(strict=True) == (
            "20240115",
            "20241231",
            None,
        )
    finally:
        dialog.deleteLater()


def test_search_rejects_invalid_date_without_query(qapp, monkeypatch) -> None:
    dialog, service = _dialog(qapp)
    warnings: list[str] = []
    monkeypatch.setattr(
        QMessageBox,
        "warning",
        staticmethod(lambda _parent, _title, text: warnings.append(text)),
    )
    try:
        dialog._date_from.setText("13/40/2024")
        dialog._on_search_clicked()
        assert service.calls == []
        assert warnings and "Study date from is not valid" in warnings[0]
    finally:
        dialog.deleteLater()


def test_browse_passes_filters_and_paginates(qapp) -> None:
    first_page = [_row()]
    second_page = [_row("4.5.6")]
    service = _FakeService([first_page, second_page])
    dialog, _ = _dialog(qapp, service=service, config=_FakeConfig(privacy=True))
    try:
        dialog._global_fts.setText("series keyword")
        dialog._patient_name.setText("Jane")
        dialog._modality.setText("CT")
        dialog._date_from.setText("01/15/2024")
        dialog._run_browse(reset=True, strict_dates=True)

        assert dialog._model.rowCount() == 1
        assert dialog._offset == 1
        assert not dialog._load_more_btn.isEnabled()
        assert service.calls[0]["global_fts_query"] == "series keyword"
        assert service.calls[0]["patient_name_contains"] == "Jane"
        assert service.calls[0]["modality"] == "CT"
        assert service.calls[0]["study_date_from"] == "20240115"
        assert service.calls[0]["privacy_mode"] is True

        dialog._on_load_more()
        assert dialog._model.rowCount() == 2
        assert dialog._offset == 2
        assert service.calls[1]["offset"] == 1
    finally:
        dialog.deleteLater()


def test_clear_filters_resets_fields_and_reloads_empty_state(qapp) -> None:
    service = _FakeService([[_row()], []])
    dialog, _ = _dialog(qapp, service=service)
    try:
        for field in (
            dialog._global_fts,
            dialog._patient_name,
            dialog._patient_id,
            dialog._modality,
            dialog._accession,
            dialog._study_desc,
            dialog._date_from,
            dialog._date_to,
        ):
            field.setText("synthetic")
        dialog._run_browse(reset=True)
        dialog._on_clear_filters_clicked()

        assert all(field.text() == "" for field in (
            dialog._global_fts,
            dialog._patient_name,
            dialog._patient_id,
            dialog._modality,
            dialog._accession,
            dialog._study_desc,
            dialog._date_from,
            dialog._date_to,
        ))
        assert dialog._model.rowCount() == 0
        assert dialog._offset == 0
        assert service.calls[-1]["offset"] == 0
    finally:
        dialog.deleteLater()


@pytest.mark.parametrize("error", [ValueError("bad filter"), RuntimeError("backend down")])
def test_query_errors_are_reported_without_replacing_existing_rows(qapp, monkeypatch, error) -> None:
    service = _FakeService([[_row()]])
    dialog, _ = _dialog(qapp, service=service)
    messages: list[tuple[str, str]] = []
    monkeypatch.setattr(
        QMessageBox,
        "warning",
        staticmethod(lambda _parent, title, text: messages.append((title, text))),
    )
    monkeypatch.setattr(
        QMessageBox,
        "critical",
        staticmethod(lambda _parent, title, text: messages.append((title, text))),
    )
    try:
        dialog._run_browse(reset=True)
        service.error = error
        dialog._run_browse(reset=True)
        assert dialog._model.rowCount() == 1
        assert messages
        assert messages[-1][0] == "Study index"
        assert ("Search parameters are invalid" if isinstance(error, ValueError) else "Query failed") in messages[-1][1]
    finally:
        dialog.deleteLater()
