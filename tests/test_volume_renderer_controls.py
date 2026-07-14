"""Tests for VolumeRenderer control methods (window scaling, opacity response,
background, scalar-domain labels).

The transfer-function tests inspect the renderer's internal vtkPiecewiseFunction
node values directly, so no live render/window is required.  Renderer
construction needs VTK; tests that require it are skipped when VTK is absent.
"""

from __future__ import annotations

import math

import pytest

from core.volume_renderer import (
    BACKGROUND_COLORS,
    BLEND_MODES,
    BUILTIN_PRESETS,
    PRESET_CT_ANATOMY_COLORS,
    PRESET_CT_BONE,
    PRESET_CT_SMOOTH_ANATOMY,
    PRESET_CT_VIVID_ANGIO,
    PRESET_GENERIC_INTENSITY,
    PRESET_GROUPS,
    PRESET_NM_DEFAULT,
    PRESET_PT_DEFAULT,
    get_default_preset_for_modality,
    scalar_domain_label,
    vtk_available,
)

pytestmark = pytest.mark.skipif(not vtk_available, reason="VTK not installed")


def _scalar_points(renderer):
    """Return the renderer's scalar-opacity control points as (x, y) tuples."""
    fn = renderer._scalar_opacity
    pts = []
    for i in range(fn.GetSize()):
        node = [0.0, 0.0, 0.0, 0.0]
        fn.GetNodeValue(i, node)
        pts.append((node[0], node[1]))
    return pts


def _make_renderer():
    from core.volume_renderer import VolumeRenderer

    return VolumeRenderer()


def _add_visible_cube(renderer) -> None:
    """Add a simple visible prop so camera view tests have concrete bounds."""
    from core.volume_renderer import vtk_mod

    cube = vtk_mod.vtkCubeSource()
    cube.SetBounds(-10.0, 10.0, -20.0, 20.0, -5.0, 5.0)
    cube.Update()
    mapper = vtk_mod.vtkPolyDataMapper()
    mapper.SetInputConnection(cube.GetOutputPort())
    actor = vtk_mod.vtkActor()
    actor.SetMapper(mapper)
    renderer.get_renderer().AddActor(actor)


def _camera_direction(renderer):
    cam = renderer.get_renderer().GetActiveCamera()
    pos = cam.GetPosition()
    focal = cam.GetFocalPoint()
    direction = tuple(pos[i] - focal[i] for i in range(3))
    length = math.sqrt(sum(v * v for v in direction))
    return tuple(v / length for v in direction)


def test_set_preset_is_identity_at_natural_wl() -> None:
    r = _make_renderer()
    r.set_preset(PRESET_CT_BONE)
    pts = _scalar_points(r)
    expected = PRESET_CT_BONE.scalar_opacity
    assert len(pts) == len(expected)
    for (x, y), (ex, ey) in zip(pts, expected, strict=False):
        assert x == pytest.approx(ex)
        assert y == pytest.approx(ey)


def test_window_scaling_compresses_range() -> None:
    r = _make_renderer()
    r.set_preset(PRESET_CT_BONE)
    # Natural width is 4000 (-1000..3000), center 1000.  Halve the window.
    r.set_window_level(2000.0, 1000.0)
    xs = [x for x, _ in _scalar_points(r)]
    # First preset point -1000 -> 1000 + (-2000)*0.5 = 0; last 3000 -> 2000.
    assert xs[0] == pytest.approx(0.0)
    assert xs[-1] == pytest.approx(2000.0)


def test_window_level_recenters() -> None:
    r = _make_renderer()
    r.set_preset(PRESET_CT_BONE)
    r.set_window_level(4000.0, 0.0)  # same width, center shifted by -1000
    xs = [x for x, _ in _scalar_points(r)]
    assert xs[0] == pytest.approx(-2000.0)
    assert xs[-1] == pytest.approx(2000.0)


def test_window_clamped_positive() -> None:
    r = _make_renderer()
    r.set_preset(PRESET_CT_BONE)
    r.set_window_level(0.0, 1000.0)  # clamped to a tiny positive width
    xs = [x for x, _ in _scalar_points(r)]
    # All points collapse near the center without raising.
    assert all(abs(x - 1000.0) < 1.0 for x in xs)


def test_reset_window_level_restores_preset_range_without_other_resets() -> None:
    r = _make_renderer()
    r.set_preset(PRESET_CT_BONE)
    r.set_window_level(2000.0, 0.0)
    r.set_threshold(75.0)
    r.set_global_opacity(0.5)
    r.set_background(0.78, 0.78, 0.80)
    r.set_quality_mode("High")

    window, center = r.reset_window_level()

    assert window == pytest.approx(4000.0)
    assert center == pytest.approx(1000.0)
    assert r._threshold_shift == pytest.approx(75.0)
    assert r._global_opacity == pytest.approx(0.5)
    assert r.get_background() == pytest.approx((0.78, 0.78, 0.80))
    assert r._mapper.GetSampleDistance() == pytest.approx(0.5)
    xs = [x for x, _ in _scalar_points(r)]
    assert xs[0] == pytest.approx(-925.0)
    assert xs[-1] == pytest.approx(3075.0)


def test_opacity_response_reshapes_curve() -> None:
    r = _make_renderer()
    r.set_preset(PRESET_CT_BONE)
    r.set_opacity_response(2.0)
    pts = dict(_scalar_points(r))
    # Preset point (400, 0.4) -> opacity 0.4**2 = 0.16.
    assert pts[400.0] == pytest.approx(0.16)
    # Fully-opaque points stay at 1.0 (1**gamma == 1).
    assert pts[3000.0] == pytest.approx(1.0)


def test_global_opacity_multiplies_after_response() -> None:
    r = _make_renderer()
    r.set_preset(PRESET_CT_BONE)
    r.set_opacity_response(2.0)
    r.set_global_opacity(0.5)
    pts = dict(_scalar_points(r))
    # (400, 0.4) -> 0.4**2 * 0.5 = 0.08.
    assert pts[400.0] == pytest.approx(0.08)


def test_set_background_roundtrips() -> None:
    r = _make_renderer()
    for _name, (cr, cg, cb) in BACKGROUND_COLORS:
        r.set_background(cr, cg, cb)
        got = r.get_background()
        assert got == pytest.approx((cr, cg, cb))


def test_set_background_clamps() -> None:
    r = _make_renderer()
    r.set_background(2.0, -1.0, 0.5)
    assert r.get_background() == pytest.approx((1.0, 0.0, 0.5))


@pytest.mark.parametrize(
    "modality,needle",
    [
        ("CT", "raw"),
        ("MR", "arbitrary"),
        ("PT", "intensity"),
        ("NM", "counts"),
        ("US", "US"),
        ("", "unknown"),
    ],
)
def test_scalar_domain_label_is_honest(modality: str, needle: str) -> None:
    label = scalar_domain_label(modality)
    assert needle.lower() in label.lower()
    # Raw CT must never claim calibrated HU.
    if modality == "CT":
        assert "raw" in label.lower()


def test_scalar_domain_label_calibrated_ct() -> None:
    assert "HU" in scalar_domain_label("CT", rescale_applied=True)


@pytest.mark.parametrize(
    "view_name,expected_direction,expected_up",
    [
        ("Anterior", (0.0, -1.0, 0.0), (0.0, 0.0, 1.0)),
        ("Posterior", (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)),
        ("Left", (1.0, 0.0, 0.0), (0.0, 0.0, 1.0)),
        ("Right", (-1.0, 0.0, 0.0), (0.0, 0.0, 1.0)),
        ("Superior", (0.0, 0.0, 1.0), (0.0, 1.0, 0.0)),
        ("Inferior", (0.0, 0.0, -1.0), (0.0, 1.0, 0.0)),
    ],
)
def test_set_view_positions_camera_on_standard_lps_axis(
    view_name: str,
    expected_direction: tuple[float, float, float],
    expected_up: tuple[float, float, float],
) -> None:
    r = _make_renderer()
    _add_visible_cube(r)

    r.set_view(view_name)

    assert _camera_direction(r) == pytest.approx(expected_direction)
    cam = r.get_renderer().GetActiveCamera()
    assert cam.GetViewUp() == pytest.approx(expected_up)


def test_set_view_ignores_unknown_view_name() -> None:
    r = _make_renderer()
    _add_visible_cube(r)
    r.set_view("Anterior")
    before = _camera_direction(r)

    r.set_view("Diagonal")

    assert _camera_direction(r) == pytest.approx(before)


# --- Preset catalog tests (T11, T15, T16, T17, T18) ---

def test_builtin_presets_includes_all_groups() -> None:
    group_names = [name for name, _ in PRESET_GROUPS]
    assert "CT" in group_names
    assert "MR" in group_names
    assert "PT / NM" in group_names
    assert "Generic" in group_names


def test_builtin_presets_flat_list_matches_groups() -> None:
    from_groups = [p for _, presets in PRESET_GROUPS for p in presets]
    assert len(BUILTIN_PRESETS) == len(from_groups)
    for a, b in zip(BUILTIN_PRESETS, from_groups, strict=False):
        assert a is b


def test_new_presets_have_valid_opacity_ramps() -> None:
    for preset in (PRESET_CT_SMOOTH_ANATOMY, PRESET_PT_DEFAULT,
                   PRESET_NM_DEFAULT, PRESET_GENERIC_INTENSITY):
        assert len(preset.scalar_opacity) >= 4
        assert len(preset.color) >= 4
        assert len(preset.scalar_opacity) == len(preset.color)
        # Monotonically increasing scalar values.
        scalars = [s for s, _ in preset.scalar_opacity]
        assert scalars == sorted(scalars)
        # Opacity values in [0, 1].
        for _, o in preset.scalar_opacity:
            assert 0.0 <= o <= 1.0


def test_modality_default_presets() -> None:
    assert get_default_preset_for_modality("CT") is PRESET_CT_BONE
    assert get_default_preset_for_modality("PT") is PRESET_PT_DEFAULT
    assert get_default_preset_for_modality("NM") is PRESET_NM_DEFAULT
    assert get_default_preset_for_modality("US") is PRESET_GENERIC_INTENSITY
    assert get_default_preset_for_modality("") is PRESET_CT_BONE


def test_no_non_ct_preset_names_imply_hu() -> None:
    """T18: Non-HU presets must not contain 'HU' in their name."""
    for _group, presets in PRESET_GROUPS:
        for p in presets:
            if not p.name.startswith("CT"):
                assert "HU" not in p.name.upper(), f"{p.name} implies HU"


def test_quality_mode_sets_sample_distance() -> None:
    from core.volume_renderer import QUALITY_MODES
    r = _make_renderer()
    for name, expected_dist in QUALITY_MODES:
        r.set_quality_mode(name)
        actual = r._mapper.GetSampleDistance()
        assert actual == pytest.approx(expected_dist), f"{name}: {actual} != {expected_dist}"


def test_render_method_auto_is_default() -> None:
    r = _make_renderer()
    r.set_render_method("Auto")
    # Should not raise and mapper should be Smart.
    assert "Smart" in r._mapper.GetClassName()


def test_render_method_cpu() -> None:
    r = _make_renderer()
    r.set_render_method("CPU")
    # vtkSmartVolumeMapper: mode 1 = ray cast (CPU).
    if hasattr(r._mapper, "GetRequestedRenderMode"):
        # RayCast mode constant is 1 in vtkSmartVolumeMapper.
        assert r._mapper.GetRequestedRenderMode() == 1


def test_interactive_quality_uses_quality_base() -> None:
    r = _make_renderer()
    r.set_quality_mode("High")  # base = 0.5
    r.set_interactive_quality(True)
    assert r._mapper.GetSampleDistance() >= 1.0
    r.set_interactive_quality(False)
    assert r._mapper.GetSampleDistance() == pytest.approx(0.5)


def test_interpolation_toggle() -> None:
    r = _make_renderer()
    r.set_interpolation(False)
    assert r._volume_property.GetInterpolationType() == 0  # VTK_NEAREST
    r.set_interpolation(True)
    assert r._volume_property.GetInterpolationType() == 1  # VTK_LINEAR


def test_custom_opacity_points() -> None:
    r = _make_renderer()
    r.set_preset(PRESET_CT_BONE)
    custom = [(0.0, 0.0), (500.0, 0.5), (1000.0, 1.0)]
    r.set_custom_opacity_points(custom)
    pts = _scalar_points(r)
    assert len(pts) == 3
    assert pts[0] == pytest.approx((0.0, 0.0))
    assert pts[1] == pytest.approx((500.0, 0.5))
    assert pts[2] == pytest.approx((1000.0, 1.0))


def test_gradient_opacity_floor_is_nonzero() -> None:
    """Gradient-opacity minimum must be > 0 so smooth volumes don't go black."""
    for _group, presets in PRESET_GROUPS:
        for p in presets:
            if p.gradient_opacity:
                min_go = min(o for _, o in p.gradient_opacity)
                assert min_go > 0.0, (
                    f"{p.name} gradient_opacity minimum is 0 — will "
                    f"produce all-black renders on smooth data"
                )


def test_gradient_opacity_strength_blending() -> None:
    r = _make_renderer()
    r.set_preset(PRESET_CT_BONE)
    r.set_gradient_opacity_enabled(True)
    r.set_gradient_opacity_strength(0.5)
    fn = r._gradient_opacity
    # With strength=0.5, each point should be blended toward 1.0.
    # Preset minimum is 0.10; blended = 0.5*0.10 + 0.5*1.0 = 0.55 > 0.10.
    node = [0.0, 0.0, 0.0, 0.0]
    fn.GetNodeValue(0, node)
    assert node[1] == pytest.approx(0.5 * 0.10 + 0.5 * 1.0)


def test_gradient_opacity_strength_zero_is_flat() -> None:
    r = _make_renderer()
    r.set_preset(PRESET_CT_BONE)
    r.set_gradient_opacity_enabled(True)
    r.set_gradient_opacity_strength(0.0)
    fn = r._gradient_opacity
    # All points should be 1.0 (no effect).
    for i in range(fn.GetSize()):
        node = [0.0, 0.0, 0.0, 0.0]
        fn.GetNodeValue(i, node)
        assert node[1] == pytest.approx(1.0)


def test_display_smoothing_off_uses_original() -> None:
    import numpy as np

    from core.volume_renderer import VolumeData, VolumeRenderer
    r = VolumeRenderer()
    arr = np.ones((10, 10, 10), dtype=np.float32) * 100.0
    vd = VolumeData(array=arr, spacing=(1,1,1), origin=(0,0,0), direction=(1,0,0,0,1,0,0,0,1))
    r.attach_volume(vd)
    r.set_display_smoothing(0.0)
    # Mapper input should be the original image.
    assert r._mapper.GetInput() is r._vtk_image_original


def test_display_smoothing_nonzero_creates_different_image() -> None:
    import numpy as np

    from core.volume_renderer import VolumeData, VolumeRenderer
    r = VolumeRenderer()
    # Use a noisy array so smoothing actually changes values.
    rng = np.random.default_rng(42)
    arr = rng.standard_normal((10, 10, 10)).astype(np.float32) * 500
    vd = VolumeData(array=arr, spacing=(1,1,1), origin=(0,0,0), direction=(1,0,0,0,1,0,0,0,1))
    r.attach_volume(vd)
    r.set_display_smoothing(1.0)
    # The smoothed image is a different vtkImageData object.
    assert r._vtk_image is not r._vtk_image_original


def test_blend_mode_names_match_constants() -> None:
    assert len(BLEND_MODES) == 3
    assert BLEND_MODES[0][0] == "Composite"
    assert BLEND_MODES[1][0] == "Max Intensity (MIP)"
    assert BLEND_MODES[2][0] == "Min Intensity (MinIP)"


def test_set_blend_mode_does_not_raise() -> None:
    r = _make_renderer()
    for name, _suffix in BLEND_MODES:
        r.set_blend_mode(name)


def test_set_lighting_roundtrips() -> None:
    r = _make_renderer()
    r.set_lighting(0.5, 0.3, 0.8, 32.0)
    assert r.get_lighting() == pytest.approx((0.5, 0.3, 0.8, 32.0))


def test_set_lighting_clamps() -> None:
    r = _make_renderer()
    r.set_lighting(-1.0, 2.0, 0.5, 0.1)
    a, d, s, p = r.get_lighting()
    assert a == pytest.approx(0.0)
    assert d == pytest.approx(1.0)
    assert p >= 1.0


def test_ssao_available() -> None:
    r = _make_renderer()
    assert r.is_ssao_available() is True


def test_ssao_enable_disable_does_not_crash() -> None:
    r = _make_renderer()
    r.set_ssao_enabled(True)
    assert r._ssao_enabled is True
    r.set_ssao_enabled(False)
    assert r._ssao_enabled is False
    assert r._ssao_pass is None


def test_false_color_presets_have_distinct_hues() -> None:
    """CT Anatomy Colors preset should use more saturated color than CT Bone."""
    def saturation(r, g, b):
        mx, mn = max(r, g, b), min(r, g, b)
        return (mx - mn) / mx if mx > 0 else 0.0

    # Pick the peak-opacity point from each preset.
    bone_peak = max(PRESET_CT_BONE.color, key=lambda t: t[0])[1:]
    max(PRESET_CT_ANATOMY_COLORS.color, key=lambda t: t[0])[1:]
    # Bone peak should be near-white (low saturation); false-color should be
    # more saturated at some point in the curve.
    bone_sat = saturation(*bone_peak)
    max_color_sat = max(saturation(r, g, b) for _, r, g, b in PRESET_CT_ANATOMY_COLORS.color)
    assert max_color_sat > bone_sat + 0.3, "False-color preset is not meaningfully more saturated than CT Bone"


def test_vivid_angio_has_red_dominant_vessel_color() -> None:
    """The vivid angio preset should have a clearly red dominant color somewhere."""
    max_red_excess = max(r - max(g, b) for _, r, g, b in PRESET_CT_VIVID_ANGIO.color)
    assert max_red_excess > 0.5, "CT Vivid Angio should have red-dominant vessel color"


def test_gradient_opacity_disabled_by_default() -> None:
    r = _make_renderer()
    r.set_preset(PRESET_CT_BONE)
    fn = r._gradient_opacity
    # Should be flat 1.0 (two points: 0->1, 255->1).
    assert fn.GetSize() == 2
    node0 = [0.0, 0.0, 0.0, 0.0]
    fn.GetNodeValue(0, node0)
    assert node0[1] == pytest.approx(1.0)


def test_gradient_opacity_enabled_uses_preset() -> None:
    r = _make_renderer()
    r.set_preset(PRESET_CT_BONE)
    r.set_gradient_opacity_enabled(True)
    fn = r._gradient_opacity
    # CT Bone has gradient_opacity with more than 2 points.
    assert PRESET_CT_BONE.gradient_opacity is not None
    assert fn.GetSize() == len(PRESET_CT_BONE.gradient_opacity)


def test_gradient_opacity_toggle_roundtrip() -> None:
    r = _make_renderer()
    r.set_preset(PRESET_CT_BONE)
    r.set_gradient_opacity_enabled(True)
    assert r._gradient_opacity.GetSize() > 2
    r.set_gradient_opacity_enabled(False)
    assert r._gradient_opacity.GetSize() == 2


def test_cropping_add_and_clear() -> None:
    import vtkmodules.all as vtk
    r = _make_renderer()
    plane = vtk.vtkPlane()
    plane.SetOrigin(0, 0, 0)
    plane.SetNormal(1, 0, 0)
    r.set_cropping([plane])
    assert r._mapper.GetNumberOfClippingPlanes() == 1
    r.clear_cropping()
    assert r._mapper.GetNumberOfClippingPlanes() == 0


def test_smooth_anatomy_has_gentler_ramp_than_bone() -> None:
    """T15: The smooth anatomy preset should have lower peak opacity than bone."""
    bone_max = max(o for _, o in PRESET_CT_BONE.scalar_opacity)
    smooth_max = max(o for _, o in PRESET_CT_SMOOTH_ANATOMY.scalar_opacity)
    assert smooth_max < bone_max
