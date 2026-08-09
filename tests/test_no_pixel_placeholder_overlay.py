"""
Unit tests for ``gui.no_pixel_placeholder_overlay.NoPixelPlaceholderOverlay``.

Verifies the bottom overlay's configure() visibility rules and that the open
callback is only wired/invoked when active + button shown + callback present.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from PySide6.QtWidgets import QWidget

from gui.no_pixel_placeholder_overlay import NoPixelPlaceholderOverlay

pytestmark = pytest.mark.qt


@pytest.fixture
def host(qapp) -> QWidget:
    """A shown parent widget so overlay visibility follows the widget hierarchy
    rather than top-level window mapping."""
    widget = QWidget()
    widget.show()
    yield widget
    widget.close()


def _make(parent: QWidget) -> NoPixelPlaceholderOverlay:
    return NoPixelPlaceholderOverlay(parent)


class TestConfigure:
    def test_active_shows_bar(self, host):
        ov = _make(host)
        ov.configure(active=True, show_open_button=False, open_callback=None)
        assert ov.isVisible() is True
        assert ov._btn.isVisible() is False
        assert ov._open_cb is None

    def test_inactive_hides_bar(self, host):
        ov = _make(host)
        ov.configure(active=False, show_open_button=True, open_callback=MagicMock())
        assert ov.isVisible() is False
        assert ov._btn.isVisible() is False

    def test_active_with_button_wires_callback(self, host):
        cb = MagicMock()
        ov = _make(host)
        ov.configure(active=True, show_open_button=True, open_callback=cb)
        assert ov.isVisible() is True
        assert ov._btn.isVisible() is True
        assert ov._open_cb is cb

    def test_active_button_without_callback_does_not_wire(self, host):
        ov = _make(host)
        ov.configure(active=True, show_open_button=True, open_callback=None)
        assert ov._btn.isVisible() is False
        assert ov._open_cb is None

    def test_button_hidden_when_requested_inactive(self, host):
        ov = _make(host)
        ov.configure(active=True, show_open_button=False, open_callback=MagicMock())
        assert ov._btn.isVisible() is False
        assert ov._open_cb is None


class TestOpenCallback:
    def test_click_invokes_callback(self, host):
        cb = MagicMock()
        ov = _make(host)
        ov.configure(active=True, show_open_button=True, open_callback=cb)
        ov._on_open_clicked()
        cb.assert_called_once()

    def test_click_noop_without_callback(self, host):
        ov = _make(host)
        ov.configure(active=True, show_open_button=False, open_callback=None)
        # Should not raise even though the button is hidden.
        ov._on_open_clicked()
