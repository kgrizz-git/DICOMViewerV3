"""Tests for the load-time Relocate… quick-action in the Study Index browser.

Covers ``StudyIndexSearchDialog._relocate_and_reopen``: when a study opened from
the index has missing files, the user can point the index at the new folder and
have the study reopened without running the bulk integrity scan.
"""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6", reason="PySide6 not installed")

from PySide6.QtWidgets import QFileDialog, QMessageBox

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
        self.relocated: list[tuple] = []
        self.relocate_result = 4

    def is_backend_available(self) -> bool:
        return True

    def relocate_study(self, study_uid, old_root, new_root) -> int:
        self.relocated.append((study_uid, old_root, new_root))
        return self.relocate_result

    def search_grouped_studies(self, **kwargs):
        return []


def _build(qapp):
    service = _FakeService()
    opened: list[list[str]] = []
    dlg = StudyIndexSearchDialog(
        service=service,  # type: ignore[arg-type]
        config_manager=_FakeConfig(),  # type: ignore[arg-type]
        open_paths_callback=opened.append,
    )
    return dlg, service, opened


def test_relocate_reopens_new_folder(qapp, monkeypatch) -> None:
    dlg, svc, opened = _build(qapp)
    try:
        monkeypatch.setattr(
            QFileDialog, "getExistingDirectory", staticmethod(lambda *a, **k: "/new/loc")
        )
        result = dlg._relocate_and_reopen("1.2.3", "/old/loc")
        assert result is True
        assert svc.relocated == [("1.2.3", "/old/loc", "/new/loc")]
        assert opened == [["/new/loc"]]
    finally:
        dlg.deleteLater()


def test_relocate_no_match_warns_and_does_not_open(qapp, monkeypatch) -> None:
    dlg, svc, opened = _build(qapp)
    svc.relocate_result = 0
    try:
        monkeypatch.setattr(
            QFileDialog, "getExistingDirectory", staticmethod(lambda *a, **k: "/new/loc")
        )
        warned = {"n": 0}
        monkeypatch.setattr(
            QMessageBox, "warning", staticmethod(lambda *a, **k: warned.__setitem__("n", 1))
        )
        result = dlg._relocate_and_reopen("1.2.3", "/old/loc")
        assert result is False
        assert svc.relocated  # service was still consulted
        assert warned["n"] == 1
        assert opened == []
    finally:
        dlg.deleteLater()


def test_relocate_cancelled_picker_is_noop(qapp, monkeypatch) -> None:
    dlg, svc, opened = _build(qapp)
    try:
        monkeypatch.setattr(
            QFileDialog, "getExistingDirectory", staticmethod(lambda *a, **k: "")
        )
        result = dlg._relocate_and_reopen("1.2.3", "/old/loc")
        assert result is False
        assert svc.relocated == []
        assert opened == []
    finally:
        dlg.deleteLater()
