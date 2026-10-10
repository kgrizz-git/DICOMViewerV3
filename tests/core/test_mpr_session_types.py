"""Read-only metadata for MPR views."""

from __future__ import annotations

import dataclasses

import pytest

from core.mpr_session_types import MprViewMetadata


def _meta(**overrides) -> MprViewMetadata:
    base = {
        "view_id": 1, "session_id": 2, "creation_seq": 3, "pane_index": None, "orientation": "Axial",
        "source_study_uid": "st", "source_series_uid": "se", "n_slices": 9, "slice_index": 4,
    }
    base.update(overrides)
    return MprViewMetadata(**base)  # type: ignore[arg-type]


def test_metadata_is_immutable_and_carries_no_arrays() -> None:
    meta = _meta()
    with pytest.raises(dataclasses.FrozenInstanceError):
        meta.slice_index = 5  # type: ignore[misc]
    assert {f.name for f in dataclasses.fields(meta)}.isdisjoint({"result", "slices", "pixels"})


def test_defaults_describe_an_unlinked_single_view_session() -> None:
    meta = _meta()
    assert (meta.view_number, meta.view_count, meta.link_group_id) == (1, 1, None)
    assert meta.photometric_interpretation is None and meta.content_stamp == ()


def test_content_stamp_must_be_hashable_for_dirty_detection() -> None:
    hash(_meta(content_stamp=(1, 2, "aip", None, ("lut", 1.0))))
