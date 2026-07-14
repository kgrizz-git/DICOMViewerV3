"""
Unit tests for ``core.study_cache`` — LRU study cache with memory monitoring.
"""

from __future__ import annotations

from pydicom.dataset import Dataset

from core.study_cache import StudyCache, estimate_study_size_mb, get_process_memory_mb

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_studies_dict(study_uids: list[str]) -> dict:
    """Build a minimal studies dict with one series per study."""
    result: dict = {}
    for uid in study_uids:
        ds = Dataset()
        ds.StudyInstanceUID = uid
        ds.StudyDescription = f"Study {uid[-4:]}"
        ds.PatientName = "Test^Patient"
        ds.StudyDate = "20260101"
        result[uid] = {"1.2.3": [ds]}
    return result


# ---------------------------------------------------------------------------
# LRU ordering
# ---------------------------------------------------------------------------

class TestLRUOrdering:
    """LRU access-order tracking."""

    def test_mark_accessed_adds_new_study(self):
        cache = StudyCache(max_studies=5)
        cache.mark_accessed("A")
        cache.mark_accessed("B")
        assert cache.get_studies_by_lru_order() == ["A", "B"]

    def test_mark_accessed_moves_to_end(self):
        cache = StudyCache(max_studies=5)
        cache.mark_accessed("A")
        cache.mark_accessed("B")
        cache.mark_accessed("C")
        # Access A again — it should move to end
        cache.mark_accessed("A")
        assert cache.get_studies_by_lru_order() == ["B", "C", "A"]

    def test_remove(self):
        cache = StudyCache(max_studies=5)
        cache.mark_accessed("A")
        cache.mark_accessed("B")
        cache.remove("A")
        assert cache.get_studies_by_lru_order() == ["B"]
        assert cache.study_count() == 1

    def test_clear(self):
        cache = StudyCache(max_studies=5)
        cache.mark_accessed("A")
        cache.mark_accessed("B")
        cache.clear()
        assert cache.get_studies_by_lru_order() == []
        assert cache.study_count() == 0

    def test_study_count(self):
        cache = StudyCache(max_studies=5)
        assert cache.study_count() == 0
        cache.mark_accessed("X")
        cache.mark_accessed("Y")
        assert cache.study_count() == 2

    def test_mark_accessed_idempotent(self):
        """Marking the same study twice should not create duplicates."""
        cache = StudyCache(max_studies=5)
        cache.mark_accessed("A")
        cache.mark_accessed("A")
        assert cache.study_count() == 1
        assert cache.get_studies_by_lru_order() == ["A"]


# ---------------------------------------------------------------------------
# Eviction candidates
# ---------------------------------------------------------------------------

class TestEvictionCandidates:
    """Eviction candidate selection."""

    def test_no_eviction_needed(self):
        cache = StudyCache(max_studies=5)
        studies = _make_studies_dict(["A", "B", "C"])
        for uid in studies:
            cache.mark_accessed(uid)
        assert cache.get_eviction_candidates(studies) == []

    def test_evicts_oldest_first(self):
        cache = StudyCache(max_studies=3)
        uids = ["A", "B", "C", "D", "E"]
        studies = _make_studies_dict(uids)
        for uid in uids:
            cache.mark_accessed(uid)
        candidates = cache.get_eviction_candidates(studies)
        # Should evict the 2 oldest: A and B
        assert candidates == ["A", "B"]

    def test_never_evicts_active_study(self):
        cache = StudyCache(max_studies=2)
        uids = ["A", "B", "C", "D"]
        studies = _make_studies_dict(uids)
        for uid in uids:
            cache.mark_accessed(uid)
        # A is oldest but also active — should not be evicted
        candidates = cache.get_eviction_candidates(
            studies, active_study_uid="A"
        )
        assert "A" not in candidates
        # Should evict B and C (oldest non-active)
        assert candidates == ["B", "C"]

    def test_custom_max_studies(self):
        cache = StudyCache(max_studies=10)
        uids = ["A", "B", "C"]
        studies = _make_studies_dict(uids)
        for uid in uids:
            cache.mark_accessed(uid)
        # Override max_studies to 2
        candidates = cache.get_eviction_candidates(studies, max_studies=2)
        assert candidates == ["A"]

    def test_untracked_studies_fall_back(self):
        """Studies not in the LRU tracker are still considered for eviction."""
        cache = StudyCache(max_studies=2)
        # Only track B and C, but studies dict has A, B, C, D
        cache.mark_accessed("B")
        cache.mark_accessed("C")
        studies = _make_studies_dict(["A", "B", "C", "D"])
        candidates = cache.get_eviction_candidates(studies)
        # Should evict B (oldest tracked) plus A or D (untracked fallback)
        assert len(candidates) == 2
        assert "B" in candidates  # oldest tracked


# ---------------------------------------------------------------------------
# Memory estimation
# ---------------------------------------------------------------------------

class TestMemoryEstimation:
    """Study size estimation (basic sanity)."""

    def test_empty_study(self):
        assert estimate_study_size_mb("missing", {}) == 0.0

    def test_nonzero_for_datasets_with_pixel_data(self):
        ds = Dataset()
        ds.StudyInstanceUID = "S1"
        # Add PixelData tag with some bytes
        ds.PixelData = b"\x00" * 10000
        studies = {"S1": {"series1": [ds]}}
        size = estimate_study_size_mb("S1", studies)
        assert size > 0.0

    def test_accounts_for_metadata_overhead(self):
        ds = Dataset()
        ds.StudyInstanceUID = "S1"
        studies = {"S1": {"series1": [ds]}}
        size = estimate_study_size_mb("S1", studies)
        # At least the 1 KB metadata overhead estimate
        assert size > 0.0


# ---------------------------------------------------------------------------
# Memory monitoring
# ---------------------------------------------------------------------------

class TestMemoryMonitoring:
    """Process memory monitoring."""

    def test_get_process_memory_returns_float(self):
        result = get_process_memory_mb()
        assert isinstance(result, float)
        # Should be non-negative
        assert result >= 0.0

    def test_would_exceed_memory_false_for_high_threshold(self):
        cache = StudyCache(memory_threshold_mb=999999.0)
        # With a very high threshold, should not exceed
        assert cache.would_exceed_memory() is False

    def test_would_exceed_memory_with_override(self):
        cache = StudyCache(memory_threshold_mb=999999.0)
        # With a tiny override, should exceed (unless memory is unmeasurable)
        result = cache.would_exceed_memory(threshold_mb=0.001)
        # If memory measurement works, this should be True
        mem = cache.get_memory_usage_mb()
        if mem > 0.0:
            assert result is True
        else:
            # Cannot measure memory; would_exceed_memory returns False
            assert result is False


# ---------------------------------------------------------------------------
# Study description helper
# ---------------------------------------------------------------------------

class TestStudyDescription:
    """get_study_description helper."""

    def test_returns_description_from_dataset(self):
        cache = StudyCache()
        ds = Dataset()
        ds.StudyDescription = "Brain MRI"
        ds.PatientName = "Doe^John"
        ds.StudyDate = "20260101"
        studies = {"S1": {"series1": [ds]}}
        desc = cache.get_study_description("S1", studies)
        assert "Brain MRI" in desc
        assert "Doe^John" in desc

    def test_falls_back_to_uid(self):
        cache = StudyCache()
        studies = {"S1": {"series1": []}}
        desc = cache.get_study_description("S1", studies)
        assert desc == "S1"

    def test_missing_study(self):
        cache = StudyCache()
        desc = cache.get_study_description("missing", {})
        assert desc == "missing"
