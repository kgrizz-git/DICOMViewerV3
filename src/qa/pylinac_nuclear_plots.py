"""
Main-thread figure rendering for nuclear QC (pylinac.nuclear).

Kept separate from ``qa.pylinac_nuclear`` (the QThread worker runner) so that
matplotlib / pylinac plotting is never imported or invoked off the GUI thread.
pylinac's ``plot()`` builds figures via pyplot; under the app's Qt matplotlib
backend that creates Qt canvases, which must happen on the main thread.

``render_nuclear_figures`` re-runs the (fast) analysis and saves one PNG per
frame. It must be called from the main/GUI thread only.
"""

from __future__ import annotations

import os
from typing import Any

from utils.config.qa_nuclear_config import (
    CENTER_OF_ROTATION_CLASS,
    FOUR_BAR_RESOLUTION_CLASS,
    MAX_COUNT_RATE_CLASS,
    PLANAR_UNIFORMITY_CLASS,
    QUADRANT_RESOLUTION_CLASS,
    TOMOGRAPHIC_CONTRAST_CLASS,
    TOMOGRAPHIC_RESOLUTION_CLASS,
    TOMOGRAPHIC_UNIFORMITY_CLASS,
)

# pylinac.nuclear classes whose plot() we can render to PNG. The value is the
# attribute name on the pylinac.nuclear module (same as the class name).
# SimpleSensitivity is intentionally absent — it has no plot().
_PLOTTABLE_CLASSES = (
    PLANAR_UNIFORMITY_CLASS,
    FOUR_BAR_RESOLUTION_CLASS,
    QUADRANT_RESOLUTION_CLASS,
    CENTER_OF_ROTATION_CLASS,
    TOMOGRAPHIC_RESOLUTION_CLASS,
    MAX_COUNT_RATE_CLASS,
    TOMOGRAPHIC_UNIFORMITY_CLASS,
    TOMOGRAPHIC_CONTRAST_CLASS,
)


def is_plottable(analysis_class: str) -> bool:
    """True when the nuclear class exposes a plot() the viewer can render."""
    return analysis_class in _PLOTTABLE_CLASSES


def render_nuclear_figures(
    input_path: str,
    *,
    analysis_class: str,
    analyze_kwargs: dict[str, Any] | None = None,
    out_path: str,
) -> list[str]:
    """
    Re-run a nuclear analysis and save its per-frame plot(s) as PNG(s).

    MAIN THREAD ONLY (creates matplotlib/Qt figures).

    Args:
        input_path: DICOM file the analysis was run on.
        analysis_class: pylinac.nuclear class name (only PlanarUniformity today).
        analyze_kwargs: kwargs passed to ``analyze()`` (same as the original run).
        out_path: chosen save path. For a single frame the figure is saved here;
            for multiple frames ``_Frame_<key>`` is inserted before the suffix.

    Returns:
        List of written PNG paths.

    Raises:
        RuntimeError: pylinac missing, unsupported class, or no figures produced.
    """
    if analysis_class not in _PLOTTABLE_CLASSES:
        raise RuntimeError(
            f"Figure export is not supported for '{analysis_class}'."
        )
    try:
        import pylinac.nuclear as _nuclear  # type: ignore[import-not-found]
    except Exception as exc:  # pragma: no cover - exercised via dialog message
        raise RuntimeError(
            "pylinac is not installed. Install required dependencies and retry."
        ) from exc

    cls = getattr(_nuclear, analysis_class, None)
    if cls is None:
        raise RuntimeError(
            f"pylinac.nuclear has no class '{analysis_class}'."
        )

    import matplotlib.pyplot as plt

    analyzer = cls(input_path)
    analyzer.analyze(**(analyze_kwargs or {}))
    figs, _axes = analyzer.plot(show=False)
    if not figs:
        raise RuntimeError("pylinac produced no figures for this analysis.")

    # PlanarUniformity yields one figure per frame (label "Frame_<key>");
    # other classes (e.g. FourBar) yield multiple plot panels for one image
    # (label by panel index).
    frame_keys = list(getattr(analyzer, "frame_results", {}).keys())
    if frame_keys and len(frame_keys) == len(figs):
        labels = [f"Frame_{key}" for key in frame_keys]
    else:
        labels = [str(i) for i in range(1, len(figs) + 1)]

    base, ext = os.path.splitext(out_path)
    if not ext:
        ext = ".png"
    multi = len(figs) > 1

    saved: list[str] = []
    try:
        for fig, label in zip(figs, labels, strict=False):
            path = f"{base}_{label}{ext}" if multi else f"{base}{ext}"
            fig.savefig(path, bbox_inches="tight", dpi=150)
            saved.append(path)
    finally:
        for fig in figs:
            plt.close(fig)
    return saved
