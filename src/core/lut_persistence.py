"""
Serialize user LUTs to and from the ``custom_luts.json`` payload.

Schema version 2 adds ``color_stops`` / ``color_interpolation`` for editable
colormaps (Phase 4b). Version 1 files hold grayscale entries only and load
unchanged. A built-in curve kind is stored by name in ``transfer`` (for
example ``"gamma"``) so its parameter survives; a control-point curve stores
``control_points`` and ignores ``transfer``.

Loading is forgiving per entry: an unknown ``interpolation`` falls back to
``linear``, a missing or null ``exp_k`` becomes ``1.0``, and an entry that
still fails validation is skipped with a warning rather than aborting the load.
Built-in colormaps are not saved here; only LUTs a user made are. Every
saved entry loads with ``source='custom'``: it comes from the user's library,
even when it began as a built-in curve with a chosen parameter.

Inputs:
    - ``LookUpTable`` instances, or the decoded JSON payload

Outputs:
    - JSON-ready dicts, or ``LookUpTable`` instances

Requirements:
    - core.lut_engine
"""

from __future__ import annotations

import logging
from typing import Any

from core.lut_color_stops import COLOR_INTERPOLATIONS
from core.lut_engine import (
    LookUpTable,
    exponential_transfer,
    gamma_transfer,
    inverse_transfer,
    linear_transfer,
    logarithmic_transfer,
    sigmoid_transfer,
)

SCHEMA_VERSION = 2
_INTERPOLATIONS = ("linear", "monotone_cubic", "catmull_rom")
_TRANSFERS = {
    "linear": linear_transfer,
    "sigmoid": sigmoid_transfer,
    "logarithmic": logarithmic_transfer,
    "exponential": exponential_transfer,
    "gamma": gamma_transfer,
    "inverse": inverse_transfer,
}
_TRANSFER_NAMES: dict[Any, str] = {marker: name for name, marker in _TRANSFERS.items()}
_logger = logging.getLogger(__name__)


def lut_to_dict(lut: LookUpTable) -> dict[str, Any]:
    """JSON-ready dict for one LUT. Raises ``ValueError`` for an unsavable LUT.

    A colormap is savable only through its ``color_stops``: a sampled table
    with no stops is a built-in and is selected by name instead.
    """
    if lut.lut_type == "colormap" and lut.color_stops is None:
        raise ValueError(f"colormap {lut.name!r} has no color stops to save")
    transfer = None
    if lut.transfer_fn is not None:
        transfer = _TRANSFER_NAMES.get(lut.transfer_fn)
        if transfer is None:
            raise ValueError(f"{lut.name!r} uses a transfer function that cannot be saved")
    entry: dict[str, Any] = {
        "name": lut.name,
        "lut_type": lut.lut_type,
        "source": "custom",
        "interpolation": lut.interpolation,
        "transfer": transfer,
        "gamma": lut.gamma,
        "sigmoid_k": lut.sigmoid_k,
        "exp_k": lut.exp_k,
        "control_points": (
            None if lut.control_points is None else [[x, y] for x, y in lut.control_points]
        ),
    }
    if lut.color_stops is not None:
        entry["color_stops"] = [[x, list(rgb)] for x, rgb in lut.color_stops]
        entry["color_interpolation"] = lut.color_interpolation
    return entry


def lut_from_dict(entry: Any) -> LookUpTable:
    """Build one LUT from a saved entry. Raises ``ValueError`` when it is invalid."""
    if not isinstance(entry, dict):
        raise ValueError("a saved LUT must be an object")
    name = entry.get("name")
    if not isinstance(name, str) or not name.strip():
        raise ValueError("a saved LUT needs a name")
    lut_type = entry.get("lut_type", "grayscale_ramp")
    if lut_type not in ("grayscale_ramp", "colormap"):
        raise ValueError(f"unknown lut_type {lut_type!r}")
    interpolation = entry.get("interpolation")
    if interpolation not in _INTERPOLATIONS:
        interpolation = "linear"
    exp_k = entry.get("exp_k")
    if exp_k is None:
        exp_k = 1.0
    if lut_type == "colormap":
        return _colormap_from_dict(name, entry)
    points = entry.get("control_points")
    transfer_name = entry.get("transfer")
    transfer = None
    if points is None and transfer_name is not None:
        transfer = _TRANSFERS.get(transfer_name)
        if transfer is None:
            raise ValueError(f"unknown transfer {transfer_name!r}")
    return LookUpTable(
        name=name,
        lut_type="grayscale_ramp",
        source="custom",
        transfer_fn=transfer,
        control_points=None if points is None else tuple((float(x), float(y)) for x, y in points),
        interpolation=interpolation,
        gamma=None if transfer is not gamma_transfer else _number(entry.get("gamma")),
        sigmoid_k=None if transfer is not sigmoid_transfer else _number(entry.get("sigmoid_k")),
        exp_k=float(exp_k),
    )


def luts_to_payload(luts: list[LookUpTable]) -> dict[str, Any]:
    """The whole ``custom_luts.json`` document."""
    return {"schema_version": SCHEMA_VERSION, "luts": [lut_to_dict(lut) for lut in luts]}


def luts_from_payload(payload: Any) -> list[LookUpTable]:
    """Every valid LUT in a decoded document. Invalid entries are skipped with a warning.

    A document that is not an object, or whose ``schema_version`` is newer than
    this build understands, yields no LUTs so a newer file is never rewritten
    by an older reader that dropped what it could not parse.
    """
    if not isinstance(payload, dict):
        return []
    version = payload.get("schema_version", 1)
    if not isinstance(version, int) or version > SCHEMA_VERSION:
        _logger.warning(
            "Custom LUT file has an unsupported schema version; ignoring it",
            extra={"operation": "lut.load", "schema_version": str(version)},
        )
        return []
    entries = payload.get("luts")
    if not isinstance(entries, list):
        return []
    loaded: list[LookUpTable] = []
    for index, entry in enumerate(entries):
        try:
            loaded.append(lut_from_dict(entry))
        except (TypeError, ValueError, KeyError, IndexError):
            _logger.warning(
                "Skipped an invalid saved LUT",
                extra={"operation": "lut.load", "entry_index": index},
            )
    return loaded


def payload_is_writable(payload: Any) -> bool:
    """False when rewriting ``payload`` would drop entries this build cannot read.

    A missing document is writable. A document from a newer schema is not:
    saving over it would replace every entry with only what this build knows.
    """
    if payload is None:
        return True
    if not isinstance(payload, dict):
        return False
    version = payload.get("schema_version", 1)
    return isinstance(version, int) and version <= SCHEMA_VERSION


def _colormap_from_dict(name: str, entry: dict[str, Any]) -> LookUpTable:
    stops = entry.get("color_stops")
    if not isinstance(stops, list):
        raise ValueError("a saved colormap needs color_stops")
    for stop in stops:
        if not isinstance(stop, list) or len(stop) != 2 or not isinstance(stop[1], list):
            raise ValueError("a saved color stop is [x, [r, g, b]]")
    mode = entry.get("color_interpolation", "linear")
    if mode not in COLOR_INTERPOLATIONS:
        mode = "linear"
    return LookUpTable(
        name=name,
        lut_type="colormap",
        source="custom",
        color_stops=tuple((stop[0], tuple(stop[1])) for stop in stops),
        color_interpolation=mode,
    )


def _number(value: Any) -> float | None:
    return None if value is None else float(value)
