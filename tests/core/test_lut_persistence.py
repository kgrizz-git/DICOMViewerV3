"""Phase 4a/4b: ``custom_luts.json`` round-trip, fallbacks, and the config file."""

from __future__ import annotations

import json
import logging

import numpy as np
import pytest

from core.lut_catalog import colormap_lut, gamma_lut, sigmoid_lut
from core.lut_engine import (
    LookUpTable,
    apply_lut_to_uint8,
    gamma_transfer,
    sigmoid_transfer,
)
from core.lut_persistence import (
    SCHEMA_VERSION,
    lut_from_dict,
    lut_to_dict,
    luts_from_payload,
    luts_to_payload,
)

_CURVE = LookUpTable(
    name="My chest curve",
    source="custom",
    control_points=((0.0, 0.0), (0.25, 0.18), (0.5, 0.55), (1.0, 1.0)),
    interpolation="catmull_rom",
)
_COLORS = LookUpTable(
    name="Heat",
    lut_type="colormap",
    source="custom",
    color_stops=((0.0, (0, 0, 0)), (0.5, (255, 0, 0)), (1.0, (255, 255, 0))),
    color_interpolation="step",
)


def _roundtrip(lut: LookUpTable) -> LookUpTable:
    """Through JSON text, as the file does."""
    return lut_from_dict(json.loads(json.dumps(lut_to_dict(lut))))


def test_control_point_curve_round_trips() -> None:
    back = _roundtrip(_CURVE)
    assert back == _CURVE
    codes = np.arange(256, dtype=np.uint8).reshape(1, -1)
    assert np.array_equal(apply_lut_to_uint8(codes, back), apply_lut_to_uint8(codes, _CURVE))


@pytest.mark.parametrize("lut", [gamma_lut(2.2), sigmoid_lut(12.0)])
def test_parameter_curve_keeps_its_kind_and_parameter(lut) -> None:
    back = _roundtrip(lut)
    assert back.transfer_fn is lut.transfer_fn
    assert (back.gamma, back.sigmoid_k) == (lut.gamma, lut.sigmoid_k)
    assert back.source == "custom"
    assert back.transfer_fn in (gamma_transfer, sigmoid_transfer)


def test_color_stops_round_trip_and_sample_the_same_table() -> None:
    back = _roundtrip(_COLORS)
    assert back.color_stops == _COLORS.color_stops
    assert back.color_interpolation == "step"
    assert np.array_equal(back.colormap, _COLORS.colormap)


def test_a_builtin_colormap_cannot_be_saved() -> None:
    hot = colormap_lut("hot")
    with pytest.raises(ValueError, match="no color stops"):
        lut_to_dict(hot)


def test_unknown_interpolation_falls_back_to_linear() -> None:
    entry = lut_to_dict(_CURVE)
    entry["interpolation"] = "bezier"
    assert lut_from_dict(entry).interpolation == "linear"


def test_missing_or_null_exp_k_is_one() -> None:
    entry = lut_to_dict(_CURVE)
    entry["exp_k"] = None
    assert lut_from_dict(entry).exp_k == 1.0
    del entry["exp_k"]
    assert lut_from_dict(entry).exp_k == 1.0


def test_an_invalid_entry_is_skipped_with_a_warning(caplog) -> None:
    payload = luts_to_payload([_CURVE, _COLORS])
    payload["luts"].insert(1, {"name": "Broken", "control_points": [[0.0, 0.0], [0.0, 1.0]]})
    payload["luts"].append({"name": ""})
    with caplog.at_level(logging.WARNING, logger="core.lut_persistence"):
        loaded = luts_from_payload(payload)
    assert [lut.name for lut in loaded] == ["My chest curve", "Heat"]
    assert len([r for r in caplog.records if "Skipped an invalid saved LUT" in r.getMessage()]) == 2


def test_version_one_grayscale_file_loads_unchanged() -> None:
    v1 = {
        "schema_version": 1,
        "luts": [
            {
                "name": "My chest curve",
                "lut_type": "grayscale_ramp",
                "source": "custom",
                "interpolation": "catmull_rom",
                "gamma": None,
                "sigmoid_k": None,
                "exp_k": 1.0,
                "control_points": [[0.0, 0.0], [0.25, 0.18], [0.5, 0.55], [1.0, 1.0]],
            }
        ],
    }
    assert luts_from_payload(v1) == [_CURVE]


def test_a_newer_schema_is_ignored_rather_than_half_read() -> None:
    payload = luts_to_payload([_CURVE])
    payload["schema_version"] = SCHEMA_VERSION + 1
    assert luts_from_payload(payload) == []
    assert luts_from_payload(["not", "a", "document"]) == []


def test_samples_are_at_i_over_255_not_at_the_control_points() -> None:
    """A steep segment's nearest table entry can differ far more than half a step."""
    steep = LookUpTable(
        name="Steep",
        source="custom",
        control_points=((0.0, 0.0), (0.25, 1.0), (0.26, 0.0), (1.0, 0.0)),
    )
    table = apply_lut_to_uint8(np.arange(256, dtype=np.uint8).reshape(1, -1), _roundtrip(steep))[0]
    x = 64 / 255
    expected = 1.0 - (x - 0.25) / 0.01
    assert int(table[64]) == int(np.rint(expected * 255))
    assert int(table[64]) != 255


def test_config_manager_reads_and_writes_the_document(tmp_path) -> None:
    from utils.config_manager import ConfigManager

    manager = ConfigManager(config_dir=tmp_path)
    assert manager.load_custom_luts_document() is None
    assert manager.save_custom_luts_document(luts_to_payload([_CURVE, _COLORS]))
    assert manager.custom_luts_path().name == "custom_luts.json"
    reloaded = ConfigManager(config_dir=tmp_path)
    assert luts_from_payload(reloaded.load_custom_luts_document()) == [_CURVE, _COLORS]


def test_unreadable_document_loads_as_none(tmp_path) -> None:
    from utils.config_manager import ConfigManager

    manager = ConfigManager(config_dir=tmp_path)
    manager.custom_luts_path().write_text("{not json", encoding="utf-8")
    assert manager.load_custom_luts_document() is None
