"""
Characterization tests for series-navigator list-update helpers (Sonar S3776).

Covers pure layout/label helpers extracted from
``SeriesNavigator.update_series_list``.
"""

from __future__ import annotations

from types import SimpleNamespace

from gui.series_navigator_model import (
    compute_study_section_width,
    first_nonempty_series_dataset,
    series_thumbnail_display_label,
    sorted_series_entries,
)


def test_first_nonempty_and_sorted_series_entries() -> None:
    empty = {"s0": []}
    assert first_nonempty_series_dataset(empty) is None

    ds_b = SimpleNamespace(SeriesNumber="2")
    ds_a = SimpleNamespace(SeriesNumber="10")
    ds_bad = SimpleNamespace(SeriesNumber="x")
    study = {"s_empty": [], "s_b": [ds_b], "s_a": [ds_a], "s_bad": [ds_bad]}
    assert first_nonempty_series_dataset(study) is ds_b
    rows = sorted_series_entries(study)
    assert [r[0] for r in rows] == [0, 2, 10]
    assert rows[0][1] == "s_bad"


def test_series_thumbnail_display_label_variants() -> None:
    long_desc = "A" * 20
    assert series_thumbnail_display_label(
        SimpleNamespace(SeriesDescription=long_desc, Modality="CT"), 3
    ) == ("A" * 16 + "…")
    assert (
        series_thumbnail_display_label(SimpleNamespace(SeriesDescription="  ", Modality="MR"), 2)
        == "MR S2"
    )
    assert series_thumbnail_display_label(SimpleNamespace(), 7) == "S7"


def test_compute_study_section_width_instances_and_mpr() -> None:
    ds = SimpleNamespace()
    series_list = [(1, "ser", ds)]
    info = SimpleNamespace(instance_count=3, max_frame_count=4)
    width = compute_study_section_width(
        series_list,
        "stu",
        show_instances_separately=True,
        multiframe_info_map={("stu", "ser"): info},
        mpr_thumbnail_specs={
            0: {"study_uid": "stu", "source_series_uid": "ser"},
            1: {"study_uid": "other", "source_series_uid": "ser"},
        },
    )
    # 68 + 4 + 3*48 + 2*4 + one MPR (5+68)
    assert width == 68 + 4 + 144 + 8 + 73

    assert (
        compute_study_section_width(
            [],
            "stu",
            show_instances_separately=False,
            multiframe_info_map={},
            mpr_thumbnail_specs={},
        )
        == 68
    )
