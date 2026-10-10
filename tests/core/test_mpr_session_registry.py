"""Focused unit tests for core.mpr_session_registry (P1 chunk 1, pure core)."""

from __future__ import annotations

import pytest

from core.mpr_session_registry import (
    DEFAULT_SESSION_CAP,
    DEFAULT_VIEW_CAP,
    AdmissionError,
    LinkGroupError,
    MprCombineState,
    MprDisplayState,
    MprSessionRegistry,
    ReservationError,
    UnknownSessionError,
    UnknownViewError,
)


def _registry(**kwargs) -> MprSessionRegistry:
    return MprSessionRegistry(**kwargs)


class TestIdsAndOwnership:
    def test_stable_unique_ids_never_reused(self) -> None:
        reg = _registry()
        s1, v1 = reg.create_session(object(), source_series_uid="S")
        s2, v2 = reg.create_session(object(), source_series_uid="S")
        assert (s1, v1) != (s2, v2)
        assert s1 != s2 and v1 != v2  # unique within each namespace
        reg.discard_session(s1)
        s3, v3 = reg.create_session(object())
        assert s3 not in (s1, s2) and v3 not in (v1, v2)

    def test_view_knows_session_and_pane_mapping(self) -> None:
        reg = _registry()
        session_id, view_id = reg.create_session(object(), pane_index=0)
        view = reg.get_view(view_id)
        assert view.session_id == session_id
        assert reg.view_for_pane(0) is view
        assert reg.view_for_pane(1) is None

    def test_unknown_ids_raise(self) -> None:
        reg = _registry()
        with pytest.raises(UnknownViewError):
            reg.get_view(999)
        with pytest.raises(UnknownSessionError):
            reg.get_session(999)
        with pytest.raises(UnknownViewError):
            reg.attach_view(999, 0)
        with pytest.raises(UnknownViewError):
            reg.detach_view(999)
        with pytest.raises(UnknownViewError):
            reg.discard_view(999)
        with pytest.raises(UnknownSessionError):
            reg.discard_session(999)


class TestSharedResultIdentity:
    def test_duplicates_share_result_by_reference(self) -> None:
        reg = _registry()
        result = object()
        session_id, first = reg.create_session(result, pane_index=0)
        second = reg.create_view(session_id, pane_index=1)
        assert reg.get_session(session_id).result is result
        assert reg.get_session(session_id).result is reg.get_session(session_id).result
        assert reg.views_for_session(session_id)[0].view_id == first
        assert len(reg.views_for_session(session_id)) == 2
        assert second != first

    def test_duplicate_view_state_is_independent(self) -> None:
        reg = _registry()
        session_id, first = reg.create_session(object())
        reg.set_view_slice(first, 3)
        reg.set_view_combine(first, MprCombineState(enabled=True, mode="mip", slice_count=6))
        second = reg.create_view(session_id)
        assert reg.get_view(second).slice_index == 0
        assert reg.get_view(second).combine.enabled is False
        assert reg.get_view(second).combine is not reg.get_view(first).combine
        assert reg.get_view(second).display is not reg.get_view(first).display

    def test_discarding_one_view_leaves_other_usable(self) -> None:
        reg = _registry()
        result = object()
        session_id, first = reg.create_session(result, pane_index=0)
        second = reg.create_view(session_id, pane_index=1)
        released = reg.discard_view(first)
        assert released is None  # session survives
        assert reg.get_session(session_id).result is result
        assert reg.view_for_pane(0) is None
        assert reg.view_for_pane(1).view_id == second


class TestPaneMapping:
    def test_attach_to_occupied_pane_detaches_occupant_without_new_slot(self) -> None:
        reg = _registry()
        _, first = reg.create_session(object(), pane_index=0)
        _, second = reg.create_session(object(), pane_index=1)
        before = reg.counts()
        reg.attach_view(first, 1)
        assert reg.view_for_pane(1).view_id == first
        assert reg.get_view(second).pane_index is None
        assert reg.counts() == before

    def test_reattach_same_pane_is_noop(self) -> None:
        reg = _registry()
        _, view_id = reg.create_session(object(), pane_index=2)
        reg.attach_view(view_id, 2)
        assert reg.view_for_pane(2).view_id == view_id

    def test_detach_is_selective_and_noop_when_detached(self) -> None:
        reg = _registry()
        _, first = reg.create_session(object(), pane_index=0)
        _, second = reg.create_session(object(), pane_index=1)
        reg.detach_view(first)
        assert reg.get_view(first).pane_index is None
        assert reg.view_for_pane(0) is None
        assert reg.view_for_pane(1).view_id == second
        reg.detach_view(first)  # no-op, no error

    def test_invalid_pane_rejected(self) -> None:
        reg = _registry()
        _, view_id = reg.create_session(object())
        with pytest.raises(ValueError):
            reg.attach_view(view_id, -1)

    def test_creation_order_survives_moves(self) -> None:
        reg = _registry()
        _, first = reg.create_session(object(), pane_index=0)
        _, second = reg.create_session(object(), pane_index=1)
        reg.detach_view(first)
        reg.attach_view(first, 1)
        assert [v.view_id for v in reg.ordered_views()] == [first, second]


class TestLifetime:
    def test_last_view_discard_releases_session(self) -> None:
        reg = _registry()
        session_id, first = reg.create_session(object())
        second = reg.create_view(session_id)
        assert reg.discard_view(first) is None
        assert reg.discard_view(second) == session_id
        with pytest.raises(UnknownSessionError):
            reg.get_session(session_id)

    def test_discard_session_removes_all_views(self) -> None:
        reg = _registry()
        session_id, first = reg.create_session(object(), pane_index=0)
        second = reg.create_view(session_id, pane_index=1)
        removed = reg.discard_session(session_id)
        assert sorted(removed) == sorted([first, second])
        assert reg.view_for_pane(0) is None
        assert reg.counts()["sessions"] == 0

    def test_close_source_series_removes_dependents_and_pending(self) -> None:
        reg = _registry()
        reg.create_session(object(), source_study_uid="ST", source_series_uid="A", pane_index=0)
        reg.create_session(object(), source_study_uid="ST", source_series_uid="B", pane_index=1)
        pending = reg.reserve_build("ST", "A")
        summary = reg.close_source_series("A")
        assert summary == {"sessions": 1, "views": 1, "reservations": 1}
        assert reg.view_for_pane(0) is None
        assert reg.view_for_pane(1) is not None
        assert reg.cancel_reservation(pending) is False  # already invalidated
        empty = reg.close_source_series("missing")
        assert empty == {"sessions": 0, "views": 0, "reservations": 0}

    def test_close_study_and_clear_all(self) -> None:
        reg = _registry()
        reg.create_session(object(), source_study_uid="ST1")
        reg.create_session(object(), source_study_uid="ST2")
        pending = reg.reserve_build("ST1", "X")
        summary = reg.close_study("ST1")
        assert summary["sessions"] == 1 and summary["reservations"] == 1
        assert reg.cancel_reservation(pending) is False
        reg.clear_all()
        assert reg.counts()["sessions"] == 0
        assert reg.counts()["views"] == 0
        assert reg.counts()["pending_views"] == 0


class TestAdmissionAndReservations:
    def test_defaults_match_plan(self) -> None:
        assert (DEFAULT_SESSION_CAP, DEFAULT_VIEW_CAP) == (8, 16)
        reg = _registry()
        assert (reg.session_cap, reg.view_cap) == (8, 16)

    def test_invalid_caps_rejected(self) -> None:
        with pytest.raises(ValueError):
            MprSessionRegistry(session_cap=0, view_cap=16)
        with pytest.raises(ValueError):
            MprSessionRegistry(session_cap=9, view_cap=8)

    def test_session_cap_blocks_new_builds_but_counts_pending(self) -> None:
        reg = _registry(session_cap=2, view_cap=16)
        reg.create_session(object())
        pending = reg.reserve_build()
        assert reg.counts()["pending_sessions"] == 1
        with pytest.raises(AdmissionError) as exc:
            reg.reserve_build()
        assert exc.value.limit_name == "session"
        assert (exc.value.current, exc.value.limit) == (2, 2)
        assert reg.cancel_reservation(pending) is True
        assert reg.reserve_build() is not None  # slot freed by cancel

    def test_view_cap_counts_reserved_duplicates(self) -> None:
        reg = _registry(session_cap=2, view_cap=2)
        session_id, _ = reg.create_session(object())
        pending = reg.reserve_view(session_id)
        assert reg.counts()["pending_views"] == 1
        with pytest.raises(AdmissionError) as exc:
            reg.reserve_view(session_id)
        assert exc.value.limit_name == "view"
        reg.cancel_reservation(pending)
        assert reg.create_view(session_id) is not None

    def test_build_reservation_needs_both_caps(self) -> None:
        reg = _registry(session_cap=2, view_cap=2)
        session_id, _ = reg.create_session(object())
        reg.create_view(session_id)  # views full (2/2), sessions open (1/2)
        with pytest.raises(AdmissionError) as exc:
            reg.reserve_build()
        assert exc.value.limit_name == "view"

    def test_release_exactly_once(self) -> None:
        reg = _registry()
        pending = reg.reserve_build()
        assert reg.cancel_reservation(pending) is True
        assert reg.cancel_reservation(pending) is False
        assert reg.cancel_reservation(999999) is False
        before = reg.counts()
        assert reg.cancel_reservation(pending) is False
        assert reg.counts() == before

    def test_confirm_then_cancel_is_final(self) -> None:
        reg = _registry()
        pending = reg.reserve_build()
        session_id, _ = reg.confirm_build(pending, result=object())
        assert reg.cancel_reservation(pending) is False
        with pytest.raises(ReservationError):
            reg.confirm_build(pending, result=object())
        assert reg.session_count == 1
        assert reg.get_session(session_id) is not None

    def test_cancel_then_confirm_fails_without_side_effects(self) -> None:
        reg = _registry()
        pending = reg.reserve_build()
        assert reg.cancel_reservation(pending) is True
        with pytest.raises(ReservationError):
            reg.confirm_build(pending, result=object())
        assert reg.counts()["sessions"] == 0

    def test_confirm_wrong_kind_and_unknown_session(self) -> None:
        reg = _registry()
        session_id, _ = reg.create_session(object())
        view_pending = reg.reserve_view(session_id)
        with pytest.raises(ReservationError):
            reg.confirm_build(view_pending, result=object())
        build_pending = reg.reserve_build()
        with pytest.raises(ReservationError):
            reg.confirm_view(build_pending)
        with pytest.raises(ReservationError):
            reg.confirm_build(424242, result=object())
        with pytest.raises(UnknownSessionError):
            reg.reserve_view(424242)
        reg.cancel_reservation(view_pending)
        reg.cancel_reservation(build_pending)

    def test_no_eviction_when_lowering_caps(self) -> None:
        reg = _registry(session_cap=4, view_cap=4)
        kept = [reg.create_session(object()) for _ in range(3)]
        reg.set_caps(1, 2)  # below current usage: nothing discarded
        assert reg.session_count == 3
        assert reg.view_count == 3
        with pytest.raises(AdmissionError):
            reg.reserve_build()
        with pytest.raises(AdmissionError):
            reg.reserve_view(kept[0][0])
        reg.set_caps(4, 4)  # raising caps re-admits growth
        assert reg.reserve_build() is not None

    def test_admission_message_identifies_counts(self) -> None:
        reg = _registry(session_cap=2, view_cap=4)
        reg.create_session(object())
        message = reg.admission_message()
        assert "sessions 1/2" in message and "views 1/4" in message


class TestLinkGroups:
    def test_create_join_leave_round_trip(self) -> None:
        reg = _registry()
        session_id, first = reg.create_session(object(), pane_index=0)
        second = reg.create_view(session_id, pane_index=1)
        third = reg.create_view(session_id)
        group = reg.create_link_group(session_id, [first, second])
        assert reg.link_members(group) == sorted([first, second])
        reg.join_link_group(third, group)
        assert reg.link_members(group) == sorted([first, second, third])
        assert reg.leave_link_group(third) is True
        assert reg.leave_link_group(third) is False
        assert reg.link_members(group) == sorted([first, second])

    def test_group_dissolves_below_two_members(self) -> None:
        reg = _registry()
        session_id, first = reg.create_session(object())
        second = reg.create_view(session_id)
        group = reg.create_link_group(session_id, [first, second])
        assert reg.leave_link_group(first) is True
        with pytest.raises(LinkGroupError):
            reg.link_members(group)
        assert reg.get_view(second).link_group_id is None

    def test_cross_session_link_rejected(self) -> None:
        reg = _registry()
        s1, v1 = reg.create_session(object())
        _, v2 = reg.create_session(object())
        with pytest.raises(LinkGroupError):
            reg.create_link_group(s1, [v1, v2])
        _, other = reg.create_session(object())
        group = reg.create_link_group(s1, [v1, reg.create_view(s1)])
        with pytest.raises(LinkGroupError):
            reg.join_link_group(other, group)
        with pytest.raises(LinkGroupError):
            reg.join_link_group(v2, 987654)
        with pytest.raises(LinkGroupError):
            reg.create_link_group(s1, [v1])

    def test_detached_members_allowed_and_discard_cleans_group(self) -> None:
        reg = _registry()
        session_id, first = reg.create_session(object())  # detached
        second = reg.create_view(session_id, pane_index=0)
        third = reg.create_view(session_id)
        group = reg.create_link_group(session_id, [first, second, third])
        reg.discard_view(first)
        assert reg.link_members(group) == sorted([second, third])


class TestSnapshots:
    def test_capture_apply_round_trip_without_aliasing(self) -> None:
        reg = _registry()
        _, view_id = reg.create_session(
            object(),
            slice_index=2,
            combine=MprCombineState(enabled=True, mode="mip", slice_count=6),
            display=MprDisplayState(window_center=40.0, window_width=400.0, wl_user_modified=True),
        )
        snapshot = reg.capture_view_snapshot(view_id)
        reg.set_view_slice(view_id, 0)
        reg.set_view_display(view_id, MprDisplayState())
        assert reg.get_view(view_id).slice_index == 0
        reg.apply_view_snapshot(snapshot)
        restored = reg.get_view(view_id)
        assert restored.slice_index == 2
        assert (restored.combine.enabled, restored.combine.mode, restored.combine.slice_count) == (True, "mip", 6)
        assert (restored.display.window_center, restored.display.window_width) == (40.0, 400.0)
        assert restored.display.wl_user_modified is True
        assert restored.pane_index is None  # snapshot never moves panes

    def test_snapshot_rejects_foreign_view(self) -> None:
        reg = _registry()
        _, view_id = reg.create_session(object())
        snapshot = reg.capture_view_snapshot(view_id)
        snapshot.view_id = 999999
        with pytest.raises(UnknownViewError):
            reg.apply_view_snapshot(snapshot)


class TestConfirmPrevalidation:
    def test_failed_build_confirm_retains_reservation_and_pane_map(self) -> None:
        reg = _registry()
        _, occupant = reg.create_session(object(), pane_index=0)
        rid = reg.reserve_build("ST", "SER")
        with pytest.raises(ValueError):
            reg.confirm_build(rid, result=object(), pane_index=-1)
        assert reg.counts()["sessions"] == 1  # no stranded session/view
        assert reg.counts()["views"] == 1
        assert reg.counts()["pending_sessions"] == 1  # token retained for retry/cancel
        assert reg.view_for_pane(0).view_id == occupant
        assert reg.cancel_reservation(rid) is True

    def test_failed_view_confirm_retains_reservation(self) -> None:
        reg = _registry()
        session_id, first = reg.create_session(object(), pane_index=0)
        rid = reg.reserve_view(session_id)
        with pytest.raises(ValueError):
            reg.confirm_view(rid, pane_index=-1)
        assert reg.counts()["views"] == 1
        assert reg.counts()["pending_views"] == 1
        assert reg.view_for_pane(0).view_id == first
        assert reg.cancel_reservation(rid) is True

    def test_post_consume_failure_in_confirm_build_creates_nothing_and_keeps_the_token(self) -> None:
        reg = _registry()
        rid = reg.reserve_build("ST", "SER")
        with pytest.raises(TypeError):
            reg.confirm_build(rid, result=object(), combine=object())  # malformed value state
        assert reg.counts()["sessions"] == 0  # no orphaned viewless session
        assert reg.counts()["views"] == 0
        assert reg.counts()["pending_sessions"] == 1  # token back to pending
        session_id, view_id = reg.confirm_build(rid, result=object())  # retry succeeds
        assert reg.counts() == {"sessions": 1, "session_cap": 8, "pending_sessions": 0,
                                "views": 1, "view_cap": 16, "pending_views": 0}
        assert reg.get_view(view_id).session_id == session_id

    def test_post_consume_failure_in_confirm_view_creates_nothing_and_keeps_the_token(self) -> None:
        reg = _registry()
        session_id, first = reg.create_session(object(), pane_index=0)
        rid = reg.reserve_view(session_id)
        with pytest.raises(TypeError):
            reg.confirm_view(rid, combine=object())  # malformed value state
        assert reg.counts()["views"] == 1
        assert reg.counts()["pending_views"] == 1
        assert reg.view_for_pane(0).view_id == first
        reg.confirm_view(rid, pane_index=1)  # retry succeeds
        assert reg.counts()["views"] == 2 and reg.cancel_reservation(rid) is False

    def test_wrappers_cancel_own_reservation_on_failure(self) -> None:
        reg = _registry()
        with pytest.raises(ValueError):
            reg.create_session(object(), pane_index=-1)
        with pytest.raises(ValueError):
            reg.create_view(reg.create_session(object())[0], pane_index=-1)
        assert reg.counts()["pending_sessions"] == 0
        assert reg.counts()["pending_views"] == 0
        assert reg.counts()["sessions"] == 1  # only the successful inner create
        assert reg.counts()["views"] == 1


class TestReservationSourceIdentity:
    def test_confirm_inherits_reservation_source(self) -> None:
        reg = _registry()
        rid = reg.reserve_build("ST", "SER")
        session_id, _ = reg.confirm_build(rid, result=object())
        assert reg.get_session(session_id).source_series_uid == "SER"
        assert [s.session_id for s in reg.sessions_for_series("SER")] == [session_id]
        summary = reg.close_source_series("SER")
        assert summary == {"sessions": 1, "views": 1, "reservations": 0}
        assert reg.counts()["sessions"] == 0


class TestLinkGroupDistinctness:
    def test_duplicate_members_rejected_without_disturbing_prior_group(self) -> None:
        reg = _registry()
        session_id, first = reg.create_session(object())
        second = reg.create_view(session_id)
        group = reg.create_link_group(session_id, [first, second])
        with pytest.raises(LinkGroupError):
            reg.create_link_group(session_id, [first, first])
        with pytest.raises(LinkGroupError):
            reg.create_link_group(session_id, [first, first, second])
        assert reg.link_members(group) == sorted([first, second])
        assert reg.get_view(first).link_group_id == group

    def test_regrouping_moves_members_and_dissolves_emptied_group(self) -> None:
        reg = _registry()
        session_id, first = reg.create_session(object())
        second = reg.create_view(session_id)
        third = reg.create_view(session_id)
        old = reg.create_link_group(session_id, [first, second])
        new = reg.create_link_group(session_id, [second, third])
        assert reg.link_members(new) == sorted([second, third])
        with pytest.raises(LinkGroupError):
            reg.link_members(old)
        assert reg.get_view(first).link_group_id is None


class TestCopyOnEntry:
    def test_shared_input_dataclasses_do_not_alias_siblings(self) -> None:
        reg = _registry()
        lut = object()
        shared_combine = MprCombineState(enabled=True, mode="mip", slice_count=6)
        shared_display = MprDisplayState(window_center=10.0, window_width=100.0, lut=lut)
        session_id, _ = reg.create_session(object())
        first = reg.create_view(session_id, combine=shared_combine, display=shared_display)
        second = reg.create_view(session_id, combine=shared_combine, display=shared_display)
        shared_combine.enabled = False
        shared_combine.mode = "aip"
        shared_display.window_center = 999.0
        for vid in (first, second):
            view = reg.get_view(vid)
            assert (view.combine.enabled, view.combine.mode, view.combine.slice_count) == (True, "mip", 6)
            assert view.display.window_center == 10.0
        assert reg.get_view(first).combine is not reg.get_view(second).combine
        assert reg.get_view(first).display is not reg.get_view(second).display
        assert reg.get_view(first).display.lut is lut  # opaque identity retained

    def test_setters_copy_inputs(self) -> None:
        reg = _registry()
        _, view_id = reg.create_session(object())
        combine = MprCombineState(enabled=True, mode="minip", slice_count=3)
        display = MprDisplayState(window_width=200.0)
        reg.set_view_combine(view_id, combine)
        reg.set_view_display(view_id, display)
        combine.enabled = False
        display.window_width = 1.0
        view = reg.get_view(view_id)
        assert (view.combine.enabled, view.combine.mode) == (True, "minip")
        assert view.display.window_width == 200.0

    def test_apply_snapshot_copies_snapshot_state(self) -> None:
        reg = _registry()
        _, view_id = reg.create_session(object(), slice_index=4)
        snapshot = reg.capture_view_snapshot(view_id)
        reg.set_view_slice(view_id, 0)
        reg.apply_view_snapshot(snapshot)
        snapshot.slice_index = 0
        snapshot.combine.enabled = True
        snapshot.display.window_center = 5.0
        view = reg.get_view(view_id)
        assert view.slice_index == 4
        assert view.combine.enabled is False
        assert view.display.window_center is None


class TestReservationTokenRemoval:
    def test_consume_and_cancel_remove_tokens(self) -> None:
        reg = _registry()
        build = reg.reserve_build()
        assert reg.counts()["pending_sessions"] == 1
        session_id, _ = reg.confirm_build(build, result=object())
        assert reg.counts()["pending_sessions"] == 0
        assert reg.cancel_reservation(build) is False  # replay of consumed token
        dup = reg.reserve_view(session_id)
        assert reg.cancel_reservation(dup) is True
        assert reg.counts()["pending_views"] == 0
        assert reg.cancel_reservation(dup) is False

    def test_clear_all_clears_reservation_tokens(self) -> None:
        reg = _registry()
        first = reg.reserve_build("ST", "A")
        reg.create_session(object(), source_study_uid="ST", source_series_uid="B")
        reg.clear_all()
        assert reg.counts()["pending_views"] == 0
        assert reg.counts()["pending_sessions"] == 0
        assert reg.cancel_reservation(first) is False
        with pytest.raises(ReservationError):
            reg.confirm_build(first, result=object())

    def test_closure_counts_tied_view_and_build_tokens(self) -> None:
        reg = _registry()
        session_id, _ = reg.create_session(object(), source_study_uid="ST", source_series_uid="A")
        tied_dup = reg.reserve_view(session_id)
        tied_build = reg.reserve_build("ST", "A")
        other = reg.reserve_build("OTHER", "B")
        summary = reg.close_source_series("A")
        assert summary == {"sessions": 1, "views": 1, "reservations": 2}
        assert reg.cancel_reservation(tied_dup) is False
        assert reg.cancel_reservation(tied_build) is False
        assert reg.cancel_reservation(other) is True  # unrelated token survives
        with pytest.raises(ReservationError):
            reg.confirm_view(tied_dup)
