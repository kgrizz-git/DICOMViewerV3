"""Approximate MPR memory estimate: deduplication, metadata-only volume sizing, no allocation."""

from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest

from core.mpr_memory_estimate import (
    THUMBNAIL_BYTES_PER_VIEW,
    BufferLedger,
    array_owner,
    estimate_memory,
    estimate_pending_volume_bytes,
    format_mib,
    sitk_volume_bytes,
)

MIB = 1024 * 1024


class _Image:
    """SimpleITK image stand-in exposing only metadata; touching pixels is an error."""

    def __init__(self, voxels: int, components: int = 1, pixel_id: str = "32-bit float") -> None:
        self._v, self._c, self._p = voxels, components, pixel_id

    def GetNumberOfPixels(self) -> int:
        return self._v

    def GetNumberOfComponentsPerPixel(self) -> int:
        return self._c

    def GetPixelIDTypeAsString(self) -> str:
        return self._p

    def GetBufferAsFloat(self):
        raise AssertionError("pixel buffer must never be touched")

    GetBufferAsArray = GetBufferAsFloat


def _result(slices, image=None) -> SimpleNamespace:
    return SimpleNamespace(slices=slices, source_volume=SimpleNamespace(sitk_image=image))


class TestVolumeSizing:
    @pytest.mark.parametrize(
        ("voxels", "components", "pixel_id", "expected"),
        [
            (1000, 1, "32-bit float", 4000),
            (1000, 1, "16-bit signed integer", 2000),
            (1000, 1, "8-bit unsigned integer", 1000),
            (1000, 1, "64-bit float", 8000),
            (1000, 3, "vector of 32-bit float", 12000),
            (1000, 1, "something unrecognised", 4000),  # float32 assumed
        ],
    )
    def test_bytes_come_from_metadata_only(self, voxels, components, pixel_id, expected) -> None:
        assert sitk_volume_bytes(_Image(voxels, components, pixel_id)) == expected

    def test_unreadable_images_count_as_zero(self) -> None:
        assert sitk_volume_bytes(object()) == 0
        assert sitk_volume_bytes(None) == 0

    def test_real_simpleitk_image_matches_its_voxel_count(self) -> None:
        sitk = pytest.importorskip("SimpleITK")
        image = sitk.Image(10, 12, 5, sitk.sitkFloat32)
        assert sitk_volume_bytes(image) == 10 * 12 * 5 * 4


class TestOwnership:
    def test_independent_arrays_own_themselves(self) -> None:
        a, b = np.zeros((4, 4), np.float32), np.zeros((4, 4), np.float32)
        assert array_owner(a)[0] != array_owner(b)[0]
        assert array_owner(a)[1] == a.nbytes

    def test_views_resolve_to_the_owning_array_at_full_size(self) -> None:
        stack = np.zeros((6, 8, 8), np.float32)
        view = stack[2]
        nested = view[::2, ::2]
        assert array_owner(view) == array_owner(stack) == array_owner(nested)
        assert array_owner(nested)[1] == stack.nbytes  # a small view keeps the whole stack alive

    def test_foreign_buffers_are_charged_through_the_buffer(self) -> None:
        raw = bytearray(4 * 16)
        a = np.frombuffer(raw, dtype=np.float32)[:8]
        b = np.frombuffer(raw, dtype=np.float32)[8:]
        assert array_owner(a)[0] == array_owner(b)[0]
        assert array_owner(a)[1] == len(raw)


class TestDeduplication:
    def test_slices_cut_from_one_stack_count_once(self) -> None:
        stack = np.zeros((5, 16, 16), np.float32)
        est = estimate_memory([_result([stack[i] for i in range(5)])], view_count=0)
        assert est.result_bytes == stack.nbytes

    def test_independent_slice_arrays_are_summed(self) -> None:
        slices = [np.zeros((16, 16), np.float32) for _ in range(5)]
        assert estimate_memory([_result(slices)], 0).result_bytes == sum(s.nbytes for s in slices)

    def test_the_same_result_or_volume_in_many_sessions_counts_once(self) -> None:
        image = _Image(1000)
        shared = _result([np.zeros((8, 8), np.float32)], image)
        once = estimate_memory([shared], 0)
        assert estimate_memory([shared, shared, shared], 0) == once
        # Different results over the SAME volume image: the volume is charged once.
        sibling = _result([np.zeros((8, 8), np.float32)], image)
        both = estimate_memory([shared, sibling], 0)
        assert both.volume_bytes == once.volume_bytes == 4000
        assert both.result_bytes == 2 * 8 * 8 * 4

    def test_independent_builds_from_one_series_are_charged_separately(self) -> None:
        a = _result([np.zeros((8, 8), np.float32)], _Image(1000))
        b = _result([np.zeros((8, 8), np.float32)], _Image(1000))
        est = estimate_memory([a, b], 0)
        assert est.volume_bytes == 8000 and est.result_bytes == 2 * 256

    def test_a_cache_loaded_result_sharing_the_volume_and_stack_adds_nothing(self) -> None:
        stack = np.zeros((4, 8, 8), np.float32)
        image = _Image(500)
        built = _result(list(stack), image)
        cache_hit = _result(list(stack), image)  # same buffers, same volume object
        assert estimate_memory([built, cache_hit], 0) == estimate_memory([built], 0)

    def test_non_array_slices_and_missing_volume_are_ignored(self) -> None:
        est = estimate_memory([SimpleNamespace(slices=["x", None], source_volume=None), object()], 0)
        assert est.total_bytes == 0

    def test_ledger_is_incremental_and_never_double_counts(self) -> None:
        ledger = BufferLedger()
        stack = np.zeros((3, 8, 8), np.float32)
        result = _result(list(stack), _Image(10))
        ledger.add_result(result)
        before = (ledger.volume_bytes, ledger.result_bytes)
        ledger.add_result(result)
        assert (ledger.volume_bytes, ledger.result_bytes) == before


class TestThumbnailsAndPending:
    def test_each_view_is_charged_a_bounded_thumbnail_copy(self) -> None:
        est = estimate_memory([], view_count=5)
        assert est.thumbnail_bytes == 5 * THUMBNAIL_BYTES_PER_VIEW == 5 * 256 * 256 * 4

    def test_duplicate_views_add_only_thumbnails_not_volume_or_result(self) -> None:
        stack = np.zeros((4, 64, 64), np.float32)
        result = _result(list(stack), _Image(64 * 64 * 4))
        base = estimate_memory([result], view_count=1)
        with_duplicates = estimate_memory([result], view_count=4)  # three shared-result duplicates
        assert with_duplicates.volume_bytes == base.volume_bytes
        assert with_duplicates.result_bytes == base.result_bytes
        assert with_duplicates.total_bytes - base.total_bytes == 3 * THUMBNAIL_BYTES_PER_VIEW

    def test_pending_bytes_are_added_and_never_negative(self) -> None:
        assert estimate_memory([], 0, pending_bytes=10 * MIB).pending_bytes == 10 * MIB
        assert estimate_memory([], 0, pending_bytes=-5).pending_bytes == 0
        assert estimate_memory([], view_count=-2).thumbnail_bytes == 0

    def test_total_is_the_sum_of_its_parts(self) -> None:
        est = estimate_memory([_result([np.zeros((4, 4), np.float32)], _Image(100))], 2, 50)
        assert est.total_bytes == 400 + 64 + 2 * THUMBNAIL_BYTES_PER_VIEW + 50


class _Dataset:
    """Dataset stand-in whose PixelData must never be read."""

    def __init__(self, rows: int, cols: int) -> None:
        self.Rows, self.Columns = rows, cols

    @property
    def PixelData(self):
        raise AssertionError("PixelData must not be read for an estimate")

    @property
    def pixel_array(self):
        raise AssertionError("pixel_array must not be decoded for an estimate")


class TestPendingVolumeEstimate:
    def test_is_rows_times_columns_times_slices_times_float32(self) -> None:
        datasets = [_Dataset(512, 512) for _ in range(100)]
        assert estimate_pending_volume_bytes(datasets) == 512 * 512 * 100 * 4

    @pytest.mark.parametrize("datasets", [[], None, [object()], [SimpleNamespace(Rows="x", Columns=3)]])
    def test_malformed_or_empty_input_is_zero(self, datasets) -> None:
        assert estimate_pending_volume_bytes(datasets) == 0


def test_format_mib_is_concise() -> None:
    assert format_mib(0) == "0 MiB"
    assert format_mib(400 * MIB) == "400 MiB"
    assert format_mib(1536 * MIB) == "1,536 MiB"
    assert format_mib(-5) == "0 MiB"
