"""
Application-facing local study index: encrypted store + background writes.
"""

from __future__ import annotations

import os
from typing import Any, Optional

from pydicom.dataset import Dataset

from core.dicom_organizer import MergeResult
from core.study_index.index_folder_thread import StudyIndexFolderThread
from core.study_index.index_write_thread import StudyIndexWriteThread
from core.study_index.keyring_storage import get_or_create_study_index_passphrase
from core.study_index.metadata_extract import dataset_to_index_row
from core.study_index.sqlcipher_store import StudyIndexStore
from utils.config_manager import ConfigManager


class LocalStudyIndexService:
    """
    MVP implementation of the local SQLCipher study index.

    - Passphrase from OS keyring (see ``keyring_storage``).
    - Optional auto-index after load via :meth:`schedule_index_after_load`.
    """

    def __init__(self, config_manager: ConfigManager, parent_widget=None) -> None:
        self._config = config_manager
        self._parent = parent_widget
        self._write_thread: Optional[StudyIndexWriteThread] = None
        self._folder_thread: Optional[StudyIndexFolderThread] = None
        self._folder_cancel = False

    @staticmethod
    def is_backend_available() -> bool:
        try:
            import sqlcipher3.dbapi2  # noqa: F401
            import keyring  # noqa: F401
            return True
        except ImportError:
            return False

    def _db_path(self) -> str:
        return self._config.get_study_index_db_path()

    def _passphrase(self) -> str:
        return get_or_create_study_index_passphrase()

    def ensure_store_ready(self) -> None:
        """Create DB file and schema if missing."""
        store = StudyIndexStore(self._db_path(), self._passphrase())
        store.init_schema()

    def search(
        self,
        *,
        patient_name_contains: str = "",
        patient_id_contains: str = "",
        modality: str = "",
        accession_contains: str = "",
        study_description_contains: str = "",
        study_date_from: str = "",
        study_date_to: str = "",
        global_fts_query: str = "",
        limit: int = 500,
        privacy_mode: bool = False,
    ) -> list[dict[str, Any]]:
        store = StudyIndexStore(self._db_path(), self._passphrase())
        store.init_schema()
        rows = store.search(
            patient_name_contains=patient_name_contains,
            patient_id_contains=patient_id_contains,
            modality=modality,
            accession_contains=accession_contains,
            study_description_contains=study_description_contains,
            study_date_from=study_date_from,
            study_date_to=study_date_to,
            global_fts_query=global_fts_query,
            limit=limit,
        )
        if not privacy_mode:
            return rows
        out = []
        for r in rows:
            rc = dict(r)
            rc["patient_name"] = "***"
            rc["patient_id"] = "***"
            rc["accession_number"] = "***"
            out.append(rc)
        return out

    def search_grouped_studies(
        self,
        *,
        patient_name_contains: str = "",
        patient_id_contains: str = "",
        modality: str = "",
        accession_contains: str = "",
        study_description_contains: str = "",
        study_date_from: str = "",
        study_date_to: str = "",
        global_fts_query: str = "",
        limit: int = 100,
        offset: int = 0,
        privacy_mode: bool = False,
    ) -> list[dict[str, Any]]:
        store = StudyIndexStore(self._db_path(), self._passphrase())
        store.init_schema()
        rows = store.search_grouped_studies(
            patient_name_contains=patient_name_contains,
            patient_id_contains=patient_id_contains,
            modality=modality,
            accession_contains=accession_contains,
            study_description_contains=study_description_contains,
            study_date_from=study_date_from,
            study_date_to=study_date_to,
            global_fts_query=global_fts_query,
            limit=limit,
            offset=offset,
        )
        if not privacy_mode:
            return rows
        out = []
        for r in rows:
            rc = dict(r)
            rc["patient_name"] = "***"
            rc["patient_id"] = "***"
            rc["accession_number"] = "***"
            out.append(rc)
        return out

    def delete_grouped_study(self, study_uid: str, study_root_path: str) -> int:
        """
        Remove every indexed instance for one (study UID, study folder) pair.

        Does not delete or modify DICOM files on disk.
        """
        if not self.is_backend_available():
            return 0
        store = StudyIndexStore(self._db_path(), self._passphrase())
        store.init_schema()
        return store.delete_study_group(study_uid, study_root_path)

    def schedule_index_after_load(
        self,
        datasets: list[Dataset],
        merge_paths: list[str],
        source_dir: str,
        _merge_result: MergeResult,
    ) -> None:
        """
        Queue a background upsert for datasets opened in this load batch.

        ``merge_paths`` must align positionally with ``datasets`` (as in
        ``merge_batch``).
        """
        if not self._config.get_study_index_auto_add_on_open():
            return
        if not self.is_backend_available():
            return
        rows: list[dict[str, Any]] = []
        for i, ds in enumerate(datasets):
            mp = merge_paths[i] if i < len(merge_paths) else ""
            if not mp or not os.path.isfile(mp):
                fn = getattr(ds, "filename", None)
                if not fn or not os.path.isfile(fn):
                    continue
                mp = fn
            rows.append(dataset_to_index_row(ds, file_path=mp, study_root_path=source_dir))
        if not rows:
            return
        if self._write_thread and self._write_thread.isRunning():
            # Avoid overlapping writes — drop duplicate schedule (MVP)
            return
        self._write_thread = StudyIndexWriteThread(
            self._db_path(),
            self._passphrase(),
            rows,
            parent=self._parent,
        )
        self._write_thread.start()

    def start_index_folder(
        self,
        root_dir: str,
        *,
        on_progress=None,
        on_finished=None,
        on_failed=None,
    ) -> None:
        """Start background folder crawl (single active job)."""
        self._folder_cancel = False
        if self._folder_thread and self._folder_thread.isRunning():
            return

        def _cancel() -> bool:
            return self._folder_cancel

        self._folder_thread = StudyIndexFolderThread(
            root_dir,
            self._db_path(),
            self._passphrase(),
            _cancel,
            parent=self._parent,
        )
        if on_progress:
            self._folder_thread.progress.connect(on_progress)
        if on_finished:

            def _ok(n: int) -> None:
                on_finished(n)

            self._folder_thread.finished_ok.connect(_ok)
        if on_failed:
            self._folder_thread.failed.connect(on_failed)
        self._folder_thread.start()

    def cancel_folder_index(self) -> None:
        self._folder_cancel = True
