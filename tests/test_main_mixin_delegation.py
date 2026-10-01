"""
Mixin delegation safety net for the ``main.py`` facade split.

Every method of the nine mixin classes in ``src/main_app_*.py`` is covered by
exactly one of:

* a case in :mod:`main_mixin_delegation_cases_handlers` /
  :mod:`main_mixin_delegation_cases_collaborators`, exercised by the two
  parametrized tests below — these pin the wiring, so a rewired slot or a
  dropped argument fails here instead of at runtime;
* a characterization test in one of the ``*_wiring`` modules, for the methods
  whose body does more than forward;
* the ``compound`` allow-list in :func:`_compound_allow_list`, whose entries are
  themselves checked by :func:`test_compound_allow_list_only_contains_genuinely_compound_methods`.

The allow-list is the weak link, so it is verified rather than trusted: the route
test below fails if a method has no route into a case table, and the AST check
fails if a single-call forward is allow-listed instead of tabulated. Both guards
were confirmed by mutation, not by inspection.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from main_mixin_delegation_cases_collaborators import (
    COLLABORATOR_CASES,
    LAYOUT_HANDLER_CASES,
)
from main_mixin_delegation_cases_handlers import HANDLER_CASES
from main_mixin_delegation_support import (
    MIXIN_MODULES,
    CollaboratorCase,
    HandlerCase,
    _mixin_class,
    _resolve_owner,
    _stub_for,
)


@pytest.mark.parametrize(
    "case",
    HANDLER_CASES + LAYOUT_HANDLER_CASES,
    ids=lambda c: f"{c.mixin_class}.{c.method}",
)
def test_mixin_forwards_to_module_handler(monkeypatch: pytest.MonkeyPatch, case: HandlerCase) -> None:
    """A mixin slot must call its module-level handler with ``(self, *args, **kwargs)``."""
    owner, attr = _resolve_owner(case.mixin_class, case.handler)
    recorder = MagicMock(name=case.handler)
    monkeypatch.setattr(owner, attr, recorder)

    stub = _stub_for(case.mixin_class)
    getattr(stub, case.method)(*case.args, **(case.kwargs or {}))

    recorder.assert_called_once_with(stub, *case.args, **(case.kwargs or {}))

    recorder.assert_called_once_with(stub, *case.args, **(case.kwargs or {}))


@pytest.mark.parametrize("case", COLLABORATOR_CASES, ids=lambda c: f"{c.mixin_class}.{c.method}")
def test_mixin_forwards_to_collaborator(case: CollaboratorCase) -> None:
    """A mixin slot must call the collaborator method with exactly the forwarded args."""
    collaborator = MagicMock(name=case.attribute)
    if case.returns is not None:
        getattr(collaborator, case.target).return_value = case.returns
    stub = _stub_for(case.mixin_class, **{case.attribute: collaborator})

    result = getattr(stub, case.method)(*case.args, **(case.kwargs or {}))

    getattr(collaborator, case.target).assert_called_once_with(
        *case.args, **(case.kwargs or {})
    )
    if case.returns is not None:
        assert result == case.returns


# --- compound bodies: a forward plus something else the table cannot express ---------


def test_redisplay_subwindow_slice_also_refreshes_slice_location_lines() -> None:
    """Redisplaying a pane must not leave its slice-location lines stale."""
    controller = MagicMock()
    line_coordinator = MagicMock()
    stub = _stub_for(
        "SubwindowManagementMixin",
        _subwindow_lifecycle_controller=controller,
        _slice_location_line_coordinator=line_coordinator,
    )

    stub._redisplay_subwindow_slice(1, True)

    controller.redisplay_subwindow_slice.assert_called_once_with(1, True)
    line_coordinator.refresh_all.assert_called_once_with()


def test_on_scroll_wheel_mode_changed_propagates_to_every_subwindow() -> None:
    """Scroll-wheel mode is global: every loaded pane's viewer must be updated."""
    viewers = [MagicMock(name=f"viewer{i}") for i in range(3)]
    subwindows = [MagicMock(name=f"sub{i}") for i in range(3)]
    for subwindow, viewer in zip(subwindows, viewers, strict=True):
        subwindow.image_viewer = viewer
    # An empty slot in the layout is skipped rather than raising.
    subwindows.append(None)
    layout = MagicMock()
    layout.get_all_subwindows.return_value = subwindows
    handler = MagicMock()
    stub = _stub_for("UIHandlersMixin", mouse_mode_handler=handler, multi_window_layout=layout)

    stub._on_scroll_wheel_mode_changed("zoom")

    handler.handle_scroll_wheel_mode_changed.assert_called_once_with("zoom")
    for viewer in viewers:
        viewer.set_scroll_wheel_mode.assert_called_once_with("zoom")


def test_on_context_menu_scroll_wheel_mode_changed_skips_global_propagation() -> None:
    """The context-menu variant is pane-local and must not touch other subwindows."""
    handler = MagicMock()
    layout = MagicMock()
    stub = _stub_for("UIHandlersMixin", mouse_mode_handler=handler, multi_window_layout=layout)

    stub._on_context_menu_scroll_wheel_mode_changed("slice")

    handler.handle_context_menu_scroll_wheel_mode_changed.assert_called_once_with("slice")
    layout.get_all_subwindows.assert_not_called()


def test_update_focused_subwindow_references_syncs_roi_measurement_controller() -> None:
    """Legacy focus pointers and the ROI measurement controller must move together."""
    controller = MagicMock()
    roi_measurement_controller = MagicMock()
    roi_manager = MagicMock()
    measurement_tool = MagicMock()
    stub = _stub_for(
        "SubwindowManagementMixin",
        _subwindow_lifecycle_controller=controller,
        roi_measurement_controller=roi_measurement_controller,
        roi_manager=roi_manager,
        measurement_tool=measurement_tool,
    )

    stub._update_focused_subwindow_references()

    controller.update_focused_subwindow_references.assert_called_once_with()
    roi_measurement_controller.update_focused_managers.assert_called_once_with(roi_manager, measurement_tool)


def test_update_focused_subwindow_references_tolerates_absent_roi_measurement_controller() -> None:
    """The legacy sync is optional: a missing controller must not raise."""
    controller = MagicMock()
    stub = _stub_for("SubwindowManagementMixin", _subwindow_lifecycle_controller=controller)

    stub._update_focused_subwindow_references()

    controller.update_focused_subwindow_references.assert_called_once_with()


def test_delete_all_rois_current_slice_also_clears_crosshairs() -> None:
    """Clearing ROIs on a slice must clear the crosshairs that pointed at them."""
    roi_coordinator = MagicMock()
    crosshair_coordinator = MagicMock()
    stub = _stub_for(
        "ROIWorkflowMixin",
        roi_coordinator=roi_coordinator,
        crosshair_coordinator=crosshair_coordinator,
    )

    stub._delete_all_rois_current_slice()

    roi_coordinator.delete_all_rois_current_slice.assert_called_once_with()
    crosshair_coordinator.handle_clear_crosshairs.assert_called_once_with()


def test_delete_all_rois_current_slice_skips_absent_crosshair_coordinator() -> None:
    """``crosshair_coordinator`` is optional; the ROI clear must still run."""
    roi_coordinator = MagicMock()
    stub = _stub_for("ROIWorkflowMixin", roi_coordinator=roi_coordinator)

    stub._delete_all_rois_current_slice()

    roi_coordinator.delete_all_rois_current_slice.assert_called_once_with()


def test_keyboard_delete_roi_unwraps_item_attribute() -> None:
    """A wrapper object carrying ``.item`` is unwrapped, not deleted directly."""
    roi_coordinator = MagicMock()
    roi_manager = MagicMock()
    stub = _stub_for("ROIWorkflowMixin", roi_coordinator=roi_coordinator, roi_manager=roi_manager)

    inner = MagicMock(name="inner_roi")
    wrapper = MagicMock(spec=["item"])
    wrapper.item = inner
    stub._keyboard_delete_roi(wrapper)

    roi_coordinator.handle_roi_delete_requested.assert_called_once_with(inner)
    roi_manager.delete_roi.assert_not_called()


def test_keyboard_delete_roi_falls_back_to_roi_manager_for_bare_item() -> None:
    """A bare ``ROIItem`` (no ``.item``) is deleted through the ROI manager + scene."""
    roi_coordinator = MagicMock()
    roi_manager = MagicMock()
    viewer = MagicMock(name="viewer")
    stub = _stub_for(
        "ROIWorkflowMixin",
        roi_coordinator=roi_coordinator,
        roi_manager=roi_manager,
        image_viewer=viewer,
    )

    class _BareRoi:
        """A plain ROI with no ``.item`` wrapper attribute."""

    roi = _BareRoi()
    stub._keyboard_delete_roi(roi)

    roi_manager.delete_roi.assert_called_once_with(roi, viewer.scene)
    roi_coordinator.handle_roi_delete_requested.assert_not_called()


def test_keyboard_delete_roi_without_viewer_is_a_no_op() -> None:
    """No viewer means no scene to delete from; the request is dropped, not raised."""
    roi_manager = MagicMock()
    stub = _stub_for("ROIWorkflowMixin", roi_manager=roi_manager, image_viewer=None)

    class _BareRoi:
        """A plain ROI with no ``.item`` wrapper attribute."""

    stub._keyboard_delete_roi(_BareRoi())

    roi_manager.delete_roi.assert_not_called()


def test_schedule_histogram_wl_only_without_dialog_coordinator_is_a_no_op() -> None:
    """Histogram throttling is skipped when the dialog coordinator is absent."""
    stub = _stub_for("DisplayProjectionMixin")
    stub._restart_single_shot_timer = MagicMock()

    stub._schedule_histogram_wl_only()

    stub._restart_single_shot_timer.assert_not_called()


def test_schedule_histogram_wl_only_restarts_the_throttle_timer() -> None:
    """W/L drags coalesce into one histogram refresh after the throttle delay."""
    callback = MagicMock(name="do_update")
    stub = _stub_for("DisplayProjectionMixin", dialog_coordinator=MagicMock())
    stub._do_update_histogram_wl_only = callback
    stub._restart_single_shot_timer = MagicMock()

    stub._schedule_histogram_wl_only()

    stub._restart_single_shot_timer.assert_called_once_with(
        "_histogram_wl_update_timer", 100, callback
    )


def test_do_update_histogram_wl_only_targets_the_focused_subwindow() -> None:
    """The throttled refresh must follow pane focus, not always pane 0."""
    coordinator = MagicMock()
    stub = _stub_for("DisplayProjectionMixin", dialog_coordinator=coordinator, focused_subwindow_index=2)

    stub._do_update_histogram_wl_only()

    coordinator.update_histogram_window_level_only_for_subwindow.assert_called_once_with(2)


def test_do_update_histogram_wl_only_without_dialog_coordinator_is_a_no_op() -> None:
    """The timer callback must tolerate the coordinator disappearing before it fires."""
    stub = _stub_for("DisplayProjectionMixin")
    stub._do_update_histogram_wl_only()


def test_update_undo_redo_state_reports_both_capabilities() -> None:
    """Undo/redo menu enablement is derived from the unified manager's two queries."""
    manager = MagicMock()
    manager.can_undo.return_value = True
    manager.can_redo.return_value = False
    main_window = MagicMock()
    stub = _stub_for("TagEditingMixin", undo_redo_manager=manager, main_window=main_window)

    stub._update_undo_redo_state()

    main_window.update_undo_redo_state.assert_called_once_with(True, False)


def test_update_undo_redo_state_without_manager_reports_both_disabled() -> None:
    """A missing undo manager must disable both actions rather than raise."""
    main_window = MagicMock()
    stub = _stub_for("TagEditingMixin", undo_redo_manager=None, main_window=main_window)

    stub._update_undo_redo_state()

    main_window.update_undo_redo_state.assert_called_once_with(False, False)


def test_fusion_notification_membership_is_tracked_per_study() -> None:
    """The once-per-study notification latch must ignore an empty study UID."""
    stub = _stub_for("SubwindowManagementMixin", _fusion_notified_studies=set())

    assert stub.has_shown_fusion_notification("1.2") is False
    stub.mark_fusion_notification_shown("1.2")
    assert stub.has_shown_fusion_notification("1.2") is True
    assert stub.has_shown_fusion_notification("1.3") is False


def test_mark_fusion_notification_shown_ignores_empty_study_uid() -> None:
    """An empty UID must not latch every later notification on."""
    notified: set[str] = set()
    stub = _stub_for("SubwindowManagementMixin", _fusion_notified_studies=notified)

    stub.mark_fusion_notification_shown("")

    assert notified == set()


@pytest.mark.qt
def test_on_undo_requested_refreshes_ui_only_after_a_successful_undo() -> None:
    """A failed undo must not refresh the ROI list or crosshairs."""
    manager = MagicMock()
    manager.can_undo.return_value = True
    manager.undo.return_value = False
    stub = _stub_for("UIHandlersMixin", undo_redo_manager=manager)
    stub._update_undo_redo_state = MagicMock()
    stub._update_roi_list = MagicMock()
    crosshair_coordinator = MagicMock()
    stub.crosshair_coordinator = crosshair_coordinator

    stub._on_undo_requested()

    manager.undo.assert_called_once_with()
    stub._update_undo_redo_state.assert_not_called()
    stub._update_roi_list.assert_not_called()
    crosshair_coordinator.update_crosshairs_for_slice.assert_not_called()


@pytest.mark.qt
def test_on_undo_requested_refreshes_ui_on_success() -> None:
    """A successful undo refreshes undo state, the ROI list, and the crosshairs."""
    manager = MagicMock()
    manager.can_undo.return_value = True
    manager.undo.return_value = True
    stub = _stub_for("UIHandlersMixin", undo_redo_manager=manager)
    stub._update_undo_redo_state = MagicMock()
    stub._update_roi_list = MagicMock()
    crosshair_coordinator = MagicMock()
    stub.crosshair_coordinator = crosshair_coordinator

    stub._on_undo_requested()

    stub._update_undo_redo_state.assert_called_once_with()
    stub._update_roi_list.assert_called_once_with()
    crosshair_coordinator.update_crosshairs_for_slice.assert_called_once_with()


@pytest.mark.qt
def test_on_redo_requested_refreshes_ui_on_success() -> None:
    """Redo mirrors undo: the same three refreshes, gated on ``redo()`` returning True."""
    manager = MagicMock()
    manager.can_redo.return_value = True
    manager.redo.return_value = True
    stub = _stub_for("UIHandlersMixin", undo_redo_manager=manager)
    stub._update_undo_redo_state = MagicMock()
    stub._update_roi_list = MagicMock()
    crosshair_coordinator = MagicMock()
    stub.crosshair_coordinator = crosshair_coordinator

    stub._on_redo_requested()

    manager.redo.assert_called_once_with()
    stub._update_undo_redo_state.assert_called_once_with()
    stub._update_roi_list.assert_called_once_with()
    crosshair_coordinator.update_crosshairs_for_slice.assert_called_once_with()


@pytest.mark.qt
def test_on_undo_requested_without_available_undo_is_a_no_op() -> None:
    """Nothing to undo must not call ``undo()`` at all."""
    manager = MagicMock()
    manager.can_undo.return_value = False
    stub = _stub_for("UIHandlersMixin", undo_redo_manager=manager)
    stub._update_undo_redo_state = MagicMock()
    stub._update_roi_list = MagicMock()

    stub._on_undo_requested()

    manager.undo.assert_not_called()
    stub._update_roi_list.assert_not_called()


def _compound_allow_list() -> dict[str, set[str]]:
    """Return the mixin methods characterized individually, per mixin class.

    Only methods whose body does more than forward belong here: a single-statement
    forward must live in a case table so its delegate is pinned.
    ``test_compound_allow_list_only_contains_genuinely_compound_methods`` enforces that.
    """
    return {
    "InitializationMixin": {
        "_init_core_managers",
        "_setup_ui",
        "_init_main_window_and_layout",
        "_init_view_widgets",
        "_post_init_subwindows_and_handlers",
        "_init_controllers_and_tools",
        "_initialize_subwindow_managers",
        "_connect_signals",
    },
    "UIHandlersMixin": {
        "_on_undo_requested",
        "_on_redo_requested",
        "_on_study_index_after_load",
        "_on_assign_series_requested",
        "_on_keyboard_shortcuts_requested",
        "_on_scroll_wheel_mode_changed",
    },
    "TagEditingMixin": {
        "_on_tag_edited",
        "_undo_tag_edit",
        "_redo_tag_edit",
        "_update_undo_redo_state",
        "_refresh_tag_ui",
    },
    "ROIWorkflowMixin": {"_keyboard_delete_roi", "_delete_all_rois_current_slice"},
    "DisplayProjectionMixin": {
        "_schedule_histogram_wl_only",
        "_do_update_histogram_wl_only",
    },
    "SubwindowManagementMixin": {
        "_create_managers_for_subwindow",
        "_refresh_slice_sync_group_indicators",
        "_sync_navigation_slider_for_subwindow",
        "_update_focused_subwindow_references",
        "has_shown_fusion_notification",
        "mark_fusion_notification_shown",
        "_redisplay_subwindow_slice",
        "_reset_fusion_handler_for_subwindow",
        "_reset_fusion_for_all_subwindows",
        "_get_rescale_params",
        "_get_subwindow_rescale_params",
        "_on_focused_subwindow_changed",
        "_update_histogram_for_focused_subwindow",
        "_do_update_histogram_for_focused_subwindow",
        "_get_thumbnail_for_view",
    },
    "MPRNavigationMixin": {
        "_on_mpr_thumbnail_clicked",
        "_on_mpr_assign_requested",
        "_on_mpr_clear_from_navigator_thumbnail",
        "_get_subwindow_mpr_output_pixel_spacing",
    },
}


def test_every_mixin_method_has_a_coverage_route() -> None:
    """Guard the guard: a new delegating mixin method must be added to a table here.

    Only one-line forwards are required. Methods with a real body (conditionals, loops,
    local computation) are covered by their own tests and are allow-listed below.
    """
    compound = _compound_allow_list()
    covered = {f"{c.mixin_class}.{c.method}" for c in HANDLER_CASES}
    covered |= {f"{c.mixin_class}.{c.method}" for c in LAYOUT_HANDLER_CASES}
    covered |= {f"{c.mixin_class}.{c.method}" for c in COLLABORATOR_CASES}
    individually_tested = {
        f"{name}.{method}"
        for name, methods in {
            "UIHandlersMixin": {
                "_on_scroll_wheel_mode_changed",
                    "_on_undo_requested",
                "_on_redo_requested",
            },
            "SubwindowManagementMixin": {
                "_redisplay_subwindow_slice",
                "_update_focused_subwindow_references",
                "has_shown_fusion_notification",
                "mark_fusion_notification_shown",
            },
            "ROIWorkflowMixin": {"_keyboard_delete_roi", "_delete_all_rois_current_slice"},
            "DisplayProjectionMixin": {
                "_schedule_histogram_wl_only",
                "_do_update_histogram_wl_only",
            },
            "TagEditingMixin": {"_update_undo_redo_state"},
        }.items()
        for method in methods
    }
    covered |= individually_tested

    uncovered: dict[str, set[str]] = {}
    for mixin_name in MIXIN_MODULES:
        mixin = _mixin_class(mixin_name)
        methods = {
            name
            for name, value in vars(mixin).items()
            if not name.startswith("__") and callable(value)
        }
        gaps = {
            name
            for name in methods
            if f"{mixin_name}.{name}" not in covered and name not in compound.get(mixin_name, set())
        }
        if gaps:
            uncovered[mixin_name] = gaps
    assert uncovered == {}, f"mixin methods with no coverage route: {uncovered}"


def test_compound_allow_list_only_contains_genuinely_compound_methods() -> None:
    """The ``compound`` allow-list must not become a hiding place for pure forwards.

    The route guard above treats an allow-listed name as covered, so a one-line
    forward parked there would never be pinned to its delegate — the exact gap
    this net exists to close. Verify each allow-listed method really does do
    something beyond the forward, by inspecting its AST rather than trusting the
    list.

    "Pure forward" means a single statement that is a bare call (optionally
    returned) with no branching inside it **and** whose arguments are only plain
    references it received. A call that constructs its own arguments — e.g.
    ``_setup_ui`` building a ``MainWindowPanels`` bundle — is assembling, not
    forwarding, and is better characterized directly than tabulated. A single
    ``if``/``try`` is compound behaviour, and a plain accessor (``return x in
    y``) is not a delegation at all, so neither is flagged.
    """
    import ast
    import inspect
    import textwrap

    _BRANCHING = (ast.If, ast.Try, ast.For, ast.While, ast.BoolOp, ast.IfExp, ast.comprehension)

    allow_listed = {
        (mixin_name, method)
        for mixin_name, methods in _compound_allow_list().items()
        for method in methods
    }
    assert allow_listed, "allow-list unexpectedly empty"

    pure_forwards: list[str] = []
    for mixin_name, method in sorted(allow_listed):
        source = textwrap.dedent(inspect.getsource(getattr(_mixin_class(mixin_name), method)))
        body = [
            stmt
            for stmt in ast.parse(source).body[0].body
            if not (isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant))
        ]
        if len(body) > 1 or any(isinstance(n, _BRANCHING) for n in ast.walk(ast.Module(body=body, type_ignores=[]))):
            continue  # genuinely compound
        call = body[0].value if isinstance(body[0], ast.Expr) else getattr(body[0], "value", None)
        if not isinstance(call, ast.Call):
            continue  # not a delegation (e.g. a plain accessor)
        if any(isinstance(node, ast.Call) for arg in call.args for node in ast.walk(arg)):
            continue  # constructs its own arguments: assembling, not forwarding
        pure_forwards.append(f"{mixin_name}.{method}")

    assert pure_forwards == [], (
        "these allow-listed methods are single-call forwards and belong in a case "
        f"table instead: {pure_forwards}"
    )
