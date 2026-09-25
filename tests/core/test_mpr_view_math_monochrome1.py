"""MONOCHROME1 display polarity in core.mpr_view_math.array_to_pil.

MPR panes bypass ``render_grayscale_image``, so the polarity has to be applied here for a pane to
agree with the single-slice viewer.
"""

from __future__ import annotations

import numpy as np
import pytest

from core.mpr_view_math import array_to_pil

_ARRAY = np.array([[0.0, 64.0, 128.0, 255.0]], dtype=np.float32)


def test_monochrome1_is_the_exact_inverse_of_monochrome2():
    mono2 = array_to_pil(_ARRAY, 127.5, 255.0, photometric_interpretation="MONOCHROME2")
    mono1 = array_to_pil(_ARRAY, 127.5, 255.0, photometric_interpretation="MONOCHROME1")
    assert mono1 is not None and mono2 is not None
    assert np.array_equal(np.array(mono1), 255 - np.array(mono2))


@pytest.mark.parametrize("photometric_interpretation", [None, "", "MONOCHROME2", "RGB"])
def test_non_monochrome1_matches_the_positional_call(photometric_interpretation):
    """The kwarg is optional; omitting it must be byte-identical to the pre-change behaviour."""
    positional = array_to_pil(_ARRAY, 127.5, 255.0)
    keyword = array_to_pil(
        _ARRAY, 127.5, 255.0, photometric_interpretation=photometric_interpretation
    )
    assert positional is not None and keyword is not None
    assert np.array_equal(np.array(positional), np.array(keyword))


def test_lowercase_photometric_interpretation_still_inverts():
    lower = array_to_pil(_ARRAY, 127.5, 255.0, photometric_interpretation="monochrome1")
    upper = array_to_pil(_ARRAY, 127.5, 255.0, photometric_interpretation="MONOCHROME1")
    assert lower is not None and upper is not None
    assert np.array_equal(np.array(lower), np.array(upper))


def test_polarity_applies_after_window_level_not_before():
    """Order matters: inverting before the window would clip the opposite tail.

    With a narrow window the mapping saturates; inverting the *mapped* result gives 255 where the
    mapped value was 0. Inverting the source first would produce a different clip pattern.
    """
    arr = np.array([[-1000.0, 0.0, 1000.0]], dtype=np.float32)
    mono1 = array_to_pil(arr, 0.0, 100.0, photometric_interpretation="MONOCHROME1")
    mono2 = array_to_pil(arr, 0.0, 100.0, photometric_interpretation="MONOCHROME2")
    assert mono1 is not None and mono2 is not None
    assert np.array_equal(np.array(mono2), np.array([[0, 127, 255]], dtype=np.uint8))
    assert np.array_equal(np.array(mono1), np.array([[255, 128, 0]], dtype=np.uint8))


def test_caller_array_is_not_modified():
    """Invariant 2: the same float array flows on to the analysis/sync path."""
    arr = _ARRAY.copy()
    original = arr.copy()
    array_to_pil(arr, 127.5, 255.0, photometric_interpretation="MONOCHROME1")
    np.testing.assert_array_equal(arr, original)


def test_failure_path_still_returns_none():
    assert array_to_pil(None, 127.5, 255.0, photometric_interpretation="MONOCHROME1") is None  # type: ignore[arg-type]
