"""Tests for the integrity-scan results dialog (relocate / remove handlers)."""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6", reason="PySide6 not installed")

from PySide6.QtWidgets import QFileDialog, QMessageBox

from core.study_index.index_service import MissingStudyRecord
from gui.dialogs.study_index_search_dialog import _MissingStudiesDialog


class _FakeService:
    def __init__(self) -> None:
        self.relocated: list[tuple] = []
        self.deleted: list[tuple] = []
        self.relocate_result = 3

    def is_backend_available(self) -> bool:
        return True

    def relocate_study(self, study_uid, old_root, new_root) -> int:
        self.relocated.append((study_uid, old_root, new_root))
        return self.relocate_result

    def delete_grouped_study(self, study_uid, root) -> int:
        self.deleted.append((study_uid, root))
        return 2


def _records(n: int = 2) -> list[MissingStudyRecord]:
    return [
        MissingStudyRecord(
            study_uid=f"1.2.{i}",
            study_root_path=f"/data/study{i}",
            patient_name=f"Pat{i}",
            study_date="20200101",
            modalities="CT",
            missing_count=1,
            total_count=3,
        )
        for i in range(n)
    ]


def _build(qapp, records=None):
    service = _FakeService()
    changed = {"n": 0}
    dlg = _MissingStudiesDialog(
        records if records is not None else _records(),
        service,  # type: ignore[arg-type]
        privacy=False,
        on_changed=lambda: changed.__setitem__("n", changed["n"] + 1),
        parent=None,
    )
    return dlg, service, changed


def test_populate_lists_rows(qapp) -> None:
    dlg, _svc, _changed = _build(qapp)
    try:
        assert dlg._table.rowCount() == 2
        assert dlg._table.item(0, 0).text() == "Pat0"
        assert dlg._table.item(0, 4).text() == "1 of 3 files missing"
    finally:
        dlg.deleteLater()


def test_relocate_selected_calls_service_and_refreshes(qapp, monkeypatch) -> None:
    dlg, svc, changed = _build(qapp)
    try:
        dlg._table.selectRow(0)
        monkeypatch.setattr(
            QFileDialog, "getExistingDirectory", staticmethod(lambda *a, **k: "/new/loc")
        )
        monkeypatch.setattr(QMessageBox, "information", staticmethod(lambda *a, **k: None))
        dlg._relocate_selected()
        assert svc.relocated == [("1.2.0", "/data/study0", "/new/loc")]
        assert changed["n"] == 1
        # Row dropped after a successful relocate.
        assert dlg._table.rowCount() == 1
    finally:
        dlg.deleteLater()


def test_relocate_no_match_keeps_rows(qapp, monkeypatch) -> None:
    dlg, svc, changed = _build(qapp)
    svc.relocate_result = 0
    try:
        dlg._table.selectRow(0)
        monkeypatch.setattr(
            QFileDialog, "getExistingDirectory", staticmethod(lambda *a, **k: "/new/loc")
        )
        warned = {"n": 0}
        monkeypatch.setattr(
            QMessageBox, "warning", staticmethod(lambda *a, **k: warned.__setitem__("n", 1))
        )
        dlg._relocate_selected()
        assert svc.relocated  # service was called
        assert warned["n"] == 1
        assert changed["n"] == 0
        assert dlg._table.rowCount() == 2  # nothing dropped
    finally:
        dlg.deleteLater()


def test_relocate_cancelled_picker_noop(qapp, monkeypatch) -> None:
    dlg, svc, changed = _build(qapp)
    try:
        dlg._table.selectRow(0)
        monkeypatch.setattr(
            QFileDialog, "getExistingDirectory", staticmethod(lambda *a, **k: "")
        )
        dlg._relocate_selected()
        assert svc.relocated == []
        assert changed["n"] == 0
    finally:
        dlg.deleteLater()


def test_remove_selected_confirmed(qapp, monkeypatch) -> None:
    dlg, svc, changed = _build(qapp)
    try:
        dlg._table.selectRow(1)
        monkeypatch.setattr(
            QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes)
        )
        dlg._remove_selected()
        assert svc.deleted == [("1.2.1", "/data/study1")]
        assert changed["n"] == 1
        assert dlg._table.rowCount() == 1
    finally:
        dlg.deleteLater()


def test_remove_selected_declined(qapp, monkeypatch) -> None:
    dlg, svc, changed = _build(qapp)
    try:
        dlg._table.selectRow(0)
        monkeypatch.setattr(
            QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.StandardButton.No)
        )
        dlg._remove_selected()
        assert svc.deleted == []
        assert changed["n"] == 0
        assert dlg._table.rowCount() == 2
    finally:
        dlg.deleteLater()


def test_remove_all_confirmed(qapp, monkeypatch) -> None:
    dlg, svc, changed = _build(qapp)
    try:
        monkeypatch.setattr(
            QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes)
        )
        monkeypatch.setattr(QMessageBox, "information", staticmethod(lambda *a, **k: None))
        dlg._remove_all()
        assert len(svc.deleted) == 2
        assert changed["n"] == 1
        assert dlg._table.rowCount() == 0
    finally:
        dlg.deleteLater()


def test_privacy_masks_patient_name(qapp) -> None:
    service = _FakeService()
    dlg = _MissingStudiesDialog(
        _records(1),
        service,  # type: ignore[arg-type]
        privacy=True,
        on_changed=lambda: None,
        parent=None,
    )
    try:
        assert dlg._table.item(0, 0).text() == "***"
    finally:
        dlg.deleteLater()
