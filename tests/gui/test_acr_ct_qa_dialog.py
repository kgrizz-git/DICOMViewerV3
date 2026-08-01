"""Tests for AcrCtQaOptionsDialog option collection."""

from __future__ import annotations

import pytest

from gui.dialogs.acr_ct_qa_dialog import AcrCtQaOptionsDialog


@pytest.mark.qt
def test_default_options_are_auto_origin_and_viewer_mode(qapp) -> None:
    dlg = AcrCtQaOptionsDialog()
    tol, origin, vanilla = dlg.get_options()
    assert tol == 0.0
    assert origin is None
    assert vanilla is False


@pytest.mark.qt
def test_extent_tolerance_only_when_enabled_and_not_vanilla(qapp) -> None:
    dlg = AcrCtQaOptionsDialog()
    dlg._extent_tol.setChecked(True)
    dlg._tol_spin.setValue(1.5)
    tol, origin, vanilla = dlg.get_options()
    assert tol == 1.5
    assert origin is None
    assert vanilla is False


@pytest.mark.qt
def test_vanilla_mode_disables_extent_and_zeros_tol(qapp) -> None:
    dlg = AcrCtQaOptionsDialog(vanilla_pylinac_default=True)
    dlg._extent_tol.setChecked(True)
    dlg._tol_spin.setValue(2.0)
    # Toggling vanilla on clears extent checkbox via _on_vanilla_toggled
    dlg._vanilla.setChecked(True)
    tol, origin, vanilla = dlg.get_options()
    assert vanilla is True
    assert tol == 0.0
    assert dlg._geom.isEnabled() is False


@pytest.mark.qt
def test_origin_slice_special_value_maps_to_none(qapp) -> None:
    dlg = AcrCtQaOptionsDialog()
    dlg._origin_spin.setValue(7)
    _, origin, _ = dlg.get_options()
    assert origin == 7
    dlg._origin_spin.setValue(-1)
    _, origin2, _ = dlg.get_options()
    assert origin2 is None
