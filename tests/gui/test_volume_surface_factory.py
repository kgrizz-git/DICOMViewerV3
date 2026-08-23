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


# ----------------------------------------------------------------------
# Muted label contrast
# ----------------------------------------------------------------------


def _contrast_ratio(fg, bg) -> float:
    """WCAG relative-luminance contrast ratio between two QColors."""

    def channel(value: int) -> float:
        v = value / 255.0
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4

    def luminance(colour) -> float:
        return (
            0.2126 * channel(colour.red())
            + 0.7152 * channel(colour.green())
            + 0.0722 * channel(colour.blue())
        )

    a, b = luminance(fg), luminance(bg)
    high, low = max(a, b), min(a, b)
    return (high + 0.05) / (low + 0.05)


@pytest.mark.parametrize(
    ("window_rgb", "text_rgb"),
    [
        ((239, 239, 239), (0, 0, 0)),  # light theme
        ((30, 30, 30), (255, 255, 255)),  # dark theme
        ((0, 0, 0), (255, 255, 255)),  # maximum contrast theme
    ],
)
def test_muted_text_meets_wcag_aa(window_rgb, text_rgb):
    """Muted labels must stay legible in any theme.

    Regression: these labels used ``palette(mid)``, a 3D-bevel shading role,
    which measures ~1.7:1 against the window background — nearly invisible.
    """
    from PySide6.QtGui import QColor, QPalette

    from gui.volume.control_panel import muted_text_color

    palette = QPalette()
    window = QColor(*window_rgb)
    palette.setColor(QPalette.ColorRole.Window, window)
    palette.setColor(QPalette.ColorRole.WindowText, QColor(*text_rgb))

    assert _contrast_ratio(muted_text_color(palette), window) >= 4.5


def test_muted_text_is_actually_muted():
    """It must still read as de-emphasised, not identical to body text."""
    from PySide6.QtGui import QColor, QPalette

    from gui.volume.control_panel import muted_text_color

    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(30, 30, 30))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(255, 255, 255))

    assert muted_text_color(palette) != QColor(255, 255, 255)


def test_palette_change_recolours_labels(qapp, monkeypatch):
    """A theme flip under a live viewer must restyle the muted labels."""
    pytest.importorskip("vtkmodules.all")
    import numpy as np
    from PySide6.QtCore import QEvent

    from core.volume_renderer import VolumeData, VolumeRenderer

    array = np.full((8, 32, 32), -1000.0, dtype=np.float32)
    array[:, 8:24, 8:24] = 300.0
    renderer = VolumeRenderer()
    renderer.attach_volume(
        VolumeData(
            array=np.ascontiguousarray(array),
            spacing=(1.0, 1.0, 1.0),
            origin=(0.0, 0.0, 0.0),
            direction=(1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0),
            rescale_applied=True,
            scalar_units="HU",
        )
    )

    from gui.volume_viewer_widget import VolumeViewerWidget

    widget = VolumeViewerWidget(renderer)
    try:
        widget.initialize(modality="CT")
        for name in ("_help_strip", "_scalar_domain_label", "_render_status_label"):
            getattr(widget, name).setStyleSheet("color: #ff0000;")
        widget.changeEvent(QEvent(QEvent.Type.PaletteChange))
        for name in ("_help_strip", "_scalar_domain_label", "_render_status_label"):
            assert "#ff0000" not in getattr(widget, name).styleSheet()
    finally:
        widget.cleanup()


def test_legacy_hatch_is_ignored_on_macos(qapp, monkeypatch):
    """Honouring the hatch on macOS would hand the user a guaranteed freeze."""
    pytest.importorskip("vtkmodules.all")
    monkeypatch.setenv(LEGACY_ENV_VAR, "1")
    monkeypatch.setattr("gui.volume.surface_factory._is_macos", lambda: True)

    from gui.volume.render_surface import VolumeRenderSurface
    from gui.volume.surface_factory import create_render_surface

    surface = create_render_surface()
    try:
        assert isinstance(surface, VolumeRenderSurface)
    finally:
        surface.cleanup()


def test_clamped_panel_reenables_horizontal_scrollbar(qapp):
    """Content wider than the cap must stay reachable, not be clipped again."""
    from PySide6.QtCore import Qt as QtNs
    from PySide6.QtWidgets import QLabel, QScrollArea, QVBoxLayout, QWidget

    from gui.volume.control_panel import (
        CONTROL_PANEL_MAX_WIDTH,
        fit_control_panel_width,
    )

    scroll = QScrollArea()
    scroll.setHorizontalScrollBarPolicy(QtNs.ScrollBarPolicy.ScrollBarAlwaysOff)
    panel = QWidget()
    layout = QVBoxLayout(panel)
    label = QLabel("x" * 4000)
    label.setWordWrap(False)
    layout.addWidget(label)
    scroll.setWidget(panel)

    assert panel.sizeHint().width() > CONTROL_PANEL_MAX_WIDTH
    fit_control_panel_width(scroll, panel)

    assert scroll.horizontalScrollBarPolicy() == QtNs.ScrollBarPolicy.ScrollBarAsNeeded
