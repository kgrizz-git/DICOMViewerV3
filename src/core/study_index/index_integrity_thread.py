"""
Background thread: scan the study index for studies whose files are missing on disk.
"""

from __future__ import annotations

import logging

from PySide6.QtCore import QThread, Signal

from core.study_index.index_service import LocalStudyIndexService
from utils.log_sanitizer import sanitized_format_exc

_logger = logging.getLogger(__name__)


class StudyIndexIntegrityThread(QThread):
    """Run ``LocalStudyIndexService.integrity_scan`` off the GUI thread."""

    progress = Signal(int, int)  # done, total
    finished_ok = Signal(object)  # list[MissingStudyRecord]
    failed = Signal(str)

    def __init__(self, service: LocalStudyIndexService, parent=None) -> None:
        super().__init__(parent)
        self._service = service

    def run(self) -> None:
        try:
            def _progress(done: int, total: int) -> None:
                self.progress.emit(done, total)

            records = self._service.integrity_scan(progress=_progress)
            self.finished_ok.emit(records)
        except Exception as e:
            _logger.debug("%s", sanitized_format_exc())
            self.failed.emit(f"{type(e).__name__}: {e}")
