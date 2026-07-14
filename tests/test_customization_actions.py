"""
Unit tests for core.actions.customization_actions (thin delegation to
app._customization_handlers).
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

from core.actions.customization_actions import (
    on_export_customizations,
    on_export_tag_presets,
    on_import_customizations,
    on_import_tag_presets,
)


def _make_app():
    return SimpleNamespace(_customization_handlers=MagicMock())


def test_on_export_customizations_delegates():
    app = _make_app()
    on_export_customizations(app)
    app._customization_handlers.export_customizations.assert_called_once_with()


def test_on_import_customizations_delegates():
    app = _make_app()
    on_import_customizations(app)
    app._customization_handlers.import_customizations.assert_called_once_with()


def test_on_export_tag_presets_delegates():
    app = _make_app()
    on_export_tag_presets(app)
    app._customization_handlers.export_tag_presets.assert_called_once_with()


def test_on_import_tag_presets_delegates():
    app = _make_app()
    on_import_tag_presets(app)
    app._customization_handlers.import_tag_presets.assert_called_once_with()
