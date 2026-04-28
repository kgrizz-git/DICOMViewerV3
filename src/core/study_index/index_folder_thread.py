"""
Background thread: crawl a folder tree and index DICOM headers into the study index.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Callable

import pydicom
from PySide6.QtCore import QThread, Signal

from core.study_index.metadata_extract import dataset_to_index_row
from core.study_index.sqlcipher_store import StudyIndexStore
from utils.log_sanitizer import sanitized_format_exc

_logger = logging.getLogger(__name__)


class StudyIndexFolderThread(QThread):
    """Index ``root_dir`` recursively using metadata-only reads."""

    progress = Signal(int, int, str)  # current, total (estimate), path snippet
    finished_ok = Signal(int)  # rows written
    failed = Signal(str)

    def __init__(
        self,
        root_dir: str,
        db_path: str,
        passphrase: str,
        should_cancel: Callable[[], bool],
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._root_dir = os.path.abspath(root_dir)
        self._db_path = db_path
        self._passphrase = passphrase
        self._should_cancel = should_cancel

    def run(self) -> None:
        try:
            paths: list[str] = []
            for dirpath, _dirnames, filenames in os.walk(self._root_dir):
                if self._should_cancel():
                    self.failed.emit("Cancelled")
                    return
                for name in filenames:
                    paths.append(os.path.join(dirpath, name))
            total = max(len(paths), 1)
            rows: list[dict[str, Any]] = []
            for i, path in enumerate(paths):
                if self._should_cancel():
                    self.failed.emit("Cancelled")
                    return
                if i % 20 == 0:
                    self.progress.emit(i + 1, total, os.path.basename(path) or path)
                try:
                    ds = pydicom.dcmread(
                        path, stop_before_pixels=True, force=True, defer_size="all"
                    )
                except Exception:
                    continue
                fp = getattr(ds, "filename", None) or path
                rows.append(
                    dataset_to_index_row(ds, file_path=fp, study_root_path=self._root_dir)
                )
            store = StudyIndexStore(self._db_path, self._passphrase)
            store.init_schema()
            store.upsert_rows(rows)
            self.finished_ok.emit(len(rows))
        except Exception as e:
            _logger.debug("%s", sanitized_format_exc())
            self.failed.emit(f"{type(e).__name__}: {e}")
