"""
XLSX export builder for QA results (no Qt).

Kept separate from ``qa_export.py`` (stdlib ``csv``/``json`` only) so the
heavier ``openpyxl`` + ``Pillow`` imports and the image-embed logic stay
isolated. Both modules remain Qt-free and independently testable.

Public:
    build_qa_workbook -- Summary/Detail/Images workbook for one or more QAResults
"""

from __future__ import annotations

import os
from typing import Any

from openpyxl import Workbook
from openpyxl.worksheet.worksheet import Worksheet

from qa.analysis_types import QAResult
from qa.qa_export import _flatten

# Guarded at import time so the Images-sheet builder can cheaply detect a
# missing Pillow install without repeatedly trying/catching per image. Pillow
# is a declared/installed dependency (see requirements.txt); this guard only
# protects against an unusual environment where it is absent.
try:
    from PIL import Image as _PILImage  # noqa: F401  (import-only availability probe)

    _PILLOW_AVAILABLE = True
except Exception:
    _PILLOW_AVAILABLE = False

_SUMMARY_HEADERS = (
    "Series/Run ID",
    "Object ROI Mean",
    "Background Mean",
    "Background Std",
    "CNR",
    "Status",
    "Warnings",
)


def _row_label(result: QAResult, label: str | None) -> str:
    """Series/Run ID column value: explicit label, else the row's series_uid."""
    if label:
        return label
    return result.series_uid or ""


def _cnr_summary_values(result: QAResult) -> tuple[Any, Any, Any, Any]:
    """
    Pull the F1 CNR intermediates for the Summary sheet.

    Reads the canonical ``metrics["low_contrast_cnr"]`` shape (see F1 in
    PYLINAC_CT_CNR_BATCH_XLSX_PLAN.md): object ROI mean is the average of
    ``object_rois[*].mean``; background mean/std and module ``cnr`` are read
    with ``.get()``. Any missing key degrades to a blank cell.
    """
    details = (result.metrics or {}).get("low_contrast_cnr")
    if not isinstance(details, dict):
        return ("", "", "", "")
    obj_mean: Any = ""
    obj_rois = details.get("object_rois")
    if isinstance(obj_rois, list) and obj_rois:
        means = [
            roi.get("mean")
            for roi in obj_rois
            if isinstance(roi, dict) and isinstance(roi.get("mean"), (int, float))
        ]
        if means:
            obj_mean = sum(means) / len(means)
    background = details.get("background")
    bg_mean = background.get("mean", "") if isinstance(background, dict) else ""
    bg_std = background.get("std", "") if isinstance(background, dict) else ""
    cnr = details.get("cnr", "")
    return (obj_mean, bg_mean, bg_std, cnr)


def _build_summary_sheet(
    ws: Worksheet, results: list[QAResult], row_labels: list[str | None]
) -> None:
    ws.append(list(_SUMMARY_HEADERS))
    for result, label in zip(results, row_labels, strict=True):
        obj_mean, bg_mean, bg_std, cnr = _cnr_summary_values(result)
        status = "success" if result.success else "failed"
        warnings_text = "; ".join(result.warnings or [])
        ws.append(
            [_row_label(result, label), obj_mean, bg_mean, bg_std, cnr, status, warnings_text]
        )


def _build_detail_sheet(
    ws: Worksheet, results: list[QAResult], row_labels: list[str | None]
) -> None:
    """
    Flat metric rows, one block per run.

    Reuses ``qa_export._flatten`` over ``result.metrics`` for the exact
    dotted-key / list-joined shape the CSV export already produces, so the
    Detail sheet matches the CSV export field-for-field.
    """
    ws.append(["Metric", "Value"])
    for result, label in zip(results, row_labels, strict=True):
        ws.append([_row_label(result, label), ""])
        for key, value in _flatten(result.metrics or {}):
            ws.append([key, value])
        ws.append([])  # blank separator row between run blocks


def _append_note(ws: Worksheet, note: str) -> None:
    ws.append([])
    ws.append([note])


def _build_images_sheet(
    wb: Workbook,
    summary_ws: Worksheet,
    results: list[QAResult],
    row_labels: list[str | None],
) -> None:
    """
    One embedded PNG per run, stacked vertically, each preceded by its
    Series/Run ID label cell.

    Degrades gracefully: if Pillow is unavailable, or none of the runs have
    an analyzed-image path on disk, the Images sheet is skipped entirely and
    a note cell is appended to the Summary sheet instead -- the rest of the
    workbook (Summary, Detail) still writes.
    """
    if not _PILLOW_AVAILABLE:
        _append_note(summary_ws, "Images sheet skipped: Pillow is not available for image embedding.")
        return

    available = [
        (result, label)
        for result, label in zip(results, row_labels, strict=True)
        if getattr(result, "analyzed_image_path", None)
        and os.path.isfile(result.analyzed_image_path)
    ]
    if not available:
        _append_note(summary_ws, "Images sheet skipped: no analyzed images were available.")
        return

    from openpyxl.drawing.image import Image as XLImage

    ws = wb.create_sheet("Images")
    row = 1
    for result, label in zip(results, row_labels, strict=True):
        ws.cell(row=row, column=1, value=_row_label(result, label))
        row += 1
        path = getattr(result, "analyzed_image_path", None)
        if path and os.path.isfile(path):
            try:
                image = XLImage(path)
                ws.add_image(image, f"A{row}")
                # Advance past the image's rendered height (~15px/row default
                # openpyxl row height) plus a small gap before the next block.
                rows_used = max(int(image.height / 15) + 1, 1)
                row += rows_used + 1
            except Exception:
                ws.cell(row=row, column=1, value="(image could not be embedded)")
                row += 2
        else:
            ws.cell(row=row, column=1, value="(no analyzed image for this run)")
            row += 2


def build_qa_workbook(
    results: list[QAResult],
    labels: list[str] | None = None,
    *,
    app_version: str = "",
) -> Workbook:
    """
    Build an in-memory openpyxl Workbook for one or more QA runs.

    The caller saves the returned workbook (``workbook.save(path)``); this
    builder stays pure and Qt-free so it is testable via an in-memory
    round-trip. Single-run export passes a 1-element ``results`` list; batch
    export passes N.

    Args:
        results: QA results, one per run/series.
        labels: Optional display labels, parallel to ``results``. When None,
            each row falls back to its ``series_uid``.
        app_version: Reserved for future provenance metadata (unused today;
            accepted for signature parity with the JSON/CSV builders).

    Sheets:
        Summary -- one row per run: Series/Run ID, object ROI mean,
            background mean/std, CNR, status, warnings (see F1's canonical
            ``metrics["low_contrast_cnr"]`` shape).
        Detail -- flat metric rows per run (reuses ``qa_export._flatten``).
        Images -- one embedded analyzed-image PNG per run, or a note cell on
            Summary when Pillow/images are unavailable.
    """
    if labels is not None and len(labels) != len(results):
        raise ValueError("labels must be parallel to results (same length)")
    row_labels: list[str | None] = list(labels) if labels is not None else [None] * len(results)

    wb = Workbook()
    summary_ws = wb.active
    summary_ws.title = "Summary"
    _build_summary_sheet(summary_ws, results, row_labels)

    detail_ws = wb.create_sheet("Detail")
    _build_detail_sheet(detail_ws, results, row_labels)

    _build_images_sheet(wb, summary_ws, results, row_labels)

    return wb
