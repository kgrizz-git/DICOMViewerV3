"""
Read user colormaps from ``.csv`` or ``.json`` files (Phase 1c import).

CSV: one color per row, as ``r,g,b`` or ``x,r,g,b``. Without ``x``, the rows
are spread evenly from 0 to 1, so a 256-row table maps one row per display
code. Channels are 0-255 integers, or floats in ``[0, 1]`` written with a
decimal point, such as ``1.0``, which are scaled to 0-255. Rows that do not
start with a number, such as a header, are skipped.

JSON: either one LUT entry in the ``custom_luts.json`` format, a whole
``custom_luts.json`` document (every valid entry is imported), or an object
with ``color_stops`` (and optional ``name`` / ``color_interpolation``).

A CSV, or a JSON object with ``color_stops``, gives a colormap built from color
stops. A JSON saved-LUT entry or document gives whatever it holds, which can
include grayscale curves. Every imported LUT can be saved and used as a
default like any other.

Inputs:
    - A file path

Outputs:
    - A list of ``LookUpTable`` values; ``ValueError`` when nothing valid is found

Requirements:
    - core.lut_color_stops, core.lut_persistence
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from core.lut_engine import LookUpTable
from core.lut_persistence import lut_from_dict, luts_from_payload

MAX_IMPORT_BYTES = 1_000_000


def import_colormap_file(path: Path) -> list[LookUpTable]:
    """Every LUT a ``.csv`` or ``.json`` file defines. Raises ``ValueError`` when none."""
    if path.stat().st_size > MAX_IMPORT_BYTES:
        raise ValueError("the colormap file is too large to be a LUT")
    text = path.read_text(encoding="utf-8-sig")
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return [_from_csv(text, path.stem)]
    if suffix == ".json":
        return _from_json(text, path.stem)
    raise ValueError("a colormap file must be .csv or .json")


def _from_csv(text: str, name: str) -> LookUpTable:
    rows, float_written = _numeric_rows(text)
    rows = _positioned(rows)
    unit = _is_unit_scale(rows, float_written)
    stops = []
    for x, r, g, b in rows:
        color = tuple(_channel(value, unit) for value in (r, g, b))
        stops.append((x, (color[0], color[1], color[2])))
    return LookUpTable(name=name, lut_type="colormap", source="file", color_stops=tuple(stops))


def _numeric_rows(text: str) -> tuple[list[list[float]], bool]:
    """Rows of 3 or 4 numbers, and whether any color cell is written as a float.

    A row that does not parse as numbers is skipped. The color cells are the
    last three; an ``x`` cell is not counted, since positions are always floats.
    """
    rows: list[list[float]] = []
    float_written = False
    for raw in csv.reader(text.splitlines()):
        cells = [cell.strip() for cell in raw if cell.strip()]
        try:
            numbers = [float(cell) for cell in cells]
        except ValueError:
            continue  # header or comment row
        if not numbers:
            continue
        if len(numbers) not in (3, 4):
            raise ValueError("each CSV row must be r,g,b or x,r,g,b")
        rows.append(numbers)
        float_written = float_written or any(_looks_float(cell) for cell in cells[-3:])
    if len(rows) < 2:
        raise ValueError("a colormap needs at least two rows")
    return rows, float_written


def _looks_float(cell: str) -> bool:
    """True for a cell written with a decimal point or an exponent, such as ``1.0``."""
    return "." in cell or "e" in cell.lower()


def _positioned(rows: list[list[float]]) -> list[list[float]]:
    """``x,r,g,b`` rows; ``r,g,b`` rows are spread evenly from 0 to 1."""
    widths = {len(row) for row in rows}
    if len(widths) != 1:
        raise ValueError("CSV rows mix r,g,b and x,r,g,b")
    if widths == {4}:
        return rows
    last = len(rows) - 1
    return [[index / last, *row] for index, row in enumerate(rows)]


def _is_unit_scale(rows: list[list[float]], float_written: bool) -> bool:
    """True when every channel is in ``[0, 1]`` and the file writes them as floats.

    ``1.0`` means full intensity; a bare ``1`` means 1 out of 255. A fractional
    value such as ``0.5`` is also read as a float even without other floats.
    """
    channels = [value for row in rows for value in row[1:]]
    in_unit = all(0.0 <= value <= 1.0 for value in channels)
    fractional = any(not float(value).is_integer() for value in channels)
    return in_unit and (float_written or fractional)


def _channel(value: float, unit: bool) -> int:
    """One 0-255 channel. Unit floats are scaled and rounded; others must be integers."""
    if unit:
        return int(round(value * 255.0))
    rounded = round(value)
    if abs(value - rounded) > 1e-6:
        raise ValueError("color channels must be 0-255 integers or 0-1 floats")
    return int(rounded)


def _from_json(text: str, name: str) -> list[LookUpTable]:
    try:
        document: Any = json.loads(text)
    except ValueError as error:
        raise ValueError("the JSON file could not be parsed") from error
    if isinstance(document, dict) and isinstance(document.get("luts"), list):
        found = luts_from_payload(document)
    elif isinstance(document, dict) and "color_stops" in document:
        entry = {"name": name, "lut_type": "colormap", **document}
        found = [lut_from_dict(entry)]
    else:
        found = [lut_from_dict(document)]
    if not found:
        raise ValueError("the JSON file holds no valid LUT")
    return found
