"""
SQLCipher-backed persistence for the local study index (MVP schema).

Opens a short-lived connection per operation with ``PRAGMA key`` and WAL mode.

Schema v2 adds ``series_description``, a denormalised ``doc`` column for FTS5, and
virtual table ``study_index_entry_fts`` (external content) with sync triggers.

Schema v3 adds a composite covering index for the grouped-study search query.
"""

from __future__ import annotations

import os
import sqlite3
import time
from collections.abc import Sequence
from pathlib import Path
from typing import Any, cast

# sqlcipher3 provides a sqlite3-compatible dbapi2 with encryption
import sqlcipher3.dbapi2 as sqlcipher_sqlite

from core.study_index.fts_doc import index_row_to_search_doc, normalize_user_fts_query

# ``sqlcipher3`` raises its own ``OperationalError`` (not always a subclass of ``sqlite3``'s).
_ST_OP = getattr(sqlcipher_sqlite, "OperationalError", sqlite3.OperationalError)
_FTS_QUERY_ERRS: tuple[type[BaseException], ...] = tuple(
    {sqlite3.OperationalError, _ST_OP},
)



_SQL_WHERE = " WHERE "
_SQL_AND = " AND "

# Whitelist of grouped-output columns that ``search_grouped_studies`` may sort by.
# Only a validated name from this set is ever placed into an ORDER BY clause.
_GROUPED_SORT_COLUMNS: frozenset[str] = frozenset(
    {
        "study_date",
        "patient_name",
        "patient_id",
        "accession_number",
        "study_description",
        "instance_count",
        "series_count",
        "indexed_at",
    }
)

def _is_windows() -> bool:
    return os.name == "nt"


def _normalize_modalities_group_concat(raw: str | None) -> str:
    """Turn ``GROUP_CONCAT(DISTINCT modality)`` into a sorted, comma-separated list."""
    if not raw:
        return ""
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    return ", ".join(sorted(set(parts)))


def _pragma_key_sql(passphrase: str) -> str:
    escaped = passphrase.replace("'", "''")
    return f"PRAGMA key = '{escaped}'"


_FTS_TRIGGERS_DDL = """
CREATE TRIGGER IF NOT EXISTS study_index_entry_ai AFTER INSERT ON study_index_entry BEGIN
  INSERT INTO study_index_entry_fts(rowid, doc) VALUES (new.id, new.doc);
END;
CREATE TRIGGER IF NOT EXISTS study_index_entry_ad AFTER DELETE ON study_index_entry BEGIN
  INSERT INTO study_index_entry_fts(study_index_entry_fts, rowid) VALUES('delete', old.id);
END;
CREATE TRIGGER IF NOT EXISTS study_index_entry_au AFTER UPDATE ON study_index_entry BEGIN
  INSERT INTO study_index_entry_fts(study_index_entry_fts, rowid) VALUES('delete', old.id);
  INSERT INTO study_index_entry_fts(rowid, doc) VALUES (new.id, new.doc);
END;
"""


def _create_fts_and_triggers(cur: sqlite3.Cursor) -> None:
    cur.execute(
        """
        CREATE VIRTUAL TABLE IF NOT EXISTS study_index_entry_fts USING fts5(
            doc,
            content='study_index_entry',
            content_rowid='id'
        );
        """
    )
    cur.executescript(_FTS_TRIGGERS_DDL)


class StudyIndexStore:
    """Create, migrate, upsert, and query study index rows."""

    SCHEMA_VERSION = 3

    def __init__(self, db_path: str, passphrase: str) -> None:
        self._db_path = db_path
        self._passphrase = passphrase

    def _connect(self) -> sqlite3.Connection:
        parent = os.path.dirname(os.path.abspath(self._db_path))
        if parent:
            parent_path = Path(parent)
            if not parent_path.exists():
                parent_path.mkdir(parents=True, mode=0o700)
        _connect_fn = cast(Any, sqlcipher_sqlite).connect
        conn = cast(sqlite3.Connection, _connect_fn(self._db_path, timeout=30.0))
        if not _is_windows():
            Path(self._db_path).chmod(0o600)
        conn.execute(_pragma_key_sql(self._passphrase))
        conn.execute("PRAGMA journal_mode=WAL;")
        return conn

    def _migrate_v1_to_v2(self, conn: sqlite3.Connection) -> None:
        """Upgrade legacy schema (no ``series_description`` / ``doc`` / FTS) to v2."""
        cur = conn.cursor()
        cur.execute("ALTER TABLE study_index_entry ADD COLUMN series_description TEXT DEFAULT '';")
        cur.execute("ALTER TABLE study_index_entry ADD COLUMN doc TEXT DEFAULT ' ';")
        cur.execute(
            "SELECT id, patient_name, patient_id, accession_number, study_description, "
            "series_description, modality, study_uid, series_uid, sop_instance_uid "
            "FROM study_index_entry"
        )
        for row in cur.fetchall():
            rid = int(row[0])
            doc = index_row_to_search_doc(
                {
                    "patient_name": row[1],
                    "patient_id": row[2],
                    "accession_number": row[3],
                    "study_description": row[4],
                    "series_description": row[5],
                    "modality": row[6],
                    "study_uid": row[7],
                    "series_uid": row[8],
                    "sop_instance_uid": row[9],
                }
            )
            cur.execute("UPDATE study_index_entry SET doc = ? WHERE id = ?", (doc, rid))
        _create_fts_and_triggers(cur)
        cur.execute("INSERT INTO study_index_entry_fts(rowid, doc) SELECT id, doc FROM study_index_entry;")
        # Also create covering index added in v3 (migration jumps to SCHEMA_VERSION).
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_grouped_study_cover "
            "ON study_index_entry(study_uid, study_root_path, study_date, patient_name, modality);"
        )
        cur.execute(f"PRAGMA user_version = {self.SCHEMA_VERSION};")

    def _migrate_v2_to_v3(self, conn: sqlite3.Connection) -> None:
        """Add composite covering index for grouped-study search."""
        cur = conn.cursor()
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_grouped_study_cover "
            "ON study_index_entry(study_uid, study_root_path, study_date, patient_name, modality);"
        )
        cur.execute(f"PRAGMA user_version = {self.SCHEMA_VERSION};")
        conn.commit()

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
                        series_description TEXT,
                        modality TEXT,
                        doc TEXT NOT NULL DEFAULT ' ',
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
                    CREATE INDEX IF NOT EXISTS idx_grouped_study_cover
                        ON study_index_entry(study_uid, study_root_path, study_date, patient_name, modality);
                    """
                )
                _create_fts_and_triggers(cur)
                cur.execute(f"PRAGMA user_version = {self.SCHEMA_VERSION};")
            elif version == 1:
                self._migrate_v1_to_v2(conn)
            elif version == 2:
                self._migrate_v2_to_v3(conn)
            elif version > self.SCHEMA_VERSION:
                raise sqlite3.OperationalError(
                    f"study_index unsupported user_version={version}; "
                    f"expected 0, 1, 2, or {self.SCHEMA_VERSION}"
                )
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
                    study_description, series_description, modality, doc, indexed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    series_description = excluded.series_description,
                    modality = excluded.modality,
                    doc = excluded.doc,
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
                        r.get("series_description") or "",
                        r.get("modality") or "",
                        index_row_to_search_doc(r),
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

    def get_file_paths_for_study(
        self, study_uid: str, study_root_path: str
    ) -> list[str]:
        """
        Return every indexed ``file_path`` for one logical study
        (``study_uid`` + ``study_root_path``).

        Uses the existing ``idx_study_uid_root`` index; fast even for large studies.
        Paths are normalised identically to :meth:`delete_study_group`.
        """
        su = (study_uid or "").strip()
        sr = os.path.normpath(os.path.abspath((study_root_path or "").strip()))
        if not su or not sr:
            return []
        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT file_path FROM study_index_entry "
                "WHERE study_uid = ? AND study_root_path = ?",
                (su, sr),
            )
            return [row[0] for row in cur.fetchall()]

    def iter_study_groups(self) -> list[dict[str, Any]]:
        """
        Return every unique (``study_uid``, ``study_root_path``) group with light metadata.

        Used by the integrity scan to walk all indexed studies. Each dict has
        ``study_uid``, ``study_root_path``, ``patient_name``, ``study_date``,
        ``instance_count``, and a normalised ``modalities`` string.
        """
        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT e.study_uid, e.study_root_path, "
                "MAX(e.patient_name) AS patient_name, "
                "MAX(e.study_date) AS study_date, "
                "COUNT(*) AS instance_count, "
                "GROUP_CONCAT(DISTINCT NULLIF(TRIM(e.modality), '')) AS _modalities_raw "
                "FROM study_index_entry AS e "
                "GROUP BY e.study_uid, e.study_root_path"
            )
            cols = [d[0] for d in cur.description]
            rows = [dict(zip(cols, row, strict=False)) for row in cur.fetchall()]
        for r in rows:
            raw = r.pop("_modalities_raw", None)
            r["modalities"] = _normalize_modalities_group_concat(raw)
            r["instance_count"] = int(r.get("instance_count") or 0)
        return rows

    def relocate_study_paths(
        self, study_uid: str, old_root: str, new_root: str
    ) -> int:
        """
        Rewrite ``file_path``/``study_root_path`` for one study by swapping the root prefix.

        Each entry's ``file_path`` has its ``old_root`` prefix replaced with ``new_root``
        (falling back to ``new_root``/basename when a stored path does not start with the
        old root). ``study_root_path`` is set to the normalised new root. The change is only
        committed when **at least one** relocated path exists on disk; otherwise nothing is
        written and ``0`` is returned. Returns the number of rows updated.
        """
        su = (study_uid or "").strip()
        if not su or not (old_root or "").strip() or not (new_root or "").strip():
            return 0
        old = os.path.normpath(os.path.abspath(old_root.strip()))
        new = os.path.normpath(os.path.abspath(new_root.strip()))
        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT id, file_path FROM study_index_entry "
                "WHERE study_uid = ? AND study_root_path = ?",
                (su, old),
            )
            entries = cur.fetchall()
            if not entries:
                return 0
            updates: list[tuple[str, str, int]] = []
            for rid, fp in entries:
                fp = fp or ""
                if fp.startswith(old):
                    new_fp = new + fp[len(old):]
                else:
                    new_fp = os.path.join(new, os.path.basename(fp))
                updates.append((new_fp, new, int(rid)))
            if not any(os.path.isfile(u[0]) for u in updates):
                return 0
            cur.executemany(
                "UPDATE study_index_entry SET file_path = ?, study_root_path = ? WHERE id = ?",
                updates,
            )
            conn.commit()
        return len(updates)

    @staticmethod
    def _col(alias: str | None, name: str) -> str:
        return f"{alias}.{name}" if alias else name

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
        table_alias: str | None = None,
    ) -> tuple[str, list[Any]]:
        clauses: list[str] = []
        params: list[Any] = []

        def add_like(column: str, needle: str) -> None:
            n = needle.strip()
            if n:
                clauses.append(f"{self._col(table_alias, column)} LIKE ? ESCAPE '\\'")
                escaped = n.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
                params.append(f"%{escaped}%")

        add_like("patient_name", patient_name_contains)
        add_like("patient_id", patient_id_contains)
        add_like("accession_number", accession_contains)
        add_like("study_description", study_description_contains)
        m = modality.strip()
        if m:
            clauses.append(f"{self._col(table_alias, 'modality')} LIKE ? ESCAPE '\\'")
            escaped = m.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            params.append(f"%{escaped}%")
        df = study_date_from.strip()
        dt = study_date_to.strip()
        if df:
            clauses.append(f"{self._col(table_alias, 'study_date')} >= ?")
            params.append(df)
        if dt:
            clauses.append(f"{self._col(table_alias, 'study_date')} <= ?")
            params.append(dt)

        where = (_SQL_WHERE + _SQL_AND.join(clauses)) if clauses else ""
        return where, params

    @staticmethod
    def _fts_exists_sql(table_alias: str) -> str:
        """
        Return ``EXISTS (...)`` SQL (no leading ``AND``) for ``MATCH`` binding.

        ``MATCH`` requires the FTS **virtual table name** as the left operand
        (aliases are not accepted in all SQLite builds); rowid ties the hit to
        ``study_index_entry`` via ``content_rowid='id'``.
        """
        return (
            "EXISTS (SELECT 1 FROM study_index_entry_fts "
            f"WHERE study_index_entry_fts.rowid = {table_alias}.id "
            "AND study_index_entry_fts MATCH ?)"
        )

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
    ) -> list[dict[str, Any]]:
        where, params = self._search_filter_clauses(
            patient_name_contains=patient_name_contains,
            patient_id_contains=patient_id_contains,
            modality=modality,
            accession_contains=accession_contains,
            study_description_contains=study_description_contains,
            study_date_from=study_date_from,
            study_date_to=study_date_to,
            table_alias=None,
        )
        fts_q = normalize_user_fts_query(global_fts_query)
        if fts_q:
            fts_sql = self._fts_exists_sql("study_index_entry")
            if where:
                where = where + _SQL_AND + fts_sql
            else:
                where = _SQL_WHERE + fts_sql
            params.append(fts_q)
        sql = (
            "SELECT file_path, study_root_path, study_uid, series_uid, sop_instance_uid, "
            "patient_name, patient_id, accession_number, study_date, study_description, "
            "series_description, modality, indexed_at FROM study_index_entry"
            + where
            + " ORDER BY study_date DESC, patient_name ASC LIMIT ?"
        )
        params = list(params)
        params.append(limit)

        with self._connect() as conn:
            cur = conn.cursor()
            try:
                cur.execute(sql, params)
            except _FTS_QUERY_ERRS as e:
                if fts_q:
                    raise ValueError(
                        "Invalid full-text search syntax. Try simpler words, or remove "
                        "special characters like quotes."
                    ) from e
                raise
            cols = [d[0] for d in cur.description]
            return [dict(zip(cols, row, strict=False)) for row in cur.fetchall()]

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
    ) -> list[dict[str, Any]]:
        """
        One row per (study_uid, study_root_path) with instance/series counts and modalities.

        Study-level text fields use SQLite aggregates (deterministic MAX). ``open_file_path``
        is MIN(file_path) for a stable default when opening from a grouped row.

        ``order_by`` is validated against a whitelist of grouped output columns; any
        other value falls back to ``study_date``. ``patient_name ASC`` is always the
        secondary tiebreak so paging stays deterministic.
        """
        where, params = self._search_filter_clauses(
            patient_name_contains=patient_name_contains,
            patient_id_contains=patient_id_contains,
            modality=modality,
            accession_contains=accession_contains,
            study_description_contains=study_description_contains,
            study_date_from=study_date_from,
            study_date_to=study_date_to,
            table_alias="e",
        )
        fts_q = normalize_user_fts_query(global_fts_query)
        if fts_q:
            fts_sql = self._fts_exists_sql("e")
            if where:
                where = where + _SQL_AND + fts_sql
            else:
                where = _SQL_WHERE + fts_sql
            params.append(fts_q)
        # Validate the sort column against a whitelist of grouped output columns. Never
        # interpolate raw user input into SQL — only a known column name reaches the query.
        order_col = order_by if order_by in _GROUPED_SORT_COLUMNS else "study_date"
        order_dir = "DESC" if descending else "ASC"
        # COUNT(DISTINCT …): ignore empty series_uid so blank rows do not inflate series_count.
        sql = (
            "SELECT e.study_uid, e.study_root_path, "
            "MAX(e.study_date) AS study_date, "
            "MAX(e.patient_name) AS patient_name, "
            "MAX(e.patient_id) AS patient_id, "
            "MAX(e.accession_number) AS accession_number, "
            "MAX(e.study_description) AS study_description, "
            "MAX(e.series_description) AS series_description, "
            "MAX(e.indexed_at) AS indexed_at, "
            "MIN(e.file_path) AS open_file_path, "
            "COUNT(*) AS instance_count, "
            "COUNT(DISTINCT NULLIF(TRIM(e.series_uid), '')) AS series_count, "
            "GROUP_CONCAT(DISTINCT NULLIF(TRIM(e.modality), '')) AS _modalities_raw "
            "FROM study_index_entry AS e"
            + where
            + " GROUP BY e.study_uid, e.study_root_path "
            + f"ORDER BY {order_col} {order_dir}, patient_name ASC "
            + "LIMIT ? OFFSET ?"
        )
        qparams = list(params)
        qparams.extend([limit, max(0, offset)])

        with self._connect() as conn:
            cur = conn.cursor()
            try:
                cur.execute(sql, qparams)
            except _FTS_QUERY_ERRS as e:
                if fts_q:
                    raise ValueError(
                        "Invalid full-text search syntax. Try simpler words, or remove "
                        "special characters like quotes."
                    ) from e
                raise
            cols = [d[0] for d in cur.description]
            rows = [dict(zip(cols, row, strict=False)) for row in cur.fetchall()]

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
