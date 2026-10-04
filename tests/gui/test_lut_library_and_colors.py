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


@pytest.mark.qt
def test_retyping_the_displayed_position_restores_the_loaded_one(qapp) -> None:
    """The spin box shows 3 decimals; putting it back to that display is a revert."""
    lut = LookUpTable(
        name="Fine",
        lut_type="colormap",
        source="custom",
        color_stops=((0.0, (0, 0, 0)), (0.12345, (255, 0, 0)), (1.0, (255, 255, 255))),
    )
    dialog = LutColorStopsDialog(lut)
    spin = dialog._table.cellWidget(1, 0)
    assert isinstance(spin, QDoubleSpinBox)
    spin.setValue(0.124)
    assert dialog.stops()[1][0] == 0.124
    spin.setValue(0.123)
    assert dialog.stops()[1][0] == 0.12345
    _ = qapp


@pytest.mark.qt
def test_a_failed_save_is_reported(qapp, monkeypatch) -> None:
    store = _Store()
    store.document = {"schema_version": 99, "luts": []}
    pane = _Pane(_CURVE, store)
    warnings: list[str] = []
    monkeypatch.setattr(lut_actions.QInputDialog, "getText", lambda *_a, **_k: ("Lung", True))
    monkeypatch.setattr(
        lut_actions.QMessageBox, "warning", lambda _p, _t, text: warnings.append(text)
    )
    lut_actions._save_current(pane)
    assert len(warnings) == 1
    assert "not saved" in warnings[0]
    assert pane.lut is _CURVE
    monkeypatch.setattr(lut_actions.QInputDialog, "getText", lambda *_a, **_k: ("  ", True))
    lut_actions._save_current(pane)
    assert len(warnings) == 2
    _ = qapp


def test_an_unreadable_file_or_unparsable_entry_blocks_writes(tmp_path) -> None:
    from pathlib import Path as _Path

    class _FileStore(_Store):
        def __init__(self, path: _Path) -> None:
            super().__init__()
            self.path = path

        def custom_luts_path(self) -> _Path:
            return self.path

    corrupt = tmp_path / "custom_luts.json"
    corrupt.write_text("{not json", encoding="utf-8")
    store = _FileStore(corrupt)
    assert save_lut(store, _CURVE, "Mine") is None
    assert store.document is None

    fresh = _FileStore(tmp_path / "missing.json")
    assert save_lut(fresh, _CURVE, "Mine") is not None

    store = _Store()
    save_lut(store, _CURVE, "Good")
    store.document["luts"].append({"name": "Broken", "control_points": [[0, 0], [0, 1]]})
    before = store.document
    assert save_lut(store, gamma_lut(2.0), "Other") is None
    assert delete_lut(store, "Good") is False
    assert store.document is before


@pytest.mark.qt
def test_choosing_the_builtin_kind_does_not_keep_a_saved_identity(qapp, monkeypatch) -> None:
    store = _Store()
    saved = save_lut(store, gamma_lut(2.2), "Mine")
    assert saved is not None
    pane = _Pane(saved, store)
    from gui.dialogs import lut_parameter_dialog

    seen: list[LookUpTable] = []
    monkeypatch.setattr(
        lut_parameter_dialog, "edit_lut_parameters", lambda start, _p: (seen.append(start), start)[1]
    )
    lut_actions._select_builtin(pane, gamma_lut(1.0))
    assert seen[0].source == "built_in"
    assert pane.lut.name == "Gamma"
    assert pane.lut.source == "built_in"
    _ = qapp


@pytest.mark.qt
def test_ok_without_edits_keeps_a_builtin_map_exactly(qapp) -> None:
    viridis = colormap_lut("viridis")
    dialog = LutColorStopsDialog(viridis)
    assert dialog.result_lut() is viridis
    dialog.set_stop_color(0, (1, 2, 3))
    edited = dialog.result_lut()
    assert edited is not None
    assert edited is not viridis
    assert edited.color_stops is not None
    _ = qapp


@pytest.mark.qt
def test_a_no_op_edit_keeps_a_builtin_map_exactly(qapp) -> None:
    viridis = colormap_lut("viridis")
    dialog = LutColorStopsDialog(viridis)
    original = dialog.stops()[0][1]
    dialog.set_stop_color(0, original)
    assert dialog.result_lut() is viridis
    dialog._interpolation.setCurrentText("step")
    assert dialog.result_lut() is not viridis
    dialog._interpolation.setCurrentText("linear")
    assert dialog.result_lut() is viridis
    _ = qapp


@pytest.mark.qt
def test_retyping_a_fine_position_restores_the_opened_map(qapp) -> None:
    mine = LookUpTable(
        name="Mine",
        lut_type="colormap",
        source="custom",
        color_stops=((0.0, (0, 0, 0)), (0.12345, (255, 0, 0)), (1.0, (255, 255, 255))),
    )
    dialog = LutColorStopsDialog(mine)
    spin = dialog._table.cellWidget(1, 0)
    assert isinstance(spin, QDoubleSpinBox)
    spin.setValue(0.5)
    assert dialog.result_lut() is not mine
    spin.setValue(0.123)
    assert dialog.result_lut() is mine
    _ = qapp


@pytest.mark.qt
@pytest.mark.parametrize("source", ["custom", "file", "dicom"])
def test_only_a_builtin_carries_its_parameter_into_the_builtin_choice(qapp, monkeypatch, source) -> None:
    import dataclasses

    from gui.dialogs import lut_parameter_dialog

    current = dataclasses.replace(gamma_lut(2.2), name="Other", source=source)
    pane = _Pane(current, _Store())
    seen: list[LookUpTable] = []
    monkeypatch.setattr(
        lut_parameter_dialog, "edit_lut_parameters", lambda start, _p: (seen.append(start), start)[1]
    )
    lut_actions._select_builtin(pane, gamma_lut(1.0))
    assert seen[0].source == "built_in"
    assert pane.lut.name == "Gamma"
    builtin = gamma_lut(3.0)
    pane.lut = builtin
    lut_actions._select_builtin(pane, gamma_lut(1.0))
    assert seen[-1] is builtin
    _ = qapp


@pytest.mark.qt
@pytest.mark.parametrize(("available", "enabled", "shown_enabled"), [(False, False, False), (True, False, True), (False, True, True)])
def test_from_dicom_action_reflects_and_sets_the_pane_choice(qapp, available, enabled, shown_enabled) -> None:
    pane = _Pane(gamma_lut(1.0), _Store())
    toggled: list[bool] = []
    pane.dicom_lut_state = lambda: (available, enabled)  # type: ignore[attr-defined]
    pane.set_dicom_lut = toggled.append  # type: ignore[attr-defined]
    menu = QMenu()
    lut_actions.populate_lut_menu(menu, pane)
    action = next(a for a in menu.actions() if a.text() == "From DICOM (VOI LUT)")
    assert action.isChecked() is enabled
    assert action.isEnabled() is shown_enabled
    if shown_enabled:
        action.trigger()
        assert toggled == [not enabled]
    _ = qapp


class _DefaultsStore(_Store):
    def __init__(self) -> None:
        super().__init__()
        self.defaults: dict[str, Any] = {}

    def get_lut_defaults(self) -> dict[str, Any]:
        return dict(self.defaults)

    def set_lut_default(self, modality: str, entry: Any) -> None:
        if entry is None:
            self.defaults.pop(modality, None)
        else:
            self.defaults[modality] = entry


def _menu_action(pane: _Pane, text: str):
    menu = QMenu()
    lut_actions.populate_lut_menu(menu, pane)
    return menu, next(a for a in menu.actions() if a.text() == text)


@pytest.mark.qt
def test_default_actions_set_and_clear_the_modality_default(qapp) -> None:
    store = _DefaultsStore()
    pane = _Pane(colormap_lut("hot"), store)
    pane.current_modality = lambda: "PT"  # type: ignore[attr-defined]
    redraws: list[bool] = []
    pane.redisplay_all_panes = lambda: redraws.append(True)  # type: ignore[attr-defined]
    _menu, use = _menu_action(pane, "Use as Default for PT")
    assert use.isEnabled()
    use.trigger()
    assert store.defaults == {"PT": {"kind": "colormap", "name": "hot"}}
    assert redraws == [True]
    _menu, clear = _menu_action(pane, "Clear Default for PT")
    assert clear.isEnabled()
    clear.trigger()
    assert store.defaults == {}
    assert redraws == [True, True]
    _ = qapp


@pytest.mark.qt
def test_an_unsaved_custom_curve_cannot_be_a_default(qapp) -> None:
    store = _DefaultsStore()
    pane = _Pane(_CURVE, store)
    pane.current_modality = lambda: "CT"  # type: ignore[attr-defined]
    _menu, use = _menu_action(pane, "Use as Default for CT")
    assert not use.isEnabled()
    saved = save_lut(store, _CURVE, "Lung")
    assert saved is not None
    pane.lut = saved
    _menu, use = _menu_action(pane, "Use as Default for CT")
    assert use.isEnabled()
    _ = qapp


def test_default_resolver_rereads_the_library_only_when_it_changes(tmp_path) -> None:
    from gui.lut_library import default_resolver

    store = _DefaultsStore()
    reads: list[bool] = []
    real = store.load_custom_luts_document

    def counted():
        reads.append(True)
        return real()

    store.load_custom_luts_document = counted  # type: ignore[method-assign]
    path = tmp_path / "custom_luts.json"
    store.custom_luts_path = lambda: path  # type: ignore[attr-defined]
    save_lut(store, _CURVE, "Lung")
    path.write_text("x", encoding="utf-8")
    store.defaults = {"CT": {"kind": "saved", "name": "Lung"}}
    resolve = default_resolver(store, lambda: "CT")
    reads.clear()
    first = resolve()
    second = resolve()
    assert first is not None
    assert second is not None
    assert first.name == "Lung"
    assert len(reads) == 1
    assert default_resolver(store, lambda: "MR")() is None


@pytest.mark.qt
def test_import_saves_and_applies_the_first_colormap(qapp, monkeypatch, tmp_path) -> None:
    from PySide6.QtWidgets import QFileDialog

    path = tmp_path / "fire.csv"
    path.write_text("0,0,0\n255,0,0\n", encoding="utf-8")
    store = _Store()
    pane = _Pane(gamma_lut(1.0), store)
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *_a, **_k: (str(path), ""))
    lut_actions._import_colormap(pane)
    assert [lut.name for lut in saved_luts(store)] == ["fire"]
    assert pane.lut.name == "fire"
    assert pane.lut.source == "custom"


@pytest.mark.qt
def test_a_bad_import_is_reported_and_changes_nothing(qapp, monkeypatch, tmp_path) -> None:
    from PySide6.QtWidgets import QFileDialog

    path = tmp_path / "bad.csv"
    path.write_text("0,0,0\n", encoding="utf-8")
    store = _Store()
    pane = _Pane(gamma_lut(1.0), store)
    warnings: list[str] = []
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *_a, **_k: (str(path), ""))
    monkeypatch.setattr(lut_actions.QMessageBox, "warning", lambda _p, _t, text: warnings.append(text))
    lut_actions._import_colormap(pane)
    assert len(warnings) == 1
    assert "not imported" in warnings[0]
    assert saved_luts(store) == []
    assert pane.lut.name == "Gamma"



@pytest.mark.qt
def test_import_never_overwrites_a_saved_lut(qapp, monkeypatch, tmp_path) -> None:
    from PySide6.QtWidgets import QFileDialog

    store = _Store()
    original = save_lut(store, gamma_lut(2.0), "fire")
    save_lut(store, gamma_lut(1.5), "fire (2)")
    path = tmp_path / "fire.csv"
    path.write_text("0,0,255\n255,0,0\n", encoding="utf-8")
    pane = _Pane(gamma_lut(1.0), store)
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *_a, **_k: (str(path), ""))
    lut_actions._import_colormap(pane)
    luts = saved_luts(store)
    assert [lut.name for lut in luts] == ["fire", "fire (2)", "fire (3)"]
    assert luts[0] == original
    assert pane.lut.name == "fire (3)"
    _ = qapp
