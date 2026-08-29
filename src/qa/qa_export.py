"""
Pure builders for single-run QA exports (no Qt, no I/O).

Shared by the facade auto-export and the nuclear result dialog's export
buttons so the JSON schema stays in one place.

Public:
    build_single_run_document   -- versioned dict for a QAResult
    build_metrics_csv           -- flat metric,value CSV (full flatten; any analysis type)
    build_batch_metrics_csv     -- wide CSV, one row per run (batch export)
    build_nuclear_frames_csv    -- per-frame uniformity CSV text for a nuclear run
    build_nuclear_flat_csv      -- metric,value CSV over a flat nuclear result
    build_nuclear_quadrants_csv -- per-quadrant resolution CSV text
    build_nuclear_spheres_csv   -- per-sphere contrast CSV text
"""

from __future__ import annotations

import csv
import io
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

from core.spreadsheet_safety import SafeCsvWriter
from qa.analysis_types import QAResult
from qa.qa_result_flatten import (
    build_metric_rows,
    build_run_provenance,
    build_tabular_run,
)

# Per-frame metric columns for nuclear PlanarUniformity CSV export.
_NUCLEAR_FRAME_FIELDS = (
    "ufov_integral_uniformity",
    "ufov_differential_uniformity",
    "cfov_integral_uniformity",
    "cfov_differential_uniformity",
)

# Per-quadrant metric columns for nuclear QuadrantResolution CSV export.
_NUCLEAR_QUADRANT_FIELDS = ("mtf", "fwhm", "lpmm", "spacing")

# Per-sphere metric columns for nuclear TomographicContrast CSV export.
_NUCLEAR_SPHERE_FIELDS = (
    "x",
    "y",
    "z",
    "radius",
    "mean",
    "mean_contrast",
    "max_contrast",
)


def _frame_sort_key(frame_label: str) -> int:
    digits = "".join(ch for ch in str(frame_label) if ch.isdigit())
    return int(digits) if digits else 0


def _csv_cell(value: Any) -> Any:
    """Coerce a cell so ``SafeCsvWriter`` can neutralize formula-like strings.

    Provenance ``errors`` / ``warnings`` are Python lists. Passing a list
    through ``csv.writer`` emits a repr that starts with ``[``, so
    ``SafeCsvWriter`` never sees the inner strings. Join lists/tuples first.
    """
    if isinstance(value, (list, tuple)):
        return "; ".join(str(item) for item in value)
    return value


def _csv_row(cells: Sequence[Any]) -> list[Any]:
    """Map ``_csv_cell`` across a row before ``SafeCsvWriter.writerow``."""
    return [_csv_cell(cell) for cell in cells]


def build_single_run_document(
    result: QAResult,
    *,
    app_version: str,
    inputs: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Build a versioned export document for a single QA run.

    ACR and nuclear runs share this shape; consumers discriminate on
    ``run.analysis_type``. Nuclear runs additionally carry
    ``run.nuclear_analysis_class`` so the payload is self-describing.

    ``raw_pylinac`` is an **opaque, pylinac-version-dependent passthrough**
    (not a stable contract) -- for CT runs it is now
    ``analyzer.results_data(as_dict=True)``, a structured dict whose exact
    keys/shape may change across pylinac releases. Consumers should treat it
    as debugging/audit context, not a schema to depend on. The CT document was
    bumped from "1.1" to "1.3" to signal its move from a stringified blob;
    single-run MRI and nuclear documents retain "1.1". "1.2" is reserved for
    the MRI compare document.
    """
    profile = result.pylinac_analysis_profile or {}
    vanilla_run = bool(profile.get("vanilla_pylinac", False))

    schema_version = "1.3" if result.analysis_type == "acr_ct" else "1.1"

    payload: dict[str, Any] = {
        "schema_version": schema_version,
        "run": {
            "timestamp_utc": datetime.now(UTC).isoformat(),
            "app_version": app_version,
            "pylinac_version": result.pylinac_version or "",
            "analysis_type": result.analysis_type,
            "status": "success" if result.success else "failed",
            "vanilla_pylinac": vanilla_run,
        },
        "series": {
            "study_uid": result.study_uid,
            "series_uid": result.series_uid,
            "modality": result.modality,
            "num_images": result.num_images,
        },
        "inputs": inputs or {},
        "pylinac_analysis_profile": profile,
        "metrics": result.metrics,
        "warnings": result.warnings,
        "errors": result.errors,
        "artifacts": {"pdf_report_path": result.pdf_report_path or ""},
        "raw_pylinac": result.raw_pylinac,
    }
    if profile.get("module") == "pylinac.nuclear":
        payload["run"]["nuclear_analysis_class"] = profile.get("nuclear_analysis_class")
    return payload


def flatten_metrics(data: dict[str, Any], prefix: str = "") -> list[tuple[str, Any]]:
    rows: list[tuple[str, Any]] = []
    for key in sorted(data, key=str):
        full = f"{prefix}{key}"
        value = data[key]
        if isinstance(value, dict):
            rows.extend(flatten_metrics(value, prefix=f"{full}."))
        elif isinstance(value, (list, tuple)):
            rows.append((full, "; ".join(str(v) for v in value)))
        else:
            rows.append((full, "" if value is None else value))
    return rows


_flatten = flatten_metrics


def extract_low_contrast_cnr_values(
    metrics: dict[str, Any] | None
) -> tuple[float | None, float | None, float | None, float | None]:
    """
    Extract low-contrast CNR intermediate values:
    (object_mean, background_mean, background_std, cnr)
    from the given metrics dictionary.
    """
    if not metrics:
        return (None, None, None, None)
    details = metrics.get("low_contrast_cnr")
    if not isinstance(details, dict):
        return (None, None, None, None)

    obj_mean = None
    obj_rois = details.get("object_rois")
    if isinstance(obj_rois, list) and obj_rois:
        means = [
            float(roi["mean"])
            for roi in obj_rois
            if isinstance(roi, dict) and isinstance(roi.get("mean"), (int, float))
        ]
        if means:
            obj_mean = sum(means) / len(means)

    background = details.get("background")
    bg_mean = None
    bg_std = None
    if isinstance(background, dict):
        if isinstance(background.get("mean"), (int, float)):
            bg_mean = float(background["mean"])
        if isinstance(background.get("std"), (int, float)):
            bg_std = float(background["std"])

    cnr = None
    if isinstance(details.get("cnr"), (int, float)):
        cnr = float(details["cnr"])

    return (obj_mean, bg_mean, bg_std, cnr)


def build_metrics_csv(result: QAResult) -> str:
    """
    Build a ``metric,value`` CSV from the **full flatten** of a QA run.

    Uses :func:`qa.qa_result_flatten.build_metric_rows` which walks
    ``result.raw_pylinac`` into dotted keys then overlays curated
    ``result.metrics`` (metrics wins on collision, curated keys stay
    top-level). Nested dicts flatten with dotted keys; lists join with ``; ``.

    Two-column shape (``metric,value``) is preserved for single-run parity.
    List/tuple metric values are joined with ``"; "`` first so
    :class:`core.spreadsheet_safety.SafeCsvWriter` can neutralize leading
    ``= + - @`` strings (R0-8). Provenance ``errors`` / ``warnings`` are
    included on the **batch** builder, not this two-column export.
    """
    buffer = io.StringIO()
    writer = SafeCsvWriter(csv.writer(buffer))
    writer.writerow(_csv_row(["metric", "value"]))
    for key, value in build_metric_rows(result):
        writer.writerow(_csv_row([key, value]))
    return buffer.getvalue()


def build_batch_metrics_csv(
    results: Sequence[QAResult],
    labels: Sequence[str] | None = None,
) -> str:
    """
    Build a wide CSV with one header row and one data row per run.

    Each row is produced by :func:`qa.qa_result_flatten.build_tabular_run`
    (provenance keys first, then flattened metric rows overlaid in place —
    metrics wins on collision, keys stay top-level).

    Column order (OQ-3): the union of keys across all rows, ordered as the
    provenance key order from :func:`build_run_provenance` first, then the
    remaining metric keys sorted by ``str`` (stable). Missing cells are empty.

    ``labels`` must be parallel to ``results``; if it is shorter or ``None``,
    unmatched results get ``label=None``. ``analyzed_image_path`` is never
    emitted (flatten denylist). List/tuple cells are joined with ``"; "``
    before :class:`core.spreadsheet_safety.SafeCsvWriter` so formula-like
    strings inside ``errors`` / ``warnings`` are actually neutralized.

    When ``results`` is empty, returns a header-only CSV built from the
    provenance keys of an empty run (no ``metric`` overflow columns).
    """
    # Build all rows up front to compute the stable column union.
    if labels is None:
        labels_seq: Sequence[str | None] = [None] * len(results)
    else:
        labels_seq = labels

    rows: list[dict[str, Any]] = []
    for idx, result in enumerate(results):
        label = labels_seq[idx] if idx < len(labels_seq) else None
        rows.append(build_tabular_run(result, label=label))

    # Fixed column order: provenance keys first, then remaining metric keys
    # sorted by str (stable). Union across all rows; missing cells empty.
    dummy = QAResult(success=False, analysis_type="")
    prov_keys = list(build_run_provenance(dummy).keys())
    seen_prov = set(prov_keys)
    overflow_keys: list[str] = []
    seen_overflow: set[str] = set()
    for row in rows:
        for key in row:
            if key not in seen_prov and key not in seen_overflow:
                seen_overflow.add(key)
                overflow_keys.append(key)
    overflow_keys.sort(key=str)
    columns = prov_keys + overflow_keys

    buffer = io.StringIO()
    writer = SafeCsvWriter(csv.writer(buffer))
    writer.writerow(_csv_row(columns))
    for row in rows:
        writer.writerow(_csv_row([row.get(col, "") for col in columns]))
    return buffer.getvalue()


def build_nuclear_frames_csv(result: QAResult) -> str:
    """
    Build per-frame uniformity CSV text for a nuclear run.

    One header row plus one row per frame. Missing metric values are left blank.
    """
    frames = (result.metrics or {}).get("frames") or {}
    buffer = io.StringIO()
    writer = SafeCsvWriter(csv.writer(buffer))
    writer.writerow(_csv_row(["frame", *_NUCLEAR_FRAME_FIELDS]))
    for frame_label in sorted(frames, key=_frame_sort_key):
        values = frames.get(frame_label) or {}
        writer.writerow(
            _csv_row(
                [frame_label, *[values.get(field, "") for field in _NUCLEAR_FRAME_FIELDS]]
            )
        )
    return buffer.getvalue()


def build_nuclear_flat_csv(result: QAResult) -> str:
    """
    Build a ``metric,value`` CSV from a flat nuclear result.

    Reads ``result.metrics["results"]`` (e.g. FourBarResolution's 8 floats),
    preserving pylinac's field order. Header-only when no results are present.
    """
    results = (result.metrics or {}).get("results") or {}
    buffer = io.StringIO()
    writer = SafeCsvWriter(csv.writer(buffer))
    writer.writerow(_csv_row(["metric", "value"]))
    for key, value in results.items():
        writer.writerow(_csv_row([key, value]))
    return buffer.getvalue()


def build_nuclear_quadrants_csv(result: QAResult) -> str:
    """
    Build a per-quadrant CSV from ``result.metrics["quadrants"]``.

    One header row plus one row per quadrant (sorted by key). Missing fields are
    left blank.
    """
    quadrants = (result.metrics or {}).get("quadrants") or {}
    buffer = io.StringIO()
    writer = SafeCsvWriter(csv.writer(buffer))
    writer.writerow(_csv_row(["quadrant", *_NUCLEAR_QUADRANT_FIELDS]))
    for quad_key in sorted(quadrants, key=str):
        values = quadrants.get(quad_key) or {}
        writer.writerow(
            _csv_row(
                [quad_key, *[values.get(field, "") for field in _NUCLEAR_QUADRANT_FIELDS]]
            )
        )
    return buffer.getvalue()


def build_nuclear_spheres_csv(result: QAResult) -> str:
    """
    Build a per-sphere CSV from ``result.metrics["spheres"]`` (TomographicContrast).

    One header row plus one row per sphere (sorted by key). Missing fields blank.
    """
    spheres = (result.metrics or {}).get("spheres") or {}
    buffer = io.StringIO()
    writer = SafeCsvWriter(csv.writer(buffer))
    writer.writerow(_csv_row(["sphere", *_NUCLEAR_SPHERE_FIELDS]))
    for sphere_key in sorted(spheres, key=str):
        values = spheres.get(sphere_key) or {}
        writer.writerow(
            _csv_row(
                [sphere_key, *[values.get(field, "") for field in _NUCLEAR_SPHERE_FIELDS]]
            )
        )
    return buffer.getvalue()
