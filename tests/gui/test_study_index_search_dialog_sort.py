"""Tests for the Study Index browser: indexed_at formatting + header-click sorting."""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6", reason="PySide6 not installed")

from gui.dialogs.study_index_search_dialog import (
    StudyIndexSearchDialog,
    _format_indexed_at_display,
    _StudyIndexGroupedModel,
)
from utils.config.study_index_config import STUDY_INDEX_BROWSER_COLUMN_IDS_DEFAULT


def test_format_indexed_at_display() -> None:
    # A fixed local epoch renders as YYYY-MM-DD HH:MM.
    from datetime import datetime

    epoch = datetime(2021, 6, 15, 9, 5).timestamp()
    assert _format_indexed_at_display(epoch) == "2021-06-15 09:05"
    assert _format_indexed_at_display(None) == ""
    assert _format_indexed_at_display("") == ""
    assert _format_indexed_at_display("not-a-number") == ""


def test_model_data_formats_indexed_at() -> None:
    from datetime import datetime

    epoch = datetime(2020, 1, 2, 3, 4).timestamp()
    model = _StudyIndexGroupedModel(["indexed_at"])
    model.set_rows([{"indexed_at": epoch}, {"indexed_at": None}])
    idx0 = model.index(0, 0)
    idx1 = model.index(1, 0)
    assert model.data(idx0) == "2020-01-02 03:04"
    assert model.data(idx1) == ""


class _FakeConfig:
    def get_study_index_browser_column_order(self) -> list[str]:
        return list(STUDY_INDEX_BROWSER_COLUMN_IDS_DEFAULT)

    def get_study_index_db_path(self) -> str:
        return "/tmp/idx.sqlite"

    def get_privacy_view(self) -> bool:
        return False


class _FakeService:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def is_backend_available(self) -> bool:
        return True

    def search_grouped_studies(self, **kwargs):
        self.calls.append(kwargs)
        return []


def _build_dialog(qapp):
    service = _FakeService()
    dlg = StudyIndexSearchDialog(
        service=service,  # type: ignore[arg-type]
        config_manager=_FakeConfig(),  # type: ignore[arg-type]
        open_paths_callback=lambda paths: None,
    )
    return dlg, service


def _logical_index_of(dlg, column_id: str) -> int:
    model = dlg._model
    for i in range(model.columnCount()):
        if model.column_id_at(i) == column_id:
            return i
    raise AssertionError(f"column {column_id!r} not found")


def test_header_click_requeries_with_sort(qapp) -> None:
    dlg, service = _build_dialog(qapp)
    try:
        service.calls.clear()
        # Click patient_name header: new column -> descending.
        dlg._on_header_section_clicked(_logical_index_of(dlg, "patient_name"))
        assert service.calls, "header click should re-query"
        last = service.calls[-1]
        assert last["order_by"] == "patient_name"
        assert last["descending"] is True
        assert last["offset"] == 0

        # Clicking the same column toggles to ascending.
        service.calls.clear()
        dlg._on_header_section_clicked(_logical_index_of(dlg, "patient_name"))
        last = service.calls[-1]
        assert last["order_by"] == "patient_name"
        assert last["descending"] is False

        # Load-more keeps the active sort.
        service.calls.clear()
        dlg._on_load_more()
        last = service.calls[-1]
        assert last["order_by"] == "patient_name"
        assert last["descending"] is False
    finally:
        dlg.deleteLater()


def test_header_click_ignores_non_sortable_column(qapp) -> None:
    dlg, service = _build_dialog(qapp)
    try:
        service.calls.clear()
        dlg._on_header_section_clicked(_logical_index_of(dlg, "modalities"))
        assert service.calls == []
        assert dlg._sort_column_id == "study_date"
    finally:
        dlg.deleteLater()


def test_indexed_at_in_default_columns() -> None:
    assert "indexed_at" in STUDY_INDEX_BROWSER_COLUMN_IDS_DEFAULT


def test_recently_indexed_clears_filters_and_sorts_by_indexed_at(qapp) -> None:
    dlg, service = _build_dialog(qapp)
    try:
        dlg._patient_name.setText("foo")
        service.calls.clear()
        dlg._on_recently_indexed_clicked()
        assert dlg._patient_name.text() == ""
        assert service.calls, "recently indexed should re-query"
        last = service.calls[-1]
        assert last["order_by"] == "indexed_at"
        assert last["descending"] is True
    finally:
        dlg.deleteLater()
