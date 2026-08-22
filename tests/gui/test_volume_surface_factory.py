"""Tests for render-surface selection and control-panel sizing."""

from __future__ import annotations

import pytest

from gui.volume.control_panel import (
    CONTROL_PANEL_MAX_WIDTH,
    CONTROL_PANEL_MIN_WIDTH,
    control_panel_width,
)
from gui.volume.surface_factory import (
    LEGACY_ENV_VAR,
    legacy_interactor_requested,
)

# ----------------------------------------------------------------------
# Escape hatch
# ----------------------------------------------------------------------


@pytest.mark.parametrize("value", ["1", "true", "TRUE", "yes", "on", " on "])
def test_legacy_requested_for_truthy_values(value):
    assert legacy_interactor_requested({LEGACY_ENV_VAR: value}) is True


@pytest.mark.parametrize("value", ["", "0", "false", "no", "off", "maybe"])
def test_legacy_not_requested_otherwise(value):
    assert legacy_interactor_requested({LEGACY_ENV_VAR: value}) is False


def test_legacy_not_requested_when_unset():
    assert legacy_interactor_requested({}) is False


def test_default_surface_is_offscreen(qapp, monkeypatch):
    """Without the env var the offscreen surface is used on every platform."""
    pytest.importorskip("vtkmodules.all")
    monkeypatch.delenv(LEGACY_ENV_VAR, raising=False)
    from gui.volume.render_surface import VolumeRenderSurface
    from gui.volume.surface_factory import create_render_surface

    surface = create_render_surface()
    try:
        assert isinstance(surface, VolumeRenderSurface)
    finally:
        surface.cleanup()


def test_unusable_legacy_falls_back_to_offscreen(qapp, monkeypatch):
    """A stale env var must never leave the user without a 3D viewer."""
    pytest.importorskip("vtkmodules.all")
    monkeypatch.setenv(LEGACY_ENV_VAR, "1")
    import gui.volume.legacy_surface as legacy

    def _boom(*_args, **_kwargs):
        raise RuntimeError("no native interactor here")

    monkeypatch.setattr(legacy, "LegacyInteractorSurface", _boom)

    from gui.volume.render_surface import VolumeRenderSurface
    from gui.volume.surface_factory import create_render_surface

    surface = create_render_surface()
    try:
        assert isinstance(surface, VolumeRenderSurface)
    finally:
        surface.cleanup()


# ----------------------------------------------------------------------
# Control-panel width
# ----------------------------------------------------------------------


def test_control_panel_width_accounts_for_scrollbar():
    """The scrollbar must not eat into the space the controls need."""
    assert control_panel_width(258, 18) > 258 + 18 - 1


def test_control_panel_width_is_clamped_low():
    assert control_panel_width(10, 0) == CONTROL_PANEL_MIN_WIDTH


def test_control_panel_width_is_clamped_high():
    assert control_panel_width(10_000, 18) == CONTROL_PANEL_MAX_WIDTH


def test_control_panel_is_wide_enough_for_its_contents(qapp, monkeypatch):
    """Regression: controls were clipped at a hardcoded 240 px column.

    With the horizontal scrollbar disabled the clipped region was unreachable
    no matter how large the window grew.
    """
    pytest.importorskip("vtkmodules.all")
    import numpy as np
    from PySide6.QtWidgets import QScrollArea

    from core.volume_renderer import VolumeData, VolumeRenderer

    array = np.full((8, 32, 32), -1000.0, dtype=np.float32)
    array[:, 8:24, 8:24] = 300.0
    volume = VolumeData(
        array=np.ascontiguousarray(array),
        spacing=(1.0, 1.0, 1.0),
        origin=(0.0, 0.0, 0.0),
        direction=(1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0),
        rescale_applied=True,
        scalar_units="HU",
    )
    renderer = VolumeRenderer()
    renderer.attach_volume(volume)

    from gui.volume_viewer_widget import VolumeViewerWidget

    widget = VolumeViewerWidget(renderer)
    try:
        widget.initialize(modality="CT")
        widget.resize(1000, 700)
        widget.show()
        qapp.processEvents()
        scroll = widget.findChildren(QScrollArea)[0]
        panel = scroll.widget()
        assert scroll.viewport().width() >= panel.sizeHint().width()
    finally:
        widget.cleanup()
