"""Tests for View-menu grouping of in-window slice/frame slider controls."""

from __future__ import annotations

import pytest

from gui.main_window import MainWindow
from utils.config_manager import ConfigManager


def _clean_text(text: str) -> str:
    return text.replace("&", "")


@pytest.mark.qt
def test_in_window_slider_controls_are_grouped_under_one_view_submenu(qapp) -> None:
    window = MainWindow(ConfigManager())

    view_menu = window.view_menu
    assert view_menu is not None

    top_level_texts = [
        _clean_text(action.text())
        for action in view_menu.actions()
        if not action.isSeparator()
    ]
    assert "In-Window Slice/Frame Slider" in top_level_texts
    assert "Show In-Window Slice/Frame Slider" not in top_level_texts
    assert "Slice/Frame Slider Placement" not in top_level_texts
    assert "Slice/Frame Slider Direction" not in top_level_texts

    slider_menu = window.slice_slider_menu
    assert slider_menu is not None

    slider_menu_texts = [
        _clean_text(action.text())
        for action in slider_menu.actions()
        if not action.isSeparator()
    ]
    assert "Show In-Window Slice/Frame Slider" in slider_menu_texts
    assert "Placement" in slider_menu_texts
    assert "Direction" in slider_menu_texts
