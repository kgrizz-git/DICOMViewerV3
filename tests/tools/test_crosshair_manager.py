"""Tests for CrosshairManager create/delete/clear and privacy mode."""

from __future__ import annotations

import pytest
from PySide6.QtCore import QPointF
from PySide6.QtWidgets import QGraphicsScene

from tools.crosshair_manager import CrosshairManager


@pytest.mark.qt
def test_set_current_slice_initializes_empty_list(qapp) -> None:
    mgr = CrosshairManager()
    mgr.set_current_slice("study", "series", 0)
    assert mgr.get_crosshairs_for_slice() == []
    assert mgr.current_study_uid == "study"


@pytest.mark.qt
def test_create_and_delete_crosshair(qapp) -> None:
    mgr = CrosshairManager()
    mgr.set_current_slice("s", "ser", 1)
    scene = QGraphicsScene()
    item = mgr.create_crosshair(QPointF(10, 20), "42", 10, 20, 1, scene)
    assert item in mgr.get_crosshairs_for_slice()
    assert len(mgr.get_crosshairs_for_slice()) == 1
    mgr.delete_crosshair(item, scene)
    assert mgr.get_crosshairs_for_slice() == []


@pytest.mark.qt
def test_clear_crosshairs_for_slice(qapp) -> None:
    mgr = CrosshairManager()
    mgr.set_current_slice("s", "ser", 2)
    scene = QGraphicsScene()
    mgr.create_crosshair(QPointF(1, 1), "1", 1, 1, 2, scene)
    mgr.create_crosshair(QPointF(2, 2), "2", 2, 2, 2, scene)
    assert len(mgr.get_crosshairs_for_slice()) == 2
    mgr.clear_crosshairs_for_slice(scene)
    assert mgr.get_crosshairs_for_slice() == []


@pytest.mark.qt
def test_privacy_mode_toggles_without_error(qapp) -> None:
    mgr = CrosshairManager()
    mgr.set_current_slice("s", "ser", 0)
    scene = QGraphicsScene()
    mgr.create_crosshair(QPointF(5, 5), "HU 10", 5, 5, 0, scene)
    mgr.set_privacy_mode(True)
    assert mgr.privacy_mode is True
    mgr.set_privacy_mode(True)  # no-op same value
    mgr.set_privacy_mode(False)
    assert mgr.privacy_mode is False
