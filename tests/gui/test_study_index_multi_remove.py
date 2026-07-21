"""Tests for multi-row "Remove from index" in the Study Index browser (Phase 2)."""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6", reason="PySide6 not installed")

from PySide6.QtCore import QItemSelectionModel
from PySide6.QtWidgets import QMessageBox

from gui.dialogs.study_index_search_dialog import StudyIndexSearchDialog
from utils.config.study_index_config import STUDY_INDEX_BROWSER_COLUMN_IDS_DEFAULT


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
        self.delete_calls: list[tuple[str, str]] = []

    def is_backend_available(self) -> bool:
        return True

    def search_grouped_studies(self, **kwargs):
        self.calls.append(kwargs)
        return []

    def delete_grouped_study(self, uid: str, root: str) -> int:
        self.delete_calls.append((uid, root))
        return 5


def _build_dialog(qapp):
    service = _FakeService()
    dlg = StudyIndexSearchDialog(
        service=service,  # type: ignore[arg-type]
        config_manager=_FakeConfig(),  # type: ignore[arg-type]
        open_paths_callback=lambda paths: None,
    )
    rows = [
        {
            "study_uid": "1.2.3",
            "study_root_path": "/data/study1",
            "patient_name": "Doe^John",
            "instance_count": 10,
        },
        {
            "study_uid": "4.5.6",
            "study_root_path": "/data/study2",
            "patient_name": "Smith^Jane",
            "instance_count": 20,
        },
    ]
    dlg._model.set_rows(rows)
    return dlg, service


def _select_rows(dlg, rows: list[int]) -> None:
    sel_model = dlg._table.selectionModel()
    sel_model.clearSelection()
    for row in rows:
        model_index = dlg._model.index(row, 0)
        sel_model.select(
            model_index,
            QItemSelectionModel.SelectionFlag.Select | QItemSelectionModel.SelectionFlag.Rows,
        )


def test_multi_select_remove_deletes_all(qapp, monkeypatch) -> None:
    dlg, service = _build_dialog(qapp)
    try:
        _select_rows(dlg, [0, 1])
        assert dlg._selected_rows() == [0, 1]

        monkeypatch.setattr(
            "gui.dialogs.study_index_search_dialog.QMessageBox.question",
            lambda *a, **k: QMessageBox.StandardButton.Yes,
        )
        monkeypatch.setattr(
            "gui.dialogs.study_index_search_dialog.QMessageBox.information",
            lambda *a, **k: None,
        )

        dlg._on_remove_from_index_clicked()

        assert len(service.delete_calls) == 2
        assert set(service.delete_calls) == {("1.2.3", "/data/study1"), ("4.5.6", "/data/study2")}
    finally:
        dlg.deleteLater()


def test_single_remove_still_works(qapp, monkeypatch) -> None:
    dlg, service = _build_dialog(qapp)
    try:
        dlg._table.selectRow(0)
        assert dlg._selected_rows() == [0]

        monkeypatch.setattr(
            "gui.dialogs.study_index_search_dialog.QMessageBox.question",
            lambda *a, **k: QMessageBox.StandardButton.Yes,
        )
        monkeypatch.setattr(
            "gui.dialogs.study_index_search_dialog.QMessageBox.information",
            lambda *a, **k: None,
        )

        dlg._on_remove_from_index_clicked()

        assert service.delete_calls == [("1.2.3", "/data/study1")]
    finally:
        dlg.deleteLater()


def test_remove_cancelled_is_noop(qapp, monkeypatch) -> None:
    dlg, service = _build_dialog(qapp)
    try:
        _select_rows(dlg, [0, 1])

        monkeypatch.setattr(
            "gui.dialogs.study_index_search_dialog.QMessageBox.question",
            lambda *a, **k: QMessageBox.StandardButton.No,
        )

        dlg._on_remove_from_index_clicked()

        assert service.delete_calls == []
    finally:
        dlg.deleteLater()
