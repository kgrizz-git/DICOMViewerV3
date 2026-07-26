"""
Characterization tests for overlay corner-text helpers (Sonar S3776 slice).

Covers numeric formatting, multiframe labels, and InstanceNumber slice display
extracted from ``get_corner_text``.
"""

from __future__ import annotations

from gui.overlay_text_builder import (
    format_instance_number_slice_display,
    format_multiframe_corner_label,
    format_overlay_numeric_value,
    try_format_multiframe_timing_line,
    try_format_slice_thickness_line,
)


def test_format_overlay_numeric_value() -> None:
    assert format_overlay_numeric_value(3.0) == "3"
    assert format_overlay_numeric_value(3.140) == "3.14"
    assert format_overlay_numeric_value("x") == "x"


def test_format_multiframe_corner_label_diffusion_and_unknown() -> None:
    assert format_multiframe_corner_label({"frame_index": 1, "total_frames": 4}) == "Frame 1/4"
    assert (
        format_multiframe_corner_label(
            {
                "frame_index": 1,
                "total_frames": 4,
                "frame_type": "diffusion",
                "diffusion_b_value": 800.0,
            }
        )
        == "b=800"
    )
    assert format_multiframe_corner_label({"frame_index": None, "total_frames": 4}) == ""


def test_format_instance_number_projection_without_type_label() -> None:
    text = format_instance_number_slice_display(
        "2",
        total_slices=10,
        stack_position=None,
        projection_enabled=True,
        projection_start_slice=0,
        projection_end_slice=3,
        projection_type=None,
        is_multiframe_dataset=False,
        frame_index=None,
        total_frames=None,
    )
    assert text == "Slice 2/10 (1-4)"


def test_try_format_slice_thickness_and_timing() -> None:
    assert (
        try_format_slice_thickness_line(
            "SliceThickness",
            "2.5",
            projection_enabled=True,
            projection_total_thickness=10.0,
        )
        == "Slice Thickness: 2.5 (10.0)"
    )
    assert (
        try_format_slice_thickness_line(
            "Other", "1", projection_enabled=True, projection_total_thickness=1.0
        )
        is None
    )
    assert (
        try_format_multiframe_timing_line(
            "NominalCardiacTriggerTime",
            {"nominal_cardiac_trigger_time_ms": 25.0},
        )
        == "NominalCardiacTriggerTime: 25 ms"
    )
    assert try_format_multiframe_timing_line("TriggerTime", None) is None
