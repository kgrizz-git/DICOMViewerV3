"""Existing pane-reset / series-assignment pathways vs the live MPR registry.

Every path that can overwrite ``subwindow_data`` must release or detach the
registry view mapped to that pane (policy: source gone -> discard its
sessions; a bare pane reset -> detach, never silently discard). Real
controller and real consumer functions; fake panes and synthetic results.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from mpr_lifecycle_harness import (
    FakeWorker,
    _add_detached_view,
    _counts,
    _make_controller,
    _make_result,
    _register_worker,
    _seed_mpr_pane,
    _signals,
    _tile_events,
)

from core.study_navigation_handlers import (
    clear_subwindow,
    clear_subwindow_content,
    close_series,
)
from gui.file_series_additive_load import refresh_appended_series_subwindows
from gui.file_series_first_slice_load import (
    clear_stale_subwindow_data,
    pre_first_slice_reset,
)


def _full_app(ctrl, app):
    """Add the app-level collaborators the consumer functions touch."""
    app._mpr_controller = ctrl
    app._reset_fusion_for_all_subwindows = MagicMock()
    app.tag_edit_history = None
    app.slice_display_manager = MagicMock()
    app.intensity_projection_controls_widget = MagicMock()
    app.cine_player = None
    app.dicom_organizer = MagicMock()
    app.annotation_manager = MagicMock()
    app._schedule_tag_export_union_rebuild = MagicMock()
    app._refresh_series_navigator_state = MagicMock()
    app._slice_sync_coordinator = MagicMock()
    return app


class TestFullReplaceLoad:
    def test_replace_load_releases_every_session_view_and_mpr_pane(self) -> None:
        ctrl, app = _make_controller()
        fired = _signals(ctrl)
        tiles = _tile_events(ctrl)
        _full_app(ctrl, app)
        _seed_mpr_pane(app, 0, _make_result())
        detached = _add_detached_view(ctrl, _make_result())
        worker = FakeWorker()
        _register_worker(ctrl, 1, worker)
        app.subwindow_data[1] = {}
        reserved = ctrl._registry.reserve_build("ST", "SE")
        ctrl._build_reservations[1] = (reserved, ("ST", "SE"))

        pre_first_slice_reset(app)

        assert _counts(ctrl) == (0, 0, 0, 0)
        assert ctrl._build_reservations == {} and 1 not in ctrl._workers
        assert worker.cancel_calls == 1
        assert app.subwindow_data[0].get("is_mpr") is None
        assert fired["cleared"] == [0]
        assert ctrl.get_view_metadata(detached) is None
        assert tiles and tiles[-1] == frozenset()  # tiles reconciled after the release

    def test_no_mpr_pane_survives_to_the_stale_data_pass_even_if_its_source_is_reloaded(self) -> None:
        ctrl, app = _make_controller()
        _full_app(ctrl, app)
        _seed_mpr_pane(app, 0, _make_result(), study="ST")
        pre_first_slice_reset(app)
        # The same series is present again after the replace; nothing may still be MPR.
        studies = {"ST": {"SE": [object()], "PRIOR-SE": [object()]}}
        assert clear_stale_subwindow_data(app, studies) == 0  # restored 2-D pane is current
        assert not any(d.get("is_mpr") for d in app.subwindow_data.values())
        assert ctrl._registry.view_count == 0

    def test_replace_load_without_a_controller_is_unchanged(self) -> None:
        _ctrl, app = _make_controller()
        _full_app(_ctrl, app)
        del app._mpr_controller
        pre_first_slice_reset(app)  # must not raise


class TestAdditiveAppend:
    def test_appended_slices_do_not_overwrite_an_mpr_panes_stack(self) -> None:
        ctrl, app = _make_controller()
        _full_app(ctrl, app)
        result = _make_result(n_slices=3)
        _seed_mpr_pane(app, 0, result, study="ST")
        native = [object(), object(), object(), object(), object()]
        app.subwindow_data[1] = {
            "current_study_uid": "ST", "current_series_uid": "SE",
            "current_datasets": [object()],
        }
        app.current_studies = {"ST": {"SE": native}}
        mpr_stack = app.subwindow_data[0]["current_datasets"]

        refresh_appended_series_subwindows(app, [("ST", "SE")])

        assert app.subwindow_data[0]["current_datasets"] is mpr_stack  # MPR pane untouched
        assert app.subwindow_data[1]["current_datasets"] is native  # native pane updated
        app.slice_navigator.set_total_slices.assert_not_called()  # focused pane is the MPR one
        assert ctrl.attached_view_id(0) is not None


class TestPaneResetSafetyNet:
    def test_bare_pane_reset_detaches_instead_of_leaving_a_stale_mapping(self) -> None:
        ctrl, app = _make_controller()
        fired = _signals(ctrl)
        _full_app(ctrl, app)
        _seed_mpr_pane(app, 0, _make_result())
        view_id = ctrl.attached_view_id(0)
        app.subwindow_data[0]["mpr_slice_index"] = 2

        clear_subwindow(app, 0)

        assert ctrl.attached_view_id(0) is None  # pane mapping released
        assert ctrl.detached_view_ids() == [view_id]  # session kept, never silently discarded
        assert ctrl._registry.get_view(view_id).slice_index == 2  # live state flushed first
        assert fired["detached"] == [0]
        assert app.subwindow_data[0]["current_dataset"] is None

    def test_reset_of_a_pane_without_a_view_is_a_no_op(self) -> None:
        ctrl, app = _make_controller()
        fired = _signals(ctrl)
        _full_app(ctrl, app)
        clear_subwindow(app, 1)
        assert _counts(ctrl) == (0, 0, 0, 0) and fired["detached"] == []

    def test_clear_window_still_detaches_once_and_keeps_identity(self) -> None:
        ctrl, app = _make_controller()
        fired = _signals(ctrl)
        _full_app(ctrl, app)
        app.focused_subwindow_index = 1
        _seed_mpr_pane(app, 0, _make_result())
        view_id = ctrl.attached_view_id(0)
        clear_subwindow_content(app, 0)
        assert ctrl.detached_view_ids() == [view_id]
        assert fired["detached"] == [0]  # no second detach from the safety net


class TestSourceClose:
    def test_close_series_discards_its_sessions_and_resets_the_pane(self) -> None:
        ctrl, app = _make_controller()
        _full_app(ctrl, app)
        tiles = _tile_events(ctrl)
        app.focused_subwindow_index = 1
        series_datasets = [object()]
        app.current_studies = {"ST": {"SE": series_datasets}}
        app.dicom_organizer.studies = {}
        app.current_study_uid = app.current_series_uid = ""
        _seed_mpr_pane(app, 0, _make_result(), study="ST")  # displays ST/SE
        same_source = _add_detached_view(ctrl, _make_result(), "ST", "SE")
        foreign = _add_detached_view(ctrl, _make_result(), "ST", "OTHER")

        with patch("core.study_navigation_handlers.clear_cached_pixel_array"):
            close_series(app, "ST", "SE")

        assert ctrl.attached_view_id(0) is None
        assert ctrl.detached_view_ids() == [foreign]
        assert ctrl._registry.session_count == 1
        assert app.subwindow_data[0].get("is_mpr") is None
        assert ctrl.get_view_metadata(same_source) is None
        assert tiles


class TestOrdinaryAssignment:
    def test_assigning_a_series_to_an_mpr_pane_is_refused_without_touching_state(self) -> None:
        from core.series_navigation_controller import assign_series_to_subwindow

        ctrl, app = _make_controller()
        _full_app(ctrl, app)
        _seed_mpr_pane(app, 0, _make_result())
        view_id = ctrl.attached_view_id(0)
        before = dict(app.subwindow_data[0])
        subwindow = app.multi_window_layout.get_subwindow(0)
        app.current_studies = {"ST": {"SE2": [object()]}}
        app.main_window = SimpleNamespace(show_toast_message=MagicMock())

        assign_series_to_subwindow(app, subwindow, "SE2", 0, "ST")

        app.main_window.show_toast_message.assert_called_once()
        assert app.subwindow_data[0] == before
        assert ctrl.attached_view_id(0) == view_id
        assert ctrl._registry.session_count == 1
