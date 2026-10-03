"""Saved LUT library, the Saved menu, and the color-stop editor."""

from __future__ import annotations

from typing import Any

import numpy as np
import pytest
from PySide6.QtWidgets import QDialogButtonBox, QDoubleSpinBox, QMenu, QWidget

from core.lut_catalog import colormap_lut, gamma_lut
from core.lut_engine import LookUpTable
from gui import lut_actions
from gui.dialogs.lut_color_stops_dialog import LutColorStopsDialog, seed_stops
from gui.lut_library import delete_lut, is_savable, library_store, save_lut, saved_luts

_CURVE = LookUpTable(
    name="Custom", source="custom", control_points=((0.0, 0.0), (0.5, 0.8), (1.0, 1.0))
)


class _Store:
    """In-memory stand-in for ConfigManager's two document methods."""

    def __init__(self) -> None:
        self.document: Any = None

    def load_custom_luts_document(self) -> Any:
        return self.document

    def save_custom_luts_document(self, document: dict[str, Any]) -> bool:
        self.document = document
        return True


class _Pane(QWidget):
    """A pane host with an active LUT and a config-owning window."""

    def __init__(self, lut: LookUpTable, store: _Store) -> None:
        super().__init__()
        self.lut = lut
        self.config_manager = store

    def current_series_lut(self) -> LookUpTable:
        return self.lut

    def apply_series_lut(self, lut: LookUpTable) -> None:
        self.lut = lut


def test_save_replaces_by_name_and_delete_removes() -> None:
    store = _Store()
    first = save_lut(store, _CURVE, "  Chest ")
    assert first is not None
    assert first.name == "Chest"
    assert first.source == "custom"
    save_lut(store, gamma_lut(2.2), "Chest")
    save_lut(store, gamma_lut(1.5), "Soft")
    names = [lut.name for lut in saved_luts(store)]
    assert names == ["Chest", "Soft"]
    assert saved_luts(store)[0].gamma == 2.2
    assert delete_lut(store, "Chest") is True
    assert delete_lut(store, "Chest") is False
    assert [lut.name for lut in saved_luts(store)] == ["Soft"]


def test_builtin_colormaps_and_blank_names_are_not_saved() -> None:
    store = _Store()
    assert is_savable(colormap_lut("hot")) is False
    assert save_lut(store, colormap_lut("hot"), "Hot copy") is None
    assert save_lut(store, _CURVE, "   ") is None
    assert saved_luts(None) == []


@pytest.mark.qt
def test_store_is_found_on_the_host_or_its_window(qapp) -> None:
    store = _Store()
    pane = _Pane(_CURVE, store)
    assert library_store(pane) is store
    assert library_store(object()) is None
    _ = qapp


@pytest.mark.qt
def test_menu_lists_saved_luts_and_selecting_one_applies_it(qapp) -> None:
    store = _Store()
    save_lut(store, _CURVE, "Chest")
    pane = _Pane(gamma_lut(1.0), store)
    menu = QMenu()
    lut_actions.populate_lut_menu(menu, pane)
    saved_menu = next(a.menu() for a in menu.actions() if a.menu() and a.text() == "Saved")
    [chest] = saved_menu.actions()
    chest.trigger()
    assert pane.lut.name == "Chest"
    assert pane.lut.control_points == _CURVE.control_points
    delete_menu = next(a.menu() for a in menu.actions() if a.menu() and a.text() == "Delete Saved")
    delete_menu.actions()[0].trigger()
    assert saved_luts(store) == []
    _ = qapp


@pytest.mark.qt
def test_save_current_as_names_and_selects_the_saved_lut(qapp, monkeypatch) -> None:
    store = _Store()
    pane = _Pane(_CURVE, store)
    monkeypatch.setattr(lut_actions.QInputDialog, "getText", lambda *_a, **_k: ("Lung", True))
    lut_actions._save_current(pane)
    assert [lut.name for lut in saved_luts(store)] == ["Lung"]
    assert pane.lut.name == "Lung"
    monkeypatch.setattr(lut_actions.QInputDialog, "getText", lambda *_a, **_k: ("Other", False))
    lut_actions._save_current(pane)
    assert [lut.name for lut in saved_luts(store)] == ["Lung"]
    _ = qapp


@pytest.mark.qt
def test_menu_has_no_saved_section_when_nothing_is_saved(qapp) -> None:
    pane = _Pane(gamma_lut(1.0), _Store())
    menu = QMenu()
    lut_actions.populate_lut_menu(menu, pane)
    assert "Saved" not in [a.text() for a in menu.actions()]
    edit_colors = next(a for a in menu.actions() if a.text() == "Edit Colors...")
    assert edit_colors.isEnabled() is False
    _ = qapp


def test_seed_stops_samples_a_builtin_colormap() -> None:
    hot = colormap_lut("hot")
    stops = seed_stops(hot)
    assert [x for x, _rgb in stops] == [0.0, 0.25, 0.5, 0.75, 1.0]
    assert stops[0][1] == tuple(int(v) for v in hot.colormap[0])
    assert stops[-1][1] == tuple(int(v) for v in hot.colormap[255])
    assert seed_stops(None) == ((0.0, (0, 0, 0)), (1.0, (255, 255, 255)))


@pytest.mark.qt
def test_color_dialog_edits_stops_and_rejects_duplicates(qapp) -> None:
    dialog = LutColorStopsDialog(None)
    ok = dialog._buttons.button(QDialogButtonBox.StandardButton.Ok)
    dialog._add_stop()
    assert [x for x, _rgb in dialog.stops()] == [0.0, 1.0, 0.5]
    dialog.set_stop_color(2, (255, 0, 0))
    lut = dialog.result_lut()
    assert lut is not None
    assert lut.lut_type == "colormap"
    assert lut.colormap[128][0] == 255
    assert lut.colormap[128][1] <= 2
    spin = dialog._table.cellWidget(2, 0)
    assert isinstance(spin, QDoubleSpinBox)
    spin.setValue(1.0)
    assert dialog.result_lut() is None
    assert ok is not None
    assert ok.isEnabled() is False
    dialog._table.setCurrentCell(2, 0)
    dialog._remove_stop()
    assert dialog.result_lut() is not None
    assert ok.isEnabled() is True
    dialog._table.setCurrentCell(0, 0)
    dialog._remove_stop()
    assert len(dialog.stops()) == 2
    _ = qapp


@pytest.mark.qt
def test_color_dialog_step_mode_reaches_the_table(qapp) -> None:
    dialog = LutColorStopsDialog(colormap_lut("viridis"))
    dialog._interpolation.setCurrentText("step")
    lut = dialog.result_lut()
    assert lut is not None
    assert lut.color_interpolation == "step"
    assert np.array_equal(lut.colormap[0], lut.colormap[63])
    _ = qapp


def test_resaving_keeps_the_entry_in_place() -> None:
    store = _Store()
    for name in ("A", "B", "C"):
        save_lut(store, _CURVE, name)
    save_lut(store, gamma_lut(2.0), "B")
    assert [lut.name for lut in saved_luts(store)] == ["A", "B", "C"]
    assert saved_luts(store)[1].gamma == 2.0


def test_a_newer_file_is_never_overwritten() -> None:
    store = _Store()
    future = {"schema_version": 99, "luts": [{"name": "FromTheFuture"}]}
    store.document = future
    assert save_lut(store, _CURVE, "Mine") is None
    assert delete_lut(store, "FromTheFuture") is False
    assert store.document is future


def test_an_unsavable_transfer_function_is_refused_not_raised() -> None:
    odd = LookUpTable(name="Odd", transfer_fn=lambda x: np.asarray(x))
    assert save_lut(_Store(), odd, "Odd") is None


@pytest.mark.qt
def test_a_saved_parameter_lut_checks_only_its_saved_entry(qapp) -> None:
    store = _Store()
    saved = save_lut(store, gamma_lut(2.2), "A")
    assert saved is not None
    pane = _Pane(saved, store)
    menu = QMenu()
    lut_actions.populate_lut_menu(menu, pane)
    checked = [
        action.text()
        for sub in (a.menu() for a in menu.actions() if a.menu())
        for action in sub.actions()
        if action.isCheckable() and action.isChecked()
    ]
    assert checked == ["A"]
    _ = qapp


@pytest.mark.qt
def test_color_dialog_keeps_untouched_positions_exact(qapp) -> None:
    lut = LookUpTable(
        name="Fine",
        lut_type="colormap",
        source="custom",
        color_stops=((0.0, (0, 0, 0)), (0.12345, (255, 0, 0)), (1.0, (255, 255, 255))),
        color_interpolation="step",
    )
    dialog = LutColorStopsDialog(lut)
    result = dialog.result_lut()
    assert result is not None
    assert result.color_stops == lut.color_stops
    assert np.array_equal(result.colormap, lut.colormap)
    spin = dialog._table.cellWidget(1, 0)
    assert isinstance(spin, QDoubleSpinBox)
    spin.setValue(0.5)
    moved = dialog.result_lut()
    assert moved is not None
    assert moved.color_stops is not None
    assert moved.color_stops[1][0] == 0.5
    _ = qapp


@pytest.mark.qt
def test_a_saved_colormap_named_like_a_builtin_checks_only_its_saved_entry(qapp) -> None:
    store = _Store()
    stops = LookUpTable(
        name="x",
        lut_type="colormap",
        source="custom",
        color_stops=((0.0, (0, 0, 0)), (1.0, (0, 255, 0))),
    )
    saved = save_lut(store, stops, "hot")
    assert saved is not None
    pane = _Pane(saved, store)
    menu = QMenu()
    lut_actions.populate_lut_menu(menu, pane)
    checked = [
        (sub.title(), action.text())
        for sub in (a.menu() for a in menu.actions() if a.menu())
        for action in sub.actions()
        if action.isCheckable() and action.isChecked()
    ]
    assert checked == [("Saved", "hot")]
    pane.lut = colormap_lut("hot")
    lut_actions.populate_lut_menu(menu, pane)
    checked = [
        (sub.title(), action.text())
        for sub in (a.menu() for a in menu.actions() if a.menu())
        for action in sub.actions()
        if action.isCheckable() and action.isChecked()
    ]
    assert checked == [("Color", "hot")]
    _ = qapp
