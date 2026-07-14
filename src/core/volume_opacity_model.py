"""
Volume opacity perception model.

Maps a UI slider position to a *resolved* global opacity using a perceptual
(power-law) response so that the low-opacity range — where small changes are
visually meaningful for faint structures — occupies a large share of the
slider travel, while the high-opacity range — where the volume already
saturates and 30% vs 75% look similar — is compressed.

The mapping is pure (no VTK / Qt) so it can be unit-tested in isolation.

Relationship between quantities:
    s = slider_value / SLIDER_MAX        (normalised position in [0, 1])
    opacity = s ** OPACITY_GAMMA          (resolved opacity in [0, 1])

With ``OPACITY_GAMMA = 2.5`` the bottom ~10% of resolved opacity occupies
roughly the bottom 40% of the slider, giving fine control where it matters.

Inputs:
    - Integer slider values in ``[0, SLIDER_MAX]``.
    - Resolved opacity floats in ``[0.0, 1.0]`` (e.g. from saved presets).

Outputs:
    - Resolved opacity floats and slider integers, plus display helpers.
"""

from __future__ import annotations

# Slider resolution.  1000 steps gives sub-0.1% precision at the low end
# once the perceptual curve is applied.
SLIDER_MAX: int = 1000

# Perceptual exponent.  > 1 redistributes slider travel toward low opacity.
OPACITY_GAMMA: float = 2.5


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def slider_to_opacity(slider_value: int) -> float:
    """
    Convert an integer slider position to a resolved opacity in ``[0, 1]``.

    Monotonically increasing.  ``0 -> 0.0`` and ``SLIDER_MAX -> 1.0``.

    Args:
        slider_value: Slider position in ``[0, SLIDER_MAX]`` (clamped).

    Returns:
        Resolved opacity in ``[0.0, 1.0]``.
    """
    s = _clamp(float(slider_value) / SLIDER_MAX, 0.0, 1.0)
    return s ** OPACITY_GAMMA


def opacity_to_slider(opacity: float) -> int:
    """
    Convert a resolved opacity in ``[0, 1]`` to the nearest slider position.

    Inverse of :func:`slider_to_opacity` (within integer rounding).

    Args:
        opacity: Resolved opacity in ``[0.0, 1.0]`` (clamped).

    Returns:
        Slider position in ``[0, SLIDER_MAX]``.
    """
    o = _clamp(opacity, 0.0, 1.0)
    s = o ** (1.0 / OPACITY_GAMMA)
    return int(round(s * SLIDER_MAX))


def percent_to_opacity(percent: float) -> float:
    """Convert a 0-100 resolved-percent value to a 0-1 opacity (clamped)."""
    return _clamp(float(percent) / 100.0, 0.0, 1.0)


def opacity_to_percent(opacity: float) -> float:
    """Convert a 0-1 resolved opacity to a 0-100 percent value (clamped)."""
    return _clamp(opacity, 0.0, 1.0) * 100.0


def format_opacity_percent(opacity: float) -> str:
    """
    Format a resolved opacity for display.

    Uses one decimal place below 10% so fine low-opacity steps are visible,
    and whole percents above 10% where the extra precision is not useful.
    """
    pct = opacity_to_percent(opacity)
    if pct < 10.0:
        return f"{pct:.1f}%"
    return f"{pct:.0f}%"


# --- Opacity-response (contrast-depth) mapping -----------------------------
# A 0..100 slider with the midpoint as the neutral gamma of 1.0 (preset curve
# unchanged); the lower half eases toward 0.4 (reveal faint material) and the
# upper half toward 3.0 (deepen contrast).
RESPONSE_NEUTRAL: int = 50
RESPONSE_GAMMA_MIN: float = 0.4
RESPONSE_GAMMA_MAX: float = 3.0


def response_to_gamma(value: int) -> float:
    """Map a 0..100 contrast-depth slider value to an opacity-response gamma.

    Returns ``RESPONSE_GAMMA_MIN`` at 0, ``1.0`` at the neutral midpoint, and
    ``RESPONSE_GAMMA_MAX`` at 100 (piecewise-linear); input is clamped to 0..100.
    """
    v = max(0, min(100, value))
    if v <= RESPONSE_NEUTRAL:
        frac = v / RESPONSE_NEUTRAL  # 0 -> min, 1 -> 1.0
        return RESPONSE_GAMMA_MIN + frac * (1.0 - RESPONSE_GAMMA_MIN)
    frac = (v - RESPONSE_NEUTRAL) / (100 - RESPONSE_NEUTRAL)  # 0 -> 1.0, 1 -> max
    return 1.0 + frac * (RESPONSE_GAMMA_MAX - 1.0)
