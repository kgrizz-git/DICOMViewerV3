"""Phase 1c: import colormaps from .csv and .json files."""

from __future__ import annotations

import json

import numpy as np
import pytest

from core.lut_engine import LookUpTable
from core.lut_import import MAX_IMPORT_BYTES, import_colormap_file
from core.lut_persistence import luts_to_payload


def _write(tmp_path, name: str, text: str):
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


def test_rgb_rows_spread_evenly_and_header_is_skipped(tmp_path) -> None:
    path = _write(tmp_path, "fire.csv", "r,g,b\n0,0,0\n255,0,0\n255,255,0\n")
    [lut] = import_colormap_file(path)
    assert lut.name == "fire"
    assert lut.lut_type == "colormap"
    assert lut.color_stops == ((0.0, (0, 0, 0)), (0.5, (255, 0, 0)), (1.0, (255, 255, 0)))


def test_a_256_row_table_maps_one_row_per_code(tmp_path) -> None:
    rows = "\n".join(f"{i},{255 - i},{i // 2}" for i in range(256))
    [lut] = import_colormap_file(_write(tmp_path, "t.csv", rows))
    expected = np.array([[i, 255 - i, i // 2] for i in range(256)], dtype=np.uint8)
    assert np.array_equal(lut.colormap, expected)


def test_xrgb_rows_and_unit_floats(tmp_path) -> None:
    path = _write(tmp_path, "u.csv", "0,0.0,0.0,0.0\n0.25,1.0,0.5,0.0\n1,1,1,1\n")
    [lut] = import_colormap_file(path)
    assert lut.color_stops == ((0.0, (0, 0, 0)), (0.25, (255, 128, 0)), (1.0, (255, 255, 255)))


@pytest.mark.parametrize(
    "text",
    ["0,0,0\n", "0,0\n1,1\n", "0,0,0\n0.5,1,1,1\n", "0,0,0\n300,0,0\n", "0,0,0\n1.5,2,3\n"],
)
def test_malformed_csv_is_rejected(tmp_path, text) -> None:
    path = _write(tmp_path, "bad.csv", text)
    with pytest.raises(ValueError):
        import_colormap_file(path)


def test_json_stops_object_entry_and_document(tmp_path) -> None:
    stops = {"color_stops": [[0, [0, 0, 0]], [1, [0, 0, 255]]], "color_interpolation": "step"}
    [blue] = import_colormap_file(_write(tmp_path, "blue.json", json.dumps(stops)))
    assert blue.name == "blue"
    assert blue.color_interpolation == "step"
    curve = LookUpTable(name="Curve", source="custom", control_points=((0.0, 0.0), (1.0, 1.0)))
    document = luts_to_payload([curve, blue])
    found = import_colormap_file(_write(tmp_path, "all.json", json.dumps(document)))
    assert [lut.name for lut in found] == ["Curve", "blue"]


@pytest.mark.parametrize("text", ["{not json", "[]", '{"luts": []}'])
def test_unusable_json_is_rejected(tmp_path, text) -> None:
    path = _write(tmp_path, "x.json", text)
    with pytest.raises(ValueError):
        import_colormap_file(path)


def test_other_extensions_and_huge_files_are_rejected(tmp_path) -> None:
    text_file = _write(tmp_path, "x.txt", "0,0,0\n1,1,1\n")
    with pytest.raises(ValueError, match=r"\.csv or \.json"):
        import_colormap_file(text_file)
    big = _write(tmp_path, "big.csv", "0,0,0\n" * (MAX_IMPORT_BYTES // 6 + 10))
    with pytest.raises(ValueError, match="too large"):
        import_colormap_file(big)
