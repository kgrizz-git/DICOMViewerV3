"""Tests for gui.overlay_text_builder text-composition helpers."""

from __future__ import annotations

from types import SimpleNamespace

from gui import overlay_text_builder as otb


class _FakeParser:
    def __init__(self, values, dataset=None) -> None:
        self._values = values
        self.dataset = dataset

    def get_tag_by_keyword(self, keyword, default=None):
        return self._values.get(keyword, default)


# --------------------------------------------------------------------------- #
# merge / get_overlay_text / get_modality
# --------------------------------------------------------------------------- #

def test_merge_dedups_extras_after_simple() -> None:
    out = otb.merge_simple_and_detailed_extra_corner_tags(
        {"upper_left": ["A", "B"]},
        {"upper_left": ["B", "C"]},
    )
    assert out["upper_left"] == ["A", "B", "C"]
    assert out["lower_right"] == []


def test_get_overlay_text_modes() -> None:
    p = _FakeParser({"PatientName": "Doe", "Modality": "CT", "X": ["a", "b"]})
    assert otb.get_overlay_text(p, "hidden", [], [], []) == ""
    assert otb.get_overlay_text(p, "minimal", ["PatientName"], [], []) == "PatientName: Doe"
    assert otb.get_overlay_text(p, "detailed", [], ["Modality"], []) == "Modality: CT"
    # custom (any other mode) + list value joined
    assert otb.get_overlay_text(p, "other", [], [], ["X"]) == "X: a, b"


def test_get_modality_value_and_default() -> None:
    assert otb.get_modality(_FakeParser({"Modality": " CT "})) == "CT"
    assert otb.get_modality(_FakeParser({})) == "default"


# --------------------------------------------------------------------------- #
# get_corner_text basics
# --------------------------------------------------------------------------- #

def test_corner_text_plain_and_privacy() -> None:
    p = _FakeParser({"PatientName": "Doe", "StudyDate": "20260101", "Empty": ""})
    txt = otb.get_corner_text(p, ["PatientName", "StudyDate", "Empty"], privacy_mode=False)
    assert "PatientName: Doe" in txt and "StudyDate: 20260101" in txt

    masked = otb.get_corner_text(p, ["PatientName"], privacy_mode=True)
    assert masked == "PatientName: PRIVACY MODE"


def test_corner_text_list_value() -> None:
    p = _FakeParser({"ImageType": ["ORIGINAL", "PRIMARY"]})
    txt = otb.get_corner_text(p, ["ImageType"], privacy_mode=False)
    assert txt == "ImageType: ORIGINAL, PRIMARY"


def test_corner_text_instance_number_with_stack_position() -> None:
    p = _FakeParser({"InstanceNumber": "5"})
    txt = otb.get_corner_text(p, ["InstanceNumber"], privacy_mode=False,
                              total_slices=11, stack_position=3)
    assert "Slice 3/11" in txt
    assert "(Instance 5)" in txt  # differs from stack position


def test_corner_text_instance_number_impossible_denominator() -> None:
    p = _FakeParser({"InstanceNumber": "104"})
    txt = otb.get_corner_text(p, ["InstanceNumber"], privacy_mode=False, total_slices=11)
    assert txt == "Slice 104"  # denominator dropped


def test_corner_text_instance_number_with_projection() -> None:
    p = _FakeParser({"InstanceNumber": "2"})
    txt = otb.get_corner_text(
        p, ["InstanceNumber"], privacy_mode=False, total_slices=10,
        projection_enabled=True, projection_start_slice=0, projection_end_slice=4,
        projection_type="mip",
    )
    assert "Slice 2/10" in txt
    assert "(1-5 MIP)" in txt


def test_corner_text_slice_thickness_projection() -> None:
    p = _FakeParser({"SliceThickness": "2.5"})
    txt = otb.get_corner_text(
        p, ["SliceThickness"], privacy_mode=False,
        projection_enabled=True, projection_total_thickness=12.5,
    )
    assert "Slice Thickness: 2.5 (12.5)" in txt


def test_corner_text_timing_tags_from_context() -> None:
    p = _FakeParser({"TriggerTime": "100", "ContentTime": "120000"})
    ctx = {"trigger_time_ms": 100.0, "content_time": "120000"}
    trig = otb.get_corner_text(p, ["TriggerTime"], privacy_mode=False, multiframe_context=ctx)
    assert "TriggerTime: 100 ms" in trig
    content = otb.get_corner_text(p, ["ContentTime"], privacy_mode=False, multiframe_context=ctx)
    assert "ContentTime: 120000" in content


def test_corner_text_multiframe_label_variants() -> None:
    p = _FakeParser({"InstanceNumber": "1"})
    # temporal
    t = otb.get_corner_text(p, ["InstanceNumber"], privacy_mode=False,
                            multiframe_context={"frame_index": 2, "total_frames": 8, "frame_type": "temporal"})
    assert "Frame 2/8" in t
    # cardiac with timing + instance prefix
    c = otb.get_corner_text(p, ["InstanceNumber"], privacy_mode=False,
                            multiframe_context={"frame_index": 1, "total_frames": 4,
                                                "frame_type": "cardiac", "trigger_time_ms": 50,
                                                "instance_index": 2, "total_instances": 3})
    assert "Phase 1/4" in c and "50 ms" in c and "Instance 2/3" in c
    # diffusion with b value
    d = otb.get_corner_text(p, ["InstanceNumber"], privacy_mode=False,
                            multiframe_context={"frame_index": 1, "total_frames": 4,
                                                "frame_type": "diffusion", "diffusion_b_value": 1000})
    assert "b=1000" in d


def test_corner_text_multiframe_dataset_frame_suffix(monkeypatch) -> None:
    monkeypatch.setattr(otb, "is_multiframe", lambda ds: True)
    monkeypatch.setattr(otb, "get_frame_count", lambda ds: 8)
    ds = SimpleNamespace(_frame_index=2, _original_dataset=object())
    p = _FakeParser({"InstanceNumber": "3"}, dataset=ds)
    txt = otb.get_corner_text(p, ["InstanceNumber"], privacy_mode=False, total_slices=10)
    assert "(Frame 3/8)" in txt


def test_corner_text_trailing_frame_info(monkeypatch) -> None:
    monkeypatch.setattr(otb, "is_multiframe", lambda ds: True)
    monkeypatch.setattr(otb, "get_frame_count", lambda ds: 5)
    ds = SimpleNamespace(_frame_index=1, _original_dataset=object())
    # InstanceNumber in tags but total_slices None and no context -> trailing "Frame: x/y"
    p = _FakeParser({"InstanceNumber": "1"}, dataset=ds)
    txt = otb.get_corner_text(p, ["InstanceNumber"], privacy_mode=False)
    assert "Frame: 2/5" in txt
