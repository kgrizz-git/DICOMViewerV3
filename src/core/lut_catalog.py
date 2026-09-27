"""
Built-in grayscale LUTs and matplotlib colormap LUTs.

Grayscale entries store a marker on ``transfer_fn`` plus the parameter fields
the engine reads at sample time. Colormap entries are pre-sampled ``(256, 3)``
uint8 tables. Matplotlib lookup goes through ``fusion_processor``'s cache so
the app has one colormap cache and one ``matplotlib.colormaps.get_cmap`` path.

Registry keys are lowercase. ``gray`` is the grayscale map; ``Gray``, ``Greys``,
and any other title-case name are rejected.

Inputs:
    - Built-in curve name and optional gamma / sigmoid_k / exp_k
    - Lowercase matplotlib colormap name from the display set

Outputs:
    - Frozen ``LookUpTable`` instances

Requirements:
    - numpy
    - matplotlib (via ``core.fusion_processor.cached_matplotlib_colormap``)
    - core.lut_engine
"""

from __future__ import annotations

from dataclasses import replace

import numpy as np

from core.fusion_processor import cached_matplotlib_colormap
from core.lut_engine import (
    LookUpTable,
    exponential_transfer,
    gamma_transfer,
    inverse_transfer,
    linear_transfer,
    logarithmic_transfer,
    sigmoid_transfer,
)

# Lowercase matplotlib names only. ``gray`` is not ``Greys``.
DISPLAY_COLORMAP_NAMES: tuple[str, ...] = (
    "hot",
    "cool",
    "jet",
    "rainbow",
    "bone",
    "gray",
    "viridis",
    "magma",
    "inferno",
    "plasma",
    "turbo",
)

_DEFAULT_SIGMOID_K = 1.0
_DEFAULT_GAMMA = 1.0
_DEFAULT_EXP_K = 1.0

_COLORMAP_LUTS: dict[str, LookUpTable] = {}


def linear_lut() -> LookUpTable:
    """Identity ramp. Matches ``apply_window_level`` byte for byte."""
    return LookUpTable(name="Linear", transfer_fn=linear_transfer)


def sigmoid_lut(k: float = _DEFAULT_SIGMOID_K) -> LookUpTable:
    """Renormalized logistic. ``k`` is steepness and is only required to be ``> 0``."""
    return LookUpTable(name="Sigmoid", transfer_fn=sigmoid_transfer, sigmoid_k=k)


def logarithmic_lut() -> LookUpTable:
    """``log(1 + x) / log(2)`` on normalized ``[0, 1]``."""
    return LookUpTable(name="Logarithmic", transfer_fn=logarithmic_transfer)


def exponential_lut(k: float = _DEFAULT_EXP_K) -> LookUpTable:
    """Affine exponential ``(exp(k x) - 1) / (exp(k) - 1)``. ``k`` is in ``[0.1, 5.0]``."""
    return LookUpTable(name="Exponential", transfer_fn=exponential_transfer, exp_k=k)


def gamma_lut(gamma: float = _DEFAULT_GAMMA) -> LookUpTable:
    """Power curve ``x ** gamma``. ``gamma`` is in ``[0.1, 5.0]``; 1.0 matches linear."""
    return LookUpTable(name="Gamma", transfer_fn=gamma_transfer, gamma=gamma)


def inverse_lut() -> LookUpTable:
    """Normalized complement ``1 - x``, which rounds to ``255 - i`` at every code."""
    return LookUpTable(name="Inverse", transfer_fn=inverse_transfer)


def builtin_grayscale_luts() -> dict[str, LookUpTable]:
    """Return the default built-in grayscale LUTs keyed by stable lowercase id."""
    return {
        "linear": linear_lut(),
        "sigmoid": sigmoid_lut(),
        "logarithmic": logarithmic_lut(),
        "exponential": exponential_lut(),
        "gamma": gamma_lut(),
        "inverse": inverse_lut(),
    }


def replace_gamma(lut: LookUpTable, gamma: float) -> LookUpTable:
    """Return a new gamma LUT with ``gamma`` updated. The original is unchanged."""
    if lut.transfer_fn is not gamma_transfer:
        raise ValueError("replace_gamma requires a gamma LUT")
    return replace(lut, gamma=gamma)


def replace_sigmoid_k(lut: LookUpTable, k: float) -> LookUpTable:
    """Return a new sigmoid LUT with steepness ``k``. The original is unchanged."""
    if lut.transfer_fn is not sigmoid_transfer:
        raise ValueError("replace_sigmoid_k requires a sigmoid LUT")
    return replace(lut, sigmoid_k=k)


def replace_exp_k(lut: LookUpTable, k: float) -> LookUpTable:
    """Return a new exponential LUT with rate ``k``. The original is unchanged."""
    if lut.transfer_fn is not exponential_transfer:
        raise ValueError("replace_exp_k requires an exponential LUT")
    return replace(lut, exp_k=k)


def colormap_lut(name: str) -> LookUpTable:
    """Return the built-in colormap LUT for a lowercase display name.

    The ``(256, 3)`` table is ``(cmap(linspace(0, 1, 256))[:, :3] * 255).astype(uint8)``,
    which matches ``cmap(..., bytes=True)`` for these maps. Instances are cached
    for the process; the matplotlib colormap itself lives in the fusion cache.
    """
    _require_display_colormap_name(name)
    cached = _COLORMAP_LUTS.get(name)
    if cached is not None:
        return cached
    built = LookUpTable(
        name=name,
        lut_type="colormap",
        source="built_in",
        colormap=_sample_colormap(name),
    )
    _COLORMAP_LUTS[name] = built
    return built


def clear_colormap_lut_cache() -> None:
    """Drop cached colormap ``LookUpTable`` instances. The fusion cache is left alone."""
    _COLORMAP_LUTS.clear()


def _require_display_colormap_name(name: str) -> None:
    """Reject title case, ``Greys``, and any name outside the display set."""
    if name not in DISPLAY_COLORMAP_NAMES:
        raise ValueError(
            f"unknown display colormap {name!r}; use a lowercase name from {DISPLAY_COLORMAP_NAMES}"
        )


def _sample_colormap(name: str) -> np.ndarray:
    """Sample 256 RGB bytes from the shared matplotlib colormap cache."""
    cmap = cached_matplotlib_colormap(name)
    samples = cmap(np.linspace(0.0, 1.0, 256))[:, :3]
    return (samples * 255.0).astype(np.uint8)
