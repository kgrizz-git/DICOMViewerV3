"""
Characterization tests for the ``UIHandlersMixin`` and ``InitializationMixin`` bodies.

The one-line forwards live in the case tables. These cover methods whose body
does more: the series-assignment sender gate, the study-index consent and
cancellation paths, the keyboard-shortcuts dialog, and the main-window panel
bundle assembled by ``_setup_ui``.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest
from main_mixin_delegation_support import _stub_for

# --- InitializationMixin: main-window panel assembly -------------------------------


_PANEL_ATTRS = (
    "multi_window_layout",
    "cine_controls_widget",
    "metadata_panel",
    "window_level_controls",
    "zoom_display_widget",
    "roi_list_panel",
    "roi_statistics_panel",
    "intensity_projection_controls_widget",
    "fusion_controls_widget",
    "series_navigator",
)


def test_setup_ui_routes_every_panel_and_callback_into_the_bundle(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Each widget must reach ``MainWindowPanels`` / ``WindowSlotMapCallbacks`` intact.

    ``_setup_ui`` is a single call, but it assembles two bundles rather than
    forwarding references, so it cannot be expressed as a case-table row. A
    swapped panel — e.g. ``roi_list_panel`` passed where ``metadata_panel`` is
    expected — would otherwise reach the layout helper silently.
    """
    import main_app_initialization as init_module
    from gui.main_window_layout_helper import MainWindowPanels, WindowSlotMapCallbacks

    attrs: dict[str, Any] = {name: MagicMock(name=name) for name in _PANEL_ATTRS}
    attrs["main_window"] = MagicMock(name="main_window")
    attrs["get_focused_subwindow_index"] = MagicMock(name="get_focused_subwindow_index")
    attrs["_get_thumbnail_for_view"] = MagicMock(name="_get_thumbnail_for_view")
    stub = _stub_for("InitializationMixin", **attrs)

    captured: dict[str, Any] = {}
    monkeypatch.setattr(
        init_module,
        "setup_main_window_content",
        lambda main_window, panels_arg, slot_map=None: captured.update(
            {"main_window": main_window, "panels": panels_arg, "slot_map": slot_map}
        ),
    )

    stub._setup_ui()

    assert captured["main_window"] is attrs["main_window"]
    built = captured["panels"]
    assert isinstance(built, MainWindowPanels)
    for name in _PANEL_ATTRS:
        assert getattr(built, name) is attrs[name], f"{name} was not routed into the panel bundle"

    slot_map = captured["slot_map"]
    assert isinstance(slot_map, WindowSlotMapCallbacks)
    assert slot_map.get_focused_view_index is attrs["get_focused_subwindow_index"]
    assert slot_map.get_thumbnail_for_view is attrs["_get_thumbnail_for_view"]
    # The layout itself is the source of the two slot-map state callbacks.
    assert slot_map.get_slot_to_view is attrs["multi_window_layout"].get_slot_to_view
    assert slot_map.get_layout_mode is attrs["multi_window_layout"].get_layout_mode


# --- UIHandlersMixin: the three bodies no other test executed ----------------------


def test_on_assign_series_requested_routes_a_subwindow_sender() -> None:
    """A request from a real pane must carry that pane plus the target study."""
    from gui.sub_window_container import SubWindowContainer

    controller = MagicMock(name="lifecycle_controller")
    stub = _stub_for("UIHandlersMixin", _subwindow_lifecycle_controller=controller)
    pane = MagicMock(spec=SubWindowContainer)
    stub.sender = MagicMock(return_value=pane)

    stub._on_assign_series_requested("1.2.3", 4, "1.2")

    controller.assign_series_to_subwindow.assert_called_once_with(
        pane, "1.2.3", 4, target_study_uid="1.2"
    )


def test_on_assign_series_requested_defaults_the_target_study_to_none() -> None:
    """An empty ``study_uid`` must reach the controller as ``None``, not ``""``.

    The controller treats the two differently, so an empty string leaking
    through would change which study a series lands in.
    """
    from gui.sub_window_container import SubWindowContainer

    controller = MagicMock(name="lifecycle_controller")
    stub = _stub_for("UIHandlersMixin", _subwindow_lifecycle_controller=controller)
    pane = MagicMock(spec=SubWindowContainer)
    stub.sender = MagicMock(return_value=pane)

    stub._on_assign_series_requested("1.2.3", 0)

    controller.assign_series_to_subwindow.assert_called_once_with(
        pane, "1.2.3", 0, target_study_uid=None
    )


def test_on_assign_series_requested_ignores_a_non_pane_sender() -> None:
    """A stray signal from another widget must not reach the lifecycle controller."""
    controller = MagicMock(name="lifecycle_controller")
    stub = _stub_for("UIHandlersMixin", _subwindow_lifecycle_controller=controller)
    stub.sender = MagicMock(return_value=MagicMock(name="toolbar_button"))

    stub._on_assign_series_requested("1.2.3", 0)

    controller.assign_series_to_subwindow.assert_not_called()


def test_on_study_index_after_load_schedules_without_prompting(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Backend available and consent already recorded: index, but never prompt.

    The argument order is the load-bearing part here — ``merge_paths`` and
    ``source_dir`` are easy to transpose, and the two are different things.
    """
    import main_app_ui_and_files as ui_module

    service = MagicMock(name="study_index_service")
    service.is_backend_available.return_value = True
    config = MagicMock(name="config_manager")
    config.needs_study_index_auto_add_consent.return_value = False
    stub = _stub_for("UIHandlersMixin", study_index_service=service, config_manager=config)
    prompt = MagicMock(name="prompt")
    monkeypatch.setattr(ui_module, "prompt_study_index_first_open", prompt)

    datasets, merge_result, source_dir, merge_paths = [1], "MERGE", "/src", ["/src/a.dcm"]
    stub._on_study_index_after_load(datasets, {"ignored": 1}, merge_result, source_dir, merge_paths)

    prompt.assert_not_called()
    service.schedule_index_after_load.assert_called_once_with(
        datasets, merge_paths, source_dir, merge_result, was_cancelled=False, force=False
    )


def test_on_study_index_after_load_forces_index_when_the_user_chooses_add_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """\"Add this one time\" indexes the batch without recording consent."""
    import main_app_ui_and_files as ui_module
    from gui.study_index_consent import StudyIndexOpenChoice

    service = MagicMock(name="study_index_service")
    service.is_backend_available.return_value = True
    config = MagicMock(name="config_manager")
    config.needs_study_index_auto_add_consent.return_value = True
    stub = _stub_for("UIHandlersMixin", study_index_service=service, config_manager=config)
    stub.main_window = MagicMock(name="main_window")
    prompt = MagicMock(return_value=StudyIndexOpenChoice.ADD_ONCE)
    monkeypatch.setattr(ui_module, "prompt_study_index_first_open", prompt)

    stub._on_study_index_after_load([], {}, "MERGE", "/src", [])

    prompt.assert_called_once_with(config, stub.main_window)
    assert service.schedule_index_after_load.call_args.kwargs["force"] is True


def test_on_study_index_after_load_does_not_prompt_when_the_backend_is_absent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An unavailable backend must skip the consent prompt entirely."""
    import main_app_ui_and_files as ui_module

    service = MagicMock(name="study_index_service")
    service.is_backend_available.return_value = False
    config = MagicMock(name="config_manager")
    stub = _stub_for("UIHandlersMixin", study_index_service=service, config_manager=config)
    prompt = MagicMock(name="prompt")
    monkeypatch.setattr(ui_module, "prompt_study_index_first_open", prompt)

    stub._on_study_index_after_load([], {}, "MERGE", "/src", [])

    prompt.assert_not_called()
    config.needs_study_index_auto_add_consent.assert_not_called()
    assert service.schedule_index_after_load.call_args.kwargs["force"] is False


def test_on_study_index_after_load_toasts_and_skips_the_prompt_when_cancelled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A cancelled load still schedules (to free caches) but must not ask consent."""
    import main_app_ui_and_files as ui_module

    service = MagicMock(name="study_index_service")
    service.is_backend_available.return_value = True
    config = MagicMock(name="config_manager")
    stub = _stub_for("UIHandlersMixin", study_index_service=service, config_manager=config)
    toast = MagicMock(name="toast")
    prompt = MagicMock(name="prompt")
    monkeypatch.setattr(ui_module, "show_cancelled_index_skip_toast", toast)
    monkeypatch.setattr(ui_module, "prompt_study_index_first_open", prompt)

    stub._on_study_index_after_load([], {}, "MERGE", "/src", [], was_cancelled=True)

    toast.assert_called_once_with(stub)
    prompt.assert_not_called()
    service.schedule_index_after_load.assert_called_once_with(
        [], [], "/src", "MERGE", was_cancelled=True, force=False
    )


def test_on_keyboard_shortcuts_requested_opens_a_modal_dialog(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """F1 / Help must open the shortcuts dialog on the main window and exec it."""
    import gui.dialogs.keyboard_shortcuts_dialog as dialog_module

    built: dict[str, Any] = {}

    class _FakeDialog:
        def __init__(self, parent: Any) -> None:
            built["parent"] = parent
            built["execd"] = 0

        def exec(self) -> int:
            built["execd"] += 1
            return 0

    monkeypatch.setattr(dialog_module, "KeyboardShortcutsDialog", _FakeDialog)
    main_window = MagicMock(name="main_window")
    stub = _stub_for("UIHandlersMixin", main_window=main_window)

    stub._on_keyboard_shortcuts_requested()

    assert built["parent"] is main_window
    assert built["execd"] == 1
