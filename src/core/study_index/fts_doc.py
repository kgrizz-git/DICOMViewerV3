"""
Build the denormalised full-text document for one ``study_index_entry`` row.

The same text is stored in column ``doc`` on ``study_index_entry`` and indexed by
SQLite FTS5 (``study_index_entry_fts``) for quick "search all text" queries.
"""

from __future__ import annotations

from typing import Any

# Bound user-supplied FTS ``MATCH`` strings to avoid huge queries / abuse.
FTS_USER_QUERY_MAX_LEN = 256

# Field order must match ``_migrate_v1_to_v2`` row dict assembly in ``sqlcipher_store``.
_DOC_FIELD_KEYS: tuple[str, ...] = (
    "patient_name",
    "patient_id",
    "accession_number",
    "study_description",
    "series_description",
    "modality",
    "study_uid",
    "series_uid",
    "sop_instance_uid",
)

_DOC_DELIM = " | "


def index_row_to_search_doc(row: dict[str, Any]) -> str:
    """
    Concatenate searchable fields into one FTS document string.

    Empty rows use a single space so FTS rows remain well-formed.
    """
    parts: list[str] = []
    for key in _DOC_FIELD_KEYS:
        raw = row.get(key)
        s = (raw if isinstance(raw, str) else str(raw or "")).strip()
        if s:
            parts.append(s)
    merged = _DOC_DELIM.join(parts)
    return merged if merged.strip() else " "


def normalize_user_fts_query(raw: str) -> str:
    """Strip and cap length for ``MATCH`` binding; empty means no FTS filter."""
    t = (raw or "").strip()
    if not t:
        return ""
    if len(t) > FTS_USER_QUERY_MAX_LEN:
        t = t[:FTS_USER_QUERY_MAX_LEN]
    return t
