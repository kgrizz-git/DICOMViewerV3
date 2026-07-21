"""
Tests for the LRU study-cache eviction trigger wired into
``FileSeriesLoadingCoordinator.handle_additive_load``.

Covers: memory-budget-based eviction (size-aware candidates), the
count-based safety-net cap, the confirmation dialog reason text, and the
cancel/undo path — all with a fake app and a mocked StudyCache so the
coordinator's decision logic is exercised in isolation from StudyCache's
own internals (covered separately in tests/test_study_cache.py).
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from pydicom.dataset import Dataset

from core.study_cache import StudyCache
from gui.file_series_loading_coordinator import FileSeriesLoadingCoordinator


def _make_app(studies: dict, study_cache) -> MagicMock:
    """Build a permissive fake app: a MagicMock with the specific attributes
    handle_additive_load's downstream (non-eviction) code needs to be
    real/inert rather than an opaque Mock, so the full method can run to
    completion without raising."""
    app = MagicMock()
    app.dicom_organizer = MagicMock()
    app.dicom_organizer.studies = studies
    app.current_studies = studies
    app.current_study_uid = ""
    app.study_cache = study_cache
    app.subwindow_data = {}
    app.subwindow_managers = {}
    app.multi_window_layout.get_all_subwindows.return_value = []
    app.focused_subwindow_index = 0
    app.main_window.series_navigator_visible = True
    return app


def _study(uid: str, num_pixel_bytes: int = 1000) -> dict:
    ds = Dataset()
    ds.StudyInstanceUID = uid
    ds.StudyDescription = f"Study {uid}"
    ds.PixelData = b"\x00" * num_pixel_bytes
    return {uid: {"series1": [ds]}}


def _merge_result(new_series: list[tuple[str, str]]) -> SimpleNamespace:
    return SimpleNamespace(
        new_series=new_series,
        appended_series=[],
        skipped_file_count=0,
        added_file_count=len(new_series),
    )


class TestEvictionUnderBudget:
    def test_no_eviction_when_under_budget_and_under_cap(self):
        studies = _study("A")
        study_cache = MagicMock(spec=StudyCache)
        study_cache.max_studies = 20
        study_cache.get_memory_budget_mb.return_value = 100.0
        study_cache.estimate_total_loaded_mb.return_value = 1.0
        study_cache.would_exceed_memory.return_value = False

        app = _make_app(studies, study_cache)
        coordinator = FileSeriesLoadingCoordinator(app)

        with patch(
            "core.study_cache.show_eviction_confirmation"
        ) as mock_confirm:
            coordinator.handle_additive_load(_merge_result([("A", "series1")]))

        mock_confirm.assert_not_called()
        study_cache.get_eviction_candidates_by_size.assert_not_called()
        study_cache.evict_study.assert_not_called()


class TestEvictionOverBudget:
    def test_exceeding_budget_requests_size_based_candidates_with_memory_reason(self):
        studies = {**_study("A"), **_study("B")}
        study_cache = MagicMock(spec=StudyCache)
        study_cache.max_studies = 20
        study_cache.get_memory_budget_mb.return_value = 10.0
        study_cache.estimate_total_loaded_mb.return_value = 500.0  # over budget
        study_cache.would_exceed_memory.return_value = False
        study_cache.get_eviction_candidates_by_size.return_value = ["A"]
        study_cache.get_study_description.return_value = "Study A"

        app = _make_app(studies, study_cache)
        coordinator = FileSeriesLoadingCoordinator(app)

        with patch(
            "core.study_cache.show_eviction_confirmation", return_value=False
        ) as mock_confirm:
            coordinator.handle_additive_load(_merge_result([("B", "series1")]))

        # Candidates were requested by size, targeting the reported budget.
        study_cache.get_eviction_candidates_by_size.assert_called_once()
        call_args = study_cache.get_eviction_candidates_by_size.call_args
        assert call_args.args[0] is studies
        assert call_args.args[1] == 10.0

        # Confirmation dialog was shown with the "memory budget" reason.
        mock_confirm.assert_called_once()
        reason = mock_confirm.call_args.args[1]
        assert reason == "memory budget"

    def test_would_exceed_memory_also_triggers_memory_budget_reason(self):
        studies = {**_study("A"), **_study("B")}
        study_cache = MagicMock(spec=StudyCache)
        study_cache.max_studies = 20
        study_cache.get_memory_budget_mb.return_value = 100.0
        study_cache.estimate_total_loaded_mb.return_value = 1.0  # under estimated budget...
        study_cache.would_exceed_memory.return_value = True  # ...but RSS check trips
        study_cache.get_eviction_candidates_by_size.return_value = ["A"]
        study_cache.get_study_description.return_value = "Study A"

        app = _make_app(studies, study_cache)
        coordinator = FileSeriesLoadingCoordinator(app)

        with patch(
            "core.study_cache.show_eviction_confirmation", return_value=False
        ) as mock_confirm:
            coordinator.handle_additive_load(_merge_result([("B", "series1")]))

        mock_confirm.assert_called_once()
        assert mock_confirm.call_args.args[1] == "memory budget"

    def test_cancel_undoes_the_merge_and_removes_new_studies(self):
        studies = {**_study("A"), **_study("B")}
        study_cache = MagicMock(spec=StudyCache)
        study_cache.max_studies = 20
        study_cache.get_memory_budget_mb.return_value = 10.0
        study_cache.estimate_total_loaded_mb.return_value = 500.0
        study_cache.would_exceed_memory.return_value = False
        study_cache.get_eviction_candidates_by_size.return_value = ["A"]
        study_cache.get_study_description.return_value = "Study A"

        app = _make_app(studies, study_cache)
        coordinator = FileSeriesLoadingCoordinator(app)

        with patch(
            "core.study_cache.show_eviction_confirmation", return_value=False
        ):
            coordinator.handle_additive_load(_merge_result([("B", "series1")]))

        # Cancelled: the newly-added study ("B") is removed from the organizer
        # and the LRU tracker; evict_study is never called on any candidate.
        app.dicom_organizer.remove_study.assert_called_once_with("B")
        study_cache.remove.assert_any_call("B")
        study_cache.evict_study.assert_not_called()

    def test_confirm_evicts_candidates_and_resyncs(self):
        studies = {**_study("A"), **_study("B")}
        study_cache = MagicMock(spec=StudyCache)
        study_cache.max_studies = 20
        study_cache.get_memory_budget_mb.return_value = 10.0
        study_cache.estimate_total_loaded_mb.return_value = 500.0
        study_cache.would_exceed_memory.return_value = False
        study_cache.get_eviction_candidates_by_size.return_value = ["A"]
        study_cache.get_study_description.return_value = "Study A"

        app = _make_app(studies, study_cache)
        coordinator = FileSeriesLoadingCoordinator(app)

        with patch(
            "core.study_cache.show_eviction_confirmation", return_value=True
        ):
            coordinator.handle_additive_load(_merge_result([("B", "series1")]))

        study_cache.evict_study.assert_called_once_with("A", app)


class TestEvictionCountCapSafetyNet:
    def test_over_cap_but_under_budget_uses_study_count_cap_reason(self):
        studies = {**_study("A"), **_study("B"), **_study("C")}
        study_cache = MagicMock(spec=StudyCache)
        study_cache.max_studies = 2  # cap exceeded by 3 studies
        study_cache.get_memory_budget_mb.return_value = 100000.0  # budget is huge
        study_cache.estimate_total_loaded_mb.return_value = 1.0  # well under budget
        study_cache.would_exceed_memory.return_value = False
        # Size-based candidates would be empty (under budget); count-based
        # fallback should be consulted to satisfy the cap.
        study_cache.get_eviction_candidates_by_size.return_value = []
        study_cache.get_eviction_candidates.return_value = ["A"]
        study_cache.get_study_description.return_value = "Study A"

        app = _make_app(studies, study_cache)
        coordinator = FileSeriesLoadingCoordinator(app)

        with patch(
            "core.study_cache.show_eviction_confirmation", return_value=False
        ) as mock_confirm:
            coordinator.handle_additive_load(_merge_result([("C", "series1")]))

        study_cache.get_eviction_candidates.assert_called_once()
        mock_confirm.assert_called_once()
        assert mock_confirm.call_args.args[1] == "study count cap"
