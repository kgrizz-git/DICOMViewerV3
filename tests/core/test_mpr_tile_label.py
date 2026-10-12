"""Navigator tile text: registry facts only, no PHI, link-state ready."""

from __future__ import annotations

from core.mpr_session_types import MprViewMetadata
from core.mpr_tile_label import tile_tag, tile_tooltip


def _meta(**overrides) -> MprViewMetadata:
    base = {
        "view_id": 5, "session_id": 2, "creation_seq": 7, "pane_index": None, "orientation": "Axial",
        "source_study_uid": "1.2.PATIENT.STUDY", "source_series_uid": "1.2.SERIES",
        "n_slices": 12, "slice_index": 3,
    }
    base.update(overrides)
    return MprViewMetadata(**base)  # type: ignore[arg-type]


def test_tag_for_a_single_view_session_is_just_the_session() -> None:
    assert tile_tag(_meta()) == "S2"


def test_tag_distinguishes_shared_result_views_and_link_state() -> None:
    assert tile_tag(_meta(view_count=2, view_number=1)) == "S2.1"
    assert tile_tag(_meta(view_count=2, view_number=2)) == "S2.2"
    assert tile_tag(_meta(view_count=2, view_number=2, link_group_id=4)) == "S2.2L"
    assert tile_tag(_meta(link_group_id=4)) == "S2L"


def test_same_source_sessions_get_different_tags() -> None:
    assert tile_tag(_meta(session_id=2)) != tile_tag(_meta(session_id=3))


def test_tooltip_for_a_detached_view() -> None:
    text = tile_tooltip(_meta(view_count=3, view_number=2), None)
    assert "MPR Axial" in text and "Session 2 · view 2 of 3" in text
    assert "Not in a window (slice 4 of 12)" in text  # a dormant linked view shows where it is
    assert "Duplicate into Window… / Duplicate Linked into Window… / Clear MPR" in text
    assert "Linked scrolling" not in text and "Unlink" not in text


def test_tooltip_for_an_attached_linked_view() -> None:
    text = tile_tooltip(_meta(pane_index=2, link_group_id=1), "3")
    assert "Window 3" in text and "Linked scrolling" in text
    assert "Unlink View / Clear MPR" in text


def test_text_never_contains_dicom_derived_identifiers() -> None:
    meta = _meta(pane_index=0, link_group_id=1, view_count=2)
    combined = tile_tag(meta) + tile_tooltip(meta, "1")
    assert "PATIENT" not in combined and "STUDY" not in combined and "SERIES" not in combined


def test_orientation_label_is_sanitized_and_bounded() -> None:
    text = tile_tooltip(_meta(orientation="Ob\nlique\x00" + "x" * 80), None)
    first = text.splitlines()[0]
    assert "\x00" not in first and len(first) <= len("MPR ") + 24
