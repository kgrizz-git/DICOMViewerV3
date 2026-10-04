"""
Read user colormaps from ``.csv`` or ``.json`` files (Phase 1c import).

CSV: one color per row, as ``r,g,b`` or ``x,r,g,b``. Without ``x``, the rows
are spread evenly from 0 to 1, so a 256-row table maps one row per display
code. Channels are 0-255 integers, or all floats in ``[0, 1]`` (then scaled to
0-255). Rows that do not start with a number, such as a header, are skipped.

JSON: either one LUT entry in the ``custom_luts.json`` format, a whole
``custom_luts.json`` document (every valid entry is imported), or an object
with ``color_stops`` (and optional ``name`` / ``color_interpolation``).

Every imported LUT is a colormap built from color stops, so it can be saved,
edited with **Edit Colors…**, and used as a default like any other.

Inputs:
    - A file path

Outputs:
    - A list of ``LookUpTable`` colormaps; ``ValueError`` when nothing valid is found

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
    rows = _positioned(_numeric_rows(text))
    scale = _unit_scale(rows)
    stops = []
    for x, r, g, b in rows:
        color = tuple(_channel(value, scale) for value in (r, g, b))
        stops.append((x, (color[0], color[1], color[2])))
    return LookUpTable(name=name, lut_type="colormap", source="file", color_stops=tuple(stops))


def _numeric_rows(text: str) -> list[list[float]]:
    """Rows of 3 or 4 numbers. A row that does not parse as numbers is skipped."""
    rows: list[list[float]] = []
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
    if len(rows) < 2:
        raise ValueError("a colormap needs at least two rows")
    return rows


def _positioned(rows: list[list[float]]) -> list[list[float]]:
    """``x,r,g,b`` rows; ``r,g,b`` rows are spread evenly from 0 to 1."""
    widths = {len(row) for row in rows}
    if len(widths) != 1:
        raise ValueError("CSV rows mix r,g,b and x,r,g,b")
    if widths == {4}:
        return rows
    last = len(rows) - 1
    return [[index / last, *row] for index, row in enumerate(rows)]


def _unit_scale(rows: list[list[float]]) -> float:
    """255 when the channels are 0-1 floats (any fractional value), else 1."""
    channels = [value for row in rows for value in row[1:]]
    in_unit = all(0.0 <= value <= 1.0 for value in channels)
    fractional = any(value != int(value) for value in channels)
    return 255.0 if in_unit and fractional else 1.0


def _channel(value: float, scale: float) -> int:
    """One 0-255 channel. Unit floats are scaled and rounded; others must be integers."""
    if scale != 1.0:
        return int(round(value * scale))
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
