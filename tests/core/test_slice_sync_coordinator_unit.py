"""Unit tests for core.slice_sync_coordinator orchestration.

SliceStack geometry and find_nearest_slice are stubbed so the coordinator's
grouping, caching, hint-debounce, and target-update dispatch are exercised
without real 3-D geometry.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

from core import slice_sync_coordinator as ssc
from core.slice_sync_coordinator import SliceSyncCoordinator


class _FakeStack:
    def __init__(self, thickness=2.0) -> None:
        self.planes = [object(), object()]
        self.slice_thickness = thickness
        self.original_indices = [0, 1]


def _coord(subwindow_data=None, managers=None) -> SliceSyncCoordinator:
    app = SimpleNamespace(
        subwindow_data=subwindow_data or {},
        subwindow_managers=managers or {},
        current_studies={},
        main_window=MagicMock(),
    )
    return SliceSyncCoordinator(app)


# --------------------------------------------------------------------------- #
# config + cache
# --------------------------------------------------------------------------- #

def test_set_enabled_and_groups_filters_small_groups() -> None:
    c = _coord()
    c.set_enabled(True)
    assert c.enabled is True
    c.set_groups([[0, 1], [2], "bad", [3, 4, 5]])
    assert c.groups == [[0, 1], [3, 4, 5]]


def test_invalidate_cache_all_study_and_series() -> None:
    c = _coord()
    c._stack_cache = {("s1", "r1"): 1, ("s1", "r2"): 2, ("s2", "r3"): 3}
    c.invalidate_cache("s1", "r1")
    assert ("s1", "r1") not in c._stack_cache and ("s1", "r2") in c._stack_cache
    c.invalidate_cache("s1")
    assert all(s != "s1" for (s, _r) in c._stack_cache)
    c.invalidate_cache()
    assert c._stack_cache == {}


def test_find_group_and_slice_index_helpers() -> None:
    c = _coord(subwindow_data={0: {"current_slice_index": 5, "current_datasets": ["a"]}})
    c.groups = [[0, 1]]
    assert c._find_group(0) == [0, 1]
    assert c._find_group(9) is None
    assert c._get_slice_index(0) == 5
    assert c._get_datasets(0) == ["a"]
    assert c._get_datasets(1) is None


# --------------------------------------------------------------------------- #
# get_current_plane / get_slice_thickness
# --------------------------------------------------------------------------- #

def test_get_current_plane(monkeypatch) -> None:
    c = _coord()
    stack = _FakeStack()
    monkeypatch.setattr(c, "_get_stack", lambda idx: stack)
    monkeypatch.setattr(c, "_get_slice_index", lambda idx: 1)
    monkeypatch.setattr(c, "_dataset_idx_to_sorted_pos", lambda idx, di, st: 1)
    assert c.get_current_plane(0) is stack.planes[1]


def test_get_current_plane_none_stack(monkeypatch) -> None:
    c = _coord()
    monkeypatch.setattr(c, "_get_stack", lambda idx: None)
    assert c.get_current_plane(0) is None


def test_get_slice_thickness(monkeypatch) -> None:
    c = _coord()
    monkeypatch.setattr(c, "_get_stack", lambda idx: _FakeStack(thickness=3.5))
    assert c.get_slice_thickness(0) == 3.5
    monkeypatch.setattr(c, "_get_stack", lambda idx: None)
    assert c.get_slice_thickness(0) is None


# --------------------------------------------------------------------------- #
# _get_stack
# --------------------------------------------------------------------------- #

def test_get_stack_mpr(monkeypatch) -> None:
    mpr = SimpleNamespace(slice_stack=_FakeStack())
    c = _coord(subwindow_data={0: {"is_mpr": True, "mpr_result": mpr}})
    assert c._get_stack(0) is mpr.slice_stack


def test_get_stack_no_series_returns_none() -> None:
    c = _coord(subwindow_data={0: {}})
    assert c._get_stack(0) is None


def test_get_stack_no_datasets_caches_none() -> None:
    c = _coord(subwindow_data={0: {"current_study_uid": "s", "current_series_uid": "r"}})
    assert c._get_stack(0) is None
    assert c._stack_cache[("s", "r")] is None


def test_get_stack_builds_from_datasets(monkeypatch) -> None:
    fake = _FakeStack()
    monkeypatch.setattr(ssc.SliceStack, "from_datasets", staticmethod(lambda ds: fake))
    c = _coord(subwindow_data={0: {"current_study_uid": "s", "current_series_uid": "r",
                                   "current_datasets": ["d0", "d1"]}})
    assert c._get_stack(0) is fake
    # cached on 2nd call
    assert c._get_stack(0) is fake


# --------------------------------------------------------------------------- #
# _dataset_idx_to_sorted_pos
# --------------------------------------------------------------------------- #

def test_dataset_idx_to_sorted_pos_direct_and_clamp() -> None:
    c = _coord()
    stack = _FakeStack()
    stack.original_indices = [0, 2, 4]
    assert c._dataset_idx_to_sorted_pos(0, 2, stack) == 1  # direct hit
    assert c._dataset_idx_to_sorted_pos(0, 3, stack) == 1  # nearest to 3 is 2 (pos 1)
    empty = _FakeStack()
    empty.original_indices = []
    assert c._dataset_idx_to_sorted_pos(0, 3, empty) is None


# --------------------------------------------------------------------------- #
# on_slice_changed
# --------------------------------------------------------------------------- #

def test_on_slice_changed_disabled_noop() -> None:
    c = _coord()
    c.enabled = False
    c.on_slice_changed(0)  # no raise


def test_on_slice_changed_not_in_group() -> None:
    c = _coord()
    c.enabled = True
    c.groups = [[1, 2]]
    c.on_slice_changed(0)  # source 0 not grouped -> returns


def test_on_slice_changed_syncs_and_surfaces_hint(monkeypatch) -> None:
    c = _coord(subwindow_data={0: {}, 1: {}})
    c.enabled = True
    c.groups = [[0, 1]]
    stack = _FakeStack()
    monkeypatch.setattr(c, "_get_stack", lambda idx: stack)
    monkeypatch.setattr(c, "_get_slice_index", lambda idx: 0)
    monkeypatch.setattr(c, "_dataset_idx_to_sorted_pos", lambda idx, di, st: 0)
    monkeypatch.setattr(c, "_update_target", lambda t, plane: "outside_coverage")
    c.on_slice_changed(0)
    c.app.main_window.update_status.assert_called_once()
    assert "window 2" in c.app.main_window.update_status.call_args[0][0]




def test_on_slice_changed_uses_mapper_for_permuted_indices(monkeypatch) -> None:
    """Collapse of the S3923 if/else must keep dataset→sorted mapping.

    When original_indices is a non-identity permutation, both an in-range and
    an out-of-range source_slice_idx must resolve through the mapper — never
    by indexing planes with the raw dataset index.
    """
    c = _coord(subwindow_data={0: {}, 1: {}})
    c.enabled = True
    c.groups = [[0, 1]]

    class _PermutedStack:
        def __init__(self) -> None:
            self.planes = ["p0", "p1", "p2"]
            # sorted_pos 0→dataset 2, 1→dataset 0, 2→dataset 1
            self.original_indices = [2, 0, 1]
            self.slice_thickness = 2.0

    stack = _PermutedStack()
    seen: list[tuple[int, object]] = []

    def _map(idx, dataset_idx, st):
        return st.original_indices.index(dataset_idx)

    def _update(target, plane):
        seen.append((target, plane))
        return None

    monkeypatch.setattr(c, "_get_stack", lambda idx: stack)
    monkeypatch.setattr(c, "_dataset_idx_to_sorted_pos", _map)
    monkeypatch.setattr(c, "_update_target", _update)

    # In-range dataset index 0 → sorted_pos 1 → plane "p1"
    monkeypatch.setattr(c, "_get_slice_index", lambda idx: 0)
    seen.clear()
    c.on_slice_changed(0)
    assert seen == [(1, "p1")]

    # Out-of-range dataset index 9 → mapper clamp/nearest → sorted_pos for nearest
    # nearest to 9 among [2,0,1] is 2 → sorted_pos 0 → plane "p0"
    def _map_clamp(idx, dataset_idx, st):
        try:
            return st.original_indices.index(dataset_idx)
        except ValueError:
            best = min(
                range(len(st.original_indices)),
                key=lambda i: abs(st.original_indices[i] - dataset_idx),
            )
            return best

    monkeypatch.setattr(c, "_dataset_idx_to_sorted_pos", _map_clamp)
    monkeypatch.setattr(c, "_get_slice_index", lambda idx: 9)
    seen.clear()
    c.on_slice_changed(0)
    assert seen == [(1, "p0")]


# --------------------------------------------------------------------------- #
# _surface_sync_hint (debounce)
# --------------------------------------------------------------------------- #

def test_surface_hint_single_multiple_and_clear() -> None:
    c = _coord()
    mw = c.app.main_window
    c._surface_sync_hint([2])
    assert "window 3" in mw.update_status.call_args[0][0]
    c._surface_sync_hint([0, 1])
    assert "1, 2" in mw.update_status.call_args[0][0]
    # Clear
    c._surface_sync_hint([])
    assert mw.update_status.call_args[0][0] == ""


def test_surface_hint_debounces_repeat() -> None:
    c = _coord()
    mw = c.app.main_window
    c._surface_sync_hint([1])
    count = mw.update_status.call_count
    c._surface_sync_hint([1])  # same hint -> no new call
    assert mw.update_status.call_count == count


# --------------------------------------------------------------------------- #
# _update_target
# --------------------------------------------------------------------------- #

def test_update_target_none_stack(monkeypatch) -> None:
    c = _coord()
    monkeypatch.setattr(c, "_get_stack", lambda idx: None)
    assert c._update_target(1, object()) is None


def test_update_target_outside_coverage(monkeypatch) -> None:
    c = _coord()
    monkeypatch.setattr(c, "_get_stack", lambda idx: _FakeStack())
    monkeypatch.setattr(ssc, "find_nearest_slice", lambda plane, stack, tol: None)
    assert c._update_target(1, object()) == "outside_coverage"


def test_update_target_no_change(monkeypatch) -> None:
    c = _coord(subwindow_data={1: {"current_slice_index": 3}})
    monkeypatch.setattr(c, "_get_stack", lambda idx: _FakeStack())
    monkeypatch.setattr(ssc, "find_nearest_slice", lambda plane, stack, tol: 3)
    assert c._update_target(1, object()) is None


def test_update_target_updates_and_displays(monkeypatch) -> None:
    sdm = MagicMock()
    c = _coord(
        subwindow_data={1: {"current_slice_index": 0, "current_datasets": ["d0", "d1"]}},
        managers={1: {"slice_display_manager": sdm}},
    )
    monkeypatch.setattr(c, "_get_stack", lambda idx: _FakeStack())
    monkeypatch.setattr(ssc, "find_nearest_slice", lambda plane, stack, tol: 1)
    c._update_target(1, object())
    assert c.app.subwindow_data[1]["current_slice_index"] == 1
    sdm.display_slice.assert_called_once()
