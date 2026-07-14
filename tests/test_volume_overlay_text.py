"""
Unit tests for the 3D viewer corner-overlay text builder.

``build_overlay_text`` composes the overlay string from preset name, opacity
percent, detail/quality mode, and blend mode. After refactor Stream B it lives
in the pure, Qt/VTK-free module ``gui.volume.overlay_text`` and is imported
directly (the previous AST-extraction hack — needed when it was a module-level
function inside the Qt widget — is no longer required).

The final test still asserts the *widget* renders the overlay via a Qt QLabel
sibling rather than VTK corner annotation (a regression guard against text glyph
bleed into the GPU volume pass).
"""

from __future__ import annotations

import os

from gui.volume.overlay_text import build_overlay_text

# Backward-compatible alias so the case bodies read unchanged.
_build_overlay_text = build_overlay_text

_SRC_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
_WIDGET_PATH = os.path.join(_SRC_DIR, "gui", "volume_viewer_widget.py")


class TestBuildOverlayText:
    """Tests for build_overlay_text — pure function, no Qt/VTK."""

    def test_preset_only_all_defaults(self):
        """Preset name only when opacity==100, detail==Normal, blend==Composite."""
        result = _build_overlay_text(
            preset_name="Bone", opacity_pct=100.0, detail="Normal", blend="Composite"
        )
        assert result == "Bone"

    def test_opacity_below_100_adds_line(self):
        """opacity_pct < 100 appends an 'Opacity X.X%' line."""
        result = _build_overlay_text(
            preset_name="Default", opacity_pct=75.0, detail="Normal", blend="Composite"
        )
        lines = result.split("\n")
        assert lines[0] == "Default"
        assert "Opacity 75.0%" in lines

    def test_opacity_at_exactly_100_no_opacity_line(self):
        """Boundary: opacity_pct == 100.0 must NOT produce an Opacity line."""
        result = _build_overlay_text(
            preset_name="Default", opacity_pct=100.0, detail="Normal", blend="Composite"
        )
        assert "Opacity" not in result

    def test_non_normal_detail_adds_line(self):
        """detail != 'Normal' appends 'Detail: <detail>' line."""
        result = _build_overlay_text(
            preset_name="CT Lung", opacity_pct=100.0, detail="Low", blend="Composite"
        )
        assert "Detail: Low" in result.split("\n")

    def test_normal_detail_no_detail_line(self):
        """detail == 'Normal' must NOT produce a Detail line."""
        result = _build_overlay_text(
            preset_name="CT Lung", opacity_pct=100.0, detail="Normal", blend="Composite"
        )
        assert "Detail:" not in result

    def test_non_composite_blend_adds_line(self):
        """blend != 'Composite' appends the blend name as a line."""
        result = _build_overlay_text(
            preset_name="Default", opacity_pct=100.0, detail="Normal", blend="Maximum Intensity"
        )
        assert "Maximum Intensity" in result.split("\n")

    def test_composite_blend_no_blend_line(self):
        """blend == 'Composite' must NOT produce a blend line."""
        result = _build_overlay_text(
            preset_name="Default", opacity_pct=100.0, detail="Normal", blend="Composite"
        )
        assert result == "Default"

    def test_empty_preset_name_no_preset_line(self):
        """Empty preset_name (separator row selected) produces no preset line."""
        result = _build_overlay_text(
            preset_name="", opacity_pct=100.0, detail="Normal", blend="Composite"
        )
        assert result == ""

    def test_all_extras_four_lines(self):
        """All non-default values → exactly 4 lines joined with newline."""
        result = _build_overlay_text(
            preset_name="MRI Brain", opacity_pct=60.0, detail="High", blend="Additive"
        )
        lines = result.split("\n")
        assert len(lines) == 4
        assert lines[0] == "MRI Brain"
        assert "Opacity 60.0%" in lines
        assert "Detail: High" in lines
        assert "Additive" in lines

    def test_empty_preset_with_extras_no_blank_line(self):
        """Empty preset_name with extras → no blank lines in output."""
        result = _build_overlay_text(
            preset_name="", opacity_pct=50.0, detail="Low", blend="Additive"
        )
        lines = result.split("\n")
        assert "" not in lines
        assert "Opacity 50.0%" in lines

    def test_opacity_just_below_100(self):
        """opacity_pct=99.9 (just below threshold) triggers the Opacity line."""
        result = _build_overlay_text(
            preset_name="Test", opacity_pct=99.9, detail="Normal", blend="Composite"
        )
        assert "Opacity 99.9%" in result

    def test_return_type_is_str(self):
        """Return value is always a str, even for all-default inputs."""
        result = _build_overlay_text(
            preset_name="", opacity_pct=100.0, detail="Normal", blend="Composite"
        )
        assert isinstance(result, str)


def test_viewport_overlay_uses_qt_sibling_not_vtk_text():
    """Overlay must not instantiate VTK corner annotation or multi-layer text."""
    with open(_WIDGET_PATH, encoding="utf-8") as fh:
        source = fh.read()
    assert "_viewport_container" in source
    assert "QLabel(self._viewport_container)" in source
    assert "vtk_mod.vtkCornerAnnotation()" not in source
    assert "_corner_annotation" not in source
    assert "SetNumberOfLayers(2)" not in source
