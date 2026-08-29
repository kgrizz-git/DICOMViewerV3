"""
Capture pylinac per-module PNGs for the QA XLSX Images sheet (P2-I1).

``run_acr_ct_analysis`` and ``run_acr_mri_large_analysis`` share this helper so
the embed-on / mkdir / ``save_images`` / swallow-failure path cannot drift.

Inputs:
    - A live (or test-double) pylinac analyzer with ``save_images(directory=...)``.
    - ``QARequest`` with ``embed_module_images_in_xlsx`` and ``module_images_out_dir``.

Outputs:
    - Mapping of module stem → absolute PNG path. Empty when embed is off, the
      directory is unset, or save fails (never raises).

Requirements:
    - Use the ``list[Path]`` returned by pylinac 3.43.2 ``save_images``, not a
      directory glob, so leftover PNGs in a reused batch temp dir cannot leak
      into the next run (P2-I3).
"""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Any

from qa.analysis_types import QARequest


def capture_analyzed_module_images(analyzer: Any, request: QARequest) -> dict[str, str]:
    """
    Save per-module PNGs when embed is on and a module-images directory is set.

    Args:
        analyzer: Pylinac ACR analyzer after ``analyze()``.
        request: Run request; both embed flag and output dir must be set.

    Returns:
        Module label (file stem) to absolute PNG path. Empty dict on skip or
        failure so the analysis run itself still succeeds.
    """
    if not request.embed_module_images_in_xlsx or not request.module_images_out_dir:
        return {}
    out_dir = Path(request.module_images_out_dir)
    try:
        out_dir.mkdir(parents=True, exist_ok=True)
        saved = analyzer.save_images(directory=str(out_dir))
    except Exception:
        return {}
    images: dict[str, str] = {}
    for item in saved or []:
        if isinstance(item, BytesIO):
            continue
        path = Path(item)
        if path.suffix.lower() != ".png":
            continue
        images[path.stem] = str(path)
    return images


def save_composite_analyzed_image(analyzer: Any, request: QARequest) -> str | None:
    """
    Save the legacy CT composite PNG only when XLSX embed is on and modules are not.

    Skips when embed is off (the composite's only purpose is XLSX embedding,
    so toggle-off must not leave an embeddable image for the workbook),
    when embed is on and ``module_images_out_dir`` is set (even if
    ``capture_analyzed_module_images`` returned empty after a save failure),
    or when no output path is set. Swallows save errors so the analysis run
    still succeeds.

    Args:
        analyzer: Pylinac ACR CT analyzer after ``analyze()``.
        request: Run request with optional ``analyzed_image_out_path``.

    Returns:
        The composite path on success, otherwise ``None``.
    """
    if not request.embed_module_images_in_xlsx:
        return None
    if request.module_images_out_dir:
        return None
    if not request.analyzed_image_out_path:
        return None
    try:
        analyzer.save_analyzed_image(request.analyzed_image_out_path)
    except Exception:
        return None
    return request.analyzed_image_out_path

