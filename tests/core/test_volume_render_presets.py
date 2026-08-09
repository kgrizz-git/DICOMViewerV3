"""
Tests for volume render transfer-function presets.

Focuses on branch coverage for preset_steepness and is_steep_preset functions.
"""

from __future__ import annotations

from core.volume_render_presets import (
    BUILTIN_PRESETS,
    PRESET_CT_BONE,
    PRESET_CT_FAT,
    PRESET_CT_SOFT_TISSUE,
    PRESET_GROUPS,
    STEEP_PRESET_THRESHOLD,
    TransferFunctionPreset,
    is_steep_preset,
    preset_steepness,
)


def test_transfer_function_preset_dataclass_creation() -> None:
    """Test that TransferFunctionPreset dataclass can be instantiated."""
    preset = TransferFunctionPreset(
        name="Test Preset",
        scalar_opacity=[(0.0, 0.0), (100.0, 0.5)],
        color=[(0.0, 0.0, 0.0, 0.0), (100.0, 1.0, 1.0, 1.0)],
    )
    assert preset.name == "Test Preset"
    assert preset.scalar_opacity == [(0.0, 0.0), (100.0, 0.5)]
    assert preset.color == [(0.0, 0.0, 0.0, 0.0), (100.0, 1.0, 1.0, 1.0)]
    assert preset.gradient_opacity is None


def test_transfer_function_preset_with_gradient_opacity() -> None:
    """Test that TransferFunctionPreset can include gradient_opacity."""
    preset = TransferFunctionPreset(
        name="Test Preset with Gradient",
        scalar_opacity=[(0.0, 0.0), (100.0, 0.5)],
        color=[(0.0, 0.0, 0.0, 0.0), (100.0, 1.0, 1.0, 1.0)],
        gradient_opacity=[(0.0, 0.1), (50.0, 0.5)],
    )
    assert preset.gradient_opacity == [(0.0, 0.1), (50.0, 0.5)]


def test_preset_steepness_with_single_point_returns_zero() -> None:
    """Test branch: len(pts) < 2 returns 0.0."""
    preset = TransferFunctionPreset(
        name="Single Point",
        scalar_opacity=[(0.0, 0.5)],
        color=[(0.0, 0.0, 0.0, 0.0)],
    )
    assert preset_steepness(preset) == 0.0


def test_preset_steepness_with_empty_points_returns_zero() -> None:
    """Test branch: empty list (len < 2) returns 0.0."""
    preset = TransferFunctionPreset(
        name="Empty",
        scalar_opacity=[],
        color=[],
    )
    assert preset_steepness(preset) == 0.0


def test_preset_steepness_window_uses_max_with_negative_difference() -> None:
    """Test branch: max(1.0, pts[-1][0] - pts[0][0]) when difference < 1.0."""
    preset = TransferFunctionPreset(
        name="Small Window",
        scalar_opacity=[(0.0, 0.0), (0.5, 1.0)],
        color=[(0.0, 0.0, 0.0, 0.0), (0.5, 1.0, 1.0, 1.0)],
    )
    # Window should be max(1.0, 0.5) = 1.0
    steepness = preset_steepness(preset)
    assert steepness > 0.0


def test_preset_steepness_window_uses_actual_difference_when_larger() -> None:
    """Test branch: max(1.0, pts[-1][0] - pts[0][0]) when difference > 1.0."""
    preset = TransferFunctionPreset(
        name="Large Window",
        scalar_opacity=[(0.0, 0.0), (100.0, 1.0)],
        color=[(0.0, 0.0, 0.0, 0.0), (100.0, 1.0, 1.0, 1.0)],
    )
    # Window should be max(1.0, 100.0) = 100.0
    steepness = preset_steepness(preset)
    assert steepness > 0.0


def test_preset_steepness_skips_zero_scalar_difference() -> None:
    """Test branch: ds <= 0.0 continues loop without updating max_slope."""
    preset = TransferFunctionPreset(
        name="Duplicate Points",
        scalar_opacity=[(0.0, 0.0), (0.0, 0.5), (100.0, 1.0)],
        color=[(0.0, 0.0, 0.0, 0.0), (0.0, 0.5, 0.5, 0.5), (100.0, 1.0, 1.0, 1.0)],
    )
    # The duplicate point at scalar 0.0 should be skipped
    steepness = preset_steepness(preset)
    assert steepness > 0.0


def test_preset_steepness_with_negative_scalar_difference() -> None:
    """Test branch: ds calculation with negative difference (abs makes it positive)."""
    preset = TransferFunctionPreset(
        name="Decreasing Scalar",
        scalar_opacity=[(100.0, 0.0), (0.0, 1.0)],
        color=[(100.0, 0.0, 0.0, 0.0), (0.0, 1.0, 1.0, 1.0)],
    )
    # Should handle negative scalar difference via abs
    steepness = preset_steepness(preset)
    assert steepness > 0.0


def test_preset_steepness_max_slope_updates_correctly() -> None:
    """Test branch: max(max_slope, ...) updates when new slope is larger."""
    preset = TransferFunctionPreset(
        name="Multiple Slopes",
        scalar_opacity=[(0.0, 0.0), (50.0, 0.1), (100.0, 1.0)],
        color=[(0.0, 0.0, 0.0, 0.0), (50.0, 0.3, 0.3, 0.3), (100.0, 1.0, 1.0, 1.0)],
    )
    steepness = preset_steepness(preset)
    # The steepest slope should be from the second segment
    assert steepness > 0.0


def test_preset_steepness_with_zero_opacity_change() -> None:
    """Test branch: abs(o1 - o0) = 0 when opacity doesn't change."""
    preset = TransferFunctionPreset(
        name="Flat Opacity",
        scalar_opacity=[(0.0, 0.5), (100.0, 0.5)],
        color=[(0.0, 0.0, 0.0, 0.0), (100.0, 1.0, 1.0, 1.0)],
    )
    # Zero opacity change should result in zero slope for that segment
    steepness = preset_steepness(preset)
    assert steepness == 0.0


def test_preset_steepness_with_many_points() -> None:
    """Test that preset_steepness handles multiple control points correctly."""
    preset = TransferFunctionPreset(
        name="Many Points",
        scalar_opacity=[(0.0, 0.0), (100.0, 0.2), (200.0, 0.4), (300.0, 0.6), (400.0, 0.8)],
        color=[(0.0, 0.0, 0.0, 0.0), (100.0, 0.2, 0.2, 0.2), (200.0, 0.4, 0.4, 0.4),
               (300.0, 0.6, 0.6, 0.6), (400.0, 0.8, 0.8, 0.8)],
    )
    steepness = preset_steepness(preset)
    assert steepness > 0.0


def test_is_steep_preset_returns_true_when_above_threshold() -> None:
    """Test branch: preset_steepness >= STEEP_PRESET_THRESHOLD returns True."""
    # CT Fat is known to be steep (~9.1)
    assert is_steep_preset(PRESET_CT_FAT) is True


def test_is_steep_preset_returns_false_when_below_threshold() -> None:
    """Test branch: preset_steepness < STEEP_PRESET_THRESHOLD returns False."""
    # CT Soft Tissue is known to be gentle (~5.0)
    assert is_steep_preset(PRESET_CT_SOFT_TISSUE) is False


def test_is_steep_preset_exactly_at_threshold() -> None:
    """Test branch boundary: preset_steepness == STEEP_PRESET_THRESHOLD."""
    # Create a preset with exactly the threshold steepness
    # For a simple 2-point preset with window=1.0, we need opacity change = 6.0
    preset = TransferFunctionPreset(
        name="Exactly Threshold",
        scalar_opacity=[(0.0, 0.0), (1.0, 6.0)],
        color=[(0.0, 0.0, 0.0, 0.0), (1.0, 1.0, 1.0, 1.0)],
    )
    # steepness = abs(6.0 - 0.0) * 1.0 / 1.0 = 6.0
    assert is_steep_preset(preset) is True


def test_is_steep_preset_just_below_threshold() -> None:
    """Test branch boundary: preset_steepness just below STEEP_PRESET_THRESHOLD."""
    # Create a preset with steepness just below threshold
    preset = TransferFunctionPreset(
        name="Just Below Threshold",
        scalar_opacity=[(0.0, 0.0), (1.0, 5.9)],
        color=[(0.0, 0.0, 0.0, 0.0), (1.0, 1.0, 1.0, 1.0)],
    )
    # steepness = abs(5.9 - 0.0) * 1.0 / 1.0 = 5.9
    assert is_steep_preset(preset) is False


def test_is_steep_preset_with_single_point_returns_false() -> None:
    """Test is_steep_preset with degenerate preset (single point)."""
    preset = TransferFunctionPreset(
        name="Single Point",
        scalar_opacity=[(0.0, 0.5)],
        color=[(0.0, 0.0, 0.0, 0.0)],
    )
    # preset_steepness returns 0.0, which is < threshold
    assert is_steep_preset(preset) is False


def test_builtin_presets_list_is_populated() -> None:
    """Test that BUILTIN_PRESETS contains all presets from groups."""
    assert len(BUILTIN_PRESETS) > 0
    # Count total presets in groups
    total_in_groups = sum(len(presets) for _, presets in PRESET_GROUPS)
    assert len(BUILTIN_PRESETS) == total_in_groups


def test_preset_groups_structure() -> None:
    """Test that PRESET_GROUPS has expected structure."""
    assert len(PRESET_GROUPS) > 0
    for group_name, presets in PRESET_GROUPS:
        assert isinstance(group_name, str)
        assert len(group_name) > 0
        assert isinstance(presets, list)
        assert all(isinstance(p, TransferFunctionPreset) for p in presets)


def test_ct_bone_preset_structure() -> None:
    """Test that CT Bone preset has expected structure."""
    assert PRESET_CT_BONE.name == "CT Bone"
    assert len(PRESET_CT_BONE.scalar_opacity) > 1
    assert len(PRESET_CT_BONE.color) > 1
    assert PRESET_CT_BONE.gradient_opacity is not None
    assert len(PRESET_CT_BONE.gradient_opacity) > 0


def test_ct_bone_steepness_meets_expectation() -> None:
    """Test that CT Bone preset has expected steepness (~7.0)."""
    steepness = preset_steepness(PRESET_CT_BONE)
    # CT Bone is known to be steep (~7.0)
    assert steepness > 6.0
    assert steepness < 8.0


def test_preset_steepness_symmetric_negative_opacity() -> None:
    """Test branch: abs(o1 - o0) with negative opacity change."""
    preset = TransferFunctionPreset(
        name="Decreasing Opacity",
        scalar_opacity=[(0.0, 1.0), (100.0, 0.0)],
        color=[(0.0, 0.0, 0.0, 0.0), (100.0, 1.0, 1.0, 1.0)],
    )
    # abs handles negative opacity change
    steepness = preset_steepness(preset)
    assert steepness > 0.0


def test_preset_steepness_with_same_scalar_negative_opacity() -> None:
    """Test branch: both ds <= 0.0 and negative opacity change."""
    preset = TransferFunctionPreset(
        name="Same Scalar Negative Opacity",
        scalar_opacity=[(0.0, 1.0), (0.0, 0.0), (100.0, 0.5)],
        color=[(0.0, 0.0, 0.0, 0.0), (0.0, 0.5, 0.5, 0.5), (100.0, 1.0, 1.0, 1.0)],
    )
    # First segment should be skipped (ds=0), second should be processed
    steepness = preset_steepness(preset)
    assert steepness > 0.0


def test_steep_preset_threshold_constant() -> None:
    """Test that STEEP_PRESET_THRESHOLD is defined and matches documentation."""
    assert isinstance(STEEP_PRESET_THRESHOLD, float)
    assert STEEP_PRESET_THRESHOLD == 6.0


def test_all_builtin_presets_have_valid_steepness() -> None:
    """Test that all builtin presets can have steepness calculated."""
    for preset in BUILTIN_PRESETS:
        steepness = preset_steepness(preset)
        assert isinstance(steepness, float)
        assert steepness >= 0.0


def test_all_builtin_presets_is_steep_preset_bool() -> None:
    """Test that is_steep_preset returns bool for all builtin presets."""
    for preset in BUILTIN_PRESETS:
        result = is_steep_preset(preset)
        assert isinstance(result, bool)


def test_preset_steepness_very_small_window() -> None:
    """Test branch: window calculation with very small scalar range."""
    preset = TransferFunctionPreset(
        name="Tiny Window",
        scalar_opacity=[(0.0, 0.0), (0.001, 1.0)],
        color=[(0.0, 0.0, 0.0, 0.0), (0.001, 1.0, 1.0, 1.0)],
    )
    # Window should be max(1.0, 0.001) = 1.0
    steepness = preset_steepness(preset)
    assert steepness > 0.0


def test_preset_steepness_large_window() -> None:
    """Test branch: window calculation with large scalar range."""
    preset = TransferFunctionPreset(
        name="Huge Window",
        scalar_opacity=[(-10000.0, 0.0), (10000.0, 1.0)],
        color=[(-10000.0, 0.0, 0.0, 0.0), (10000.0, 1.0, 1.0, 1.0)],
    )
    # Window should be max(1.0, 20000.0) = 20000.0
    steepness = preset_steepness(preset)
    assert steepness > 0.0


def test_preset_steepness_multiple_max_candidates() -> None:
    """Test branch: max() when multiple segments have same slope."""
    preset = TransferFunctionPreset(
        name="Equal Slopes",
        scalar_opacity=[(0.0, 0.0), (100.0, 0.5), (200.0, 1.0)],
        color=[(0.0, 0.0, 0.0, 0.0), (100.0, 0.5, 0.5, 0.5), (200.0, 1.0, 1.0, 1.0)],
    )
    # Both segments have same slope, max should still work
    steepness = preset_steepness(preset)
    assert steepness > 0.0


def test_preset_steepness_with_negative_scalar_range() -> None:
    """Test branch: window calculation with negative scalar range."""
    preset = TransferFunctionPreset(
        name="Negative Range",
        scalar_opacity=[(-500.0, 0.0), (-100.0, 1.0)],
        color=[(-500.0, 0.0, 0.0, 0.0), (-100.0, 1.0, 1.0, 1.0)],
    )
    # Window should be max(1.0, -100 - (-500)) = max(1.0, 400) = 400
    steepness = preset_steepness(preset)
    assert steepness > 0.0


def test_preset_steepness_with_mixed_sign_scalar_range() -> None:
    """Test branch: window calculation spanning negative to positive."""
    preset = TransferFunctionPreset(
        name="Mixed Sign",
        scalar_opacity=[(-1000.0, 0.0), (1000.0, 1.0)],
        color=[(-1000.0, 0.0, 0.0, 0.0), (1000.0, 1.0, 1.0, 1.0)],
    )
    # Window should be max(1.0, 1000 - (-1000)) = max(1.0, 2000) = 2000
    steepness = preset_steepness(preset)
    assert steepness > 0.0


def test_preset_steepness_with_very_large_opacity_change() -> None:
    """Test branch: abs(o1 - o0) with very large opacity change."""
    preset = TransferFunctionPreset(
        name="Large Opacity Change",
        scalar_opacity=[(0.0, 0.0), (100.0, 100.0)],
        color=[(0.0, 0.0, 0.0, 0.0), (100.0, 1.0, 1.0, 1.0)],
    )
    # Large opacity change should result in high steepness
    steepness = preset_steepness(preset)
    assert steepness > 0.0


def test_preset_steepness_with_fractional_opacity() -> None:
    """Test branch: abs(o1 - o0) with fractional opacity values."""
    preset = TransferFunctionPreset(
        name="Fractional Opacity",
        scalar_opacity=[(0.0, 0.1), (100.0, 0.9)],
        color=[(0.0, 0.0, 0.0, 0.0), (100.0, 1.0, 1.0, 1.0)],
    )
    # Fractional opacity values should work correctly
    steepness = preset_steepness(preset)
    assert steepness > 0.0


def test_preset_steepness_with_very_small_scalar_difference() -> None:
    """Test branch: ds calculation with very small but non-zero scalar difference."""
    preset = TransferFunctionPreset(
        name="Tiny Scalar Diff",
        scalar_opacity=[(0.0, 0.0), (0.0001, 1.0)],
        color=[(0.0, 0.0, 0.0, 0.0), (0.0001, 1.0, 1.0, 1.0)],
    )
    # Very small scalar difference should result in very high steepness
    steepness = preset_steepness(preset)
    assert steepness > 0.0


def test_transfer_function_preset_equality() -> None:
    """Test that TransferFunctionPreset instances with same values are equal."""
    preset1 = TransferFunctionPreset(
        name="Test Preset",
        scalar_opacity=[(0.0, 0.0), (100.0, 0.5)],
        color=[(0.0, 0.0, 0.0, 0.0), (100.0, 1.0, 1.0, 1.0)],
    )
    preset2 = TransferFunctionPreset(
        name="Test Preset",
        scalar_opacity=[(0.0, 0.0), (100.0, 0.5)],
        color=[(0.0, 0.0, 0.0, 0.0), (100.0, 1.0, 1.0, 1.0)],
    )
    assert preset1 == preset2


def test_transfer_function_preset_inequality() -> None:
    """Test that TransferFunctionPreset instances with different values are not equal."""
    preset1 = TransferFunctionPreset(
        name="Test Preset 1",
        scalar_opacity=[(0.0, 0.0), (100.0, 0.5)],
        color=[(0.0, 0.0, 0.0, 0.0), (100.0, 1.0, 1.0, 1.0)],
    )
    preset2 = TransferFunctionPreset(
        name="Test Preset 2",
        scalar_opacity=[(0.0, 0.0), (100.0, 0.5)],
        color=[(0.0, 0.0, 0.0, 0.0), (100.0, 1.0, 1.0, 1.0)],
    )
    assert preset1 != preset2


def test_preset_groups_contains_all_expected_modalities() -> None:
    """Test that PRESET_GROUPS contains expected modality groups."""
    group_names = [name for name, _ in PRESET_GROUPS]
    assert "CT" in group_names
    assert "MR" in group_names
    assert "PT / NM" in group_names
    assert "Generic" in group_names


def test_preset_groups_ct_has_expected_presets() -> None:
    """Test that CT group contains expected presets."""
    ct_group = next((presets for name, presets in PRESET_GROUPS if name == "CT"), None)
    assert ct_group is not None
    preset_names = [p.name for p in ct_group]
    assert "CT Bone" in preset_names
    assert "CT Soft Tissue" in preset_names
    assert "CT Lung" in preset_names


def test_preset_groups_mr_has_expected_presets() -> None:
    """Test that MR group contains expected presets."""
    mr_group = next((presets for name, presets in PRESET_GROUPS if name == "MR"), None)
    assert mr_group is not None
    preset_names = [p.name for p in mr_group]
    assert "MR Default" in preset_names
    assert "MR T1 Brain" in preset_names
    assert "MR T2 Brain" in preset_names


def test_builtin_presets_no_duplicates() -> None:
    """Test that BUILTIN_PRESETS contains no duplicate presets."""
    preset_ids = [id(p) for p in BUILTIN_PRESETS]
    assert len(preset_ids) == len(set(preset_ids)), "BUILTIN_PRESETS contains duplicates"


def test_builtin_presets_all_have_names() -> None:
    """Test that all builtin presets have non-empty names."""
    for preset in BUILTIN_PRESETS:
        assert preset.name
        assert len(preset.name) > 0


def test_builtin_presets_all_have_valid_scalar_opacity() -> None:
    """Test that all builtin presets have valid scalar_opacity arrays."""
    for preset in BUILTIN_PRESETS:
        assert len(preset.scalar_opacity) >= 2
        # Each point should be a tuple of (scalar, opacity)
        for point in preset.scalar_opacity:
            assert isinstance(point, tuple)
            assert len(point) == 2
            assert isinstance(point[0], (int, float))
            assert isinstance(point[1], (int, float))


def test_builtin_presets_all_have_valid_color() -> None:
    """Test that all builtin presets have valid color arrays."""
    for preset in BUILTIN_PRESETS:
        assert len(preset.color) >= 2
        # Each point should be a tuple of (scalar, r, g, b)
        for point in preset.color:
            assert isinstance(point, tuple)
            assert len(point) == 4
            assert isinstance(point[0], (int, float))
            assert all(isinstance(c, (int, float)) for c in point[1:])


def test_is_steep_preset_with_all_builtin_presets() -> None:
    """Test is_steep_preset classification for all builtin presets."""
    steep_count = 0
    gentle_count = 0
    for preset in BUILTIN_PRESETS:
        is_steep = is_steep_preset(preset)
        if is_steep:
            steep_count += 1
        else:
            gentle_count += 1
    # Should have both steep and gentle presets
    assert steep_count > 0
    assert gentle_count > 0


def test_preset_steepness_idempotent() -> None:
    """Test that preset_steepness returns the same value for repeated calls."""
    preset = PRESET_CT_BONE
    steepness1 = preset_steepness(preset)
    steepness2 = preset_steepness(preset)
    assert steepness1 == steepness2


def test_preset_steepness_with_single_point_large_opacity() -> None:
    """Test branch: single point with large opacity value still returns 0.0."""
    preset = TransferFunctionPreset(
        name="Single Point Large Opacity",
        scalar_opacity=[(0.0, 100.0)],
        color=[(0.0, 0.0, 0.0, 0.0)],
    )
    assert preset_steepness(preset) == 0.0


def test_preset_steepness_with_three_points_middle_skipped() -> None:
    """Test branch: middle point with same scalar as previous is skipped."""
    preset = TransferFunctionPreset(
        name="Skip Middle",
        scalar_opacity=[(0.0, 0.0), (0.0, 0.5), (100.0, 1.0)],
        color=[(0.0, 0.0, 0.0, 0.0), (0.0, 0.5, 0.5, 0.5), (100.0, 1.0, 1.0, 1.0)],
    )
    steepness = preset_steepness(preset)
    assert steepness > 0.0
