"""
Display look-up tables applied after window/level and after net inversion.

The display composition is ``final(x) = LUT(P_inv(u))`` with
``u = uint8(WL(x))`` from truncating ``astype(np.uint8)``. ``P_inv`` (MONOCHROME1
XOR the pane invert flag) is applied by the display path before this module.
``apply_lut_to_uint8`` is the only call those paths should make.
``apply_window_level`` stays window/level only and must not grow a ``lut``
argument: it runs before polarity, so a LUT there would invert the order.

``apply_lut`` is a test and one-shot wrapper. It windows (or normalizes) and
then calls ``apply_lut_to_uint8``. It does not apply photometric polarity.

Built-in transfer functions are marker callables stored on ``transfer_fn``.
Sampling compares them by identity and reads ``gamma``, ``sigmoid_k``, and
``exp_k`` from the LUT at sample time, so ``dataclasses.replace`` updates a
parameter without rebuilding a closure. A slider replaces the LUT; it does
not assign into a frozen instance.

The ``[0, 1]`` to ``[0, 255]`` scale uses ``np.rint``. Truncating ``astype``
misses 50 inverse-LUT codes. Identity truncates exactly, so a gamma of 1.0
cannot catch that bug.

Inputs:
    - Frozen ``LookUpTable`` values, uint8 display arrays, raw pixel arrays,
      optional window/level and rescale parameters

Outputs:
    - uint8 ``(H, W)`` grayscale or uint8 ``(H, W, 3)`` colormap arrays
    - Normalized ``y = f(x)`` samples for the transfer-function display

Requirements:
    - numpy
    - core.lut_curve (control-point interpolation)
    - core.dicom_window_level.apply_window_level
    - core.display_normalize.normalize_to_uint8
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

import numpy as np

from core.dicom_window_level import apply_window_level
from core.display_normalize import normalize_to_uint8
from core.lut_curve import CATMULL_ROM, clamp_unit_interval, evaluate_univariate

LutType = Literal["grayscale_ramp", "colormap"]
Interpolation = Literal["linear", "monotone_cubic", "catmull_rom"]
LutSource = Literal["built_in", "dicom", "file", "custom"]
TransferFn = Callable[[float], np.ndarray]

_GAMMA_MIN = 0.1
_GAMMA_MAX = 5.0
_EXP_MIN = 0.1
_EXP_MAX = 5.0


def linear_transfer(_x: float) -> np.ndarray:
    """Marker for the linear ramp. ``lut_engine`` reads no extra parameter."""
    raise RuntimeError("sample linear LUTs through lut_engine, not the marker")


def sigmoid_transfer(_x: float) -> np.ndarray:
    """Marker for the renormalized sigmoid. Steepness is ``LookUpTable.sigmoid_k``."""
    raise RuntimeError("sample sigmoid LUTs through lut_engine, not the marker")


def logarithmic_transfer(_x: float) -> np.ndarray:
    """Marker for ``log(1 + x) / log(2)``."""
    raise RuntimeError("sample logarithmic LUTs through lut_engine, not the marker")


def exponential_transfer(_x: float) -> np.ndarray:
    """Marker for the affine exponential. The rate is ``LookUpTable.exp_k``."""
    raise RuntimeError("sample exponential LUTs through lut_engine, not the marker")


def gamma_transfer(_x: float) -> np.ndarray:
    """Marker for ``x ** gamma``. The exponent is ``LookUpTable.gamma``."""
    raise RuntimeError("sample gamma LUTs through lut_engine, not the marker")


def inverse_transfer(_x: float) -> np.ndarray:
    """Marker for ``1 - x`` on normalized input (not ``255 - x``)."""
    raise RuntimeError("sample inverse LUTs through lut_engine, not the marker")


_BUILTIN_MARKERS = (
    linear_transfer,
    sigmoid_transfer,
    logarithmic_transfer,
    exponential_transfer,
    gamma_transfer,
    inverse_transfer,
)


@dataclass(frozen=True, eq=False)
class LookUpTable:
    """Immutable display LUT shared across panes.

    ``__post_init__`` sorts control points, rejects duplicate or out-of-range
    ``x``, and clamps ``y`` to ``[0, 1]``. The dataclass is frozen, so that
    normalization is written with ``object.__setattr__`` (plain assignment
    raises ``FrozenInstanceError``).
    """

    name: str
    lut_type: LutType = "grayscale_ramp"
    source: LutSource = "built_in"
    transfer_fn: TransferFn | None = None
    colormap: np.ndarray | None = None  # (256, 3) uint8 for color LUTs
    control_points: tuple[tuple[float, float], ...] | None = None
    interpolation: Interpolation = "linear"
    gamma: float | None = None  # 0.1–5.0, used when transfer_fn is gamma
    sigmoid_k: float | None = None  # steepness > 0, used when transfer_fn is sigmoid
    exp_k: float = 1.0  # 0.1–5.0, used when transfer_fn is exponential

    def __post_init__(self) -> None:
        """Validate fields and normalize control points via ``object.__setattr__``.

        Frozen instances reject ordinary assignment, including here, so the
        sorted and y-clamped control points and the write-protected colormap
        copy are stored with ``object.__setattr__``.
        """
        object.__setattr__(  # privacy-check: allow[structural-event-private-mutation] review=kgrizz-git
            self,
            "control_points",
            _normalized_control_points(self.control_points),
        )
        object.__setattr__(  # privacy-check: allow[structural-event-private-mutation] review=kgrizz-git
            self,
            "colormap",
            _frozen_colormap(self.colormap, self.lut_type),
        )
        _validate_parameters(self)

    def __eq__(self, other: object) -> bool:
        """Field equality. Colormap arrays compare by value, markers by identity."""
        if not isinstance(other, LookUpTable):
            return NotImplemented
        return _fields_equal(self, other)

    def __hash__(self) -> int:
        """Hash of the fields ``__eq__`` compares, so equal LUTs hash equal.

        The colormap is hashed from its bytes because a bare ``ndarray`` is
        unhashable; the shape is included so a reshape cannot collide.
        """
        return hash(
            (
                self.name,
                self.lut_type,
                self.source,
                self.transfer_fn,
                self.control_points,
                self.interpolation,
                self.gamma,
                self.sigmoid_k,
                self.exp_k,
                None if self.colormap is None else (self.colormap.shape, self.colormap.tobytes()),
            )
        )


def apply_lut_to_uint8(
    display_array: np.ndarray,
    lut: LookUpTable | None = None,
) -> np.ndarray:
    """Map an already windowed, polarity-corrected uint8 image through ``lut``.

    ``lut=None`` returns ``display_array`` unchanged (the same object). A
    grayscale ramp returns uint8 ``(H, W)``. A colormap returns uint8
    ``(H, W, 3)``.
    """
    if lut is None:
        return display_array
    _require_uint8_image(display_array)
    if lut.lut_type == "colormap":
        table = lut.colormap
        if table is None:
            raise ValueError(f"colormap LUT {lut.name!r} has no color table")
        return table[display_array]
    return _grayscale_bytes(lut)[display_array]


def apply_lut(
    pixel_array: np.ndarray,
    window_center: float | None,
    window_width: float | None,
    rescale_slope: float | None = None,
    rescale_intercept: float | None = None,
    *,
    lut: LookUpTable | None = None,
) -> np.ndarray:
    """Window or normalize raw pixels, then apply ``lut``. No polarity stage.

    Both window arguments must be set, or both must be ``None`` (min/max
    normalize, matching ``normalize_to_uint8``). Rescale is applied only when
    both slope and intercept are set, matching ``apply_window_level``.
    """
    display = _window_or_normalize(
        pixel_array,
        window_center,
        window_width,
        rescale_slope,
        rescale_intercept,
    )
    return apply_lut_to_uint8(display, lut)


def evaluate_lut(
    lut: LookUpTable,
    x: np.ndarray,
    *,
    clamp_overshoot: bool = True,
) -> np.ndarray:
    """Evaluate a grayscale LUT on normalized ``x`` in ``[0, 1]``.

    Control points win over ``transfer_fn`` when both are set, because the
    control-point list is the editable curve. Catmull–Rom samples are clamped
    to ``[0, 1]`` when ``clamp_overshoot`` is true. Other modes are not clamped
    to the first/last y span.
    """
    if lut.lut_type != "grayscale_ramp":
        raise ValueError(f"{lut.name!r} is a colormap and has no scalar curve")
    query = np.asarray(x, dtype=np.float64)
    if lut.control_points is not None:
        return _evaluate_control_points(lut, query, clamp_overshoot=clamp_overshoot)
    return _evaluate_transfer(lut, query)


def renormalized_sigmoid(x: np.ndarray, k: float) -> np.ndarray:
    """Endpoint-renormalized logistic on ``[0, 1]``, center 0.5.

    ``y = (s(x) - s(0)) / (s(1) - s(0))`` with ``s(t) = 1 / (1 + exp(-k * (t - 0.5)))``.
    Endpoints are 0 and 1. ``y(0.5)`` stays within ``1e-12`` of 0.5. The
    computation follows ``x``'s floating dtype so a large ``k`` stays finite
    in both float32 and float64. ``k`` must be ``> 0``.
    """
    if not math.isfinite(k) or k <= 0.0:
        raise ValueError(f"sigmoid_k must be finite and > 0, got {k!r}")
    values = np.asarray(x)
    if not np.issubdtype(values.dtype, np.floating):
        values = np.asarray(values, dtype=np.float64)
    dtype = values.dtype
    rate = np.asarray(k, dtype=dtype)
    half = np.asarray(0.5, dtype=dtype)
    curve = _logistic(rate * (values - half))
    start = _logistic(rate * np.asarray(-0.5, dtype=dtype))
    end = _logistic(rate * half)
    return (curve - start) / (end - start)


def _normalized_control_points(
    points: tuple[tuple[float, float], ...] | None,
) -> tuple[tuple[float, float], ...] | None:
    """Sort by x, reject duplicate or out-of-range x, and clamp y to ``[0, 1]``."""
    if points is None or len(points) == 0:
        return None
    parsed = [_parse_control_point(point) for point in points]
    parsed.sort(key=lambda item: item[0])
    _reject_bad_control_x(parsed)
    if len(parsed) < 2:
        raise ValueError("control_points need at least two points")
    return tuple((x, min(1.0, max(0.0, y))) for x, y in parsed)


def _parse_control_point(point: tuple[float, float]) -> tuple[float, float]:
    """Return one finite ``(x, y)`` pair."""
    try:
        x_raw, y_raw = point
    except (TypeError, ValueError) as exc:
        raise ValueError("control points must be (x, y) pairs") from exc
    x = float(x_raw)
    y = float(y_raw)
    if not math.isfinite(x) or not math.isfinite(y):
        raise ValueError("control points must be finite")
    return x, y


def _reject_bad_control_x(points: list[tuple[float, float]]) -> None:
    """Require x strictly increasing and inside ``[0, 1]``."""
    previous: float | None = None
    for x, _y in points:
        if x < 0.0 or x > 1.0:
            raise ValueError(f"control point x must be in [0, 1], got {x}")
        if previous is not None and x == previous:
            raise ValueError(f"duplicate control point x={x}")
        previous = x


def _frozen_colormap(colormap: np.ndarray | None, lut_type: LutType) -> np.ndarray | None:
    """Require ``(256, 3)`` uint8 for colormap LUTs and return a read-only copy."""
    if lut_type == "colormap":
        if colormap is None:
            raise ValueError("colormap LUTs require a (256, 3) uint8 colormap")
        return _copy_colormap(colormap)
    if colormap is not None:
        raise ValueError("colormap arrays require lut_type 'colormap'")
    return None


def _copy_colormap(colormap: np.ndarray) -> np.ndarray:
    """Copy a ``(256, 3)`` uint8 table and mark it read-only."""
    array = np.asarray(colormap)
    if array.shape != (256, 3) or array.dtype != np.uint8:
        raise ValueError(
            f"colormap must have shape (256, 3) and dtype uint8, got {array.shape} {array.dtype}"
        )
    frozen = np.array(array, dtype=np.uint8, copy=True)
    frozen.setflags(write=False)
    return frozen


def _validate_parameters(lut: LookUpTable) -> None:
    """Check exp_k always, and gamma / sigmoid_k only when that marker is selected."""
    if not _in_closed_range(lut.exp_k, _EXP_MIN, _EXP_MAX):
        raise ValueError(f"exp_k must be in [{_EXP_MIN}, {_EXP_MAX}], got {lut.exp_k!r}")
    _validate_gamma(lut)
    _validate_sigmoid(lut)
    if lut.interpolation not in ("linear", "monotone_cubic", "catmull_rom"):
        raise ValueError(f"unknown interpolation {lut.interpolation!r}")


def _validate_gamma(lut: LookUpTable) -> None:
    """Gamma applies only to the gamma marker, and then only inside ``[0.1, 5.0]``."""
    if lut.transfer_fn is gamma_transfer:
        if lut.gamma is None or not _in_closed_range(lut.gamma, _GAMMA_MIN, _GAMMA_MAX):
            raise ValueError(f"gamma must be in [{_GAMMA_MIN}, {_GAMMA_MAX}], got {lut.gamma!r}")
        return
    if lut.gamma is not None:
        raise ValueError("gamma is only valid when transfer_fn is gamma_transfer")


def _validate_sigmoid(lut: LookUpTable) -> None:
    """Sigmoid steepness applies only to the sigmoid marker, and must be ``> 0``."""
    if lut.transfer_fn is sigmoid_transfer:
        if lut.sigmoid_k is None or not math.isfinite(lut.sigmoid_k) or lut.sigmoid_k <= 0.0:
            raise ValueError(f"sigmoid_k must be finite and > 0, got {lut.sigmoid_k!r}")
        return
    if lut.sigmoid_k is not None:
        raise ValueError("sigmoid_k is only valid when transfer_fn is sigmoid_transfer")


def _in_closed_range(value: float, low: float, high: float) -> bool:
    """True when ``value`` is finite and inside ``[low, high]``."""
    return math.isfinite(value) and low <= value <= high


def _fields_equal(left: LookUpTable, right: LookUpTable) -> bool:
    """Compare two LUTs without using ``ndarray`` truth values."""
    return (
        left.name == right.name
        and left.lut_type == right.lut_type
        and left.source == right.source
        and left.transfer_fn is right.transfer_fn
        and left.control_points == right.control_points
        and left.interpolation == right.interpolation
        and left.gamma == right.gamma
        and left.sigmoid_k == right.sigmoid_k
        and left.exp_k == right.exp_k
        and _colormap_equal(left.colormap, right.colormap)
    )


def _colormap_equal(left: np.ndarray | None, right: np.ndarray | None) -> bool:
    """Compare optional colormap tables by shape and values."""
    if left is None or right is None:
        return left is None and right is None
    return left.shape == right.shape and np.array_equal(left, right)


def _require_uint8_image(display_array: np.ndarray) -> None:
    """Reject anything other than a 2-D uint8 image. ``lut=None`` skips this."""
    if display_array.dtype != np.uint8 or display_array.ndim != 2:
        raise TypeError(
            "apply_lut_to_uint8 expects a 2-D uint8 image "
            f"(got ndim={display_array.ndim}, dtype={display_array.dtype})"
        )


def _window_or_normalize(
    pixel_array: np.ndarray,
    window_center: float | None,
    window_width: float | None,
    rescale_slope: float | None,
    rescale_intercept: float | None,
) -> np.ndarray:
    """Match today's window path, or min/max normalize when no window is set."""
    if window_center is None and window_width is None:
        return normalize_to_uint8(
            _rescale_if_requested(pixel_array, rescale_slope, rescale_intercept)
        )
    if window_center is None or window_width is None:
        raise ValueError("window_center and window_width must both be set or both be None")
    return apply_window_level(
        pixel_array,
        window_center,
        window_width,
        rescale_slope,
        rescale_intercept,
    )


def _rescale_if_requested(
    pixel_array: np.ndarray,
    rescale_slope: float | None,
    rescale_intercept: float | None,
) -> np.ndarray:
    """Apply slope and intercept only when both are present."""
    if rescale_slope is None and rescale_intercept is None:
        return pixel_array
    if rescale_slope is None or rescale_intercept is None:
        raise ValueError("rescale_slope and rescale_intercept must both be set or both be None")
    return np.asarray(pixel_array, dtype=np.float64) * rescale_slope + rescale_intercept


def _grayscale_bytes(lut: LookUpTable) -> np.ndarray:
    """Sample the grayscale curve at ``i / 255`` and round to uint8."""
    xs = np.arange(256, dtype=np.float64) / 255.0
    values = evaluate_lut(lut, xs, clamp_overshoot=True)
    return np.clip(np.rint(values * 255.0), 0, 255).astype(np.uint8)


def _evaluate_control_points(
    lut: LookUpTable,
    query: np.ndarray,
    *,
    clamp_overshoot: bool,
) -> np.ndarray:
    """Sample stored control points. Clamp only Catmull–Rom, and only to ``[0, 1]``."""
    points = lut.control_points
    if points is None:
        raise ValueError("control point evaluation requires control_points")
    xs = np.array([point[0] for point in points], dtype=np.float64)
    ys = np.array([point[1] for point in points], dtype=np.float64)
    sampled = evaluate_univariate(xs, ys, query, lut.interpolation)
    if clamp_overshoot and lut.interpolation == CATMULL_ROM:
        return clamp_unit_interval(sampled)
    return sampled


def _evaluate_transfer(lut: LookUpTable, query: np.ndarray) -> np.ndarray:
    """Dispatch a built-in marker, reading parameters from ``lut`` now."""
    transfer = lut.transfer_fn
    if transfer is None or transfer is linear_transfer:
        return query
    if transfer is gamma_transfer:
        return _gamma_curve(query, lut.gamma)
    if transfer is sigmoid_transfer:
        return np.asarray(renormalized_sigmoid(query, _required_sigmoid_k(lut)), dtype=np.float64)
    if transfer is logarithmic_transfer:
        return np.log1p(query) / np.log(2.0)
    if transfer is exponential_transfer:
        return np.expm1(lut.exp_k * query) / np.expm1(lut.exp_k)
    if transfer is inverse_transfer:
        return 1.0 - query
    return _sample_custom_transfer(transfer, query)


def _gamma_curve(query: np.ndarray, gamma: float | None) -> np.ndarray:
    """``x ** gamma``. Gamma 1 is the identity so it stays byte-identical to linear."""
    if gamma is None:
        raise ValueError("gamma LUT is missing gamma")
    return np.power(query, gamma)


def _required_sigmoid_k(lut: LookUpTable) -> float:
    """Return the sigmoid steepness stored on ``lut``."""
    if lut.sigmoid_k is None:
        raise ValueError("sigmoid LUT is missing sigmoid_k")
    return lut.sigmoid_k


def _sample_custom_transfer(transfer: TransferFn, query: np.ndarray) -> np.ndarray:
    """Call a non-marker ``transfer_fn`` once per normalized sample."""
    if transfer in _BUILTIN_MARKERS:
        raise RuntimeError(f"unhandled built-in marker {transfer.__name__}")
    flat = query.reshape(-1)
    out = np.empty(flat.shape, dtype=np.float64)
    for index, value in enumerate(flat):
        sampled = np.asarray(transfer(float(value)), dtype=np.float64).reshape(-1)
        out[index] = float(sampled[0])
    return out.reshape(query.shape)


def _logistic(z: np.ndarray) -> np.ndarray:
    """Stable ``1 / (1 + exp(-z))`` in ``z``'s dtype, including large ``|z|``."""
    flat = np.atleast_1d(np.asarray(z))
    out = np.empty(flat.shape, dtype=flat.dtype)
    positive = flat >= 0
    negative = ~positive
    with np.errstate(over="ignore", invalid="ignore"):
        out[positive] = 1.0 / (1.0 + np.exp(-flat[positive]))
        exp_z = np.exp(flat[negative])
        out[negative] = exp_z / (1.0 + exp_z)
    return out.reshape(np.shape(z))
