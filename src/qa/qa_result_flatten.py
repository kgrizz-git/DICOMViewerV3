"""
Canonical flatten builders for QA run results (Qt-free, no I/O).

This module is the single source of truth for turning a :class:`QAResult`
into export-ready metric rows, provenance dicts, and wide tabular rows.
CSV, XLSX Detail, and future CLI/DB surfaces all consume these builders so
the flatten contract stays in one place.

Inputs:
    A :class:`QAResult` carrying ``raw_pylinac`` (the full
    ``results_data(as_dict=True)`` tree) plus curated ``result.metrics``
    entries harvested live by the runner (e.g. CT ``low_contrast_cnr``).

Outputs:
    - ``build_metric_rows``: stable-sorted ``[(dotted_key, value), ...]``
    - ``build_run_provenance``: compact audit dict (study/series, versions, status)
    - ``build_tabular_run``: one wide dict merging provenance + metric rows

Merge rule (locked, OQ-5):
    1. Walk ``raw_pylinac`` into dotted keys (nested dicts → dotted, lists/tuples
       joined with ``"; "``).
    2. Overlay curated ``result.metrics`` entries on top. Curated/harvested keys
       stay **TOP-LEVEL** (``low_contrast_cnr``, ``low_contrast_score``,
       ``num_images``, ``phantom_roll``, ``origin_slice``, ...) — no literal
       ``metrics.`` prefix, matching today's CSV paths and the F1 contract.
    3. On a genuine dotted-key collision, metrics wins (provenance-curated scalars).
       Wide rows from ``build_tabular_run`` overlay flatten keys onto provenance
       **in place** (same win rule, keys stay top-level — no ``metric.`` rename).
       Exception: audit list keys ``warnings`` / ``errors`` are owned by
       :func:`build_run_provenance` (preflight + runner). Pylinac dumps always
       expose top-level ``warnings`` (often ``[]``); those must not clobber the
       merged ``QAResult`` lists when building batch CSV rows.

Requirements:
    - Do not put ``analyzed_image_path`` or any filesystem path into flatten output.
    - Do not add ``metrics_flat`` to JSON (export-layer only).
    - Stable sort of metric keys (sorted by str, like ``qa_export.flatten_metrics``).
    - Failed runs / empty ``raw_pylinac`` still return provenance + errors; no crash.
"""

from __future__ import annotations

from typing import Any

from qa.analysis_types import QAResult

# Keys that must never appear in flatten output even if a runner or dump
# accidentally stores them under raw_pylinac / metrics.
_PATH_FIELD_DENYLIST = frozenset(
    {"analyzed_image_path", "analyzed_module_images", "pdf_report_path"}
)

# Provenance audit lists owned by QAResult / build_run_provenance. Pylinac
# results_data always includes top-level ``warnings`` (often empty); walking
# that key into flatten would overwrite preflight/runner warnings in
# build_tabular_run.
_PROVENANCE_AUDIT_DENYLIST = frozenset({"warnings", "errors"})

_FLATTEN_DENYLIST = _PATH_FIELD_DENYLIST | _PROVENANCE_AUDIT_DENYLIST


def _is_denied_key(key: Any) -> bool:
    """Return True when *key* must not appear in flatten metric rows."""
    return str(key) in _FLATTEN_DENYLIST


def _walk_raw_pylinac(data: Any, prefix: str) -> dict[str, Any]:
    """
    Recursively walk a ``raw_pylinac`` subtree into a flat dotted-key dict.

    Nested dicts are expanded with dotted keys; lists/tuples are joined with
    ``"; "``; ``None`` becomes ``""``; scalars pass through unchanged.
    Keys named in the flatten denylist (path-bearing fields and provenance
    audit lists ``warnings`` / ``errors``) and their subtrees are skipped.
    """
    rows: dict[str, Any] = {}
    if isinstance(data, dict):
        for key in sorted(data, key=str):
            if _is_denied_key(key):
                continue
            full = f"{prefix}{key}" if prefix else str(key)
            rows.update(_walk_raw_pylinac(data[key], prefix=f"{full}."))
    elif isinstance(data, (list, tuple)):
        rows[prefix.rstrip(".")] = "; ".join(str(v) for v in data)
    else:
        rows[prefix.rstrip(".")] = "" if data is None else data
    return rows


def build_metric_rows(result: QAResult) -> list[tuple[str, Any]]:
    """
    Build stable-sorted ``[(dotted_key, value), ...]`` for a QA run.

    Walks ``result.raw_pylinac`` into dotted keys, then overlays curated
    ``result.metrics`` entries on top (metrics wins on collision). Curated
    metrics stay top-level (no ``metrics.`` prefix). Result is stable-sorted
    by key string.

    Returns an empty list when both ``raw_pylinac`` and ``metrics`` are empty
    (e.g. a failed run) — callers should still use ``build_run_provenance``.
    """
    flat: dict[str, Any] = {}

    # 1. Walk raw_pylinac into dotted keys.
    raw = result.raw_pylinac or {}
    flat.update(_walk_raw_pylinac(raw, prefix=""))

    # 2. Overlay curated metrics on top (top-level keys, metrics wins collisions).
    metrics = result.metrics or {}
    for key in sorted(metrics, key=str):
        if _is_denied_key(key):
            continue
        value = metrics[key]
        if isinstance(value, dict):
            # Nested curated dict → dotted overlay (still top-level prefix).
            flat.update(_walk_raw_pylinac(value, prefix=f"{key}."))
        elif isinstance(value, (list, tuple)):
            flat[key] = "; ".join(str(v) for v in value)
        else:
            flat[key] = "" if value is None else value

    # 3. Stable sort by key.
    return sorted(flat.items(), key=lambda kv: str(kv[0]))


def build_run_provenance(result: QAResult, label: str | None = None) -> dict[str, Any]:
    """
    Build a compact provenance/audit dict for a QA run.

    Includes analysis type, success, pylinac version, study/series UIDs,
    modality, num_images, optional label, errors, and warnings. Deliberately
    compact — not the full JSON document. ``analyzed_image_path`` and other
    filesystem paths are never included.
    """
    prov: dict[str, Any] = {
        "analysis_type": result.analysis_type,
        "success": result.success,
        "pylinac_version": result.pylinac_version,
        "study_uid": result.study_uid,
        "series_uid": result.series_uid,
        "modality": result.modality,
        "num_images": result.num_images,
        "label": label,
        "errors": list(result.errors) if result.errors else [],
        "warnings": list(result.warnings) if result.warnings else [],
    }
    return prov


def build_tabular_run(result: QAResult, label: str | None = None) -> dict[str, Any]:
    """
    Build one wide row dict merging provenance + flattened metric rows.

    Used for batch CSV/XLSX Summary where each run is a single row. Provenance
    keys come first (in insertion order); metric rows are then overlaid in
    place. On a key collision the flatten/metrics value **wins** and the key
    stays **top-level** (locked merge rule — no ``metric.`` / ``metrics.``
    rename), except ``warnings`` / ``errors`` which stay provenance-owned.
    Typical metric overlap is ``num_images``.
    """
    row: dict[str, Any] = build_run_provenance(result, label=label)
    for key, value in build_metric_rows(result):
        if key in _PROVENANCE_AUDIT_DENYLIST:
            continue
        row[key] = value
    return row
