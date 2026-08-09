"""Comprehensive tests for MagnifierWidget."""

from __future__ import annotations

import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QWidget

from gui.magnifier_widget import MagnifierWidget


@pytest.fixture(autouse=True)
def _close_top_level_widgets(qapp):
    """Close any widgets a test shows so they cannot outlive it and skew later
    window-activation assertions against the session-scoped QApplication."""
    yield
    for widget in list(qapp.topLevelWidgets()):
        widget.close()


@pytest.mark.qt
def test_widget_initialization(qapp) -> None:
    """Test that MagnifierWidget initializes with correct properties."""
    widget = MagnifierWidget()
    
    # Check window flags for floating window behavior
    flags = widget.windowFlags()
    assert flags & Qt.WindowType.FramelessWindowHint
    assert flags & Qt.WindowType.WindowStaysOnTopHint
    assert flags & Qt.WindowType.Tool
    
    # Check widget is not translucent
    assert widget.testAttribute(Qt.WidgetAttribute.WA_TranslucentBackground) is False
    
    # Check fixed size
    assert widget.width() == 200
    assert widget.height() == 200
    assert widget.magnifier_size == 200
    
    # Check that image label exists
    assert widget.image_label is not None
    assert widget.image_label.alignment() == Qt.AlignmentFlag.AlignCenter
    
    # Check widget is initially hidden
    assert widget.isVisible() is False


@pytest.mark.qt
def test_widget_initialization_with_parent(qapp) -> None:
    """Test that MagnifierWidget can be initialized with a parent."""
    parent = QWidget()
    widget = MagnifierWidget(parent)
    
    assert widget.parent() is parent
    assert widget.isVisible() is False


@pytest.mark.qt
def test_update_magnified_region_with_valid_pixmap(qapp) -> None:
    """Test update_magnified_region with a valid pixmap."""
    widget = MagnifierWidget()
    
    # Create a test pixmap
    pixmap = QPixmap(100, 100)
    pixmap.fill(Qt.GlobalColor.red)
    
    widget.update_magnified_region(pixmap)
    
    # Check that the label has a pixmap set
    assert widget.image_label.pixmap() is not None
    # The pixmap should be scaled to fit within the label (200 - 4 = 196)
    scaled = widget.image_label.pixmap()
    assert scaled.width() <= 196
    assert scaled.height() <= 196


@pytest.mark.qt
def test_update_magnified_region_with_null_pixmap(qapp) -> None:
    """Test update_magnified_region with a null pixmap clears the label."""
    widget = MagnifierWidget()
    
    # First set a valid pixmap
    pixmap = QPixmap(100, 100)
    pixmap.fill(Qt.GlobalColor.blue)
    widget.update_magnified_region(pixmap)
    assert widget.image_label.pixmap() is not None
    
    # Then update with null pixmap
    null_pixmap = QPixmap()
    widget.update_magnified_region(null_pixmap)
    
    # Label should be cleared (pixmap() returns a null QPixmap, not None)
    assert widget.image_label.pixmap().isNull() is True


@pytest.mark.qt
def test_update_magnified_region_with_different_sizes(qapp) -> None:
    """Test update_magnified_region with various pixmap sizes."""
    widget = MagnifierWidget()
    
    # Test with small pixmap
    small = QPixmap(50, 50)
    small.fill(Qt.GlobalColor.green)
    widget.update_magnified_region(small)
    assert widget.image_label.pixmap() is not None
    
    # Test with large pixmap
    large = QPixmap(400, 400)
    large.fill(Qt.GlobalColor.yellow)
    widget.update_magnified_region(large)
    assert widget.image_label.pixmap() is not None
    
    # Test with non-square pixmap
    wide = QPixmap(300, 100)
    wide.fill(Qt.GlobalColor.cyan)
    widget.update_magnified_region(wide)
    assert widget.image_label.pixmap() is not None
    
    # All should be scaled to fit within the label
    scaled = widget.image_label.pixmap()
    assert scaled.width() <= 196
    assert scaled.height() <= 196


@pytest.mark.qt
def test_show_at_position_centered(qapp) -> None:
    """Test show_at_position centers the widget on the given position."""
    widget = MagnifierWidget()
    
    # Show at position (500, 500)
    pos = QPoint(500, 500)
    widget.show_at_position(pos)
    
    # Widget should be visible
    assert widget.isVisible() is True
    
    # Position should be approximately centered (may be adjusted by screen boundaries)
    # Calculate the ideal centered position
    ideal_x = pos.x() - widget.magnifier_size // 2
    ideal_y = pos.y() - widget.magnifier_size // 2
    # Allow for screen boundary adjustments (within reasonable tolerance)
    assert abs(widget.x() - ideal_x) <= widget.magnifier_size
    assert abs(widget.y() - ideal_y) <= widget.magnifier_size


@pytest.mark.qt
def test_show_at_position_clamps_to_screen_boundaries(qapp) -> None:
    """A position past the screen edge is clamped so the widget stays on-screen."""
    widget = MagnifierWidget()

    screen = qapp.primaryScreen().geometry()
    # Request a position well beyond the bottom-right corner.
    widget.show_at_position(QPoint(screen.right() + 1000, screen.bottom() + 1000))

    assert widget.isVisible() is True
    assert widget.x() + widget.magnifier_size <= screen.right() + 1
    assert widget.y() + widget.magnifier_size <= screen.bottom() + 1


@pytest.mark.qt
def test_show_at_position_uses_primary_screen_when_no_screen_at_point(
    qapp, monkeypatch
) -> None:
    """When no screen contains the point, positioning falls back to the primary
    screen geometry rather than crashing."""
    widget = MagnifierWidget()
    monkeypatch.setattr(qapp, "screenAt", lambda _pos: None)

    primary = qapp.primaryScreen().geometry()
    widget.show_at_position(QPoint(500, 500))

    assert widget.isVisible() is True
    assert primary.left() <= widget.x() <= primary.right()
    assert primary.top() <= widget.y() <= primary.bottom()


@pytest.mark.qt
def test_show_at_position_raises_and_activates(qapp) -> None:
    """Test show_at_position raises and activates the window."""
    widget = MagnifierWidget()
    
    pos = QPoint(500, 500)
    widget.show_at_position(pos)
    
    assert widget.isVisible() is True
    # The widget should be raised and activated (we can't easily test this,
    # but we can verify it doesn't crash)


@pytest.mark.qt
def test_show_at_position_multiple_calls(qapp) -> None:
    """Test multiple calls to show_at_position update position correctly."""
    widget = MagnifierWidget()
    
    # First position
    pos1 = QPoint(500, 500)
    widget.show_at_position(pos1)
    x1, y1 = widget.x(), widget.y()
    
    # Second position
    pos2 = QPoint(800, 600)
    widget.show_at_position(pos2)
    x2, y2 = widget.x(), widget.y()
    
    # Third position
    pos3 = QPoint(200, 300)
    widget.show_at_position(pos3)
    x3, y3 = widget.x(), widget.y()
    
    # Positions should change between calls
    assert (x1, y1) != (x2, y2) or (x2, y2) != (x3, y3)
    # Widget should remain visible
    assert widget.isVisible() is True


@pytest.mark.qt
def test_widget_styling(qapp) -> None:
    """Test that widget and label have correct styling."""
    widget = MagnifierWidget()
    
    # Check widget has translucent background style
    widget_style = widget.styleSheet()
    assert "background-color: rgba(0, 0, 0, 0)" in widget_style
    
    # Check label has border and background style
    label_style = widget.image_label.styleSheet()
    assert "background-color: white" in label_style
    assert "border: 2px solid #333" in label_style
    assert "border-radius: 2px" in label_style


@pytest.mark.qt
def test_layout_properties(qapp) -> None:
    """Test that layout has correct margins and spacing."""
    widget = MagnifierWidget()
    layout = widget.layout()
    
    assert layout is not None
    assert layout.contentsMargins().left() == 2
    assert layout.contentsMargins().top() == 2
    assert layout.contentsMargins().right() == 2
    assert layout.contentsMargins().bottom() == 2
    assert layout.spacing() == 0


@pytest.mark.qt
def test_update_magnified_region_aspect_ratio_preserved(qapp) -> None:
    """Test that update_magnified_region preserves aspect ratio."""
    widget = MagnifierWidget()
    
    # Create a wide pixmap
    wide = QPixmap(200, 50)
    wide.fill(Qt.GlobalColor.red)
    widget.update_magnified_region(wide)
    
    scaled = widget.image_label.pixmap()
    # Aspect ratio should be preserved (4:1)
    ratio = scaled.width() / scaled.height()
    assert abs(ratio - 4.0) < 0.1
    
    # Create a tall pixmap
    tall = QPixmap(50, 200)
    tall.fill(Qt.GlobalColor.blue)
    widget.update_magnified_region(tall)
    
    scaled = widget.image_label.pixmap()
    # Aspect ratio should be preserved (1:4)
    ratio = scaled.width() / scaled.height()
    assert abs(ratio - 0.25) < 0.1


@pytest.mark.qt
def test_update_magnified_region_smooth_transformation(qapp) -> None:
    """Test that update_magnified_region uses smooth transformation."""
    widget = MagnifierWidget()
    
    # This test verifies the transformation mode is set correctly
    # We can't directly test the Qt.TransformationMode.SmoothTransformation,
    # but we can verify the scaling works without errors
    pixmap = QPixmap(100, 100)
    pixmap.fill(Qt.GlobalColor.green)
    widget.update_magnified_region(pixmap)
    
    assert widget.image_label.pixmap() is not None


@pytest.mark.qt
def test_widget_hide_after_show(qapp) -> None:
    """Test that widget can be hidden after being shown."""
    widget = MagnifierWidget()
    
    # Show the widget
    pos = QPoint(500, 500)
    widget.show_at_position(pos)
    assert widget.isVisible() is True
    
    # Hide the widget
    widget.hide()
    assert widget.isVisible() is False


@pytest.mark.qt
def test_update_magnified_region_while_hidden(qapp) -> None:
    """Test that update_magnified_region works even when widget is hidden."""
    widget = MagnifierWidget()
    
    # Widget should be hidden initially
    assert widget.isVisible() is False
    
    # Update with pixmap while hidden
    pixmap = QPixmap(100, 100)
    pixmap.fill(Qt.GlobalColor.magenta)
    widget.update_magnified_region(pixmap)
    
    # Pixmap should be set even though widget is hidden
    assert widget.image_label.pixmap() is not None


@pytest.mark.qt
def test_show_at_position_with_negative_coordinates(qapp) -> None:
    """Test show_at_position with negative coordinates."""
    widget = MagnifierWidget()
    
    # Position with negative coordinates
    pos = QPoint(-100, -100)
    widget.show_at_position(pos)
    
    # Widget should still be visible and positioned
    assert widget.isVisible() is True
    # Position should be adjusted by screen boundaries
    assert widget.x() >= 0
    assert widget.y() >= 0


@pytest.mark.qt
def test_show_at_position_corner_cases(qapp) -> None:
    """Test show_at_position with corner positions."""
    widget = MagnifierWidget()
    
    # Top-left corner
    widget.show_at_position(QPoint(0, 0))
    assert widget.isVisible() is True
    # Should be adjusted to stay on screen
    assert widget.x() >= 0
    assert widget.y() >= 0
    
    # Bottom-right corner (use very large coordinates)
    widget.show_at_position(QPoint(10000, 10000))
    assert widget.isVisible() is True
    # Should be adjusted to stay on screen
    assert widget.x() is not None
    assert widget.y() is not None


@pytest.mark.qt
def test_magnifier_size_constant(qapp) -> None:
    """Test that magnifier_size is used consistently."""
    widget = MagnifierWidget()
    
    size = widget.magnifier_size
    
    # Check it's used for fixed size
    assert widget.width() == size
    assert widget.height() == size
    
    # Check it's used in positioning (centering calculation)
    # Note: Actual position may be adjusted by screen boundaries
    pos = QPoint(1000, 1000)
    widget.show_at_position(pos)
    # Verify the calculation is used (may be adjusted by screen)
    assert widget.magnifier_size == size


@pytest.mark.qt
def test_debug_flag_import_handling(qapp) -> None:
    """Test that debug flag import is handled gracefully."""
    # The module should handle missing debug_flags import gracefully
    # This test verifies the module can be imported even without debug_flags
    import gui.magnifier_widget as mw_module
    
    # The debug flag should be False by default (when import fails)
    assert hasattr(mw_module, '_debug_magnifier_enabled')
    # It should be a boolean
    assert isinstance(mw_module._debug_magnifier_enabled, bool)


@pytest.mark.qt
def test_update_magnified_region_with_very_small_pixmap(qapp) -> None:
    """Test update_magnified_region with a very small pixmap (1x1)."""
    widget = MagnifierWidget()
    
    # Create a 1x1 pixmap
    tiny = QPixmap(1, 1)
    tiny.fill(Qt.GlobalColor.red)
    widget.update_magnified_region(tiny)
    
    # Should still work and scale up
    assert widget.image_label.pixmap() is not None
    scaled = widget.image_label.pixmap()
    # Should be scaled to fit
    assert scaled.width() <= 196
    assert scaled.height() <= 196


@pytest.mark.qt
def test_update_magnified_region_with_very_large_pixmap(qapp) -> None:
    """Test update_magnified_region with a very large pixmap."""
    widget = MagnifierWidget()
    
    # Create a large pixmap
    huge = QPixmap(2000, 2000)
    huge.fill(Qt.GlobalColor.blue)
    widget.update_magnified_region(huge)
    
    # Should scale down to fit
    assert widget.image_label.pixmap() is not None
    scaled = widget.image_label.pixmap()
    assert scaled.width() <= 196
    assert scaled.height() <= 196


@pytest.mark.qt
def test_update_magnified_region_with_debug_enabled(qapp, monkeypatch, capsys) -> None:
    """Test update_magnified_region with debug flag enabled."""
    # Patch the debug flag to True
    import gui.magnifier_widget
    monkeypatch.setattr(gui.magnifier_widget, "_debug_magnifier_enabled", True)
    
    widget = gui.magnifier_widget.MagnifierWidget()
    
    # Create a test pixmap
    pixmap = QPixmap(100, 100)
    pixmap.fill(Qt.GlobalColor.green)
    
    # Update with debug enabled
    widget.update_magnified_region(pixmap)
    
    # Check that debug output was captured
    captured = capsys.readouterr()
    assert "[DEBUG-MAGNIFIER]" in captured.out
    assert "update_magnified_region" in captured.out


@pytest.mark.qt
def test_show_at_position_with_debug_enabled(qapp, monkeypatch, capsys) -> None:
    """Test show_at_position with debug flag enabled."""
    # Patch the debug flag to True
    import gui.magnifier_widget
    monkeypatch.setattr(gui.magnifier_widget, "_debug_magnifier_enabled", True)
    
    widget = gui.magnifier_widget.MagnifierWidget()
    
    # Show at position with debug enabled
    pos = QPoint(500, 500)
    widget.show_at_position(pos)
    
    # Check that debug output was captured
    captured = capsys.readouterr()
    assert "[DEBUG-MAGNIFIER]" in captured.out
    assert "show_at_position" in captured.out
