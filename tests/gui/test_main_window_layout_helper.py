"""
Comprehensive unit tests for src/gui/main_window_layout_helper.py.

Achieves 100% statement and branch coverage for setup_main_window_content,
MainWindowPanels, and WindowSlotMapCallbacks.
"""

from unittest.mock import MagicMock

import pytest
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QWidget

from gui.main_window_layout_helper import (
    MainWindowPanels,
    WindowSlotMapCallbacks,
    setup_main_window_content,
)


class MockMainWindow(QWidget):
    """Minimal MainWindow mock widget for layout testing."""
    rescale_toggle_changed = Signal(bool)
    fusion_technical_doc_requested = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.center_panel = QWidget()
        self.left_panel = QWidget()
        self.right_panel = QWidget()
        self.set_series_navigator = MagicMock()


@pytest.fixture
def mock_panels(qapp) -> MainWindowPanels:
    """Fixture providing MainWindowPanels with child widgets."""
    return MainWindowPanels(
        multi_window_layout=QWidget(),
        cine_controls_widget=QWidget(),
        metadata_panel=QWidget(),
        window_level_controls=QWidget(),
        zoom_display_widget=QWidget(),
        roi_list_panel=QWidget(),
        roi_statistics_panel=QWidget(),
        intensity_projection_controls_widget=QWidget(),
        fusion_controls_widget=QWidget(),
        series_navigator=QWidget(),
    )



@pytest.fixture
def mock_slot_map() -> WindowSlotMapCallbacks:
    """Fixture providing WindowSlotMapCallbacks."""
    return WindowSlotMapCallbacks(
        get_slot_to_view=MagicMock(),
        get_layout_mode=MagicMock(),
        get_focused_view_index=MagicMock(),
        get_thumbnail_for_view=MagicMock(),
    )


def test_dataclasses_instantiation(mock_panels: MainWindowPanels, mock_slot_map: WindowSlotMapCallbacks) -> None:
    """Test MainWindowPanels and WindowSlotMapCallbacks dataclass initialization."""
    assert mock_panels.multi_window_layout is not None
    assert mock_slot_map.get_slot_to_view is not None


def test_setup_main_window_content_new_layouts(
    qapp, mock_panels: MainWindowPanels, mock_slot_map: WindowSlotMapCallbacks
) -> None:
    """Test setup_main_window_content creates new layouts when panels have no pre-existing layouts."""
    main_window = MockMainWindow()

    setup_main_window_content(main_window, mock_panels, slot_map=mock_slot_map)

    assert main_window.center_panel.layout() is not None
    assert main_window.left_panel.layout() is not None
    assert main_window.right_panel.layout() is not None

    assert hasattr(main_window, "use_rescaled_values_checkbox")
    assert hasattr(main_window, "wl_presets_row_layout")
    main_window.set_series_navigator.assert_called_once_with(mock_panels.series_navigator)


def test_setup_main_window_content_existing_layouts(
    qapp, mock_panels: MainWindowPanels, mock_slot_map: WindowSlotMapCallbacks
) -> None:
    """Test setup_main_window_content reuses existing layouts on center, left, and right panels."""
    from PySide6.QtWidgets import QVBoxLayout

    main_window = MockMainWindow()
    center_layout = QVBoxLayout(main_window.center_panel)
    left_layout = QVBoxLayout(main_window.left_panel)
    right_layout = QVBoxLayout(main_window.right_panel)

    setup_main_window_content(main_window, mock_panels, slot_map=mock_slot_map)

    assert main_window.center_panel.layout() is center_layout
    assert main_window.left_panel.layout() is left_layout
    assert main_window.right_panel.layout() is right_layout


def test_setup_main_window_content_slot_map_callbacks_success(
    qapp, mock_panels: MainWindowPanels, mock_slot_map: WindowSlotMapCallbacks
) -> None:
    """Test wiring window-slot map callbacks when set_window_slot_map_callbacks and show_window_slot_map_action exist."""
    main_window = MockMainWindow()
    main_window.set_window_slot_map_callbacks = MagicMock()
    main_window.set_window_slot_map_visible = MagicMock()

    action = MagicMock()
    action.isChecked.return_value = True
    main_window.show_window_slot_map_action = action

    setup_main_window_content(main_window, mock_panels, slot_map=mock_slot_map)

    main_window.set_window_slot_map_callbacks.assert_called_once_with(
        get_slot_to_view=mock_slot_map.get_slot_to_view,
        get_layout_mode=mock_slot_map.get_layout_mode,
        get_focused_view_index=mock_slot_map.get_focused_view_index,
        get_thumbnail_for_view=mock_slot_map.get_thumbnail_for_view,
    )
    main_window.set_window_slot_map_visible.assert_called_once_with(True)


def test_setup_main_window_content_slot_map_callbacks_exception_handled(
    qapp, mock_panels: MainWindowPanels, mock_slot_map: WindowSlotMapCallbacks
) -> None:
    """Test exception in set_window_slot_map_callbacks is safely caught without raising."""
    main_window = MockMainWindow()
    main_window.set_window_slot_map_callbacks = MagicMock(side_effect=Exception("Wiring exception"))

    # Should not raise exception
    setup_main_window_content(main_window, mock_panels, slot_map=mock_slot_map)


def test_setup_main_window_content_slot_map_no_action(
    qapp, mock_panels: MainWindowPanels, mock_slot_map: WindowSlotMapCallbacks
) -> None:
    """Test window-slot map wiring when set_window_slot_map_callbacks exists but show_window_slot_map_action is missing."""
    main_window = MockMainWindow()
    main_window.set_window_slot_map_callbacks = MagicMock()

    setup_main_window_content(main_window, mock_panels, slot_map=mock_slot_map)

    main_window.set_window_slot_map_callbacks.assert_called_once()
    assert not hasattr(main_window, "set_window_slot_map_visible")


def test_flaw_setup_content_raises_attribute_error_when_rescale_signal_missing(
    qapp, mock_panels: MainWindowPanels, mock_slot_map: WindowSlotMapCallbacks
) -> None:
    """Document flaw: setup_main_window_content raises AttributeError if main_window lacks rescale_toggle_changed."""
    main_window = QWidget()  # Standard QWidget lacking rescale_toggle_changed signal
    main_window.center_panel = QWidget()
    main_window.left_panel = QWidget()
    main_window.right_panel = QWidget()
    main_window.set_series_navigator = MagicMock()

    with pytest.raises(AttributeError, match="has no attribute 'rescale_toggle_changed'"):
        setup_main_window_content(main_window, mock_panels, slot_map=mock_slot_map)


def test_flaw_setup_content_silently_swallows_slot_map_wiring_exceptions(
    qapp, mock_panels: MainWindowPanels, mock_slot_map: WindowSlotMapCallbacks
) -> None:
    """Document flaw: exceptions in set_window_slot_map_callbacks are silently swallowed with bare except Exception: pass."""
    main_window = MockMainWindow()
    main_window.set_window_slot_map_callbacks = MagicMock(
        side_effect=RuntimeError("Thumbnail wiring failure")
    )

    # Bare except Exception: pass swallows the error silently without raising
    setup_main_window_content(main_window, mock_panels, slot_map=mock_slot_map)
    main_window.set_window_slot_map_callbacks.assert_called_once()
