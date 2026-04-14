"""
SQLCipher-backed persistence for the local study index (MVP schema).

Opens a short-lived connection per operation with ``PRAGMA key`` and WAL mode.
"""

from __future__ import annotations

import os
import time
import sqlite3
from typing import Any, Sequence, cast

# sqlcipher3 provides a sqlite3-compatible dbapi2 with encryption
import sqlcipher3.dbapi2 as sqlcipher_sqlite


def _normalize_modalities_group_concat(raw: str | None) -> str:
    """Turn ``GROUP_CONCAT(DISTINCT modality)`` into a sorted, comma-separated list."""
    if not raw:
        return ""
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    return ", ".join(sorted(set(parts)))


def _pragma_key_sql(passphrase: str) -> str:
    escaped = passphrase.replace("'", "''")
    return f"PRAGMA key = '{escaped}'"


class StudyIndexStore:
    """Create, migrate, upsert, and query study index rows."""

    SCHEMA_VERSION = 1

    def __init__(self, db_path: str, passphrase: str) -> None:
        self._db_path = db_path
        self._passphrase = passphrase

    def _connect(self) -> sqlite3.Connection:
        parent = os.path.dirname(os.path.abspath(self._db_path))
        if parent:
            os.makedirs(parent, exist_ok=True)
        _connect_fn = cast(Any, sqlcipher_sqlite).connect
        conn = cast(sqlite3.Connection, _connect_fn(self._db_path, timeout=30.0))
        conn.execute(_pragma_key_sql(self._passphrase))
        conn.execute("PRAGMA journal_mode=WAL;")
        return conn

    def init_schema(self) -> None:
        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute("PRAGMA user_version;")
            row = cur.fetchone()
            version = int(row[0]) if row and row[0] is not None else 0
            if version == 0:
                cur.executescript(
                    """
                    CREATE TABLE IF NOT EXISTS study_index_entry (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        file_path TEXT NOT NULL UNIQUE,
                        study_root_path TEXT NOT NULL,
                        study_uid TEXT NOT NULL,
                        series_uid TEXT,
                        sop_instance_uid TEXT,
                        patient_name TEXT,
                        patient_id TEXT,
                        accession_number TEXT,
                        study_date TEXT,
                        study_description TEXT,
                        modality TEXT,
                        indexed_at REAL NOT NULL
                    );
                    CREATE INDEX IF NOT EXISTS idx_study_uid_root
                        ON study_index_entry(study_uid, study_root_path);
                    CREATE INDEX IF NOT EXISTS idx_patient_name
                        ON study_index_entry(patient_name);
                    CREATE INDEX IF NOT EXISTS idx_modality
                        ON study_index_entry(modality);
                    CREATE INDEX IF NOT EXISTS idx_study_date
                        ON study_index_entry(study_date);
                    """
                )
                cur.execute(f"PRAGMA user_version = {self.SCHEMA_VERSION};")
            conn.commit()

    def upsert_rows(self, rows: Sequence[dict[str, Any]]) -> None:
        if not rows:
            return
        now = time.time()
        with self._connect() as conn:
            cur = conn.cursor()
            cur.executemany(
                """
                INSERT INTO study_index_entry (
                    file_path, study_root_path, study_uid, series_uid, sop_instance_uid,
                    patient_name, patient_id, accession_number, study_date,
                    study_description, modality, indexed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(file_path) DO UPDATE SET
                    study_root_path = excluded.study_root_path,
                    study_uid = excluded.study_uid,
                    series_uid = excluded.series_uid,
                    sop_instance_uid = excluded.sop_instance_uid,
                    patient_name = excluded.patient_name,
                    patient_id = excluded.patient_id,
                    accession_number = excluded.accession_number,
                    study_date = excluded.study_date,
                    study_description = excluded.study_description,
                    modality = excluded.modality,
                    indexed_at = excluded.indexed_at
                """,
                [
                    (
                        r["file_path"],
                        r["study_root_path"],
                        r["study_uid"],
                        r.get("series_uid") or "",
                        r.get("sop_instance_uid") or "",
                        r.get("patient_name") or "",
                        r.get("patient_id") or "",
                        r.get("accession_number") or "",
                        r.get("study_date") or "",
                        r.get("study_description") or "",
                        r.get("modality") or "",
                        now,
                    )
                    for r in rows
                ],
            )
            conn.commit()

    def delete_study_group(self, study_uid: str, study_root_path: str) -> int:
        """
        Delete all index rows for one logical study (``study_uid`` + ``study_root_path``).

        Returns the number of instance rows removed. Paths are normalised like upserts.
        """
        su = (study_uid or "").strip()
        sr = os.path.normpath(os.path.abspath((study_root_path or "").strip()))
        if not su or not sr:
            return 0
        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute(
                "DELETE FROM study_index_entry WHERE study_uid = ? AND study_root_path = ?",
                (su, sr),
            )
            cur.execute("SELECT changes()")
            row = cur.fetchone()
            n = int(row[0]) if row and row[0] is not None else 0
            conn.commit()
        return n

    def _search_filter_clauses(
        self,
        *,
        patient_name_contains: str = "",
        patient_id_contains: str = "",
        modality: str = "",
        accession_contains: str = "",
        study_description_contains: str = "",
        study_date_from: str = "",
        study_date_to: str = "",
    ) -> tuple[str, list[Any]]:
        clauses: list[str] = []
        params: list[Any] = []

        def add_like(column: str, needle: str) -> None:
            n = needle.strip()
            if n:
                clauses.append(f"{column} LIKE ? ESCAPE '\\'")
                escaped = n.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
                params.append(f"%{escaped}%")

        add_like("patient_name", patient_name_contains)
        add_like("patient_id", patient_id_contains)
        add_like("accession_number", accession_contains)
        add_like("study_description", study_description_contains)
        m = modality.strip()
        if m:
            clauses.append("modality LIKE ? ESCAPE '\\'")
            escaped = m.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            params.append(f"%{escaped}%")
        df = study_date_from.strip()
        dt = study_date_to.strip()
        if df:
            clauses.append("study_date >= ?")
            params.append(df)
        if dt:
            clauses.append("study_date <= ?")
            params.append(dt)

        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        return where, params

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
        limit: int = 500,
    ) -> list[dict[str, Any]]:
        where, params = self._search_filter_clauses(
            patient_name_contains=patient_name_contains,
            patient_id_contains=patient_id_contains,
            modality=modality,
            accession_contains=accession_contains,
            study_description_contains=study_description_contains,
            study_date_from=study_date_from,
            study_date_to=study_date_to,
        )
        sql = (
            "SELECT file_path, study_root_path, study_uid, series_uid, sop_instance_uid, "
            "patient_name, patient_id, accession_number, study_date, study_description, "
            "modality, indexed_at FROM study_index_entry"
            + where
            + " ORDER BY study_date DESC, patient_name ASC LIMIT ?"
        )
        params = list(params)
        params.append(limit)

        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute(sql, params)
            cols = [d[0] for d in cur.description]
            return [dict(zip(cols, row)) for row in cur.fetchall()]

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
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """
        One row per (study_uid, study_root_path) with instance/series counts and modalities.

        Study-level text fields use SQLite aggregates (deterministic MAX). ``open_file_path``
        is MIN(file_path) for a stable default when opening from a grouped row.
        """
        where, params = self._search_filter_clauses(
            patient_name_contains=patient_name_contains,
            patient_id_contains=patient_id_contains,
            modality=modality,
            accession_contains=accession_contains,
            study_description_contains=study_description_contains,
            study_date_from=study_date_from,
            study_date_to=study_date_to,
        )
        # COUNT(DISTINCT …): ignore empty series_uid so blank rows do not inflate series_count.
        sql = (
            "SELECT study_uid, study_root_path, "
            "MAX(study_date) AS study_date, "
            "MAX(patient_name) AS patient_name, "
            "MAX(patient_id) AS patient_id, "
            "MAX(accession_number) AS accession_number, "
            "MAX(study_description) AS study_description, "
            "MIN(file_path) AS open_file_path, "
            "COUNT(*) AS instance_count, "
            "COUNT(DISTINCT NULLIF(TRIM(series_uid), '')) AS series_count, "
            "GROUP_CONCAT(DISTINCT NULLIF(TRIM(modality), '')) AS _modalities_raw "
            "FROM study_index_entry"
            + where
            + " GROUP BY study_uid, study_root_path "
            + "ORDER BY study_date DESC, patient_name ASC "
            + "LIMIT ? OFFSET ?"
        )
        qparams = list(params)
        qparams.extend([limit, max(0, offset)])

        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute(sql, qparams)
            cols = [d[0] for d in cur.description]
            rows = [dict(zip(cols, row)) for row in cur.fetchall()]

        for r in rows:
            raw = r.pop("_modalities_raw", None)
            r["modalities"] = _normalize_modalities_group_concat(raw)
            r["instance_count"] = int(r.get("instance_count") or 0)
            r["series_count"] = int(r.get("series_count") or 0)
        return rows


def is_plain_sqlite_readable(path: str) -> bool:
    """Return True if ``path`` looks like an unencrypted SQLite database."""
    if not os.path.isfile(path):
        return False
    try:
        with open(path, "rb") as f:
            header = f.read(16)
        return header.startswith(b"SQLite format 3\x00")
    except OSError:
        return False


def verify_encrypted_header(path: str) -> bool:
    """
    Best-effort check: file exists and does not start with the standard SQLite magic.

    SQLCipher files are not valid plain SQLite; stdlib ``sqlite3`` should fail to read.
    """
    if not os.path.isfile(path):
        return True
    return not is_plain_sqlite_readable(path)
