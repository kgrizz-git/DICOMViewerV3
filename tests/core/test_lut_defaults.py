"""Per-modality default LUTs: entries, resolution, and the series fallback."""

from __future__ import annotations

import dataclasses
from types import SimpleNamespace

import pytest

from core.lut_catalog import colormap_lut, gamma_lut, linear_lut
from core.lut_defaults import default_entry, resolve_default
from core.lut_engine import LookUpTable, gamma_transfer
from core.lut_series_state import get_series_lut, set_series_lut

_SAVED = LookUpTable(name="Mine", source="custom", control_points=((0.0, 0.0), (0.5, 0.8), (1.0, 1.0)))


def test_entries_name_builtins_curves_and_saved_luts() -> None:
    assert default_entry(colormap_lut("hot")) == {"kind": "colormap", "name": "hot"}
    assert default_entry(_SAVED) == {"kind": "saved", "name": "Mine"}
    curve = default_entry(gamma_lut(2.2))
    assert curve is not None
    assert curve["kind"] == "curve"
    edited = LookUpTable(
        name="x", lut_type="colormap", source="file",
        color_stops=((0.0, (0, 0, 0)), (1.0, (9, 9, 9))),
    )
    assert default_entry(edited) is None


def test_resolution_round_trips_each_kind() -> None:
    assert resolve_default({"kind": "colormap", "name": "hot"}, []) == colormap_lut("hot")
    assert resolve_default({"kind": "saved", "name": "Mine"}, [_SAVED]) is _SAVED
    entry = default_entry(gamma_lut(2.2))
    resolved = resolve_default(entry, [])
    assert resolved is not None
    assert resolved.transfer_fn is gamma_transfer
    assert resolved.gamma == 2.2
    assert resolved.source == "built_in"


@pytest.mark.parametrize(
    "entry",
    [None, "hot", {"kind": "colormap", "name": "nope"}, {"kind": "saved", "name": "Gone"}, {"kind": "curve", "lut": 3}],
)
def test_stale_or_malformed_entries_resolve_to_nothing(entry) -> None:
    assert resolve_default(entry, [_SAVED]) is None


def _view_state(default: LookUpTable | None) -> SimpleNamespace:
    return SimpleNamespace(
        series_defaults={},
        current_series_identifier="s1",
        lut_default_resolver=lambda: default,
    )


def test_a_series_that_never_chose_takes_the_default() -> None:
    view_state = _view_state(colormap_lut("hot"))
    assert get_series_lut(view_state, "s1") == colormap_lut("hot")
    # Only the shown series: another series id still reads Linear.
    assert get_series_lut(view_state, "s2").name == linear_lut().name


def test_a_chosen_lut_beats_the_default() -> None:
    view_state = _view_state(colormap_lut("hot"))
    chosen = dataclasses.replace(gamma_lut(1.5))
    set_series_lut(view_state, chosen, "s1")
    assert get_series_lut(view_state, "s1") is chosen


def test_no_default_is_linear() -> None:
    assert get_series_lut(_view_state(None), "s1").name == linear_lut().name


def test_config_sets_and_clears_defaults(tmp_path) -> None:
    from utils.config_manager import ConfigManager

    manager = ConfigManager(config_dir=tmp_path)
    assert manager.get_lut_defaults() == {}
    manager.set_lut_default("PT", {"kind": "colormap", "name": "hot"})
    assert ConfigManager(config_dir=tmp_path).get_lut_defaults() == {"PT": {"kind": "colormap", "name": "hot"}}
    manager.set_lut_default("PT", None)
    assert ConfigManager(config_dir=tmp_path).get_lut_defaults() == {}
