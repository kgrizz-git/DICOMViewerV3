"""
Unit tests for asymmetric 3-pane multi-window layouts (Stream LP-A).

Uses a headless QApplication when available.
"""

from __future__ import annotations

import sys

import pytest

from utils.config.layout_config import THREE_PANE_CYCLE_ORDER, THREE_PANE_LAYOUT_MODES


@pytest.fixture(scope="module")
def qapp():
    """Ensure a QApplication exists for QWidget-based layout tests."""
    try:
        from PySide6.QtWidgets import QApplication
    except ImportError:
        pytest.skip("PySide6 not available")
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app


@pytest.fixture
def multi_window_layout(qapp):
    from gui.multi_window_layout import MultiWindowLayout

    layout = MultiWindowLayout()
    yield layout
    layout.deleteLater()


class TestThreePaneGridCells:
    """Screenshot / composite grid cell descriptors match T0 slot table."""

    @pytest.mark.parametrize(
        "mode,expected",
        [
            ("1+2R", [(0, 0, 0), (0, 1, 1), (1, 1, 2)]),
            ("2L+1", [(0, 0, 1), (1, 0, 2), (0, 1, 3)]),
            ("2T+1", [(0, 0, 0), (1, 0, 1), (1, 1, 2)]),
            ("1+2B", [(0, 0, 0), (0, 1, 1), (1, 0, 2)]),
        ],
    )
    def test_get_screenshot_grid_cells_default_slot_order(
        self, multi_window_layout, mode, expected
    ):
        multi_window_layout.set_layout(mode)
        assert multi_window_layout.get_screenshot_grid_cells() == expected

    def test_three_pane_visible_count(self, multi_window_layout, qapp):
        multi_window_layout.show()
        qapp.processEvents()
        for mode in THREE_PANE_LAYOUT_MODES:
            multi_window_layout.set_layout(mode)
            qapp.processEvents()
            visible = [
                sw for sw in multi_window_layout.get_all_subwindows() if sw.isVisible()
            ]
            assert len(visible) == 3, mode
            hidden = [
                sw
                for sw in multi_window_layout.get_all_subwindows()
                if not sw.isVisible()
            ]
            assert len(hidden) == 1, mode


class TestThreePaneCycle:
    def test_cycle_order_from_1x1(self, multi_window_layout):
        multi_window_layout.set_layout("1x1")
        multi_window_layout.cycle_three_pane_layout()
        assert multi_window_layout.get_layout_mode() == "1+2R"

    def test_cycle_wraps(self, multi_window_layout):
        multi_window_layout.set_layout("1+2B")
        multi_window_layout.cycle_three_pane_layout()
        assert multi_window_layout.get_layout_mode() == "1+2R"

    def test_full_cycle_sequence(self, multi_window_layout):
        multi_window_layout.set_layout("1+2R")
        seen = []
        for _ in range(len(THREE_PANE_CYCLE_ORDER) + 1):
            seen.append(multi_window_layout.get_layout_mode())
            multi_window_layout.cycle_three_pane_layout()
        assert seen[:4] == list(THREE_PANE_CYCLE_ORDER)
        assert seen[4] == "1+2R"


class TestTwoPaneToggle:
    def test_toggle_1x2_2x1(self, multi_window_layout):
        multi_window_layout.set_layout("1x2")
        multi_window_layout.toggle_two_pane_layout()
        assert multi_window_layout.get_layout_mode() == "2x1"
        multi_window_layout.toggle_two_pane_layout()
        assert multi_window_layout.get_layout_mode() == "1x2"

    def test_from_three_pane_uses_last_two_pane_default(self, multi_window_layout):
        multi_window_layout.set_layout("1+2R")
        multi_window_layout.toggle_two_pane_layout()
        assert multi_window_layout.get_layout_mode() in ("1x2", "2x1")
