"""
Background thread: upsert study index rows without blocking the UI thread.
"""

from __future__ import annotations

import traceback
from typing import Any, Sequence

from PySide6.QtCore import QThread, Signal

from core.study_index.sqlcipher_store import StudyIndexStore


class StudyIndexWriteThread(QThread):
    """Runs :meth:`StudyIndexStore.upsert_rows` off the GUI thread."""

    finished_ok = Signal()
    failed = Signal(str)

    def __init__(
        self,
        db_path: str,
        passphrase: str,
        rows: Sequence[dict[str, Any]],
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._db_path = db_path
        self._passphrase = passphrase
        self._rows = list(rows)

    def run(self) -> None:
        try:
            store = StudyIndexStore(self._db_path, self._passphrase)
            store.init_schema()
            store.upsert_rows(self._rows)
            self.finished_ok.emit()
        except Exception as e:
            traceback.print_exc()
            self.failed.emit(f"{type(e).__name__}: {e}")
