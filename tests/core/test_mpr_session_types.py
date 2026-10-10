"""Navigator key helpers and read-only metadata for MPR views."""

from __future__ import annotations

import dataclasses

import pytest

from core.mpr_session_types import (
    MprViewMetadata,
    detached_nav_key,
    detached_view_id_from_nav_key,
)


def test_detached_key_is_the_negative_exact_view_id_and_round_trips() -> None:
    assert detached_nav_key(1) == -1  # view 1 is a real view, not a "the detached one" sentinel
    assert detached_nav_key(12) == -12
    assert detached_view_id_from_nav_key(-12) == 12


def test_pane_keys_are_not_detached_ids() -> None:
    assert detached_view_id_from_nav_key(0) is None
    assert detached_view_id_from_nav_key(3) is None


def test_metadata_is_immutable_and_carries_no_arrays() -> None:
    meta = MprViewMetadata(
        view_id=1, session_id=2, creation_seq=3, pane_index=None, orientation="Axial",
        source_study_uid="st", source_series_uid="se", n_slices=9, slice_index=4,
    )
    assert meta.photometric_interpretation is None
    with pytest.raises(dataclasses.FrozenInstanceError):
        meta.slice_index = 5  # type: ignore[misc]
    assert {f.name for f in dataclasses.fields(meta)}.isdisjoint({"result", "slices", "pixels"})
