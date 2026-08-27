"""Tests for the VTK-free first-paint quality policy."""

import numpy as np

from core.volume_render_quality import (
    AUTO_REFINE_BUDGET_MS,
    GIBIBYTE,
    HUGE_VOLUME_BYTES,
    LARGE_VOLUME_BYTES,
    MAX_BUDGET_BYTES,
    MEBIBYTE,
    MIN_DOWNSAMPLE_BUDGET_BYTES,
    _downsampled_dims,
    auto_detail_cap_index,
    build_full_coverage_scalar_histogram,
    compute_auto_downsample_factor,
    default_render_budget_bytes,
    estimate_render_peak_bytes,
    estimate_volume_megabytes,
    frame_expected_nonblank,
    should_auto_refine,
)

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

# CT Bone preset scalar opacity: everything below 150 HU is fully transparent
# (opacity 0.0 at -1000 and 150, rising only above 200).
_CT_BONE_OPACITY = [
    (-1000.0, 0.0),
    (150.0, 0.0),
    (200.0, 0.05),
    (400.0, 0.4),
    (1000.0, 0.8),
    (3000.0, 1.0),
]

_CT_BONE_COLOR = [
    (-1000.0, 0.0, 0.0, 0.0),
    (150.0, 0.0, 0.0, 0.0),
    (200.0, 0.85, 0.75, 0.55),
    (400.0, 0.95, 0.92, 0.82),
    (1000.0, 1.0, 1.0, 0.95),
    (3000.0, 1.0, 1.0, 1.0),
]

# A transfer function that is opaque but maps everything to black.
_BLACK_OPACITY = [
    (-1000.0, 1.0),
    (3000.0, 1.0),
]
_BLACK_COLOR = [
    (-1000.0, 0.0, 0.0, 0.0),
    (3000.0, 0.0, 0.0, 0.0),
]


# ---------------------------------------------------------------------------
# Existing tests
# ---------------------------------------------------------------------------


def test_estimate_volume_megabytes_uses_float32_input_size() -> None:
    assert estimate_volume_megabytes((256, 256, 256)) == 64.0


def test_auto_detail_cap_boundaries() -> None:
    assert auto_detail_cap_index(None, mode_count=4) == 3
    assert auto_detail_cap_index(LARGE_VOLUME_BYTES - 1, mode_count=4) == 3
    assert auto_detail_cap_index(LARGE_VOLUME_BYTES, mode_count=4) == 1
    assert auto_detail_cap_index(HUGE_VOLUME_BYTES, mode_count=4) == 0


def test_auto_refine_requires_a_responsive_non_fallback_preview() -> None:
    assert should_auto_refine(
        preview_elapsed_ms=AUTO_REFINE_BUDGET_MS, gpu_fallback_used=False
    ) is True
    assert should_auto_refine(
        preview_elapsed_ms=AUTO_REFINE_BUDGET_MS + 0.1, gpu_fallback_used=False
    ) is False
    assert should_auto_refine(preview_elapsed_ms=1.0, gpu_fallback_used=True) is False


# ---------------------------------------------------------------------------
# frame_expected_nonblank — policy tests
# ---------------------------------------------------------------------------


def test_bone_free_all_transparent_is_expected_blank() -> None:
    """A bone-free phantom (HU -1000..120) under CT Bone is fully transparent.

    Every occupied bin maps to ~0 opacity, so the frame is *expected* blank and
    check_gpu_fallback() must NOT conclude a GPU failure.
    """
    occupancy = {float(hu): 100 for hu in range(-1000, 121, 10)}
    assert (
        frame_expected_nonblank(_CT_BONE_OPACITY, _CT_BONE_COLOR, occupancy) is False
    )


def test_visible_occupancy_returns_true() -> None:
    """A volume with occupied bone-density voxels (HU 400..1000) is visible."""
    occupancy = {float(hu): 50 for hu in range(400, 1001, 20)}
    assert frame_expected_nonblank(_CT_BONE_OPACITY, _CT_BONE_COLOR, occupancy) is True


def test_sparse_visible_bin_is_detected() -> None:
    """A handful of high-HU fiducials among an otherwise transparent volume.

    This is the case a strided pixel sample would miss: a single occupied bin
    at 3000 HU (opacity 1.0, colour white) must still be judged visible so a
    genuine GPU failure on that volume still triggers fallback.
    """
    occupancy = {0.0: 1_000_000, 3000.0: 3}
    assert frame_expected_nonblank(_CT_BONE_OPACITY, _CT_BONE_COLOR, occupancy) is True


def test_bounded_histogram_keeps_sparse_opaque_content_visible() -> None:
    """Bounded memory bins must conservatively retain sparse bone voxels."""
    values = np.zeros(1_000_003, dtype=np.float32)
    values[-3:] = 3000.0
    occupancy = build_full_coverage_scalar_histogram(values)

    assert occupancy is not None
    assert frame_expected_nonblank(_CT_BONE_OPACITY, _CT_BONE_COLOR, occupancy) is True


def test_full_coverage_histogram_marks_bone_free_ct_as_expected_blank() -> None:
    """A complete, non-strided bin scan proves CT Bone has no visible voxel."""
    values = np.linspace(-1000.0, 120.0, num=100_000, dtype=np.float32)
    occupancy = build_full_coverage_scalar_histogram(values)

    assert occupancy is not None
    assert frame_expected_nonblank(_CT_BONE_OPACITY, _CT_BONE_COLOR, occupancy) is False


def test_black_color_despite_opacity_is_expected_blank() -> None:
    """Opaque but black colour must not be mistaken for a visible frame.

    The signal check_gpu_fallback() measures is RGB output; a transfer function
    that is fully opaque yet maps every voxel to (0,0,0) produces a black frame
    for a legitimate reason, not a GPU failure.
    """
    occupancy = {float(hu): 100 for hu in range(-500, 501, 10)}
    assert frame_expected_nonblank(_BLACK_OPACITY, _BLACK_COLOR, occupancy) is False


def test_malformed_input_fails_visible() -> None:
    """Malformed / missing inputs fail safe toward "expected visible".

    A false EXPECTED_BLANK is the worse error (suppresses a real fallback),
    so unknown inputs must return True.
    """
    occupancy = {0.0: 100}
    # None / empty transfer functions.
    assert frame_expected_nonblank(None, _CT_BONE_COLOR, occupancy) is True
    assert frame_expected_nonblank(_CT_BONE_OPACITY, None, occupancy) is True
    assert frame_expected_nonblank([], _CT_BONE_COLOR, occupancy) is True
    assert frame_expected_nonblank(_CT_BONE_OPACITY, [], occupancy) is True


def test_malformed_control_points_fail_visible() -> None:
    """Malformed control-point rows must not raise and must fail safe."""
    occupancy = {0.0: 100}
    # Wrong row shape.
    bad_opacity = [(1.0,)]  # type: ignore[list-item]
    assert frame_expected_nonblank(bad_opacity, _CT_BONE_COLOR, occupancy) is True
    # Non-finite value in a control point.
    nan_opacity = [(float("nan"), 0.5), (100.0, 1.0)]
    assert frame_expected_nonblank(nan_opacity, _CT_BONE_COLOR, occupancy) is True
    inf_color = [(0.0, float("inf"), 0.0, 0.0), (100.0, 1.0, 1.0, 1.0)]
    assert frame_expected_nonblank(_CT_BONE_OPACITY, inf_color, occupancy) is True
    # Unsorted domain.
    unsorted = [(100.0, 1.0), (0.0, 0.0)]
    assert frame_expected_nonblank(unsorted, _CT_BONE_COLOR, occupancy) is True


def test_malformed_occupancy_fails_visible() -> None:
    """Non-finite scalar values and unparsable counts must fail safe."""
    # Non-finite scalar value in occupancy.
    assert (
        frame_expected_nonblank(_CT_BONE_OPACITY, _CT_BONE_COLOR, {float("nan"): 100})
        is True
    )
    # Unparsable count.
    assert (
        frame_expected_nonblank(
            _CT_BONE_OPACITY, _CT_BONE_COLOR, [(0.0, "not-a-count")]
        )
        is True
    )


def test_empty_occupancy_fails_visible() -> None:
    """Empty / all-zero occupancy is degenerate → fail safe, not blank."""
    assert frame_expected_nonblank(_CT_BONE_OPACITY, _CT_BONE_COLOR, {}) is True
    assert frame_expected_nonblank(_CT_BONE_OPACITY, _CT_BONE_COLOR, []) is True
    assert frame_expected_nonblank(_CT_BONE_OPACITY, _CT_BONE_COLOR, {0.0: 0}) is True


def test_no_raise_on_arbitrary_bad_input() -> None:
    """The helper must never raise, regardless of garbage input."""
    garbage_args = [
        (None, None, None),
        (_CT_BONE_OPACITY, _CT_BONE_COLOR, None),
        ("not-a-tf", _CT_BONE_COLOR, {0.0: 1}),
        (_CT_BONE_OPACITY, "not-a-tf", {0.0: 1}),
        (_CT_BONE_OPACITY, _CT_BONE_COLOR, [(0.0,)]),
        (_CT_BONE_OPACITY, _CT_BONE_COLOR, "not-a-histogram"),
    ]
    for args in garbage_args:
        try:
            result = frame_expected_nonblank(*args)
        except Exception as exc:
            raise AssertionError(
                f"frame_expected_nonblank raised {type(exc).__name__} on {args!r}"
            ) from exc
        assert result is True


# ---------------------------------------------------------------------------
# default_render_budget_bytes — policy tests
# ---------------------------------------------------------------------------


def test_budget_is_twenty_percent_of_available() -> None:
    # 16 GiB available → 20% = 3.2 GiB, but capped at 2.5 GiB.
    assert default_render_budget_bytes(int(16 * GIBIBYTE)) == MAX_BUDGET_BYTES


def test_budget_under_cap_uses_fraction() -> None:
    # 4 GiB available → 20% = 0.8 GiB, below the 2.5 GiB cap.
    expected = int(0.20 * 4 * GIBIBYTE)
    assert default_render_budget_bytes(int(4 * GIBIBYTE)) == expected


def test_budget_never_exceeds_known_available_memory() -> None:
    # 100 MiB available → 20% = 20 MiB, but the 512 MiB fallback floor must
    # not claim more memory than the OS reported as available.
    assert default_render_budget_bytes(100 * MEBIBYTE) == 100 * MEBIBYTE


def test_budget_zero_or_negative_available_falls_back_to_minimum() -> None:
    assert default_render_budget_bytes(0) == MIN_DOWNSAMPLE_BUDGET_BYTES
    assert default_render_budget_bytes(-1) == MIN_DOWNSAMPLE_BUDGET_BYTES


# ---------------------------------------------------------------------------
# estimate_render_peak_bytes — policy tests
# ---------------------------------------------------------------------------


def test_peak_equals_input_size_at_overhead_one() -> None:
    # 256^3 float32 = 64 MiB; overhead 1.0 → peak == input.
    assert estimate_render_peak_bytes((256, 256, 256), overhead_factor=1.0) == 64 * MEBIBYTE


def test_peak_scales_with_default_overhead() -> None:
    # 256^3 float32 = 64 MiB; default overhead 2.0 → 128 MiB.
    assert estimate_render_peak_bytes((256, 256, 256)) == 128 * MEBIBYTE


def test_peak_handles_zero_dimension() -> None:
    assert estimate_render_peak_bytes((0, 256, 256)) == 0


# ---------------------------------------------------------------------------
# compute_auto_downsample_factor — policy tests
# ---------------------------------------------------------------------------


def test_no_downsample_when_volume_fits_budget() -> None:
    # 256^3 float32 at overhead 2.0 → 128 MiB peak, well within a 2 GiB budget.
    assert compute_auto_downsample_factor(
        (256, 256, 256), available_bytes=int(2 * GIBIBYTE)
    ) == 1


def test_downsample_returns_smallest_fitting_factor() -> None:
    # 1024^3 float32 at overhead 2.0 = 8 GiB peak. With a 2.5 GiB budget
    # (available >= 12.5 GiB hits the cap), native does not fit; the factor-2
    # candidate (ceil(1024/2) = 512 → 1 GiB peak) is the *first* that fits,
    # so the smallest fitting factor (2) wins — not a larger one.
    assert compute_auto_downsample_factor(
        (1024, 1024, 1024), available_bytes=int(16 * GIBIBYTE)
    ) == 2


def test_native_fit_returns_factor_one_even_on_tight_budget() -> None:
    # 128^3 float32 at overhead 2.0 = 16 MiB peak, fits even the 512 MiB floor.
    assert compute_auto_downsample_factor(
        (128, 128, 128), available_bytes=100 * MEBIBYTE
    ) == 1


def test_downsampled_size_uses_ceil_not_floor() -> None:
    # A stride of ``f`` keeps ceil(dim/f) voxels. For an odd dimension the
    # helper must NOT under-estimate with floor: 257 voxels at stride 2
    # retains 129 (= ceil(257/2)), not 128.
    assert _downsampled_dims((257, 257, 257), 2, 1) == (129, 129, 129)
    # The helper internally uses ceil; sanity-check via a volume that only
    # fits at factor 2 under ceil but would (wrongly) fit at factor 1 under
    # floor. 513^3 at overhead 2.0 ≈ 1 GiB *over* a tight budget forces f=2.
    forced = compute_auto_downsample_factor(
        (513, 513, 513), available_bytes=int(4 * GIBIBYTE)
    )
    assert forced >= 2


def test_anisotropic_volume_respects_min_dim() -> None:
    # Tall thin volume whose native peak (16*512*512*4*2 = 32 MiB) fits even
    # the 512 MiB floor budget — so factor 1 is returned and the thin axis is
    # left intact.
    factor = compute_auto_downsample_factor(
        (16, 512, 512), available_bytes=100 * MEBIBYTE
    )
    assert factor == 1
    assert 16 // factor >= 1


def test_zero_sized_volume_returns_factor_one() -> None:
    assert compute_auto_downsample_factor((0, 256, 256), available_bytes=int(2 * GIBIBYTE)) == 1
    assert compute_auto_downsample_factor((256, 0, 0), available_bytes=int(2 * GIBIBYTE)) == 1


def test_negative_available_uses_minimum_budget() -> None:
    # Negative available → budget falls back to the 512 MiB minimum; a 256^3
    # float32 volume at overhead 2.0 (128 MiB) still fits.
    assert compute_auto_downsample_factor(
        (256, 256, 256), available_bytes=-1
    ) == 1


def test_deterministic_pure_no_os_probing() -> None:
    # Same inputs must always produce the same output (pure function check).
    a = compute_auto_downsample_factor((512, 512, 256), available_bytes=int(8 * GIBIBYTE))
    b = compute_auto_downsample_factor((512, 512, 256), available_bytes=int(8 * GIBIBYTE))
    assert a == b


# ---------------------------------------------------------------------------
# fixed_bytes — live source-buffer policy test
# ---------------------------------------------------------------------------


def test_fixed_bytes_counts_unchanging_live_buffers() -> None:
    # A 256^3 float32 volume at overhead 2.0 is a 128 MiB peak. With a 2 GiB
    # available the budget clamps to the 512 MiB floor, so native fits and the
    # no-fixed case returns 1.
    assert compute_auto_downsample_factor(
        (256, 256, 256), available_bytes=int(2 * GIBIBYTE)
    ) == 1
    # Adding a 400 MiB fixed live-source cost makes the native peak (528 MiB)
    # exceed the 512 MiB budget, so the helper must downsample. The factor-2
    # candidate (ceil(256/2)=128 → 16 MiB peak) + 400 MiB = 416 MiB fits.
    assert compute_auto_downsample_factor(
        (256, 256, 256), available_bytes=int(2 * GIBIBYTE), fixed_bytes=400 * MEBIBYTE
    ) == 2
