"""
Comprehensive unit tests for src/gui/app_handler_bootstrap.py.

Achieves 100% statement and branch coverage for initialize_handlers.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from gui.app_handler_bootstrap import initialize_handlers


@pytest.fixture
def mock_app() -> SimpleNamespace:
    """Create a fully populated mock DICOMViewerApp instance."""
    app = SimpleNamespace()

    # Image viewer and main window
    app.image_viewer = MagicMock()
    app.main_window = MagicMock()
    app.main_window.image_viewer = app.image_viewer
    app.main_window.update_status = MagicMock()

    # Layout and subwindows
    app.multi_window_layout = MagicMock()
    subwindow = MagicMock()
    subwindow.image_viewer = app.image_viewer
    app.multi_window_layout.get_all_subwindows.return_value = [subwindow]

    # Managers required for KeyboardEventHandler and bootstrap
    app.roi_coordinator = MagicMock()
    app.measurement_coordinator = MagicMock()
    app.text_annotation_coordinator = MagicMock()
    app.arrow_annotation_coordinator = MagicMock()
    app.crosshair_coordinator = MagicMock()
    app.overlay_coordinator = MagicMock()

    app.roi_manager = MagicMock()
    app.measurement_tool = MagicMock()
    app.text_annotation_tool = MagicMock()
    app.arrow_annotation_tool = MagicMock()
    app.crosshair_manager = MagicMock()
    app.overlay_manager = MagicMock()

    app.view_state_manager = MagicMock()
    app.slice_display_manager = MagicMock()
    app.metadata_controller = MagicMock()

    app.subwindow_managers = {
        0: {
            "view_state_manager": app.view_state_manager,
            "slice_display_manager": app.slice_display_manager,
            "roi_coordinator": app.roi_coordinator,
            "measurement_coordinator": app.measurement_coordinator,
            "text_annotation_coordinator": app.text_annotation_coordinator,
            "arrow_annotation_coordinator": app.arrow_annotation_coordinator,
            "crosshair_coordinator": app.crosshair_coordinator,
            "overlay_coordinator": app.overlay_coordinator,
            "roi_manager": app.roi_manager,
            "measurement_tool": app.measurement_tool,
            "text_annotation_tool": app.text_annotation_tool,
            "arrow_annotation_tool": app.arrow_annotation_tool,
            "crosshair_manager": app.crosshair_manager,
            "overlay_manager": app.overlay_manager,
        }
    }

    # Configuration, loader, organizer, dialogs
    app.config_manager = MagicMock()
    app.config_manager.get_cine_default_speed.return_value = 10
    app.config_manager.get_cine_default_loop.return_value = True

    app.dicom_loader = MagicMock()
    app.dicom_organizer = MagicMock()
    app.file_dialog = MagicMock()

    app.current_studies = []
    app.tag_edit_history = MagicMock()
    app.undo_redo_manager = MagicMock()
    app._mpr_controller = MagicMock()
    app.slice_navigator = MagicMock()
    app.cine_controls_widget = MagicMock()
    app.roi_statistics_panel = MagicMock()
    app.subwindow_data = {}

    # Callbacks
    app._clear_data = MagicMock()
    app._on_study_index_after_load = MagicMock()
    app._on_settings_applied = MagicMock()
    app._on_overlay_config_applied = MagicMock()
    app.get_histogram_callbacks_for_subwindow = MagicMock()
    app.get_focused_subwindow_index = MagicMock(return_value=0)
    app._refresh_tag_ui = MagicMock()
    app._open_wl_preset_manager = MagicMock()
    app._on_annotation_options_applied = MagicMock()
    app._on_tag_edited = MagicMock()
    app._on_undo_requested = MagicMock()
    app._on_redo_requested = MagicMock()
    app._apply_imported_customizations = MagicMock()
    app._connect_all_subwindow_context_menu_signals = MagicMock()
    app._cycle_overlay_detail_mode = MagicMock()
    app._keyboard_delete_roi = MagicMock()
    app._update_roi_list = MagicMock()
    app._on_reset_all_views = MagicMock()
    app._open_quick_window_level = MagicMock()

    return app


def test_initialize_handlers_success(mock_app: SimpleNamespace) -> None:
    """Test initialize_handlers successfully instantiates and attaches all handlers to app."""
    with patch("gui.app_handler_bootstrap.LocalStudyIndexService"):
        initialize_handlers(mock_app)

        assert hasattr(mock_app, "_file_series_coordinator")
        assert hasattr(mock_app, "study_index_service")
        assert hasattr(mock_app, "file_operations_handler")
        assert hasattr(mock_app, "dialog_coordinator")
        assert hasattr(mock_app, "_privacy_controller")
        assert hasattr(mock_app, "_customization_handlers")
        assert hasattr(mock_app, "mouse_mode_handler")
        assert hasattr(mock_app, "cine_player")
        assert hasattr(mock_app, "cine_app_facade")
        assert hasattr(mock_app, "keyboard_event_handler")

        # Verify context menu signal wiring called
        mock_app._connect_all_subwindow_context_menu_signals.assert_called_once()

        # Test undo/redo callbacks assigned to dialog_coordinator
        callbacks = mock_app.dialog_coordinator.undo_redo_callbacks
        callbacks[0]()  # undo
        mock_app._on_undo_requested.assert_called_once()

        callbacks[1]()  # redo
        mock_app._on_redo_requested.assert_called_once()

        mock_app.undo_redo_manager.can_undo.return_value = True
        assert callbacks[2]() is True

        mock_app.undo_redo_manager.can_redo.return_value = False
        assert callbacks[3]() is False

        # Test when undo_redo_manager is None
        mock_app.undo_redo_manager = None
        assert callbacks[2]() is False
        assert callbacks[3]() is False


def test_initialize_handlers_fallback_subwindow_managers(
    mock_app: SimpleNamespace,
) -> None:
    """Test initialize_handlers falls back to subwindow_managers[0] when app.roi_coordinator is missing."""
    delattr(mock_app, "roi_coordinator")

    with patch("gui.app_handler_bootstrap.LocalStudyIndexService"):
        initialize_handlers(mock_app)

        assert mock_app.roi_coordinator is not None
        assert mock_app.image_viewer is not None


def test_initialize_handlers_fallback_subwindows_first_element_falsy(
    mock_app: SimpleNamespace,
) -> None:
    """Test fallback branch when subwindows list contains None as first element (hits 69->75 branch)."""
    delattr(mock_app, "roi_coordinator")
    mock_app.multi_window_layout.get_all_subwindows.return_value = [None]
    original_image_viewer = mock_app.image_viewer

    with patch("gui.app_handler_bootstrap.LocalStudyIndexService"):
        initialize_handlers(mock_app)

    # Managers are recovered from subwindow_managers[0], but the falsy first
    # subwindow must not overwrite the existing image_viewer, and setup still
    # completes through keyboard-handler wiring.
    assert mock_app.roi_coordinator is not None
    assert mock_app.image_viewer is original_image_viewer
    assert mock_app.keyboard_event_handler is not None


def test_initialize_handlers_raises_when_no_subwindow_managers(
    mock_app: SimpleNamespace,
) -> None:
    """Test initialize_handlers raises RuntimeError if managers missing and no subwindows exist."""
    delattr(mock_app, "roi_coordinator")
    mock_app.multi_window_layout.get_all_subwindows.return_value = []

    with pytest.raises(RuntimeError, match="No subwindow managers available"):
        initialize_handlers(mock_app)


def test_initialize_handlers_raises_when_image_viewer_is_none(
    mock_app: SimpleNamespace,
) -> None:
    """Test initialize_handlers raises RuntimeError if image_viewer is None."""
    mock_app.image_viewer = None

    with pytest.raises(RuntimeError, match="image_viewer must be set"):
        initialize_handlers(mock_app)


def test_initialize_handlers_raises_when_keyboard_managers_missing(
    mock_app: SimpleNamespace,
) -> None:
    """Test initialize_handlers raises RuntimeError if required KeyboardEventHandler managers missing."""
    mock_app.roi_manager = None

    with (
        patch("gui.app_handler_bootstrap.LocalStudyIndexService"),
        pytest.raises(RuntimeError, match="Required managers not initialized"),
    ):
        initialize_handlers(mock_app)


def test_undo_callback_requires_initialized_app_handler(
    mock_app: SimpleNamespace,
) -> None:
    """Undo callbacks are only valid after complete application initialization."""
    delattr(mock_app, "_on_undo_requested")

    with patch("gui.app_handler_bootstrap.LocalStudyIndexService"):
        initialize_handlers(mock_app)
        undo_cb = mock_app.dialog_coordinator.undo_redo_callbacks[0]
        with pytest.raises(
            AttributeError,
            match=r"'types.SimpleNamespace' object has no attribute '_on_undo_requested'",
        ):
            undo_cb()


def test_fallback_rejects_missing_required_image_viewer(
    mock_app: SimpleNamespace,
) -> None:
    """Fallback setup rejects an incomplete subwindow rather than continuing."""
    delattr(mock_app, "roi_coordinator")
    existing_viewer = MagicMock()
    mock_app.image_viewer = existing_viewer

    # Subwindow 0 exists but has image_viewer = None
    sub0 = SimpleNamespace(image_viewer=None)
    mock_app.multi_window_layout.get_all_subwindows.return_value = [sub0]

    with patch("gui.app_handler_bootstrap.LocalStudyIndexService"):  # noqa: SIM117
        with pytest.raises(RuntimeError, match="image_viewer must be set"):
            initialize_handlers(mock_app)
