"""Transactional MPR transfers, worker guards, and source-closure release.

Owns the failure-atomicity and background-build safety that
``MprController`` invokes during relocate / attach / install / close.
Extracted so ``gui/mpr_controller.py`` stays within its line budget;
behavior contracts:

- Validate install targets and payloads before any mutation, including
  before ``mpr_previous_state`` is written.
- Preserve the source view until the destination install succeeds.
- Snapshot the destination's pane/manager/viewer/toolbar state and restore
  it when an install fails, for both ordinary 2-D and existing MPR
  destinations. Replacing an occupied destination on success keeps the
  displaced view alive as a detached registry view (never discarded); the
  registry commit happens only after the install succeeded.
- Transfers move an existing view: they never reserve or confirm admission.
  The payload handed to ``_install_mpr_payload_at_subwindow`` is an adapter
  built from the owning view and session (``mpr_controller_sessions``).
- Background builds are fenced by worker identity plus pane and source
  generations. Cancellation retires the native worker (request stop, keep
  alive until it actually terminates) and invalidates its callbacks; a late
  callback can neither pop a newer worker nor activate a stale result.
- Source closure lives in ``gui.mpr_source_closure``.

Conventions match the controller: ``app`` and ``controller`` are duck-typed,
shared UI syncs only for the focused pane, and helpers never raise for
missing managers or widgets.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from PySide6.QtWidgets import QMessageBox

from core.lut_series_state import clear_mpr_lut_override
from core.mpr_session_types import detached_nav_key
from gui.mpr_controller_sessions import (
    build_view_payload,
    capture_pane_payload,
    find_view,
    refresh_view_from_pane,
)
from gui.mpr_frame_snapshot import capture_frame, restore_frame
from utils.debug_flags import DEBUG_MPR


def _txn_log(message: str) -> None:
    """Print an MPR transaction debug message when DEBUG_MPR is enabled."""
    if DEBUG_MPR:
        print(f"[DEBUG-MPR] {message}")


_ABSENT = object()


@dataclass
class DestinationSnapshot:
    """Pre-install destination state for failure rollback.

    ``data`` is a shallow copy of the pane's ``subwindow_data`` dict
    (install paths replace lists rather than mutating them, so shallow is
    exact); ``was_mpr`` records whether the pane showed MPR. ``manager`` /
    ``viewer`` hold plain attribute values; ``toolbar`` holds center/width /
    unit (None when the pane has no shared controls); ``main_toggle``
    records the main-window rescale toggle (None unknown). A missing pane
    manager or viewer is recorded as None and skipped.
    """

    data: dict[str, Any] | None = None
    was_mpr: bool = False
    manager: dict[str, Any] | None = None
    viewer: dict[str, Any] | None = None
    toolbar: dict[str, Any] | None = None
    main_toggle: bool | None = None
    frame: Any = None
    banner_text: str | None = None
    nav_total: int | None = None
    nav_current: int | None = None


def validate_install_request(
    app: Any, get_image_viewer: Callable[[int], Any], idx: int, payload: Any
) -> tuple[Any, int, Any] | None:
    """Validate an install target and payload without mutating anything.

    Requires a real destination pane *and* viewer (a transfer into a
    viewer-less slot cannot render), plus a usable result with slices.
    Returns ``(result, clamped_slice_index, source_dataset)`` or None.
    Runs before ``mpr_previous_state`` is written.
    """
    if not isinstance(payload, dict):
        return None
    data = app.subwindow_data.get(idx)
    if data is None:
        return None
    try:
        viewer = get_image_viewer(idx)
    except Exception:
        return None
    if viewer is None:
        return None
    result = payload.get("mpr_result")
    if result is None:
        return None
    try:
        source_datasets = result.source_volume.source_datasets
        if not source_datasets:
            return None
        n_slices = int(getattr(result, "n_slices", 0) or 0)
    except Exception:
        return None
    if n_slices < 1:
        return None
    try:
        slice_index = int(payload.get("mpr_slice_index", 0))
    except (TypeError, ValueError):
        return None
    return result, max(0, min(slice_index, n_slices - 1)), source_datasets[0]


def capture_destination_snapshot(
    app: Any, get_image_viewer: Callable[[int], Any], idx: int
) -> DestinationSnapshot:
    """Snapshot destination pane dict plus display state (read-only)."""
    live = app.subwindow_data.get(idx)
    data = dict(live) if isinstance(live, dict) else None
    was_mpr = bool(data.get("is_mpr", False)) if data is not None else False
    managers = app.subwindow_managers.get(idx, {})
    view_state_manager = managers.get("view_state_manager")
    manager: dict[str, Any] | None = None
    if view_state_manager is not None:
        override = view_state_manager.series_defaults.get("__mpr__") if isinstance(
            getattr(view_state_manager, "series_defaults", None), dict
        ) else None
        manager = {
            "window_center": getattr(view_state_manager, "current_window_center", None),
            "window_width": getattr(view_state_manager, "current_window_width", None),
            "user_modified": getattr(view_state_manager, "window_level_user_modified", None),
            "use_rescaled": getattr(view_state_manager, "use_rescaled_values", None),
            "rescale_slope": getattr(view_state_manager, "rescale_slope", None),
            "rescale_intercept": getattr(view_state_manager, "rescale_intercept", None),
            "rescale_type": getattr(view_state_manager, "rescale_type", None),
            "series_id": getattr(view_state_manager, "current_series_identifier", None),
            "context": {name: getattr(view_state_manager, name, _ABSENT) for name in (
                "current_dataset", "current_studies", "current_study_uid",
                "current_series_uid", "current_slice_index",
            )},
            "lut_override": (
                override.get("current_lut") if isinstance(override, dict) else _ABSENT
            ),
        }
    viewer_obj = None
    try:
        viewer_obj = get_image_viewer(idx)
    except Exception:
        viewer_obj = None
    viewer: dict[str, Any] | None = None
    if viewer_obj is not None:
        viewer = {
            "inverted": getattr(viewer_obj, "image_inverted", None),
            "rescale_toggle": getattr(viewer_obj, "use_rescaled_values", None),
            "mouse_mode": getattr(viewer_obj, "mouse_mode", None),
            "mode_override": getattr(viewer_obj, "_mpr_mode_override", None),
            # Retain the frame reference (no copy); rollback repaints it.
            "original_image": getattr(viewer_obj, "original_image", None),
        }
    toolbar: dict[str, Any] | None = None
    wl_controls = getattr(app, "window_level_controls", None)
    if wl_controls is not None:
        toolbar = {
            "window_center": getattr(wl_controls, "window_center", None),
            "window_width": getattr(wl_controls, "window_width", None),
            "unit": getattr(wl_controls, "unit", None),
        }
    main_toggle: bool | None = None
    checkbox = getattr(getattr(app, "main_window", None), "use_rescaled_values_checkbox", None)
    getter = getattr(checkbox, "isChecked", None)
    if callable(getter):
        try:
            main_toggle = bool(getter())
        except Exception:
            main_toggle = None
    banner_text = _read_banner_text(managers.get("overlay_manager"))
    nav_total, nav_current = _read_nav_state(getattr(app, "slice_navigator", None))
    return DestinationSnapshot(
        data=data, was_mpr=was_mpr, manager=manager, viewer=viewer,
        toolbar=toolbar, main_toggle=main_toggle, frame=capture_frame(viewer_obj), banner_text=banner_text,
        nav_total=nav_total, nav_current=nav_current,
    )


def _read_banner_text(overlay_manager: Any) -> str | None:
    """Current MPR banner text, or None when hidden/unavailable."""
    owner = getattr(overlay_manager, "viewport_overlay_widget", overlay_manager)
    label = getattr(owner, "mpr_banner_label", None)
    text = getattr(label, "text", None)
    if not callable(text):
        return None
    try:
        value = text()
    except Exception:
        return None
    return value if isinstance(value, str) and value else None


def _read_nav_state(navigator: Any) -> tuple[int | None, int | None]:
    """Slice-navigator (total, current) as ints, else Nones."""
    if navigator is None:
        return None, None
    total = getattr(navigator, "total_slices", None)
    current = getattr(navigator, "current_slice_index", None)
    total = total if isinstance(total, int) and not isinstance(total, bool) else None
    current = current if isinstance(current, int) and not isinstance(current, bool) else None
    return total, current


def restore_destination_snapshot(
    app: Any, get_image_viewer: Callable[[int], Any], idx: int, snapshot: DestinationSnapshot
) -> bool:
    """Restore captured pane values, banner, and (when focused) shared chrome.

    Shared controls (toolbar, main toggle, navigator) restore only when
    *idx* is the focused pane: they belong to whichever pane has focus, and
    an unfocused rollback must not rewrite another pane's controls. Returns
    True when every applicable step succeeded.
    """
    managers = app.subwindow_managers.get(idx, {})
    ok = _restore_manager_snapshot(managers.get("view_state_manager"), snapshot.manager)
    viewer_ok, viewer_obj = _restore_viewer_snapshot(get_image_viewer, idx, snapshot.viewer)
    ok = viewer_ok and ok
    ok = _restore_banner_snapshot(managers.get("overlay_manager"), snapshot) and ok
    if idx != getattr(app, "focused_subwindow_index", -1):
        return ok
    ok = _restore_toolbar_snapshot(getattr(app, "window_level_controls", None), snapshot.toolbar) and ok
    if snapshot.main_toggle is not None and hasattr(app, "main_window"):
        try:
            app.main_window.set_rescale_toggle_state(snapshot.main_toggle)
        except Exception:
            ok = False
    ok = _restore_nav_snapshot(getattr(app, "slice_navigator", None), snapshot) and ok
    return ok


def _restore_manager_snapshot(view_state_manager: Any, saved: dict[str, Any] | None) -> bool:
    """Write captured pane view-state values back (no validation)."""
    if saved is None or view_state_manager is None:
        return saved is None
    try:
        view_state_manager.current_window_center = saved["window_center"]
        view_state_manager.current_window_width = saved["window_width"]
        view_state_manager.window_level_user_modified = saved["user_modified"]
        view_state_manager.use_rescaled_values = saved["use_rescaled"]
        view_state_manager.rescale_slope = saved["rescale_slope"]
        view_state_manager.rescale_intercept = saved["rescale_intercept"]
        view_state_manager.rescale_type = saved["rescale_type"]
        view_state_manager.current_series_identifier = saved["series_id"]
        for name, value in saved.get("context", {}).items():
            if value is not _ABSENT:
                setattr(view_state_manager, name, value)
        if saved["lut_override"] is _ABSENT:
            clear_mpr_lut_override(view_state_manager)
        else:
            bucket = view_state_manager.series_defaults.setdefault("__mpr__", {})
            if isinstance(bucket, dict):
                bucket["current_lut"] = saved["lut_override"]
    except Exception:
        return False
    return True


def _restore_viewer_snapshot(
    get_image_viewer: Callable[[int], Any], idx: int, saved: dict[str, Any] | None
) -> tuple[bool, Any]:
    """Write captured viewer flags back (inversion, toggles, mouse mode)."""
    if saved is None:
        return True, None
    try:
        viewer_obj = get_image_viewer(idx)
    except Exception:
        return False, None
    if viewer_obj is None:
        return False, None
    try:
        if saved["inverted"] is not None:
            viewer_obj.image_inverted = saved["inverted"]
        if saved["rescale_toggle"] is not None:
            viewer_obj.use_rescaled_values = saved["rescale_toggle"]
        # The mode override gates tool-mode changes: restore it before the
        # mouse mode so the mode actually applies instead of being blocked.
        viewer_obj._mpr_mode_override = saved["mode_override"]
        if isinstance(saved["mouse_mode"], str):
            setter = getattr(viewer_obj, "set_mouse_mode", None)
            if callable(setter):
                setter(saved["mouse_mode"])
    except Exception:
        return False, viewer_obj
    return True, viewer_obj


def _restore_banner_snapshot(overlay_manager: Any, snapshot: DestinationSnapshot) -> bool:
    """Restore the pane's pre-install banner text (None hides)."""
    if overlay_manager is None:
        return True
    setter = getattr(overlay_manager, "set_mpr_banner", None)
    if not callable(setter):
        return True
    try:
        setter(snapshot.banner_text)
    except Exception:
        return False
    return True


def _restore_nav_snapshot(navigator: Any, snapshot: DestinationSnapshot) -> bool:
    """Restore slice-navigator total/current without emitting change signals."""
    if navigator is None:
        return True
    try:
        if snapshot.nav_total is None or snapshot.nav_current is None:
            return True
        setter = getattr(navigator, "set_total_slices", None)
        if callable(setter):
            setter(snapshot.nav_total)
        navigator.current_slice_index = snapshot.nav_current
    except Exception:
        return False
    return True


def _restore_toolbar_snapshot(wl_controls: Any, saved: dict[str, Any] | None) -> bool:
    """Write captured toolbar W/L back with signals blocked."""
    if saved is None or wl_controls is None:
        return saved is None
    if saved["window_center"] is None or saved["window_width"] is None:
        return True
    try:
        wl_controls.set_window_level(
            saved["window_center"], saved["window_width"],
            block_signals=True, unit=saved["unit"],
        )
        if saved["unit"] is None:
            wl_controls.set_unit(None)
    except Exception:
        return False
    return True


def restore_failed_install(
    controller: Any, idx: int, snapshot: DestinationSnapshot,
    get_image_viewer: Callable[[int], Any],
) -> bool:
    """Restore original data, controls and last-good pixels without resampling.

    The original frame is restored directly, so a persistent rendering failure
    cannot destroy an existing view. No teardown or success signals are emitted.
    """
    app = controller._app
    data = app.subwindow_data.get(idx)
    if data is None or snapshot.data is None:
        return False
    data.clear()
    data.update(snapshot.data)
    try:
        values_ok = restore_destination_snapshot(app, get_image_viewer, idx, snapshot)
        viewer = get_image_viewer(idx)
        picture_ok = restore_frame(viewer, snapshot.frame)
        sync = getattr(app, "_sync_navigation_slider_for_subwindow", None)
        if callable(sync):
            sync(idx)
    except Exception as exc:
        _txn_log(f"snapshot restore failed: {exc}")
        return False
    return values_ok and picture_ok

# ---------------------------------------------------------------------------
# Transfer orchestration (source preserved until install success)
# ---------------------------------------------------------------------------


def _focus_destination(controller: Any, idx: int) -> None:
    """Best-effort focus the destination subwindow before a transfer."""
    try:
        sub = controller._app.multi_window_layout.get_subwindow(idx)
        if sub is not None:
            sub.set_focused(True)
    except Exception:
        pass


def capture_mpr_payload(controller: Any, idx: int) -> dict[str, Any] | None:
    """Payload adapter for the view attached to *idx* (flushes live pane state)."""
    return capture_pane_payload(controller, idx)


def detach_mpr_view(controller: Any, idx: int) -> None:
    """Detach pane *idx*'s view; the registry keeps it (and its session) alive.

    Nothing is created or discarded: detaching an empty or non-MPR pane is a
    no-op, and the same view ID survives, so re-detach/reattach keeps its
    identity and order.
    """
    if not controller.is_mpr(idx):
        return
    if capture_mpr_payload(controller, idx) is None:
        return
    view = controller._registry.view_for_pane(idx)
    if view is None:  # pragma: no cover (capture requires a registry view)
        return
    controller._cancel_mpr_worker(idx)
    controller._tear_down_mpr_at_subwindow(idx)
    controller._registry.detach_view(view.view_id)
    controller.mpr_detached.emit(idx)


def detach_view_on_pane_reset(controller: Any, idx: int) -> bool:
    """Detach (never discard) a view still mapped to *idx* before the pane is reset.

    Safety net for pathways that overwrite ``subwindow_data``: the pane's live
    state is flushed into the view, the pane mapping is released, and the
    view stays available as a detached tile. Returns True when a view was
    detached; a no-op for panes without a mapped view.
    """
    view = refresh_view_from_pane(controller, idx)
    if view is None:
        return False
    controller._registry.detach_view(view.view_id)
    controller.mpr_detached.emit(idx)
    return True


def validate_transfer_target(
    app: Any, get_image_viewer: Callable[[int], Any], idx: int
) -> bool:
    """True when *idx* is a real destination pane with a viewer.

    Runs before focus changes, worker cancellation, or any mutation, so an
    invalid drop neither cancels a valid build nor steals focus.
    """
    if app.subwindow_data.get(idx) is None:
        return False
    try:
        viewer = get_image_viewer(idx)
    except Exception:
        return False
    return viewer is not None


def _commit_install(controller: Any, view_id: int, to_idx: int) -> bool:
    """Commit a successful install to the registry; True when it displaced a view.

    ``attach_view`` moves the view and detaches any occupant of *to_idx* in
    one registry step, so the displaced view survives with its flushed
    state. Runs only after the pane install succeeded.
    """
    displaced = controller._registry.view_for_pane(to_idx) is not None
    controller._registry.attach_view(view_id, to_idx)
    return displaced


def relocate_mpr_view(controller: Any, from_idx: int, to_idx: int) -> None:
    """Move the view attached to *from_idx* to *to_idx*, transactionally.

    The source view is torn down only after the destination install
    succeeds. A failed install restores the destination (direct restore for
    an occupied MPR pane, install-time rollback otherwise) and leaves the
    source and registry untouched. A successful install over an occupied MPR
    pane preserves the displaced view as detached. Destination builds are
    cancelled regardless of pane mode. Emits no signals on failure.
    """
    if from_idx == to_idx:
        _focus_destination(controller, to_idx)
        return
    if not controller.is_mpr(from_idx):
        return
    payload = controller._capture_mpr_payload(from_idx)
    view = controller._registry.view_for_pane(from_idx)
    if payload is None or view is None:
        return
    app = controller._app
    if not validate_transfer_target(app, controller._get_image_viewer, to_idx):
        _txn_log(f"relocate to window {to_idx} refused: invalid destination")
        return
    if validate_install_request(app, controller._get_image_viewer, to_idx, payload) is None:
        _txn_log(f"relocate to window {to_idx} refused: invalid payload")
        return
    _focus_destination(controller, to_idx)
    controller._cancel_mpr_worker(to_idx)
    refresh_view_from_pane(controller, to_idx)
    if not controller._install_mpr_payload_at_subwindow(to_idx, payload):
        return
    displaced = _commit_install(controller, view.view_id, to_idx)
    controller._cancel_mpr_worker(from_idx)
    controller._tear_down_mpr_at_subwindow(from_idx)
    controller.mpr_cleared.emit(from_idx)
    if displaced:
        controller.mpr_detached.emit(to_idx)
    controller.mpr_activated.emit(to_idx)


def attach_detached_view(controller: Any, view_id: int, to_idx: int) -> None:
    """Attach the detached view *view_id* to *to_idx*, transactionally.

    Stale, unknown or already-attached IDs are silent no-ops. The view stays
    detached until the install succeeds; a failed install restores an
    occupied destination directly and warns, leaving every view where it
    was. A successful install over an occupied MPR pane preserves the
    displaced view as detached.
    """
    view = find_view(controller, view_id)
    if view is None or view.pane_index is not None:
        return
    payload = build_view_payload(controller, view_id)
    if payload is None:
        return
    app = controller._app
    if not validate_transfer_target(app, controller._get_image_viewer, to_idx):
        _txn_log(f"attach to window {to_idx} refused: invalid destination")
        _warn_attach_failed(controller, False)
        return
    dest_was_mpr = controller.is_mpr(to_idx)
    if validate_install_request(app, controller._get_image_viewer, to_idx, payload) is None:
        _warn_attach_failed(controller, dest_was_mpr)
        return
    _focus_destination(controller, to_idx)
    controller._cancel_mpr_worker(to_idx)
    refresh_view_from_pane(controller, to_idx)
    if not controller._install_mpr_payload_at_subwindow(to_idx, payload):
        _warn_attach_failed(controller, dest_was_mpr)
        return
    displaced = _commit_install(controller, view_id, to_idx)
    _clear_detached_thumbnail(controller, view_id)
    if displaced:
        controller.mpr_detached.emit(to_idx)
    controller.mpr_activated.emit(to_idx)


def _clear_detached_thumbnail(controller: Any, view_id: int) -> None:
    """Clear the navigator tile of a view that just left the detached state."""
    try:
        if hasattr(controller._app, "series_navigator"):
            controller._app.series_navigator.clear_mpr_thumbnail(detached_nav_key(view_id))
    except Exception:
        pass


def _warn_attach_failed(controller: Any, had_backup: bool) -> None:
    """Warn about an attach failure without touching either session."""
    try:
        QMessageBox.warning(
            controller._app.main_window,
            "MPR",
            "Could not attach the detached MPR to this window.\n"
            "The detached view is still available in the navigator."
            + ("\nThe previous MPR in this window was restored." if had_backup else ""),
        )
    except Exception:
        pass


__all__ = [
    "DestinationSnapshot",
    "attach_detached_view",
    "capture_destination_snapshot",
    "capture_mpr_payload",
    "detach_mpr_view",
    "detach_view_on_pane_reset",
    "relocate_mpr_view",
    "restore_destination_snapshot",
    "restore_failed_install",
    "validate_install_request",
    "validate_transfer_target",
]
