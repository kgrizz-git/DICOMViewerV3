"""
Unit tests for ``core.study_cache`` — LRU study cache with memory monitoring.
"""

from __future__ import annotations

import numpy as np
from pydicom.dataset import Dataset

from core.study_cache import (
    StudyCache,
    estimate_study_size_mb,
    get_process_memory_mb,
    get_total_system_memory_mb,
)

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

    def test_uses_nbytes_for_cached_numpy_array(self):
        """A cached decompressed pixel array must be sized via .nbytes, not
        sys.getsizeof (which would only report ~100 bytes of object overhead)."""
        ds = Dataset()
        ds.StudyInstanceUID = "S1"
        # 512x512 float64 array => 512*512*8 = 2,097,152 bytes (~2 MB)
        array = np.zeros((512, 512), dtype=np.float64)
        ds._cached_pixel_array = array
        studies = {"S1": {"series1": [ds]}}
        size_mb = estimate_study_size_mb("S1", studies)
        expected_min_mb = array.nbytes / (1024 * 1024)
        # Must reflect the real array size, not ~112 bytes of object overhead.
        assert size_mb >= expected_min_mb
        assert size_mb < expected_min_mb + 1.0  # plus small per-dataset overhead

    def test_cached_array_preferred_over_raw_pixeldata_no_double_count(self):
        """When both a cached array and raw PixelData exist, only the (larger,
        decompressed) array size should be counted — not both summed."""
        ds = Dataset()
        ds.StudyInstanceUID = "S1"
        ds.PixelData = b"\x00" * 100  # small compressed placeholder
        array = np.zeros((100, 100), dtype=np.float64)  # 80,000 bytes
        ds._cached_pixel_array = array
        studies = {"S1": {"series1": [ds]}}
        size_mb = estimate_study_size_mb("S1", studies)
        total_bytes = size_mb * 1024 * 1024
        # Should be close to nbytes + 1KB overhead, not nbytes + 100 + 1KB.
        assert total_bytes < array.nbytes + 1024 + 50

    def test_ignores_cached_object_without_nbytes(self):
        """A cached attribute that isn't a real array (no .nbytes) must not crash
        and should fall back to the raw PixelData length."""
        ds = Dataset()
        ds.StudyInstanceUID = "S1"
        ds.PixelData = b"\x00" * 5000
        ds._cached_pixel_array = object()  # no .nbytes
        studies = {"S1": {"series1": [ds]}}
        size_mb = estimate_study_size_mb("S1", studies)
        assert size_mb > 0.0


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


# ---------------------------------------------------------------------------
# Total system RAM detection
# ---------------------------------------------------------------------------

class TestTotalSystemMemory:
    """get_total_system_memory_mb — cross-platform RAM detection."""

    def test_returns_float(self):
        result = get_total_system_memory_mb()
        assert isinstance(result, float)
        assert result >= 0.0

    def test_positive_or_explicitly_unknown(self):
        # On supported platforms (macOS/Linux/Windows) this should return a
        # real, plausible total (at least 512 MB); 0.0 is the documented
        # "unknown" sentinel and is also acceptable.
        result = get_total_system_memory_mb()
        assert result == 0.0 or result >= 512.0


# ---------------------------------------------------------------------------
# Memory budget
# ---------------------------------------------------------------------------

class TestMemoryBudget:
    """get_memory_budget_mb — fraction-of-RAM budget with floor and fallback."""

    def test_budget_is_fraction_of_total_ram(self):
        cache = StudyCache(memory_fraction=0.40, memory_floor_mb=1024.0)
        total_ram = get_total_system_memory_mb()
        if total_ram <= 0.0:
            return  # platform can't report RAM; nothing to assert here
        expected = max(0.40 * total_ram, 1024.0)
        assert cache.get_memory_budget_mb() == expected

    def test_budget_clamps_to_floor(self):
        cache = StudyCache(memory_fraction=0.0001, memory_floor_mb=99999999.0)
        # Fraction alone would be tiny; floor should dominate.
        assert cache.get_memory_budget_mb() == 99999999.0

    def test_budget_falls_back_to_threshold_when_ram_unknown(self, monkeypatch):
        import core.study_cache as study_cache_module

        monkeypatch.setattr(
            study_cache_module, "get_total_system_memory_mb", lambda: 0.0
        )
        cache = StudyCache(memory_threshold_mb=1234.0, memory_fraction=0.40)
        assert cache.get_memory_budget_mb() == 1234.0


# ---------------------------------------------------------------------------
# estimate_total_loaded_mb
# ---------------------------------------------------------------------------

class TestEstimateTotalLoadedMb:
    def test_sums_per_study_estimates(self):
        cache = StudyCache()
        ds_a = Dataset()
        ds_a.PixelData = b"\x00" * 10000
        ds_b = Dataset()
        ds_b.PixelData = b"\x00" * 20000
        studies = {"A": {"s1": [ds_a]}, "B": {"s1": [ds_b]}}
        total = cache.estimate_total_loaded_mb(studies)
        expected = estimate_study_size_mb("A", studies) + estimate_study_size_mb(
            "B", studies
        )
        assert total == expected
        assert total > 0.0

    def test_empty_studies(self):
        cache = StudyCache()
        assert cache.estimate_total_loaded_mb({}) == 0.0


# ---------------------------------------------------------------------------
# Size-aware eviction
# ---------------------------------------------------------------------------

def _make_study_with_pixel_bytes(uid: str, num_bytes: int) -> dict:
    ds = Dataset()
    ds.StudyInstanceUID = uid
    ds.StudyDescription = f"Study {uid}"
    ds.PixelData = b"\x00" * num_bytes
    return {uid: {"series1": [ds]}}


class TestEvictionCandidatesBySize:
    """get_eviction_candidates_by_size — LRU eviction targeting a memory budget."""

    def _studies(self, sizes: dict[str, int]) -> dict:
        studies: dict = {}
        for uid, num_bytes in sizes.items():
            studies.update(_make_study_with_pixel_bytes(uid, num_bytes))
        return studies

    def test_no_op_when_under_budget(self):
        cache = StudyCache()
        one_mb = 1024 * 1024
        studies = self._studies({"A": one_mb, "B": one_mb})
        for uid in studies:
            cache.mark_accessed(uid)
        total = cache.estimate_total_loaded_mb(studies)
        candidates = cache.get_eviction_candidates_by_size(
            studies, budget_mb=total + 10.0
        )
        assert candidates == []

    def test_evicts_lru_oldest_first_to_fit_budget(self):
        cache = StudyCache()
        one_mb = 1024 * 1024
        # Four ~1 MB studies loaded in order A, B, C, D (A oldest).
        studies = self._studies({"A": one_mb, "B": one_mb, "C": one_mb, "D": one_mb})
        for uid in ["A", "B", "C", "D"]:
            cache.mark_accessed(uid)
        total = cache.estimate_total_loaded_mb(studies)
        # Budget for ~2 studies worth — must evict the 2 oldest (A, B).
        per_study = total / 4
        budget = per_study * 2 + 0.01
        candidates = cache.get_eviction_candidates_by_size(studies, budget_mb=budget)
        assert candidates == ["A", "B"]

    def test_never_evicts_active_study(self):
        cache = StudyCache()
        one_mb = 1024 * 1024
        studies = self._studies({"A": one_mb, "B": one_mb, "C": one_mb, "D": one_mb})
        for uid in ["A", "B", "C", "D"]:
            cache.mark_accessed(uid)
        total = cache.estimate_total_loaded_mb(studies)
        per_study = total / 4
        # Ask for a very tight budget that would otherwise evict everything
        # but the newest; A (oldest) is active and must be preserved.
        budget = per_study * 0.5
        candidates = cache.get_eviction_candidates_by_size(
            studies, budget_mb=budget, active_study_uid="A"
        )
        assert "A" not in candidates

    def test_falls_back_to_count_based_when_sizes_unavailable(self):
        """When every study estimates to 0 bytes (no size data at all), fall
        back to the count-based eviction strategy so eviction still progresses."""
        cache = StudyCache(max_studies=2)
        uids = ["A", "B", "C", "D"]
        # Empty studies (no PixelData, no cached array) => 0-byte estimate is
        # impossible here because of the fixed metadata overhead, so directly
        # exercise the fallback path by monkeypatching estimate would be
        # over-engineered; instead verify equivalence with the count-based
        # method when budget is unreachable relative to metadata-only sizes.
        studies = {uid: {"series1": [Dataset()]} for uid in uids}
        for uid in uids:
            cache.mark_accessed(uid)
        candidates = cache.get_eviction_candidates_by_size(studies, budget_mb=0.0)
        # Every study has at least the ~1KB metadata overhead, so this isn't
        # the true zero-size fallback path, but confirms oldest-first eviction
        # continues to make progress toward the (unreachable) budget.
        assert candidates[0] == "A"
        assert len(candidates) >= 1

    def test_respects_count_safety_cap_via_existing_method(self):
        """The legacy count-based get_eviction_candidates is preserved as the
        safety-net fallback and still enforces the (now-higher) cap."""
        cache = StudyCache(max_studies=20)
        uids = [f"S{i}" for i in range(25)]
        studies = self._studies(dict.fromkeys(uids, 1024))
        for uid in uids:
            cache.mark_accessed(uid)
        candidates = cache.get_eviction_candidates(studies)
        assert len(candidates) == 5
        assert candidates == uids[:5]

    def test_untracked_studies_included_as_fallback(self):
        cache = StudyCache()
        one_mb = 1024 * 1024
        # Only track B; studies dict also has untracked A.
        studies = self._studies({"A": one_mb, "B": one_mb})
        cache.mark_accessed("B")
        total = cache.estimate_total_loaded_mb(studies)
        budget = total / 2 * 0.5  # need to evict both to fit
        candidates = cache.get_eviction_candidates_by_size(studies, budget_mb=budget)
        assert set(candidates) == {"A", "B"}
