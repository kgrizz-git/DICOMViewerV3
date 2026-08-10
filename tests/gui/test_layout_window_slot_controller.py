"""
Comprehensive unit tests for src/gui/layout_window_slot_controller.py.

Achieves 100% statement and branch coverage for layout_window_slot_controller.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtCore import QRect
from PySide6.QtWidgets import QWidget

from gui.image_viewer import ImageViewer
from gui.layout_window_slot_controller import (
    capture_subwindow_view_states,
    connect_all_subwindow_context_menu_signals,
    connect_all_subwindow_transform_signals,
    ensure_all_subwindows_have_managers,
    on_expand_to_1x1_requested,
    on_layout_change_requested,
    on_layout_changed,
    on_main_window_layout_changed,
    on_swap_view_requested,
    on_window_slot_map_cell_clicked,
    on_window_slot_map_popup_requested,
    refresh_window_slot_map_widgets,
    restore_subwindow_views,
)
from gui.sub_window_container import SubWindowContainer


@pytest.fixture
def mock_app(qapp) -> SimpleNamespace:
    """Fixture providing a mock DICOMViewerApp instance with real QWidget main_window."""
    app = SimpleNamespace()
    app._subwindow_lifecycle_controller = MagicMock()
    app._slice_location_line_coordinator = MagicMock()
    app.multi_window_layout = MagicMock()

    # PySide6 QWidget parent for dialogs
    main_win = QWidget()
    main_win.window_slot_map_widget = MagicMock()
    main_win.config_manager = MagicMock()
    main_win.update_status = MagicMock()
    main_win.frameGeometry = MagicMock(return_value=QRect(0, 0, 800, 600))
    app.main_window = main_win

    app.series_navigator = MagicMock()
    app.config_manager = MagicMock()
    app._get_subwindow_assignments = MagicMock(return_value={})
    app.get_focused_subwindow_index = MagicMock(return_value=0)
    app._get_thumbnail_for_view = MagicMock(return_value=None)
    app._on_window_slot_map_cell_clicked = MagicMock()
    app.sender = MagicMock(return_value=None)
    return app


def test_on_layout_changed(mock_app: SimpleNamespace) -> None:
    """Test on_layout_changed delegates to lifecycle controller and triggers refreshes."""
    with patch("gui.layout_window_slot_controller.refresh_window_slot_map_widgets") as mock_refresh:
        on_layout_changed(mock_app, "2x2")
        mock_app._subwindow_lifecycle_controller.on_layout_changed.assert_called_once_with("2x2")
        mock_refresh.assert_called_once_with(mock_app)


def test_on_main_window_layout_changed(mock_app: SimpleNamespace) -> None:
    """Test on_main_window_layout_changed delegates to lifecycle controller."""
    on_main_window_layout_changed(mock_app, "1x2")
    mock_app._subwindow_lifecycle_controller.on_main_window_layout_changed.assert_called_once_with("1x2")


def test_lifecycle_delegates(mock_app: SimpleNamespace) -> None:
    """Test thin delegate functions passing through to lifecycle controller."""
    states = {0: {"zoom": 1.0}}
    mock_app._subwindow_lifecycle_controller.capture_subwindow_view_states.return_value = states

    assert capture_subwindow_view_states(mock_app) == states
    mock_app._subwindow_lifecycle_controller.capture_subwindow_view_states.assert_called_once()

    restore_subwindow_views(mock_app, states)
    mock_app._subwindow_lifecycle_controller.restore_subwindow_views.assert_called_once_with(states)

    ensure_all_subwindows_have_managers(mock_app)
    mock_app._subwindow_lifecycle_controller.ensure_all_subwindows_have_managers.assert_called_once()

    connect_all_subwindow_transform_signals(mock_app)
    mock_app._subwindow_lifecycle_controller.connect_all_subwindow_transform_signals.assert_called_once()

    connect_all_subwindow_context_menu_signals(mock_app)
    mock_app._subwindow_lifecycle_controller.connect_all_subwindow_context_menu_signals.assert_called_once()

    on_layout_change_requested(mock_app, "1x1")
    mock_app._subwindow_lifecycle_controller.on_layout_change_requested.assert_called_once_with("1x1")


def test_on_expand_to_1x1_requested_not_subwindow_container(mock_app: SimpleNamespace) -> None:
    """Test on_expand_to_1x1_requested when sender is not a SubWindowContainer."""
    mock_app.sender.return_value = MagicMock()  # Not a SubWindowContainer
    on_expand_to_1x1_requested(mock_app)
    mock_app.multi_window_layout.set_layout.assert_not_called()


def test_on_expand_to_1x1_requested_revert_from_1x1(mock_app: SimpleNamespace, qapp) -> None:
    """Test on_expand_to_1x1_requested when layout is currently 1x1 (reverts to previous layout)."""
    container = MagicMock(spec=SubWindowContainer)
    mock_app.sender.return_value = container
    mock_app.multi_window_layout.get_layout_mode.return_value = "1x1"
    mock_app.multi_window_layout.get_revert_layout.return_value = "2x2"

    on_expand_to_1x1_requested(mock_app)
    mock_app.multi_window_layout.set_layout.assert_called_once_with("2x2")


def test_on_expand_to_1x1_requested_expand_to_1x1(mock_app: SimpleNamespace, qapp) -> None:
    """Test on_expand_to_1x1_requested when layout is not 1x1 (expands focused subwindow to 1x1)."""
    container = MagicMock(spec=SubWindowContainer)
    mock_app.sender.return_value = container
    mock_app.multi_window_layout.get_layout_mode.return_value = "2x2"

    on_expand_to_1x1_requested(mock_app)
    mock_app.multi_window_layout.set_focused_subwindow.assert_called_once_with(container)
    mock_app.multi_window_layout.set_layout.assert_called_once_with("1x1")


def test_on_swap_view_requested_guards(mock_app: SimpleNamespace) -> None:
    """Test on_swap_view_requested early return guards."""
    # 1. Sender is not ImageViewer
    mock_app.sender.return_value = MagicMock()
    on_swap_view_requested(mock_app, 1)
    mock_app.multi_window_layout.swap_views.assert_not_called()

    # 2. Sender is ImageViewer but subwindow_index is None
    viewer = MagicMock(spec=ImageViewer)
    viewer.subwindow_index = None
    mock_app.sender.return_value = viewer
    on_swap_view_requested(mock_app, 1)
    mock_app.multi_window_layout.swap_views.assert_not_called()

    # 3. Invalid other_index (< 0, >= 4, or == subwindow_index)
    viewer.subwindow_index = 1
    mock_app.sender.return_value = viewer

    on_swap_view_requested(mock_app, -1)
    mock_app.multi_window_layout.swap_views.assert_not_called()

    on_swap_view_requested(mock_app, 4)
    mock_app.multi_window_layout.swap_views.assert_not_called()

    on_swap_view_requested(mock_app, 1)  # same as sender index
    mock_app.multi_window_layout.swap_views.assert_not_called()


def test_on_swap_view_requested_valid_swaps(mock_app: SimpleNamespace) -> None:
    """Test on_swap_view_requested in 2x2 and non-2x2 layout modes."""
    viewer = MagicMock(spec=ImageViewer)
    viewer.subwindow_index = 0
    mock_app.sender.return_value = viewer

    # Case A: layout is "1x2" (not "2x2") -> updates status bar
    mock_app.multi_window_layout.get_layout_mode.return_value = "1x2"
    on_swap_view_requested(mock_app, 1)
    mock_app.multi_window_layout.swap_views.assert_called_once_with(0, 1)
    mock_app._subwindow_lifecycle_controller.schedule_viewport_resized.assert_called_once()
    mock_app.main_window.update_status.assert_called_once_with(
        "Slot order updated; switch to 2x2 to see positions."
    )
    mock_app.series_navigator.set_subwindow_assignments.assert_called_once()

    # Case B: layout is "2x2" -> status bar not updated
    mock_app.main_window.update_status.reset_mock()
    mock_app.multi_window_layout.get_layout_mode.return_value = "2x2"
    on_swap_view_requested(mock_app, 2)
    mock_app.main_window.update_status.assert_not_called()


def test_refresh_window_slot_map_widgets_embedded_and_popup(mock_app: SimpleNamespace) -> None:
    """Test refresh_window_slot_map_widgets with embedded widget and popup widget."""
    widget = MagicMock()
    mock_app.main_window.window_slot_map_widget = widget

    popup_widget = MagicMock()
    mock_app._window_slot_map_widget_popup = popup_widget

    refresh_window_slot_map_widgets(mock_app)
    widget.refresh.assert_called_once()
    popup_widget.refresh.assert_called_once()

    # Test exception handling in refresh and connect
    widget.cell_clicked.connect.side_effect = Exception("Connect error")
    widget.refresh.side_effect = Exception("Refresh error")
    popup_widget.cell_clicked.connect.side_effect = Exception("Connect error")
    popup_widget.refresh.side_effect = Exception("Refresh error")

    refresh_window_slot_map_widgets(mock_app)  # Should catch exceptions safely

    # Test when main_window.window_slot_map_widget is None but popup_widget is present
    mock_app.main_window.window_slot_map_widget = None
    popup_widget.refresh.reset_mock()
    refresh_window_slot_map_widgets(mock_app)
    popup_widget.refresh.assert_called_once()



def test_on_window_slot_map_cell_clicked_guards_and_success(mock_app: SimpleNamespace) -> None:
    """Test on_window_slot_map_cell_clicked under all guard conditions and valid click."""
    # 1. Exception in get_slot_to_view
    mock_app.multi_window_layout.get_slot_to_view.side_effect = Exception("Layout error")
    on_window_slot_map_cell_clicked(mock_app, 0)
    mock_app.multi_window_layout.set_focused_subwindow.assert_not_called()

    # Restore get_slot_to_view
    mock_app.multi_window_layout.get_slot_to_view.side_effect = None
    mock_app.multi_window_layout.get_slot_to_view.return_value = [0, 1, 2, 3]

    # 2. slot < 0 or slot >= len(stv)
    on_window_slot_map_cell_clicked(mock_app, -1)
    on_window_slot_map_cell_clicked(mock_app, 4)
    mock_app.multi_window_layout.set_focused_subwindow.assert_not_called()

    # 3. view_idx out of bounds of subwindows
    mock_app.multi_window_layout.get_all_subwindows.return_value = [SimpleNamespace()]
    on_window_slot_map_cell_clicked(mock_app, 2)  # stv[2] = 2 >= 1 subwindows
    mock_app.multi_window_layout.set_focused_subwindow.assert_not_called()

    # 4. subwindow is None
    mock_app.multi_window_layout.get_all_subwindows.return_value = [None, None, None, None]
    on_window_slot_map_cell_clicked(mock_app, 0)
    mock_app.multi_window_layout.set_focused_subwindow.assert_not_called()

    # 5. Valid click -> sets focused subwindow
    sub0 = SimpleNamespace(name="sub0")
    mock_app.multi_window_layout.get_all_subwindows.return_value = [sub0, None, None, None]
    on_window_slot_map_cell_clicked(mock_app, 0)
    mock_app.multi_window_layout.set_focused_subwindow.assert_called_once_with(sub0)


def test_on_window_slot_map_popup_requested_no_base_widget(mock_app: SimpleNamespace) -> None:
    """Test popup requested when main_window lacks window_slot_map_widget."""
    mock_app.main_window.window_slot_map_widget = None
    on_window_slot_map_popup_requested(mock_app)
    assert not hasattr(mock_app, "_window_slot_map_dialog")


def test_on_window_slot_map_popup_requested_toggle_close(mock_app: SimpleNamespace) -> None:
    """Test popup requested closes dialog if already visible (toggle behavior)."""
    dlg = MagicMock()
    dlg.isVisible.return_value = True
    mock_app._window_slot_map_dialog = dlg

    on_window_slot_map_popup_requested(mock_app)
    dlg.close.assert_called_once()


def test_on_window_slot_map_popup_requested_no_map_widget(mock_app: SimpleNamespace) -> None:
    """Test popup requested when dialog.get_map_widget returns None."""
    dlg = MagicMock()
    dlg.isVisible.return_value = False
    dlg.get_map_widget.return_value = None
    mock_app._window_slot_map_dialog = dlg

    on_window_slot_map_popup_requested(mock_app)
    dlg.get_map_widget.assert_called_once()


@patch("gui.layout_window_slot_controller.WindowSlotMapPopupDialog")
def test_on_window_slot_map_popup_requested_create_and_show_saved_pos(
    mock_dlg_cls: MagicMock, mock_app: SimpleNamespace
) -> None:
    """Test creating WindowSlotMapPopupDialog with saved position and position change callback."""
    mock_dlg = MagicMock()
    mock_widget = MagicMock()
    mock_dlg.get_map_widget.return_value = mock_widget
    mock_dlg.width.return_value = 100
    mock_dlg.height.return_value = 100
    mock_dlg_cls.return_value = mock_dlg

    mock_app.config_manager.get_layout_map_popup_position.return_value = (500, 400)

    on_window_slot_map_popup_requested(mock_app)

    mock_dlg_cls.assert_called_once()
    mock_dlg.show.assert_called_once()
    mock_dlg.raise_.assert_called_once()
    assert mock_app._window_slot_map_widget_popup is mock_widget

    # Extract on_position_changed callback passed to WindowSlotMapPopupDialog
    _, kwargs = mock_dlg_cls.call_args
    on_position_changed = kwargs["on_position_changed"]

    # Test callback execution
    on_position_changed(200, 300)
    mock_app.config_manager.set_layout_map_popup_position.assert_called_once_with(200, 300)

    # Test exception handling in callback
    mock_app.config_manager.set_layout_map_popup_position.side_effect = Exception("Config error")
    on_position_changed(200, 300)  # Should handle exception safely


@patch("gui.layout_window_slot_controller.WindowSlotMapPopupDialog")
def test_on_window_slot_map_popup_requested_existing_hidden_dialog_no_saved_pos(
    mock_dlg_cls: MagicMock, mock_app: SimpleNamespace
) -> None:
    """Test popup requested with existing hidden dialog, no saved position, and error resilience."""
    mock_dlg = MagicMock()
    mock_dlg.isVisible.return_value = False
    mock_widget = MagicMock()
    mock_dlg.get_map_widget.return_value = mock_widget
    mock_app._window_slot_map_dialog = mock_dlg

    # Saved position is None -> places near cursor
    mock_app.config_manager.get_layout_map_popup_position.return_value = None

    # Test exception handling in set_callbacks and cell_clicked.connect
    mock_widget.set_callbacks.side_effect = Exception("Callbacks error")
    mock_widget.cell_clicked.connect.side_effect = Exception("Connect error")

    on_window_slot_map_popup_requested(mock_app)
    mock_dlg.show.assert_called_once()
    mock_dlg.raise_.assert_called_once()


def test_on_swap_view_requested_rejects_index_outside_current_four_slot_contract(mock_app: SimpleNamespace) -> None:
    """The current application supports exactly four view slots."""
    viewer = MagicMock(spec=ImageViewer)
    viewer.subwindow_index = 0
    mock_app.sender.return_value = viewer
    mock_app.multi_window_layout.get_all_subwindows.return_value = [MagicMock() for _ in range(9)]

    on_swap_view_requested(mock_app, 5)
    mock_app.multi_window_layout.swap_views.assert_not_called()


@patch("gui.layout_window_slot_controller.WindowSlotMapPopupDialog")
def test_popup_uses_app_config_manager_for_accent(
    mock_dlg_cls: MagicMock, mock_app: SimpleNamespace
) -> None:
    """Popup set_callbacks wires get_accent_id from app.config_manager."""
    mock_dlg = MagicMock()
    mock_widget = MagicMock()
    mock_dlg.get_map_widget.return_value = mock_widget
    mock_dlg_cls.return_value = mock_dlg

    mock_app.config_manager.get_layout_map_popup_position.return_value = None

    on_window_slot_map_popup_requested(mock_app)

    mock_widget.set_callbacks.assert_called_once()
    kwargs = mock_widget.set_callbacks.call_args.kwargs
    assert kwargs["get_accent_id"] is mock_app.config_manager.get_accent
