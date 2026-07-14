"""
Tests for Window/Level preset menu access points (View menu wiring helpers, right pane).

Verifies shared ``wire_dynamic_wl_preset_menu`` / ``create_wl_presets_menu_button`` without
duplicating catalog logic covered in ``test_wl_preset_catalog.py``.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from PySide6.QtWidgets import QApplication, QMenu

from core.wl_preset_catalog import WindowLevelPreset
from gui.window_level_controls import WindowLevelControls
from gui.wl_preset_menu import (
    WLPresetMenuContext,
    create_wl_presets_menu_button,
    wire_dynamic_wl_preset_menu,
)


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


class TestWireDynamicWlPresetMenu:
    def test_about_to_show_populates_grouped_actions(self, qapp) -> None:
        menu = QMenu()
        preset = WindowLevelPreset(40.0, 400.0, True, "Lung", "builtin", "CT")
        ctx = WLPresetMenuContext(
            preset_objects=[preset],
            current_index=0,
            unit="HU",
            use_rescaled=True,
            rescale_slope=1.0,
            rescale_intercept=-1024.0,
        )
        on_select = MagicMock()
        wire_dynamic_wl_preset_menu(menu, get_context=lambda: ctx, on_select=on_select)
        menu.aboutToShow.emit()
        actions = [a.text() for a in menu.actions() if not a.isSeparator()]
        assert any("Built-in" in t or "Lung" in t for t in actions) or len(menu.actions()) > 0
        submenus = [a for a in menu.actions() if a.menu() is not None]
        assert submenus, "expected at least one preset submenu"

    def test_legacy_fallback_when_no_context_callback(self, qapp) -> None:
        menu = QMenu()
        legacy = [(40.0, 400.0, True, "Test")]
        wire_dynamic_wl_preset_menu(
            menu,
            get_legacy_presets=lambda: legacy,
            on_select=MagicMock(),
        )
        menu.aboutToShow.emit()
        assert len(menu.actions()) >= 1


class TestWindowLevelControlsPresetsButton:
    def test_attach_creates_presets_button(self, qapp) -> None:
        controls = WindowLevelControls()
        btn = controls.attach_wl_presets_menu(
            on_select=MagicMock(),
            get_context=lambda: WLPresetMenuContext(preset_objects=[], current_index=0),
        )
        assert btn is controls.wl_presets_button
        assert btn.text() == "Presets…"
        assert btn.menu() is not None

    def test_create_presets_button_has_menu(self, qapp) -> None:
        btn = create_wl_presets_menu_button(
            None,
            on_select=MagicMock(),
            get_context=lambda: WLPresetMenuContext(preset_objects=[], current_index=0),
        )
        assert btn.menu() is not None
