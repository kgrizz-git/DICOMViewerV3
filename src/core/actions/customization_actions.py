"""
Customization import/export menu handlers delegated from ``DICOMViewerApp``.

Inputs:
    ``app``: running ``DICOMViewerApp`` instance.

Outputs:
    Side effects via ``CustomizationHandlers`` (file dialogs, config apply).

Requirements:
    ``app._customization_handlers`` initialized during app construction.
"""

from __future__ import annotations

# pyright: reportImportCycles=false

from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from main import DICOMViewerApp


def on_export_customizations(app: "DICOMViewerApp") -> None:
    """Handle Export Customizations request."""
    app._customization_handlers.export_customizations()


def on_import_customizations(app: "DICOMViewerApp") -> None:
    """Handle Import Customizations request."""
    app._customization_handlers.import_customizations()


def on_export_tag_presets(app: "DICOMViewerApp") -> None:
    """Handle Export Tag Presets request."""
    app._customization_handlers.export_tag_presets()


def on_import_tag_presets(app: "DICOMViewerApp") -> None:
    """Handle Import Tag Presets request."""
    app._customization_handlers.import_tag_presets()
