"""Tests for core.photometric_polarity — the shared MONOCHROME1 display-polarity helper."""

from __future__ import annotations

import numpy as np
import pytest
from pydicom.dataset import Dataset

from core.photometric_polarity import (
    apply_monochrome1_polarity,
    dataset_photometric_interpretation,
    is_monochrome1,
    normalize_photometric_interpretation,
)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("MONOCHROME1", "MONOCHROME1"),
        ("monochrome1", "MONOCHROME1"),
        ("  MONOCHROME1  ", "MONOCHROME1"),
        ("MONOCHROME2", "MONOCHROME2"),
        (["MONOCHROME1", "MONOCHROME2"], "MONOCHROME1"),
        (("MONOCHROME1",), "MONOCHROME1"),
        ([], ""),
        (None, ""),
        ("", ""),
        ("RGB", "RGB"),
    ],
)
def test_normalize_photometric_interpretation(value, expected):
    assert normalize_photometric_interpretation(value) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("MONOCHROME1", True),
        ("monochrome1", True),
        (["MONOCHROME1"], True),
        ("MONOCHROME2", False),
        ("MONOCHROME1 ANYTHING", False),
        ("PALETTE COLOR", False),
        (None, False),
        ("", False),
    ],
)
def test_is_monochrome1(value, expected):
    assert is_monochrome1(value) is expected


def test_dataset_photometric_interpretation_reads_tag():
    ds = Dataset()
    ds.PhotometricInterpretation = "MONOCHROME1"
    assert dataset_photometric_interpretation(ds) == "MONOCHROME1"


def test_dataset_photometric_interpretation_missing_tag_is_empty():
    assert dataset_photometric_interpretation(Dataset()) == ""


def test_dataset_photometric_interpretation_none_dataset_is_empty():
    assert dataset_photometric_interpretation(None) == ""


def test_dataset_photometric_interpretation_reads_through_attribute_proxy():
    """Per-frame wrappers proxy metadata to a parent dataset; getattr must resolve through them."""

    class _Proxy:
        def __init__(self, parent):
            self._parent = parent

        def __getattr__(self, name):
            return getattr(self._parent, name)

    parent = Dataset()
    parent.PhotometricInterpretation = "MONOCHROME1"
    assert dataset_photometric_interpretation(_Proxy(parent)) == "MONOCHROME1"


def test_apply_polarity_inverts_monochrome1():
    arr = np.array([[0, 100, 255]], dtype=np.uint8)
    out = apply_monochrome1_polarity(arr, "MONOCHROME1")
    assert np.array_equal(out, np.array([[255, 155, 0]], dtype=np.uint8))
    assert out.dtype == np.uint8


def test_apply_polarity_is_identity_for_monochrome2():
    arr = np.array([[0, 100, 255]], dtype=np.uint8)
    out = apply_monochrome1_polarity(arr, "MONOCHROME2")
    assert out is arr


def test_apply_polarity_is_identity_for_missing_pi():
    arr = np.array([[0, 100, 255]], dtype=np.uint8)
    assert apply_monochrome1_polarity(arr, None) is arr
    assert apply_monochrome1_polarity(arr, "") is arr


def test_apply_polarity_does_not_mutate_caller_array():
    """Invariant 2: the same buffer may flow onward to stored-value analysis paths."""
    arr = np.array([[0, 100, 255]], dtype=np.uint8)
    original = arr.copy()
    apply_monochrome1_polarity(arr, "MONOCHROME1")
    assert np.array_equal(arr, original)


def test_apply_polarity_casts_non_uint8_input():
    arr = np.array([[0.0, 100.0, 255.0]], dtype=np.float32)
    out = apply_monochrome1_polarity(arr, "MONOCHROME1")
    assert out.dtype == np.uint8
    assert np.array_equal(out, np.array([[255, 155, 0]], dtype=np.uint8))


def test_apply_polarity_skips_three_channel_arrays():
    """A colour array cannot be MONOCHROME1; the shape guard prevents silent RGB inversion."""
    arr = np.zeros((2, 2, 3), dtype=np.uint8)
    assert apply_monochrome1_polarity(arr, "MONOCHROME1") is arr


def test_apply_polarity_is_its_own_inverse():
    arr = np.array([[0, 37, 200, 255]], dtype=np.uint8)
    once = apply_monochrome1_polarity(arr, "MONOCHROME1")
    twice = apply_monochrome1_polarity(once, "MONOCHROME1")
    assert np.array_equal(twice, arr)
