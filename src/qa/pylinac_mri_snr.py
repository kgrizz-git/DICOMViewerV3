"""
Harvest ACR-style uncorrected MRI SNR from a live pylinac ACR MRI analyzer.

pylinac 3.43.2 does not export SNR. The viewer computes one uncorrected ratio
on the **uniformity slice** (same module as PIU/PSG):

    mri_snr = S̄ / mean(σ of two frequency-encode ghost-free background ROIs)

Signal (S̄) is pylinac's existing **Center** disk ROI mean (``pixel_value``).
Noise is the mean of ``std`` on the two ``ghost_rois`` along the
**frequency-encode** axis. No NEMA 0.655 Rayleigh factor (OQ-10).

Inputs:
    A post-``analyze()`` ACRMRILarge (or viewer subclass) instance.

Outputs:
    A dict with ``mri_snr``, ``mri_snr_signal_mean``, ``mri_snr_noise_mean``,
    and audit keys for the noise ROI pair / phase-encode tag — or ``None``
    when ROIs are missing or noise is non-finite / zero.

Requirements:
    Qt-free. Never log PHI. Best-effort: harvest failure must not fail the run.
"""

from __future__ import annotations

import math
from typing import Any

# pylinac 3.43.2 ``ghost_rois`` keys are spatial (fixed phantom-centered
# angles): Top/Bottom = vertical; Left/Right = horizontal.
# DICOM ``InPlanePhaseEncodingDirection``:
#   ROW = phase along rows (left–right) → ghosts Left/Right → noise Top/Bottom
#   COL = phase along columns (top–bottom) → ghosts Top/Bottom → noise Left/Right
# Noise is the frequency-encode (ghost-free) pair. Fallback when the tag is
# missing is ROW / frequency COL (PMC8321175 §2.2) → Top/Bottom.
_FREQ_GHOST_PAIR_BY_PHASE: dict[str, tuple[str, str]] = {
    "ROW": ("Top", "Bottom"),
    "COL": ("Left", "Right"),
}
_FALLBACK_PHASE = "ROW"
_ALTERNATE_GHOST_PAIR: dict[tuple[str, str], tuple[str, str]] = {
    ("Top", "Bottom"): ("Left", "Right"),
    ("Left", "Right"): ("Top", "Bottom"),
}


def _as_float(value: object) -> float | None:
    """Coerce a ROI statistic to float; None on missing/non-numeric/non-finite."""
    if value is None or isinstance(value, bool):
        return None
    if not isinstance(value, (int, float, str)):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return number


def _roi_stat(roi: object, attr: str) -> float | None:
    """Read ``pixel_value`` / ``mean`` / ``std`` from a pylinac ROI object."""
    return _as_float(getattr(roi, attr, None))


def _center_signal_mean(uniformity_module: Any) -> float | None:
    """Mean of pylinac's Center disk ROI (pixel_value, then mean)."""
    rois = getattr(uniformity_module, "rois", None)
    if not isinstance(rois, dict):
        return None
    center = rois.get("Center")
    if center is None:
        return None
    signal = _roi_stat(center, "pixel_value")
    if signal is None:
        signal = _roi_stat(center, "mean")
    return signal


def _normalize_phase_encoding(raw: object) -> str | None:
    """Map DICOM InPlanePhaseEncodingDirection to ROW or COL."""
    if raw is None:
        return None
    text = str(raw).strip().upper()
    if text == "ROW":
        return "ROW"
    if text in {"COL", "COLUMN"}:
        return "COL"
    return None


def phase_encoding_direction_from_analyzer(analyzer: Any) -> tuple[str, bool]:
    """
    Return (ROW|COL, used_fallback).

    Reads ``dicom_stack.metadata.InPlanePhaseEncodingDirection``. Fallback when
    the tag is missing is phase=ROW / frequency=COL (PMC8321175 §2.2).
    """
    stack = getattr(analyzer, "dicom_stack", None)
    metadata = getattr(stack, "metadata", None) if stack is not None else None
    raw = getattr(metadata, "InPlanePhaseEncodingDirection", None)
    normalized = _normalize_phase_encoding(raw)
    if normalized is None:
        return _FALLBACK_PHASE, True
    return normalized, False


def frequency_encode_ghost_roi_names(phase: str) -> tuple[str, str]:
    """Ghost-ROI pair on the frequency-encode axis for *phase* (ROW or COL)."""
    return _FREQ_GHOST_PAIR_BY_PHASE.get(phase, _FREQ_GHOST_PAIR_BY_PHASE[_FALLBACK_PHASE])


def _mean_noise_std(uniformity_module: Any, names: tuple[str, str]) -> float | None:
    """Mean of pixel σ on the named ghost_rois."""
    ghosts = getattr(uniformity_module, "ghost_rois", None)
    if not isinstance(ghosts, dict):
        return None
    stds: list[float] = []
    for name in names:
        roi = ghosts.get(name)
        std = _roi_stat(roi, "std") if roi is not None else None
        if std is None:
            return None
        stds.append(std)
    if len(stds) != 2:
        return None
    return (stds[0] + stds[1]) / 2.0


def extract_mri_snr_acr_style(analyzer: Any) -> dict[str, Any] | None:
    """
    Compute uncorrected ACR-style SNR from the live uniformity module.

    Returns None when the analyzer has no usable Center / ghost ROIs or when
    the noise term is zero (avoid inf). Does not apply 0.655.
    """
    uniformity = getattr(analyzer, "uniformity_module", None)
    if uniformity is None:
        return None
    signal = _center_signal_mean(uniformity)
    if signal is None:
        return None
    phase, used_fallback = phase_encoding_direction_from_analyzer(analyzer)
    pair = frequency_encode_ghost_roi_names(phase)
    noise = _mean_noise_std(uniformity, pair)
    if noise is None or noise == 0.0:
        return None
    alternate = _ALTERNATE_GHOST_PAIR[pair]
    alternate_noise = _mean_noise_std(uniformity, alternate)
    return {
        "mri_snr": signal / noise,
        "mri_snr_signal_mean": signal,
        "mri_snr_noise_mean": noise,
        "mri_snr_noise_roi_pair": f"{pair[0]}/{pair[1]}",
        "mri_snr_phase_encoding_direction": phase,
        "mri_snr_phase_encoding_fallback": used_fallback,
        "mri_snr_selected_pair_noisier_than_alternate": (
            alternate_noise is not None and noise > alternate_noise
        ),
    }


def overlay_mri_snr_metrics(
    metrics: dict[str, Any],
    analyzer: Any,
    warnings: list[str] | None = None,
) -> None:
    """Merge SNR harvest into curated metrics when available.

    On harvest failure, append a single physicist-facing warning when
    *warnings* is provided. Never fails the run.
    """
    harvested = extract_mri_snr_acr_style(analyzer)
    if harvested:
        noisier = bool(
            harvested.pop("mri_snr_selected_pair_noisier_than_alternate", False)
        )
        metrics.update(harvested)
        if warnings is not None and noisier:
            warnings.append(
                "MRI SNR used the frequency-encode ghost-ROI pair from "
                "InPlanePhaseEncodingDirection, but the other pair had lower "
                "background σ. Confirm phase-encode axis vs Top/Bottom vs "
                "Left/Right placement."
            )
        return
    if warnings is not None:
        warnings.append(
            "MRI SNR not computed: missing Center or frequency-encode ghost "
            "ROIs, or background noise was zero."
        )
