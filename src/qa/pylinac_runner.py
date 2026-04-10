"""
Stage 1 pylinac runner entrypoints.

The GUI should call this module (via a worker) instead of importing pylinac
directly. This keeps pylinac optional and allows graceful error handling when
the dependency is missing.

Public functions:
    run_acr_ct_analysis(request)          -- single-run ACR CT analysis
    run_acr_mri_large_analysis(request)   -- single-run ACR MRI Large analysis
    run_acr_mri_large_batch(base, configs)-- multi-run compare-mode batch;
                                            produces a combined PDF via pypdf
    build_mri_pdf_notes(result)           -- always-on interpretation notes (List[str])
    build_mri_compare_pdf_notes(batch)    -- comparison table + notes (List[str])
    build_mri_compare_summary_pdf(batch, path) -- viewer-authored summary PDF
    assemble_mri_compare_pdf(summary, runs, out) -- merge summary + run PDFs

Requirements:
    pylinac (optional, graceful fallback when missing)
    pypdf>=4.0.0 (optional, graceful fallback when missing)
    reportlab (transitively installed by pylinac)
    qa.analysis_types.QARequest / QAResult / LcRunConfig / MRIBatchResult
    qa.pylinac_extent_subclasses (ACRCTForViewer, ACRMRILargeForViewer; RelaxedExtent aliases)
"""

from __future__ import annotations

import inspect
import logging
import shutil
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

from qa.analysis_types import (
    LcRunConfig,
    MRIBatchResult,
    QARequest,
    QAResult,
    build_pylinac_analysis_profile,
)
from utils.config.qa_pylinac_config import (
    DEFAULT_ACR_MRI_LOW_CONTRAST_METHOD,
    DEFAULT_ACR_MRI_LOW_CONTRAST_VISIBILITY_SANITY_MULTIPLIER,
    DEFAULT_ACR_MRI_LOW_CONTRAST_VISIBILITY_THRESHOLD,
)
from utils.debug_flags import DEBUG_PYLINAC_QA

# Stock pylinac CatPhanBase message; viewer mixin uses a different out-of-range wording.
_PYLINAC_IMAGE_INDEX_FAILURE_MARKERS = (
    "beyond the image extent",
    "out of range for the loaded stack",
)

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
_NOTES_LINES: List[str] = [
    "MTF: rMTF 50% = freq where contrast = 50% of peak. Higher = sharper.",
    f"  Docs: {_NOTES_PYLINAC_DOCS_ACR}",
    "LC SCORE (0-40): sequential stopped count, 4 slices x up to 10 spokes.",
    "  Spoke complete = all 3 disks green. Stops at first incomplete spoke.",
    "  Circles: Blue=boundary/BG ROIs  Green=visible  Red=not visible.",
    f"  Docs: {_NOTES_PYLINAC_DOCS_CONTRAST}",
]

# Full interpretation text used in the viewer-generated compare summary PDF
# (reportlab platypus, no line-count or width constraint).
_NOTES_LINES_FULL: List[str] = [
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
# JSON helpers
# ---------------------------------------------------------------------------


def _jsonable(value: Any) -> Any:
    """Best-effort conversion to JSON-friendly primitives."""
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    return str(value)


def _image_count(analyzer: Any, request: QARequest) -> int:
    n = len(request.dicom_paths)
    stack = getattr(analyzer, "dicom_stack", None)
    if stack is not None:
        try:
            return int(len(stack))
        except Exception:
            pass
    return n


def _missing_pylinac_result(request: QARequest) -> QAResult:
    return QAResult(
        success=False,
        analysis_type=request.analysis_type,
        errors=[
            "pylinac is not installed. Install required dependencies and retry."
        ],
        study_uid=request.study_uid,
        series_uid=request.series_uid,
        modality=request.modality,
        num_images=len(request.dicom_paths),
        pylinac_analysis_profile=build_pylinac_analysis_profile(
            request, engine="(pylinac not installed)"
        ),
    )


# ---------------------------------------------------------------------------
# PDF notes helpers
# ---------------------------------------------------------------------------


def _build_mri_notes_lines() -> List[str]:
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



def build_mri_pdf_notes(result: QAResult) -> List[str]:
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


def build_mri_compare_pdf_notes(batch: MRIBatchResult) -> List[str]:
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
    lines: List[str] = [header, sep]
    for i, (cfg, r) in enumerate(zip(batch.run_configs, batch.run_results)):
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
    cfg: "LcRunConfig",
) -> Optional[Path]:
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
    notes: List[str] = [
        f"{run_label}: method={cfg.low_contrast_method}",
        f"  threshold={cfg.low_contrast_visibility_threshold:.6f}",
        f"  sanity_mult={cfg.low_contrast_visibility_sanity_multiplier:.3f}",
        "(See combined PDF summary page for full interpretation notes.)",
    ]
    try:
        analyzer.publish_pdf(str(temp_path), notes=notes)
        return temp_path
    except Exception as exc:
        logger.warning("_write_per_run_temp_pdf failed for %s: %s", run_label, exc)
        return None


def build_mri_compare_summary_pdf(
    batch: "MRIBatchResult",
    output_path: Path,
    *,
    base_request: Optional["QARequest"] = None,
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
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
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
    for i, (cfg, r) in enumerate(zip(batch.run_configs, batch.run_results)):
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
    run_pdf_paths: List[Optional[Path]],
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

    paths_to_merge: List[Path] = []
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
        logger.error("assemble_mri_compare_pdf failed: %s", exc)
        success = False

    # Best-effort cleanup of temp files
    for p in [summary_path] + [x for x in run_pdf_paths if x is not None]:
        try:
            Path(p).unlink(missing_ok=True)
        except Exception:
            pass

    return success


# ---------------------------------------------------------------------------
# MRI analyzer construction helper
# ---------------------------------------------------------------------------


def _build_mri_analyzer(
    request: QARequest,
    *,
    cls: Any,
    extent_tol_mm: Optional[float] = None,
) -> Any:
    """
    Construct an ACRMRILarge (or subclass) analyzer from a QARequest.

    Handles both dicom_paths and folder_path source modes. When
    ``extent_tol_mm`` is not None, sets ``_scan_extent_tolerance_mm`` on the
    instance (viewer subclasses only; omit for stock ``ACRMRILarge``).

    Does NOT call analyze().

    Args:
        request: Input payload carrying paths and check_uid.
        cls: ``ACRMRILarge`` or ``ACRMRILargeForViewer``.
        extent_tol_mm: Optional scan-extent tolerance in mm for viewer class.

    Returns:
        An unanalyzed analyzer instance.

    Raises:
        ValueError: If neither dicom_paths nor folder_path are provided.
    """
    if request.dicom_paths:
        analyzer = cls(request.dicom_paths, check_uid=request.check_uid)
    elif request.folder_path:
        analyzer = cls(request.folder_path, check_uid=request.check_uid)
    else:
        raise ValueError("No DICOM paths or folder were provided.")
    if extent_tol_mm is not None:
        analyzer._scan_extent_tolerance_mm = float(extent_tol_mm)
    return analyzer


def _build_mri_analyze_kwargs(
    analyzer: Any,
    request: QARequest,
    *,
    lc_method: str,
    lc_vis: float,
    lc_sanity: float,
) -> Dict[str, Any]:
    """
    Build the keyword-argument dict for analyze() using signature inspection.

    Only passes kwargs that the installed pylinac version exposes, ensuring
    backward compatibility with older builds.

    Args:
        analyzer: An unanalyzed ACRMRILarge instance (used for signature).
        request: Input payload for echo, check_uid, origin_slice.
        lc_method: Contrast method string.
        lc_vis: Visibility threshold float.
        lc_sanity: Sanity multiplier float.

    Returns:
        Dict of kwargs ready to unpack into analyzer.analyze(**kwargs).
    """
    sig = inspect.signature(analyzer.analyze)
    kwargs: Dict[str, Any] = {}
    if "echo_number" in sig.parameters:
        kwargs["echo_number"] = request.echo_number
    if "check_uid" in sig.parameters:
        kwargs["check_uid"] = request.check_uid
    if request.origin_slice is not None and "origin_slice" in sig.parameters:
        kwargs["origin_slice"] = int(request.origin_slice)
    if "low_contrast_method" in sig.parameters:
        kwargs["low_contrast_method"] = lc_method
    if "low_contrast_visibility_threshold" in sig.parameters:
        kwargs["low_contrast_visibility_threshold"] = lc_vis
    if "low_contrast_visibility_sanity_multiplier" in sig.parameters:
        kwargs["low_contrast_visibility_sanity_multiplier"] = lc_sanity
    return kwargs


def _build_mri_extra_warnings(analyzer: Any) -> list[str]:
    """
    Return warnings for any low-contrast kwargs that the installed pylinac
    version does not expose on analyze().
    """
    sig = inspect.signature(analyzer.analyze)
    warnings: list[str] = []
    if "check_uid" not in sig.parameters:
        warnings.append(
            "This pylinac build does not expose analyze(check_uid=...); "
            "the value is stored in JSON for reproducibility only."
        )
    if "low_contrast_visibility_threshold" not in sig.parameters:
        warnings.append(
            "This pylinac build does not expose "
            "analyze(low_contrast_visibility_threshold=...); "
            "the value is stored in JSON for reproducibility only."
        )
    if "low_contrast_method" not in sig.parameters:
        warnings.append(
            "This pylinac build does not expose "
            "analyze(low_contrast_method=...); "
            "the value is stored in JSON for reproducibility only."
        )
    if "low_contrast_visibility_sanity_multiplier" not in sig.parameters:
        warnings.append(
            "This pylinac build does not expose "
            "analyze(low_contrast_visibility_sanity_multiplier=...); "
            "the value is stored in JSON for reproducibility only."
        )
    return warnings


# ---------------------------------------------------------------------------
# ACR CT
# ---------------------------------------------------------------------------


def _acr_ct_stack_diagnostic_lines(analyzer: Any) -> List[str]:
    """
    Best-effort context when slice indexing fails during ACR CT analysis.

    DICOM Viewer uses ``ACRCTForViewer``, which allows origin indices
    ``0 .. num_images-1``. If this still fails, the index is out of range for
    the loaded stack or another stage failed after localization.
    """
    lines: List[str] = []
    try:
        stack = getattr(analyzer, "dicom_stack", None)
        n = len(stack) if stack is not None else 0
    except Exception:
        n = 0
    lines.append(f"Images in stack (pylinac): {n}")
    if n <= 0:
        lines.append("Stack reports zero images — check DICOM paths or folder contents.")
    else:
        lines.append(
            "This app allows origin_slice indices 0 … N-1 (N = num_images). "
            "Stock pylinac alone allows only strictly interior indices "
            "(see JSON pylinac_analysis_profile.relaxed_image_extent)."
        )
    try:
        stack = getattr(analyzer, "dicom_stack", None)
        sp = getattr(stack, "slice_spacing", None) if stack is not None else None
        if sp is not None:
            lines.append(f"dicom_stack.slice_spacing (mm): {sp}")
    except Exception:
        pass
    try:
        from pylinac.core.image import z_position  # type: ignore[import-not-found]

        stack = getattr(analyzer, "dicom_stack", None)
        metas = getattr(stack, "metadatas", None) if stack is not None else None
        if metas:
            zs = [float(z_position(m)) for m in metas]
            lines.append(
                f"ImagePositionPatient Z (mm) min/max: {min(zs):.3f} … {max(zs):.3f} "
                f"(span {max(zs) - min(zs):.3f})"
            )
    except Exception:
        pass
    lines.append(
        "Typical causes: wrong/empty series, non-axial order, partial phantom, or "
        "bad HU localization. Override with analyze(origin_slice=...) from the CT "
        "options dialog if needed."
    )
    return lines


def run_acr_ct_analysis(request: QARequest) -> QAResult:
    """
    Run ACR CT analysis through pylinac with normalized output.

    Args:
        request: Normalized request payload from UI/worker.

    Returns:
        QAResult with success/failure details and normalized payload.
    """
    try:
        from pylinac import ACRCT  # type: ignore[import-not-found]
        import pylinac  # type: ignore[import-not-found]

        from qa.pylinac_extent_subclasses import ACRCTForViewer
    except Exception:
        return _missing_pylinac_result(request)

    py_ver = getattr(pylinac, "__version__", None)
    tol = float(request.scan_extent_tolerance_mm or 0.0)
    vanilla = bool(getattr(request, "vanilla_pylinac", False))
    eff_tol = 0.0 if vanilla else tol
    warn_ignore_tol = vanilla and tol > 0.0
    cls = ACRCT if vanilla else ACRCTForViewer
    engine = "ACRCT" if vanilla else "ACRCTForViewer"
    profile = build_pylinac_analysis_profile(request, engine=engine)

    analyzer: Any = None
    try:
        if request.dicom_paths:
            analyzer = cls(request.dicom_paths, check_uid=request.check_uid)
        elif request.folder_path:
            # CatPhanBase / ACRCT load from a folder via __init__, not from_folder.
            analyzer = cls(request.folder_path, check_uid=request.check_uid)
        else:
            return QAResult(
                success=False,
                analysis_type=request.analysis_type,
                errors=["No DICOM paths or folder were provided."],
                study_uid=request.study_uid,
                series_uid=request.series_uid,
                modality=request.modality,
                pylinac_version=py_ver,
                pylinac_analysis_profile=profile,
            )

        if not vanilla:
            analyzer._scan_extent_tolerance_mm = eff_tol

        if DEBUG_PYLINAC_QA and analyzer is not None:
            for ln in _acr_ct_stack_diagnostic_lines(analyzer):
                print(f"[DEBUG-PYLINAC-QA] {ln}")

        analyze_kwargs: Dict[str, Any] = {}
        if request.origin_slice is not None:
            analyze_kwargs["origin_slice"] = int(request.origin_slice)
        analyzer.analyze(**analyze_kwargs)

        raw: Dict[str, Any] = {}
        try:
            rd = analyzer.results_data()
            if isinstance(rd, dict):
                raw = _jsonable(rd)
            else:
                raw = {"results_data": _jsonable(rd)}
        except Exception:
            raw = {}

        pdf_report_path: Optional[str] = None
        if request.output_pdf_path:
            try:
                analyzer.publish_pdf(request.output_pdf_path)
                pdf_report_path = request.output_pdf_path
            except Exception:
                pdf_report_path = None

        num_images = _image_count(analyzer, request)
        metrics: Dict[str, Any] = {
            "input_count": len(request.dicom_paths),
            "origin_slice_override": request.origin_slice,
            "scan_extent_tolerance_mm": eff_tol,
            "vanilla_pylinac": vanilla,
        }
        if warn_ignore_tol:
            metrics["scan_extent_tolerance_requested_mm"] = tol
        for key in ("num_images", "phantom_roll", "catphan_model", "origin_slice"):
            if key in raw:
                metrics[key] = raw[key]

        ct_warnings: List[str] = []
        if warn_ignore_tol:
            ct_warnings.append(
                "Scan extent tolerance is ignored in vanilla pylinac mode (stock ACRCT)."
            )

        return QAResult(
            success=True,
            analysis_type=request.analysis_type,
            metrics=metrics,
            warnings=ct_warnings,
            errors=[],
            raw_pylinac=raw,
            pdf_report_path=pdf_report_path,
            study_uid=request.study_uid,
            series_uid=request.series_uid,
            modality=request.modality,
            num_images=num_images,
            pylinac_version=py_ver,
            pylinac_analysis_profile=profile,
        )
    except Exception as exc:
        err_text = f"ACR CT analysis failed: {exc}"
        msg = str(exc)
        if analyzer is not None and any(
            m in msg.lower() for m in _PYLINAC_IMAGE_INDEX_FAILURE_MARKERS
        ):
            extra = "\n".join(_acr_ct_stack_diagnostic_lines(analyzer))
            err_text = f"{err_text}\n\n{extra}"
        n_fail = len(request.dicom_paths)
        if analyzer is not None:
            try:
                n_fail = len(analyzer.dicom_stack)
            except Exception:
                pass
        return QAResult(
            success=False,
            analysis_type=request.analysis_type,
            errors=[err_text],
            study_uid=request.study_uid,
            series_uid=request.series_uid,
            modality=request.modality,
            num_images=n_fail,
            pylinac_version=py_ver,
            pylinac_analysis_profile=profile,
        )


# ---------------------------------------------------------------------------
# ACR MRI Large — single run
# ---------------------------------------------------------------------------


def run_acr_mri_large_analysis(request: QARequest) -> QAResult:
    """
    Run ACR MRI Large analysis through pylinac with normalized output.

    Always-on interpretation notes (MTF, low-contrast, circle colors, pylinac
    documentation links) are passed to publish_pdf via the ``notes`` argument.

    Args:
        request: Normalized request payload from UI/worker.

    Returns:
        QAResult with success/failure details and normalized payload.
    """
    try:
        from pylinac import ACRMRILarge  # type: ignore[import-not-found]
        import pylinac  # type: ignore[import-not-found]

        from qa.pylinac_extent_subclasses import ACRMRILargeForViewer
    except Exception:
        return _missing_pylinac_result(request)

    py_ver = getattr(pylinac, "__version__", None)
    tol = float(request.scan_extent_tolerance_mm or 0.0)
    vanilla = bool(getattr(request, "vanilla_pylinac", False))
    eff_tol = 0.0 if vanilla else tol
    warn_ignore_tol = vanilla and tol > 0.0
    mri_cls = ACRMRILarge if vanilla else ACRMRILargeForViewer
    engine = "ACRMRILarge" if vanilla else "ACRMRILargeForViewer"
    profile = build_pylinac_analysis_profile(request, engine=engine)

    lc_method = str(
        getattr(request, "low_contrast_method", DEFAULT_ACR_MRI_LOW_CONTRAST_METHOD)
        or DEFAULT_ACR_MRI_LOW_CONTRAST_METHOD
    )
    lc_vis = float(
        getattr(
            request,
            "low_contrast_visibility_threshold",
            DEFAULT_ACR_MRI_LOW_CONTRAST_VISIBILITY_THRESHOLD,
        )
        or DEFAULT_ACR_MRI_LOW_CONTRAST_VISIBILITY_THRESHOLD
    )
    lc_sanity = float(
        getattr(
            request,
            "low_contrast_visibility_sanity_multiplier",
            DEFAULT_ACR_MRI_LOW_CONTRAST_VISIBILITY_SANITY_MULTIPLIER,
        )
        or DEFAULT_ACR_MRI_LOW_CONTRAST_VISIBILITY_SANITY_MULTIPLIER
    )

    try:
        try:
            analyzer = _build_mri_analyzer(
                request,
                cls=mri_cls,
                extent_tol_mm=None if vanilla else eff_tol,
            )
        except ValueError as ve:
            return QAResult(
                success=False,
                analysis_type=request.analysis_type,
                errors=[str(ve)],
                study_uid=request.study_uid,
                series_uid=request.series_uid,
                modality=request.modality,
                pylinac_version=py_ver,
                pylinac_analysis_profile=profile,
            )

        analyze_kwargs = _build_mri_analyze_kwargs(
            analyzer, request, lc_method=lc_method, lc_vis=lc_vis, lc_sanity=lc_sanity
        )
        extra_warnings = list(_build_mri_extra_warnings(analyzer))
        if warn_ignore_tol:
            extra_warnings.append(
                "Scan extent tolerance is ignored in vanilla pylinac mode "
                "(stock ACRMRILarge)."
            )

        analyzer.analyze(**analyze_kwargs)

        # as_dict=True returns a plain dict (via pydantic model_dump_json + json.loads)
        # so raw_pylinac is always a proper serializable dict.
        raw: Dict[str, Any] = {}
        try:
            raw = _jsonable(analyzer.results_data(as_dict=True))
        except Exception:
            raw = {}

        pdf_report_path: Optional[str] = None
        if request.output_pdf_path:
            try:
                notes_lines = _build_mri_notes_lines()
                analyzer.publish_pdf(request.output_pdf_path, notes=notes_lines)
                pdf_report_path = request.output_pdf_path
            except Exception:
                pdf_report_path = None

        num_images = _image_count(analyzer, request)
        metrics: Dict[str, Any] = {
            "input_count": len(request.dicom_paths),
            "echo_number": request.echo_number,
            "check_uid": request.check_uid,
            "origin_slice_override": request.origin_slice,
            "scan_extent_tolerance_mm": eff_tol,
            "vanilla_pylinac": vanilla,
            "low_contrast_method": lc_method,
            "low_contrast_visibility_threshold": lc_vis,
            "low_contrast_visibility_sanity_multiplier": lc_sanity,
        }
        if warn_ignore_tol:
            metrics["scan_extent_tolerance_requested_mm"] = tol
        for key in (
            "num_images",
            "phantom_roll",
            "has_sagittal_module",
            "origin_slice",
        ):
            if key in raw:
                metrics[key] = raw[key]
        # Pull top-level low-contrast score for compare tables
        lc_score = _extract_lc_score(raw)
        if lc_score is not None:
            metrics["low_contrast_score"] = lc_score

        return QAResult(
            success=True,
            analysis_type=request.analysis_type,
            metrics=metrics,
            warnings=extra_warnings,
            errors=[],
            raw_pylinac=raw,
            pdf_report_path=pdf_report_path,
            study_uid=request.study_uid,
            series_uid=request.series_uid,
            modality=request.modality,
            num_images=num_images,
            pylinac_version=py_ver,
            pylinac_analysis_profile=profile,
        )
    except Exception as exc:
        return QAResult(
            success=False,
            analysis_type=request.analysis_type,
            errors=[f"ACR MRI Large analysis failed: {exc}"],
            study_uid=request.study_uid,
            series_uid=request.series_uid,
            modality=request.modality,
            num_images=len(request.dicom_paths),
            pylinac_version=py_ver,
            pylinac_analysis_profile=profile,
        )


def _extract_lc_score(raw: Dict[str, Any]) -> Optional[int]:
    """
    Best-effort extraction of the low-contrast score from raw pylinac output.

    When results_data(as_dict=True) is used the pydantic model is serialized
    via model_dump_json, so the field name is the pydantic field name:
    ``low_contrast_multi_slice_module``.  Legacy or future shapes may use
    ``low_contrast_multi_slice`` or a top-level ``low_contrast_score``.

    Args:
        raw: Plain dict from analyzer.results_data(as_dict=True).

    Returns:
        Integer score if found, else None.
    """
    # Top-level convenience key (older / future shape)
    if "low_contrast_score" in raw:
        try:
            return int(raw["low_contrast_score"])
        except (TypeError, ValueError):
            pass
    # Pydantic serialized shape from pylinac 3.42.0 (via as_dict=True)
    lc_multi = raw.get("low_contrast_multi_slice_module") or raw.get(
        "low_contrast_multi_slice"
    )
    if isinstance(lc_multi, dict) and "score" in lc_multi:
        try:
            return int(lc_multi["score"])
        except (TypeError, ValueError):
            pass
    return None


# ---------------------------------------------------------------------------
# ACR MRI Large — multi-run compare mode
# ---------------------------------------------------------------------------


def run_acr_mri_large_batch(
    base_request: QARequest,
    run_configs: List[LcRunConfig],
    *,
    app_version: str = "",
) -> MRIBatchResult:
    """
    Run ACR MRI Large analysis for each LcRunConfig in a compare-mode batch.

    The analyzer is re-instantiated for every run to guarantee independence
    (pylinac does not guarantee idempotent multiple analyze() calls on the
    same object).

    PDF output (when base_request.output_pdf_path is set):
        Each run writes a temporary pylinac PDF to a temp directory.
        After all runs finish, a viewer-authored summary page is prepended and
        all pages are merged into a single combined PDF via pypdf.  The temp
        files are cleaned up automatically.  The combined PDF path is stored
        in run_results[0].pdf_report_path.

    Args:
        base_request: A QARequest carrying DICOM source info, echo, check_uid,
            scan-extent tolerance, and origin_slice.  The low-contrast fields
            on base_request are IGNORED; each run_config provides its own.
        run_configs: 1–3 LcRunConfig entries in the order to run them.
        app_version: Application version string embedded in the summary PDF.

    Returns:
        MRIBatchResult with one QAResult per config, in the same order.
        run_results[0].pdf_report_path is the combined PDF path if PDF output
        was requested and succeeded, else None / empty string.
    """
    from dataclasses import replace as dc_replace

    try:
        from pylinac import ACRMRILarge  # type: ignore[import-not-found]
        import pylinac  # type: ignore[import-not-found]

        from qa.pylinac_extent_subclasses import ACRMRILargeForViewer
    except Exception:
        # pylinac missing — return a failed result for every config
        failed = _missing_pylinac_result(base_request)
        return MRIBatchResult(
            run_results=[failed for _ in run_configs],
            run_configs=list(run_configs),
        )

    py_ver = getattr(pylinac, "__version__", None)
    tol = float(base_request.scan_extent_tolerance_mm or 0.0)
    vanilla = bool(getattr(base_request, "vanilla_pylinac", False))
    eff_tol = 0.0 if vanilla else tol
    warn_ignore_tol = vanilla and tol > 0.0
    mri_cls = ACRMRILarge if vanilla else ACRMRILargeForViewer

    # Allocate a temp directory for per-run PDFs (used only when PDF output is requested)
    tmp_dir: Optional[Path] = None
    run_pdf_paths: List[Optional[Path]] = []
    if base_request.output_pdf_path:
        try:
            tmp_dir = Path(tempfile.mkdtemp(prefix="dicom_viewer_mri_compare_"))
        except Exception as exc:
            logger.warning("Could not create temp dir for compare PDFs: %s", exc)
            tmp_dir = None

    run_results: List[QAResult] = []
    for run_idx, cfg in enumerate(run_configs):
        # Build a per-run QARequest; PDF path is handled via temp files, not QARequest.
        per_run_request = dc_replace(
            base_request,
            low_contrast_method=cfg.low_contrast_method,
            low_contrast_visibility_threshold=cfg.low_contrast_visibility_threshold,
            low_contrast_visibility_sanity_multiplier=cfg.low_contrast_visibility_sanity_multiplier,
            output_pdf_path=None,  # temp PDFs written directly, not via QARequest
        )
        engine = "ACRMRILarge" if vanilla else "ACRMRILargeForViewer"
        profile = build_pylinac_analysis_profile(per_run_request, engine=engine)

        try:
            analyzer = _build_mri_analyzer(
                per_run_request,
                cls=mri_cls,
                extent_tol_mm=None if vanilla else eff_tol,
            )
        except ValueError as ve:
            run_results.append(
                QAResult(
                    success=False,
                    analysis_type=base_request.analysis_type,
                    errors=[str(ve)],
                    study_uid=base_request.study_uid,
                    series_uid=base_request.series_uid,
                    modality=base_request.modality,
                    pylinac_version=py_ver,
                    pylinac_analysis_profile=profile,
                )
            )
            run_pdf_paths.append(None)
            continue

        analyze_kwargs = _build_mri_analyze_kwargs(
            analyzer,
            per_run_request,
            lc_method=cfg.low_contrast_method,
            lc_vis=cfg.low_contrast_visibility_threshold,
            lc_sanity=cfg.low_contrast_visibility_sanity_multiplier,
        )
        extra_warnings = list(_build_mri_extra_warnings(analyzer))
        if warn_ignore_tol:
            extra_warnings.append(
                "Scan extent tolerance is ignored in vanilla pylinac mode "
                "(stock ACRMRILarge)."
            )

        try:
            analyzer.analyze(**analyze_kwargs)

            raw: Dict[str, Any] = {}
            try:
                raw = _jsonable(analyzer.results_data(as_dict=True))
            except Exception:
                raw = {}

            # Write a temp PDF for this run (merged later into the combined PDF)
            run_pdf: Optional[Path] = None
            if tmp_dir is not None:
                temp_path = tmp_dir / f"run{run_idx + 1}.pdf"
                run_pdf = _write_per_run_temp_pdf(
                    analyzer, temp_path, cfg.label, cfg
                )
            run_pdf_paths.append(run_pdf)

            num_images = _image_count(analyzer, per_run_request)
            metrics: Dict[str, Any] = {
                "input_count": len(per_run_request.dicom_paths),
                "echo_number": per_run_request.echo_number,
                "check_uid": per_run_request.check_uid,
                "origin_slice_override": per_run_request.origin_slice,
                "scan_extent_tolerance_mm": eff_tol,
                "vanilla_pylinac": vanilla,
                "low_contrast_method": cfg.low_contrast_method,
                "low_contrast_visibility_threshold": cfg.low_contrast_visibility_threshold,
                "low_contrast_visibility_sanity_multiplier": cfg.low_contrast_visibility_sanity_multiplier,
                "run_label": cfg.label,
            }
            if warn_ignore_tol:
                metrics["scan_extent_tolerance_requested_mm"] = tol
            for key in (
                "num_images",
                "phantom_roll",
                "has_sagittal_module",
                "origin_slice",
            ):
                if key in raw:
                    metrics[key] = raw[key]
            lc_score = _extract_lc_score(raw)
            if lc_score is not None:
                metrics["low_contrast_score"] = lc_score

            run_results.append(
                QAResult(
                    success=True,
                    analysis_type=per_run_request.analysis_type,
                    metrics=metrics,
                    warnings=extra_warnings,
                    errors=[],
                    raw_pylinac=raw,
                    pdf_report_path=None,  # set on run_results[0] after merge
                    study_uid=per_run_request.study_uid,
                    series_uid=per_run_request.series_uid,
                    modality=per_run_request.modality,
                    num_images=num_images,
                    pylinac_version=py_ver,
                    pylinac_analysis_profile=profile,
                )
            )
        except Exception as exc:
            run_results.append(
                QAResult(
                    success=False,
                    analysis_type=per_run_request.analysis_type,
                    errors=[f"ACR MRI Large batch run ({cfg.label}) failed: {exc}"],
                    study_uid=per_run_request.study_uid,
                    series_uid=per_run_request.series_uid,
                    modality=per_run_request.modality,
                    num_images=len(per_run_request.dicom_paths),
                    pylinac_version=py_ver,
                    pylinac_analysis_profile=profile,
                )
            )
            run_pdf_paths.append(None)

    batch = MRIBatchResult(run_results=run_results, run_configs=list(run_configs))

    # Assemble combined PDF: [summary page] + [run0.pdf] + [run1.pdf] + ...
    final_pdf_path: Optional[str] = None
    if base_request.output_pdf_path and tmp_dir is not None:
        try:
            summary_path = tmp_dir / "summary.pdf"
            build_mri_compare_summary_pdf(
                batch,
                summary_path,
                base_request=base_request,
                app_version=app_version,
            )
            output_path = Path(base_request.output_pdf_path)
            ok = assemble_mri_compare_pdf(summary_path, run_pdf_paths, output_path)
            if ok:
                final_pdf_path = str(output_path)
        except Exception as exc:
            logger.error("compare PDF assembly failed: %s", exc)
        finally:
            # Clean up temp dir regardless of success
            try:
                shutil.rmtree(tmp_dir, ignore_errors=True)
            except Exception:
                pass

    # Store combined PDF path on the first run result
    if run_results and final_pdf_path:
        run_results[0].pdf_report_path = final_pdf_path

    return batch
