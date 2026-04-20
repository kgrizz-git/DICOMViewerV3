"""Unit tests for merge_simple_and_detailed_extra_corner_tags."""

from gui.overlay_text_builder import merge_simple_and_detailed_extra_corner_tags


def test_merge_preserves_simple_order_then_appends_new_extras() -> None:
    simple = {"upper_left": ["A", "B"], "upper_right": [], "lower_left": [], "lower_right": []}
    extras = {"upper_left": ["C", "D"], "upper_right": [], "lower_left": [], "lower_right": []}
    out = merge_simple_and_detailed_extra_corner_tags(simple, extras)
    assert out["upper_left"] == ["A", "B", "C", "D"]


def test_merge_dedupes_extras_already_in_simple() -> None:
    simple = {"upper_left": ["StudyDate", "PatientName"], "upper_right": [], "lower_left": [], "lower_right": []}
    extras = {
        "upper_left": ["PatientName", "Modality", "StudyDate"],
        "upper_right": [],
        "lower_left": [],
        "lower_right": [],
    }
    out = merge_simple_and_detailed_extra_corner_tags(simple, extras)
    assert out["upper_left"] == ["StudyDate", "PatientName", "Modality"]


def test_merge_empty_extras_returns_simple_copy_shape() -> None:
    simple = {
        "upper_left": ["X"],
        "upper_right": ["Y"],
        "lower_left": [],
        "lower_right": ["Z"],
    }
    extras: dict = {}
    out = merge_simple_and_detailed_extra_corner_tags(simple, extras)
    assert out == {
        "upper_left": ["X"],
        "upper_right": ["Y"],
        "lower_left": [],
        "lower_right": ["Z"],
    }


def test_merge_all_corners_independently() -> None:
    simple = {
        "upper_left": ["a"],
        "upper_right": ["b"],
        "lower_left": ["c"],
        "lower_right": ["d"],
    }
    extras = {
        "upper_left": ["a2"],
        "upper_right": ["b"],
        "lower_left": [],
        "lower_right": ["d", "d2"],
    }
    out = merge_simple_and_detailed_extra_corner_tags(simple, extras)
    assert out["upper_left"] == ["a", "a2"]
    assert out["upper_right"] == ["b"]
    assert out["lower_left"] == ["c"]
    assert out["lower_right"] == ["d", "d2"]
