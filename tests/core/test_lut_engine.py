"""
Tests for the display LUT engine (window/level stays separate; LUT is uint8-only).

Covers the Phase 1 contracts in ``LUTS_AND_COLORMAPS_PLAN.md``: linear matches
``apply_window_level``, ``lut=None`` is today's bytes, inverse rounding is
exact, sigmoid is endpoint-renormalized, and colormap output is ``(H, W, 3)``.
"""

from __future__ import annotations

import inspect
from dataclasses import FrozenInstanceError

import matplotlib
import numpy as np
import pytest

from core.dicom_image_render import normalize_to_uint8
from core.dicom_window_level import apply_window_level
from core.fusion_processor import cached_matplotlib_colormap
from core.lut_catalog import (
    DISPLAY_COLORMAP_NAMES,
    clear_colormap_lut_cache,
    colormap_lut,
    exponential_lut,
    gamma_lut,
    inverse_lut,
    linear_lut,
    logarithmic_lut,
    replace_gamma,
    sigmoid_lut,
)
from core.lut_engine import (
    LookUpTable,
    apply_lut,
    apply_lut_to_uint8,
    evaluate_lut,
    linear_transfer,
    renormalized_sigmoid,
)


def _half_transfer(x: float) -> np.ndarray:
    """Custom transfer used to prove sampling stays on normalized x."""
    return np.array(x * 0.5)


def _ramp_bytes(lut: LookUpTable) -> np.ndarray:
    """Return the 256-entry uint8 table by mapping codes 0..255."""
    ramp = np.arange(256, dtype=np.uint8).reshape(1, 256)
    return apply_lut_to_uint8(ramp, lut)[0]


def test_apply_window_level_has_no_lut_parameter() -> None:
    """A lut argument on window/level would run before polarity."""
    assert "lut" not in inspect.signature(apply_window_level).parameters


def test_linear_lut_matches_apply_window_level() -> None:
    """Linear LUT output is byte-identical to window/level, including rescale."""
    pixels = np.array([[0.0, 10.0, 50.0], [100.0, 200.0, 400.0]])
    expected = apply_window_level(pixels.copy(), 40.0, 80.0, 2.0, -10.0)
    got = apply_lut(pixels.copy(), 40.0, 80.0, 2.0, -10.0, lut=linear_lut())
    none_lut = apply_lut(pixels.copy(), 40.0, 80.0, 2.0, -10.0, lut=None)
    np.testing.assert_array_equal(got, expected)
    np.testing.assert_array_equal(none_lut, expected)


def test_none_lut_on_uint8_returns_the_same_object() -> None:
    """``apply_lut_to_uint8(arr, None)`` must not copy."""
    display = np.arange(6, dtype=np.uint8).reshape(2, 3)
    assert apply_lut_to_uint8(display, None) is display


def test_no_window_matches_normalize_to_uint8() -> None:
    """Missing window/level uses the same min/max normalize as the display path."""
    pixels = np.array([[0.0, 5.0], [10.0, 2.0]])
    np.testing.assert_array_equal(apply_lut(pixels, None, None), normalize_to_uint8(pixels))
    rescaled = pixels * 2.0 + 3.0
    got = apply_lut(pixels, None, None, 2.0, 3.0)
    np.testing.assert_array_equal(got, normalize_to_uint8(rescaled))


def test_window_arguments_must_both_be_set_or_both_be_absent() -> None:
    """A half-specified window is not a silent normalize."""
    pixels = np.zeros((2, 2))
    with pytest.raises(ValueError, match="window_center and window_width"):
        apply_lut(pixels, 40.0, None)


def test_gamma_one_matches_linear_bytes() -> None:
    """Gamma 1 is the identity. This equality does not prove the rounding mode."""
    np.testing.assert_array_equal(_ramp_bytes(gamma_lut(1.0)), _ramp_bytes(linear_lut()))


def test_inverse_lut_is_exact_complement() -> None:
    """Truncating the scale misses 50 codes; round-to-nearest misses none."""
    table = _ramp_bytes(inverse_lut())
    expected = (255 - np.arange(256)).astype(np.uint8)
    np.testing.assert_array_equal(table, expected)


@pytest.mark.parametrize("k", [0.1, 1.0, 5.0, 2000.0])
def test_sigmoid_endpoints_are_black_and_white(k: float) -> None:
    """Renormalization pins both ends. The raw logistic does not."""
    table = _ramp_bytes(sigmoid_lut(k))
    assert table[0] == 0
    assert table[255] == 255


@pytest.mark.parametrize("k", [0.1, 1.0, 5.0])
def test_renormalized_sigmoid_midpoint_stays_near_one_half(k: float) -> None:
    """``y(0.5)`` stays within 1e-12 of 0.5. A one-ulp bound is too tight."""
    midpoint = float(renormalized_sigmoid(np.array([0.5]), k)[0])
    assert abs(midpoint - 0.5) < 1e-12


@pytest.mark.parametrize("dtype", [np.float32, np.float64])
def test_large_sigmoid_k_stays_finite(dtype: type[np.floating]) -> None:
    """``k = 2000`` is finite at the ends and the center in float32 and float64."""
    samples = np.array([0.0, 0.5, 1.0], dtype=dtype)
    curve = renormalized_sigmoid(samples, 2000.0)
    assert curve.dtype == dtype
    assert np.all(np.isfinite(curve))
    np.testing.assert_allclose(curve, [0.0, 0.5, 1.0], atol=1e-5)


def test_steep_sigmoid_approximates_a_step() -> None:
    """A large k stays dark below the center and bright above it."""
    table = _ramp_bytes(sigmoid_lut(2000.0))
    assert table[0] == 0
    assert table[120] == 0
    assert table[136] == 255
    assert table[255] == 255


@pytest.mark.parametrize("builder", [logarithmic_lut, exponential_lut])
def test_log_and_exponential_reach_both_ends(builder) -> None:
    """Divide-by-max exponential leaves x=0 above black. The affine form does not."""
    table = _ramp_bytes(builder())
    assert table[0] == 0
    assert table[255] == 255


def test_colormap_output_is_rgb() -> None:
    """Color LUTs expand a 2-D uint8 image to ``(H, W, 3)``."""
    image = np.array([[0, 255], [128, 10]], dtype=np.uint8)
    colored = apply_lut_to_uint8(image, colormap_lut("viridis"))
    assert colored.shape == (2, 2, 3)
    assert colored.dtype == np.uint8
    viridis = colormap_lut("viridis").colormap
    assert viridis is not None
    np.testing.assert_array_equal(colored[0, 0], viridis[0])
    np.testing.assert_array_equal(colored[0, 1], viridis[255])


def test_all_zero_and_single_value_images_match_window_level() -> None:
    """Flat images stay on the existing window/level path when the LUT is linear."""
    zeros = np.zeros((4, 4), dtype=np.float64)
    single = np.full((3, 3), 7.0)
    np.testing.assert_array_equal(
        apply_lut(zeros.copy(), 128.0, 256.0, lut=linear_lut()),
        apply_window_level(zeros.copy(), 128.0, 256.0),
    )
    np.testing.assert_array_equal(
        apply_lut(single.copy(), 40.0, 350.0, lut=None),
        apply_window_level(single.copy(), 40.0, 350.0),
    )
    assert apply_lut(zeros.copy(), None, None).shape == (4, 4)


def test_uint8_image_is_required_when_a_lut_is_set() -> None:
    """The display path casts to uint8 before the LUT. Float input is rejected."""
    with pytest.raises(TypeError, match="uint8"):
        apply_lut_to_uint8(np.zeros((2, 2), dtype=np.float32), linear_lut())


def test_parameter_ranges_and_marker_pairing() -> None:
    """gamma and exp_k are closed ranges; sigmoid_k is only required to be > 0."""
    gamma_lut(0.1)
    gamma_lut(5.0)
    exponential_lut(0.1)
    exponential_lut(5.0)
    sigmoid_lut(1e-3)
    with pytest.raises(ValueError, match="gamma"):
        gamma_lut(0.09)
    with pytest.raises(ValueError, match="exp_k"):
        exponential_lut(5.01)
    with pytest.raises(ValueError, match="sigmoid_k"):
        sigmoid_lut(0.0)
    with pytest.raises(ValueError, match="gamma_transfer"):
        LookUpTable(name="Linear", transfer_fn=linear_transfer, gamma=1.0)


def test_replace_builds_a_new_lut_and_leaves_the_original() -> None:
    """Sliders use replace. Assigning on a frozen LUT raises."""
    original = gamma_lut(1.0)
    updated = replace_gamma(original, 2.2)
    assert original.gamma == 1.0
    assert updated.gamma == 2.2
    assert evaluate_lut(updated, np.array([0.25]))[0] == pytest.approx(0.25**2.2)
    with pytest.raises(FrozenInstanceError):
        original.gamma = 2.2  # pyright: ignore[reportAttributeAccessIssue]


def test_equal_luts_hash_equal_and_work_as_dict_keys() -> None:
    """``__eq__`` and ``__hash__`` stay consistent: equal LUTs are interchangeable keys."""
    from dataclasses import replace

    lut = gamma_lut(2.2)
    same = replace(lut)
    assert same is not lut
    assert same == lut
    assert hash(same) == hash(lut)

    lut_map = {lut: "pane-1"}
    assert lut_map[same] == "pane-1"

    hot = colormap_lut("hot")
    hot_same = replace(hot)
    assert hot_same == hot
    assert hash(hot_same) == hash(hot)


def test_control_points_are_sorted_and_y_is_clamped() -> None:
    """Normalization is part of construction, via object.__setattr__ on the frozen LUT."""
    lut = LookUpTable(
        name="edited",
        source="custom",
        control_points=((1.0, 1.4), (0.0, -0.2), (0.5, 0.25)),
    )
    assert lut.control_points == ((0.0, 0.0), (0.5, 0.25), (1.0, 1.0))


def test_duplicate_or_out_of_range_x_is_rejected() -> None:
    """x is strictly increasing inside [0, 1]. y is the only clamped axis."""
    with pytest.raises(ValueError, match="duplicate"):
        LookUpTable(
            name="bad",
            control_points=((0.0, 0.0), (0.5, 0.2), (0.5, 0.8), (1.0, 1.0)),
        )
    with pytest.raises(ValueError, match=r"\[0, 1\]"):
        LookUpTable(name="bad", control_points=((0.0, 0.0), (1.2, 0.5)))


def test_custom_transfer_is_sampled_on_normalized_x() -> None:
    """A non-marker callable receives normalized x, and the engine scales to bytes."""
    lut = LookUpTable(name="half", source="custom", transfer_fn=_half_transfer)
    np.testing.assert_allclose(evaluate_lut(lut, np.array([0.0, 1.0])), [0.0, 0.5])
    assert _ramp_bytes(lut)[255] == 128


def test_display_colormaps_are_lowercase_and_share_the_fusion_cache(monkeypatch) -> None:
    """Title case and ``Greys`` are different maps. Sampling goes through the fusion lookup."""
    calls: list[str] = []
    real_lookup = cached_matplotlib_colormap

    def record(name: str):
        calls.append(name)
        return real_lookup(name)

    monkeypatch.setattr("core.lut_catalog.cached_matplotlib_colormap", record)
    clear_colormap_lut_cache()
    hot = colormap_lut("hot")
    assert hot.colormap is not None
    assert hot.colormap.shape == (256, 3)
    assert hot.colormap.dtype == np.uint8
    assert calls == ["hot"]
    via_bytes = matplotlib.colormaps.get_cmap("hot")(np.linspace(0, 1, 256), bytes=True)[:, :3]
    np.testing.assert_array_equal(hot.colormap, via_bytes)
    gray = colormap_lut("gray").colormap
    greys = matplotlib.colormaps.get_cmap("Greys")(np.linspace(0, 1, 256))[:, :3]
    greys_bytes = (greys * 255.0).astype(np.uint8)
    assert gray is not None
    assert not np.array_equal(gray, greys_bytes)
    with pytest.raises(ValueError, match="lowercase"):
        colormap_lut("Hot")
    with pytest.raises(ValueError, match="lowercase"):
        colormap_lut("Greys")
    for name in DISPLAY_COLORMAP_NAMES:
        table = colormap_lut(name).colormap
        assert table is not None
        assert table.shape == (256, 3)
