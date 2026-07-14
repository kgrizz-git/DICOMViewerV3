"""
MRI PDF notes builders and compare-mode PDF assembly helpers.

Extracted from pylinac_runner.py (Phase 6 refactor). All public names are
re-exported from pylinac_runner.py for backward compatibility.

Public functions:
    build_mri_pdf_notes(result)           -- always-on interpretation notes (List[str])
    build_mri_compare_pdf_notes(batch)    -- comparison table + notes (List[str])
    build_mri_compare_summary_pdf(batch, path) -- viewer-authored summary PDF
    assemble_mri_compare_pdf(summary, runs, out) -- merge summary + run PDFs
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from utils.log_sanitizer import sanitize_exception

logger = logging.getLogger(__name__)

from qa.analysis_types import LcRunConfig, MRIBatchResult, QARequest, QAResult

# ---------------------------------------------------------------------------
# Interpretation note text (module-level constants for easy maintenance)
#
# Notes are rendered by pylinac publish_pdf(notes=list[str]).
# pylinac places the notes label at (1, 4.5) cm and body at (1, 4) cm from
# the bottom of the A4 page.  The "Generated with pylinac..." footer sits at
# y=0.5 cm.  At font size 10, each line is ~0.42 cm tall, leaving room for
# ~6-7 lines before the footer is reached.  Lines must also stay within
# ~90 chars to avoid overrunning the right page edge at x=20 cm.
# Keep _NOTES_LINES to <=6 short lines.  Full details are in the JSON export.
# ---------------------------------------------------------------------------

_NOTES_PYLINAC_DOCS_ACR = "https://pylinac.readthedocs.io/en/latest/acr.html"
_NOTES_PYLINAC_DOCS_CONTRAST = (
    "https://pylinac.readthedocs.io/en/latest/topics/contrast.html"
)

# Lines rendered in the PDF notes block.  Each element = one rendered line.
# Max ~90 chars per line; max 6 lines total (space constraint).
_NOTES_LINES: list[str] = [
    "MTF: rMTF 50% = freq where contrast = 50% of peak. Higher = sharper.",
    f"  Docs: {_NOTES_PYLINAC_DOCS_ACR}",
    "LC SCORE (0-40): sequential stopped count, 4 slices x up to 10 spokes.",
    "  Spoke complete = all 3 disks green. Stops at first incomplete spoke.",
    "  Circles: Blue=boundary/BG ROIs  Green=visible  Red=not visible.",
    f"  Docs: {_NOTES_PYLINAC_DOCS_CONTRAST}",
]

# Full interpretation text used in the viewer-generated compare summary PDF
# (reportlab platypus, no line-count or width constraint).
_NOTES_LINES_FULL: list[str] = [
    "<b>MTF (High-Contrast Resolution)</b>",
    "The rMTF curves show how well the system resolves fine spatial detail. "
    "rMTF 50% is the spatial frequency (lp/mm) at which modulation falls to "
    "50% of its peak — higher values indicate sharper in-plane resolution. "
    "Row-wise and column-wise values reflect resolution along each image axis; "
    "a large difference may indicate directional asymmetry in the acquisition "
    "or reconstruction. MTF values depend on acquisition parameters (FOV, "
    "matrix, reconstruction kernel) and are meaningful only when compared "
    "across sessions with constant parameters.",
    f"Pylinac docs (ACR): {_NOTES_PYLINAC_DOCS_ACR}",
    "",
    "<b>Low-Contrast Detectability Score (0–40)</b>",
    "The score is a <b>sequential stopped count</b> across 4 slices "
    "(slices 8–11). Each slice contributes up to 10 spoke-scores. "
    "A spoke is <i>complete</i> only when ALL 3 of its disks are visible. "
    "Counting on each slice stops at the first incomplete spoke — even if "
    "later spokes are all green, they do not count toward the score. "
    "The total score is the sum of per-slice scores (maximum 40).",
    "",
    "<b>Circle overlay colors in pylinac PDFs</b>",
    "• <font color='blue'>Blue (large)</font>: outer boundary of the detected "
    "low-contrast region (~40 mm radius).",
    "• <font color='blue'>Blue (small)</font>: background reference ROIs used "
    "to measure local contrast.",
    "• <font color='green'>Green</font>: disk ROI that pylinac considers "
    "VISIBLE (contrast visibility ≥ threshold AND ≤ sanity cap).",
    "• <font color='red'>Red</font>: disk ROI that pylinac considers NOT "
    "VISIBLE (below threshold OR exceeds sanity cap for tiny disks).",
    "",
    "<b>Key parameters (recorded in JSON export)</b>",
    "• low_contrast_method (default Weber): contrast equation before "
    "visibility is computed (Weber, Michelson, etc.).",
    "• low_contrast_visibility_threshold (default 0.001): minimum Rose-model "
    "visibility for a disk to count as seen; lower = more permissive.",
    "• low_contrast_visibility_sanity_multiplier (default 3.0): suppresses "
    "unrealistically large visibility on tiny disks.",
    f"Pylinac docs (contrast/visibility): {_NOTES_PYLINAC_DOCS_CONTRAST}",
]


# ---------------------------------------------------------------------------
# PDF notes helpers
# ---------------------------------------------------------------------------


def _build_mri_notes_lines() -> list[str]:
    """
    Return the standard always-on interpretation notes as a list of strings.

    pylinac's ``publish_pdf(notes=list[str])`` renders each element as one
    line.  Passing a plain ``str`` (even with embedded ``\\n``) causes
    ``textLine`` to render only the first line.  This function returns the
    pre-split list directly.

    Returns:
        List[str] ready to pass as the ``notes`` kwarg to ``publish_pdf``.
    """
    return list(_NOTES_LINES)


def build_mri_pdf_notes(result: QAResult) -> list[str]:
    """
    Build always-on interpretation notes for an ACR MRI Large PDF.

    The notes cover MTF meaning, low-contrast scoring rules, circle color
    meanings, and links to pylinac documentation.  Returns a list of strings
    because pylinac's ``publish_pdf`` renders each list element as one line
    (passing a plain string only renders the first line).

    Args:
        result: The QAResult for this run (reserved for per-run metric inserts
            in future extensions; currently unused).

    Returns:
        List[str] for the ``notes`` argument of ``ACRMRILarge.publish_pdf``.
    """
    return _build_mri_notes_lines()


def build_mri_compare_pdf_notes(batch: MRIBatchResult) -> list[str]:
    """
    Build interpretation notes for the primary run PDF of a compare-mode batch.

    Prepends a settings-and-score comparison table (with scores from completed
    runs) to the standard notes block.

    Args:
        batch: MRIBatchResult from run_acr_mri_large_batch().

    Returns:
        List[str] for the ``notes`` argument of ``ACRMRILarge.publish_pdf``.
    """
    header = "COMPARE MODE — LOW-CONTRAST SETTINGS AND SCORES"
    sep = "-" * min(len(header), 60)
    lines: list[str] = [header, sep]
    for i, (cfg, r) in enumerate(zip(batch.run_configs, batch.run_results, strict=False)):
        score = r.metrics.get("low_contrast_score", "N/A") if r.success else "FAILED"
        lines.append(
            f"  Run {i + 1} ({cfg.label}): score={score}"
            f"  method={cfg.low_contrast_method}"
            f"  thr={cfg.low_contrast_visibility_threshold:.6f}"
            f"  sanity={cfg.low_contrast_visibility_sanity_multiplier:.3f}"
        )
    lines.append("")
    lines.extend(_NOTES_LINES)
    return lines


# ---------------------------------------------------------------------------
# Compare-mode PDF helpers (temp PDFs, summary page, merger)
# ---------------------------------------------------------------------------


def _write_per_run_temp_pdf(
    analyzer: Any,
    temp_path: Path,
    run_label: str,
    cfg: LcRunConfig,
) -> Path | None:
    """
    Write a per-run pylinac PDF to a temporary file.

    Passes a compact 4-line notes block (run label + parameters) so the
    pylinac first-page notes area stays within its 6-line space limit.

    Args:
        analyzer: An already-analyzed ACRMRILarge instance.
        temp_path: Destination path for the temp PDF.
        run_label: Human-readable label (e.g. "Run 1").
        cfg: LcRunConfig for this run (used in notes lines).

    Returns:
        The path if the PDF was written successfully, None on failure.
    """
    notes: list[str] = [
        f"{run_label}: method={cfg.low_contrast_method}",
        f"  threshold={cfg.low_contrast_visibility_threshold:.6f}",
        f"  sanity_mult={cfg.low_contrast_visibility_sanity_multiplier:.3f}",
        "(See combined PDF summary page for full interpretation notes.)",
    ]
    try:
        analyzer.publish_pdf(str(temp_path), notes=notes)
        return temp_path
    except Exception as exc:
        logger.warning("_write_per_run_temp_pdf failed for %s: %s", run_label, sanitize_exception(str(exc)))
        return None


def build_mri_compare_summary_pdf(
    batch: MRIBatchResult,
    output_path: Path,
    *,
    base_request: QARequest | None = None,
    app_version: str = "",
) -> None:
    """
    Build a viewer-authored summary PDF for a compare-mode batch.

    Uses reportlab platypus (already installed as a pylinac dependency) so
    layout is flow-based and not constrained by pylinac's fixed coordinates.

    Page 1 contains:
    - Report title and metadata (study UID, date, image count, app/pylinac versions)
    - Run parameter and score comparison table
    - Full interpretation notes (MTF, LC score, circle colors, docs links)

    Args:
        batch: MRIBatchResult from run_acr_mri_large_batch().
        output_path: Destination Path for the summary PDF.
        base_request: Optional QARequest used to embed study/series metadata.
        app_version: Application version string to embed in the report.
    """
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import cm
        from reportlab.platypus import (
            Paragraph,
            SimpleDocTemplate,
            Spacer,
            Table,
            TableStyle,
        )
    except ImportError as exc:
        raise RuntimeError(
            f"reportlab is required to build the compare summary PDF: {exc}"
        ) from exc

    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
        title="ACR MRI Large — Low-Contrast Compare Report",
        author="DICOM Viewer V3",
    )
    styles = getSampleStyleSheet()
    note_style = ParagraphStyle(
        "NoteBody",
        parent=styles["Normal"],
        fontSize=9,
        leading=13,
        spaceAfter=2,
    )
    elements = []

    # Title
    elements.append(
        Paragraph(
            "ACR MRI Large — Low-Contrast Compare Mode Report",
            styles["Title"],
        )
    )
    elements.append(Spacer(1, 0.3 * cm))

    # Metadata block
    py_ver = (
        batch.run_results[0].pylinac_version
        if batch.run_results
        else ""
    )
    meta_rows = [
        ["Generated by", f"DICOM Viewer V3 {app_version}".strip()],
        ["Pylinac version", py_ver or "(unknown)"],
        ["Runs in this comparison", str(len(batch.run_configs))],
    ]
    if base_request is not None:
        if base_request.study_uid:
            meta_rows.append(["Study UID", base_request.study_uid])
        if base_request.series_uid:
            meta_rows.append(["Series UID", base_request.series_uid])
        if base_request.dicom_paths:
            meta_rows.append(["Images loaded", str(len(base_request.dicom_paths))])
    meta_table = Table(meta_rows, colWidths=[4.5 * cm, None])
    meta_table.setStyle(
        TableStyle(
            [
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#555555")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 1),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
            ]
        )
    )
    elements.append(meta_table)
    elements.append(Spacer(1, 0.4 * cm))

    # Run comparison table
    elements.append(Paragraph("Run Comparison", styles["Heading2"]))
    elements.append(Spacer(1, 0.2 * cm))
    headers = ["Run", "Label", "Method", "Threshold", "Sanity ×", "LC Score", "Status"]
    table_data = [headers]
    for i, (cfg, r) in enumerate(zip(batch.run_configs, batch.run_results, strict=False)):
        score = (
            str(r.metrics.get("low_contrast_score", "N/A")) if r.success else "—"
        )
        status = "OK" if r.success else "FAILED"
        table_data.append(
            [
                str(i + 1),
                cfg.label,
                cfg.low_contrast_method,
                f"{cfg.low_contrast_visibility_threshold:.6f}",
                f"{cfg.low_contrast_visibility_sanity_multiplier:.3f}",
                score,
                status,
            ]
        )
    run_table = Table(table_data, repeatRows=1)
    run_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2c3e50")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("ALIGN", (1, 1), (2, -1), "LEFT"),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                (
                    "ROWBACKGROUNDS",
                    (0, 1),
                    (-1, -1),
                    [colors.white, colors.HexColor("#f2f2f2")],
                ),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )
    elements.append(run_table)
    elements.append(Spacer(1, 0.5 * cm))

    # Full interpretation notes
    elements.append(Paragraph("Interpretation Notes", styles["Heading2"]))
    elements.append(Spacer(1, 0.2 * cm))
    for line in _NOTES_LINES_FULL:
        if not line:
            elements.append(Spacer(1, 0.2 * cm))
        else:
            elements.append(Paragraph(line, note_style))

    doc.build(elements)


def assemble_mri_compare_pdf(
    summary_path: Path,
    run_pdf_paths: list[Path | None],
    output_path: Path,
) -> bool:
    """
    Merge the viewer summary PDF with per-run pylinac PDFs into one file.

    Writes ``[summary_path] + [p for p in run_pdf_paths if p exists]`` to
    ``output_path``.  Cleans up ``summary_path`` and all temp run PDFs after
    a successful or failed merge (best-effort cleanup).

    Requires ``pypdf>=4.0.0`` (added to requirements.txt).

    Args:
        summary_path: Path to the viewer-authored summary PDF.
        run_pdf_paths: Per-run temp PDF paths (None entries are skipped).
        output_path: Final combined PDF path chosen by the user.

    Returns:
        True if the combined PDF was written successfully, False otherwise.
    """
    try:
        import pypdf  # type: ignore[import-not-found]
    except ImportError:
        logger.error(
            "pypdf is not installed; cannot assemble combined compare PDF. "
            "Install with: pip install pypdf>=4.0.0"
        )
        return False

    paths_to_merge: list[Path] = []
    if summary_path.exists():
        paths_to_merge.append(summary_path)
    for p in run_pdf_paths:
        if p is not None and Path(p).exists():
            paths_to_merge.append(Path(p))

    if not paths_to_merge:
        logger.warning("assemble_mri_compare_pdf: no source PDFs found to merge.")
        return False

    try:
        writer = pypdf.PdfWriter()
        for pdf_path in paths_to_merge:
            reader = pypdf.PdfReader(str(pdf_path))
            for page in reader.pages:
                writer.add_page(page)
        with open(str(output_path), "wb") as fh:
            writer.write(fh)
        success = True
    except Exception as exc:
        logger.error("assemble_mri_compare_pdf failed: %s", sanitize_exception(str(exc)))
        success = False

    # Best-effort cleanup of temp files
    for p in [summary_path] + [x for x in run_pdf_paths if x is not None]:
        try:
            Path(p).unlink(missing_ok=True)
        except Exception:
            pass

    return success
