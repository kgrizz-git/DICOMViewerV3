"""
Application-facing local study index: encrypted store + background writes.
"""

from __future__ import annotations

import logging
import os
import shutil
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_logger = logging.getLogger(__name__)

from pydicom.dataset import Dataset

from core.dicom_organizer import MergeResult
from core.study_index.index_folder_thread import StudyIndexFolderThread
from core.study_index.index_write_thread import StudyIndexWriteThread
from core.study_index.keyring_storage import get_or_create_study_index_passphrase
from core.study_index.metadata_extract import dataset_to_index_row
from core.study_index.sqlcipher_store import StudyIndexStore
from utils.config_manager import ConfigManager
from utils.privacy.safe_storage import DeletionResult, secure_unlink


def _safe_remove(path: str) -> None:
    """Best-effort delete; ignore a missing file or a transient OS error."""
    try:
        os.remove(path)
    except OSError:
        pass


@dataclass
class MissingStudyRecord:
    """One indexed study whose files are (partly or wholly) missing on disk."""

    study_uid: str
    study_root_path: str
    patient_name: str
    study_date: str
    modalities: str
    missing_count: int
    total_count: int


class LocalStudyIndexService:
    """
    MVP implementation of the local SQLCipher study index.

    - Passphrase from OS keyring (see ``keyring_storage``).
    - Optional auto-index after load via :meth:`schedule_index_after_load`.
    """

    def __init__(self, config_manager: ConfigManager, parent_widget=None) -> None:
        self._config = config_manager
        self._parent = parent_widget
        self._write_thread: StudyIndexWriteThread | None = None
        self._folder_thread: StudyIndexFolderThread | None = None
        self._folder_cancel = False
        self._schema_initialized = False
        self._cached_db_path: str = ""

    @staticmethod
    def is_backend_available() -> bool:
        try:
            import keyring  # noqa: F401
            import sqlcipher3.dbapi2  # noqa: F401
            return True
        except ImportError:
            return False

    def _db_path(self) -> str:
        return self._config.get_study_index_db_path()

    def _passphrase(self) -> str:
        return get_or_create_study_index_passphrase()

    def _get_ready_store(self) -> StudyIndexStore:
        """Return a StudyIndexStore, running init_schema() only on first use or DB path change."""
        db_path = self._db_path()
        store = StudyIndexStore(db_path, self._passphrase())
        if not self._schema_initialized or db_path != self._cached_db_path:
            store.init_schema()
            self._schema_initialized = True
            self._cached_db_path = db_path
        return store

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
        store = self._get_ready_store()
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
        order_by: str = "study_date",
        descending: bool = True,
        privacy_mode: bool = False,
    ) -> list[dict[str, Any]]:
        store = self._get_ready_store()
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
            order_by=order_by,
            descending=descending,
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
        store = self._get_ready_store()
        return store.delete_study_group(study_uid, study_root_path)

    def get_file_paths_for_study(
        self, study_uid: str, study_root_path: str
    ) -> list[str]:
        """
        Return every indexed file path for one (study UID, study folder) pair.

        Uses the existing ``idx_study_uid_root`` index — fast regardless of study size.
        Returns an empty list when the backend is unavailable or inputs are blank.
        """
        if not self.is_backend_available():
            return []
        store = self._get_ready_store()
        return store.get_file_paths_for_study(study_uid, study_root_path)

    def integrity_scan(
        self, progress: Callable[[int, int], None] | None = None
    ) -> list[MissingStudyRecord]:
        """
        Find indexed studies whose files are missing on disk.

        Walks every unique ``(study_uid, study_root_path)`` group, gathers its indexed
        file paths, and counts how many no longer exist (``os.path.isfile``). A study is
        reported when its root folder is gone **or** at least one member file is missing.

        ``progress(done, total)`` is called after each study when supplied. Returns an
        empty list when the backend is unavailable.
        """
        if not self.is_backend_available():
            return []
        store = self._get_ready_store()
        groups = store.iter_study_groups()
        total = len(groups)
        records: list[MissingStudyRecord] = []
        for i, g in enumerate(groups):
            study_uid = (g.get("study_uid") or "").strip()
            root = (g.get("study_root_path") or "").strip()
            paths = store.get_file_paths_for_study(study_uid, root)
            total_count = len(paths)
            missing_count = sum(1 for p in paths if not os.path.isfile(p))
            root_gone = bool(root) and not os.path.isdir(root)
            if root_gone or missing_count > 0:
                records.append(
                    MissingStudyRecord(
                        study_uid=study_uid,
                        study_root_path=root,
                        patient_name=str(g.get("patient_name") or ""),
                        study_date=str(g.get("study_date") or ""),
                        modalities=str(g.get("modalities") or ""),
                        missing_count=missing_count,
                        total_count=total_count,
                    )
                )
            if progress is not None:
                progress(i + 1, total)
        return records

    def relocate_study(self, study_uid: str, old_root: str, new_root: str) -> int:
        """
        Point an indexed study at a new folder by rewriting its stored paths.

        Delegates the SQL UPDATE to the store, which only commits when at least one
        relocated path exists on disk. Blank inputs are rejected. Returns rows updated.
        """
        if not self.is_backend_available():
            return 0
        if not (study_uid or "").strip() or not (old_root or "").strip() or not (new_root or "").strip():
            return 0
        store = self._get_ready_store()
        return store.relocate_study_paths(study_uid, old_root, new_root)

    # --- Metadata (About this index) -----------------------------------------

    def row_count(self) -> int:
        """Total number of indexed instance rows (0 when the backend is unavailable)."""
        if not self.is_backend_available():
            return 0
        return self._get_ready_store().row_count()

    def db_file_size_bytes(self) -> int | None:
        """Size of the DB file on disk in bytes, or ``None`` if it does not exist yet."""
        try:
            return os.path.getsize(self._db_path())
        except OSError:
            return None

    def db_last_modified(self) -> float | None:
        """Last-modified time (epoch seconds) of the DB file, or ``None`` if absent."""
        try:
            return os.path.getmtime(self._db_path())
        except OSError:
            return None

    @staticmethod
    def is_encrypted() -> bool:
        """The local study index is always encrypted at rest (SQLCipher)."""
        return True

    # --- Move / Export / Import ----------------------------------------------

    def move_database(self, new_db_path: str) -> str:
        """Copy the DB to ``new_db_path``, verify it, switch config, delete the old file.

        The copy is verified with ``PRAGMA integrity_check`` (opened through SQLCipher)
        **before** the config path is updated, and the old file is only deleted once the
        new path is persisted. On any failure the copy is removed and the original DB and
        config are left untouched (no half-moved state). Returns the resolved new path.
        """
        if not self.is_backend_available():
            raise RuntimeError("Study index backend is unavailable.")
        new_path = os.path.normpath(os.path.abspath((new_db_path or "").strip()))
        if not new_path:
            raise ValueError("A destination path is required.")
        old_path = self._db_path()
        if new_path == old_path:
            raise ValueError("The destination is the same as the current location.")
        if os.path.exists(new_path):
            raise FileExistsError("A file already exists at the destination.")

        passphrase = self._passphrase()
        # Make sure the source exists and fold the WAL into the main file before copying.
        self.ensure_store_ready()
        StudyIndexStore(old_path, passphrase).checkpoint()

        parent = os.path.dirname(new_path)
        if parent and not os.path.isdir(parent):
            os.makedirs(parent, mode=0o700, exist_ok=True)
        shutil.copy2(old_path, new_path)

        try:
            verified = StudyIndexStore(new_path, passphrase).integrity_check()
        except Exception:
            verified = False
        if not verified:
            _safe_remove(new_path)
            raise RuntimeError("The copied database failed verification; move aborted.")

        if not self._config.set_study_index_db_path(new_path):
            _safe_remove(new_path)
            raise RuntimeError("Could not save the new index location; move aborted.")

        # Old location is now stale — remove it and its WAL sidecars securely.
        try:
            secure_unlink(Path(old_path))
        except OSError:
            _safe_remove(old_path)
        for sidecar in (f"{old_path}-wal", f"{old_path}-shm", f"{old_path}-journal"):
            _safe_remove(sidecar)

        self._schema_initialized = False
        self._cached_db_path = ""
        return new_path

    def export_entries(self) -> list[dict[str, Any]]:
        """Return every indexed instance row (metadata + file paths only, no pixel data)."""
        if not self.is_backend_available():
            return []
        return self._get_ready_store().iter_all_entries()

    def import_entries(self, rows: list[dict[str, Any]]) -> tuple[int, int]:
        """Upsert imported rows into the current DB, skipping duplicates.

        Duplicates are keyed on ``(study_uid, file_path)`` against the existing database
        and within the incoming batch. Returns ``(imported, skipped)``.
        """
        if not self.is_backend_available() or not rows:
            return (0, 0)
        store = self._get_ready_store()
        existing = store.existing_study_file_keys()
        to_add: list[dict[str, Any]] = []
        skipped = 0
        for r in rows:
            study_uid = (r.get("study_uid") or "").strip()
            file_path = (r.get("file_path") or "").strip()
            key = (study_uid, file_path)
            if not study_uid or not file_path or key in existing:
                skipped += 1
                continue
            existing.add(key)
            to_add.append(r)
        if to_add:
            store.upsert_rows(to_add)
        return (len(to_add), skipped)

    def schedule_index_after_load(
        self,
        datasets: list[Dataset],
        merge_paths: list[str],
        source_dir: str,
        _merge_result: MergeResult,
        *,
        was_cancelled: bool = False,
        force: bool = False,
    ) -> None:
        """
        Queue a background upsert for datasets opened in this load batch.

        ``merge_paths`` must align positionally with ``datasets`` (as in
        ``merge_batch``).

        When *was_cancelled* is True (user stopped a folder/file load part-way),
        indexing is skipped so the encrypted index is not left with incomplete
        study metadata.

        When *force* is True (e.g. the user chose "Add this one time" at the
        first-open prompt), this batch is indexed even though the persistent
        auto-add-on-open preference is off/unrecorded.
        """
        if was_cancelled:
            _logger.info("Skipping auto-index: load was cancelled by user")
            return
        if not force and not self._config.get_study_index_auto_add_on_open():
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

    def clear_all_data(self) -> DeletionResult:
        """Clear the encrypted index when no background index operation is active."""

        if self._write_thread and self._write_thread.isRunning():
            return DeletionResult(failed=1)
        if self._folder_thread and self._folder_thread.isRunning():
            return DeletionResult(failed=1)
        db_path = Path(self._db_path())
        removed = 0
        failed = 0
        for candidate in (
            db_path,
            Path(f"{db_path}-journal"),
            Path(f"{db_path}-wal"),
            Path(f"{db_path}-shm"),
        ):
            try:
                removed += int(secure_unlink(candidate))
            except OSError:
                failed += 1
        self._schema_initialized = False
        self._cached_db_path = ""
        return DeletionResult(removed=removed, failed=failed)
