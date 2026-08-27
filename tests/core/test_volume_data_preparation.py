"""Compatibility and dependency-boundary tests for volume preparation."""

from __future__ import annotations

import ast
from pathlib import Path

import core.volume_data_preparation as volume_data_preparation
from core.volume_data_preparation import (
    VolumeData as PreparedVolumeData,
)
from core.volume_data_preparation import (
    _calibrate_volume_array as calibrate_prepared_array,
)
from core.volume_data_preparation import (
    prepare_volume_data,
)
from core.volume_renderer import (
    VolumeData as RendererVolumeData,
)
from core.volume_renderer import (
    VolumeRenderer,
)
from core.volume_renderer import (
    _calibrate_volume_array as calibrate_renderer_array,
)


def test_volume_renderer_keeps_data_preparation_compatibility_facade() -> None:
    """Existing renderer imports and staticmethod calls stay exact aliases."""
    assert RendererVolumeData is PreparedVolumeData
    assert calibrate_renderer_array is calibrate_prepared_array
    assert VolumeRenderer.prepare_volume_data is prepare_volume_data


def test_volume_data_preparation_has_no_direct_vtk_import() -> None:
    """Preparation stays usable off the GUI/VTK thread and import boundary."""
    source = Path(volume_data_preparation.__file__).read_text(encoding="utf-8")
    imports = list(ast.walk(ast.parse(source)))
    imported_modules = [
        alias.name
        for node in imports
        if isinstance(node, ast.Import)
        for alias in node.names
    ]
    imported_modules.extend(
        node.module or ""
        for node in imports
        if isinstance(node, ast.ImportFrom)
    )
    assert not any(module.startswith("vtk") for module in imported_modules)
