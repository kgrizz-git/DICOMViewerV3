"""Focused tests for SliceLocationLineCoordinator manager lifecycle."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from PySide6.QtWidgets import QGraphicsScene

from gui.slice_location_line_coordinator import SliceLocationLineCoordinator


@pytest.mark.qt
def test_ensure_and_remove_manager(qapp) -> None:
    app = SimpleNamespace()
    coord = SliceLocationLineCoordinator(app)
    scene = QGraphicsScene()
    mgr = coord.ensure_manager(0, scene)
    assert 0 in coord._managers
    assert coord.ensure_manager(0, scene) is mgr
    coord.remove_manager(0)
    assert 0 not in coord._managers


@pytest.mark.qt
def test_remove_missing_manager_is_noop(qapp) -> None:
    coord = SliceLocationLineCoordinator(SimpleNamespace())
    coord.remove_manager(99)
    assert 99 not in coord._managers
    assert coord._managers == {}
