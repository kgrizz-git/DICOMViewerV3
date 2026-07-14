"""Focused unit tests for core.dicom_organizer pure behaviors."""

from __future__ import annotations

import os
import sys
from types import SimpleNamespace
from unittest.mock import patch

from pydicom.dataset import Dataset
from pydicom.tag import Tag

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from core.dicom_organizer import DICOMOrganizer, MultiFrameSeriesInfo
from core.multiframe_handler import FrameType

STUDY_UID = "1.2.826.0.1.3680043.8.498.1"
SERIES_UID = "1.2.826.0.1.3680043.8.498.2"
OTHER_SERIES_UID = "1.2.826.0.1.3680043.8.498.3"


def _dataset(**attrs) -> Dataset:
    ds = Dataset()
    for key, value in attrs.items():
        setattr(ds, key, value)
    return ds


def test_sort_slices_prefers_instance_number_then_slice_location_then_ipp() -> None:
    organizer = DICOMOrganizer()
    by_instance = _dataset(InstanceNumber=2)
    by_slice_location = _dataset(SliceLocation=1.0)
    by_ipp = _dataset(ImagePositionPatient=[0.0, 0.0, 3.0])

    result = organizer._sort_slices(
        [(by_instance, "a"), (by_ipp, "b"), (by_slice_location, "c")]
    )

    assert [item[1] for item in result] == ["c", "a", "b"]


def test_ensure_study_and_series_uids_is_deterministic_for_same_seed() -> None:
    organizer = DICOMOrganizer()
    ds1 = _dataset(SOPInstanceUID="1.2.3")
    ds2 = _dataset(SOPInstanceUID="1.2.3")

    organizer._ensure_study_and_series_uids(ds1, idx=0, file_path="/tmp/a.dcm")
    organizer._ensure_study_and_series_uids(ds2, idx=1, file_path="/tmp/b.dcm")

    assert str(ds1.StudyInstanceUID).startswith("2.25.")
    assert str(ds1.SeriesInstanceUID).startswith("2.25.")
    assert ds1.StudyInstanceUID == ds2.StudyInstanceUID
    assert ds1.SeriesInstanceUID == ds2.SeriesInstanceUID


def test_identity_seed_falls_back_from_file_meta_to_path_to_index() -> None:
    organizer = DICOMOrganizer()

    meta_seed = organizer._identity_seed_for_synthetic_uids(
        SimpleNamespace(file_meta=SimpleNamespace(MediaStorageSOPInstanceUID="9.8.7")),
        idx=3,
        file_path=None,
    )
    path_seed = organizer._identity_seed_for_synthetic_uids(
        SimpleNamespace(file_meta=SimpleNamespace(MediaStorageSOPInstanceUID="  ")),
        idx=4,
        file_path="./relative/file.dcm",
    )
    index_seed = organizer._identity_seed_for_synthetic_uids(
        _dataset(),
        idx=5,
        file_path=None,
    )

    assert meta_seed == "9.8.7"
    assert path_seed.startswith("path:")
    assert path_seed.endswith(os.path.normpath(os.path.abspath("./relative/file.dcm")))
    assert index_seed == "index:5"


def test_organize_collects_series_and_annotation_sidecars() -> None:
    organizer = DICOMOrganizer()
    image2 = _dataset(
        StudyInstanceUID=STUDY_UID,
        SeriesInstanceUID=SERIES_UID,
        SeriesNumber="5",
        InstanceNumber=2,
    )
    image1 = _dataset(
        StudyInstanceUID=STUDY_UID,
        SeriesInstanceUID=SERIES_UID,
        SeriesNumber="5",
        InstanceNumber=1,
        GraphicAnnotationSequence=[],
    )
    image1.add_new(Tag(0x6000, 0x3000), "OB", b"\x00")
    presentation_state = _dataset(
        StudyInstanceUID=STUDY_UID,
        SOPClassUID="1.2.840.10008.5.1.4.1.1.11.1",
    )
    key_object = _dataset(
        StudyInstanceUID=STUDY_UID,
        SOPClassUID="1.2.840.10008.5.1.4.1.1.88.59",
    )

    studies = organizer.organize(
        [image2, presentation_state, key_object, image1],
        file_paths=["/tmp/2.dcm", "/tmp/ps.dcm", "/tmp/ko.dcm", "/tmp/1.dcm"],
    )

    assert list(studies) == [STUDY_UID]
    assert [ds.InstanceNumber for ds in studies[STUDY_UID][f"{SERIES_UID}_5"]] == [1, 2]
    assert organizer.get_file_path(STUDY_UID, f"{SERIES_UID}_5", 1) == "/tmp/1.dcm"
    assert organizer.get_file_path(STUDY_UID, f"{SERIES_UID}_5", 2) == "/tmp/2.dcm"
    assert organizer.get_presentation_states(STUDY_UID) == [presentation_state]
    assert organizer.get_key_objects(STUDY_UID) == [key_object]


def test_organize_expands_multiframe_datasets_and_tracks_frame_paths() -> None:
    organizer = DICOMOrganizer()
    original = _dataset(
        StudyInstanceUID=STUDY_UID,
        SeriesInstanceUID=SERIES_UID,
        InstanceNumber=4,
    )
    frame0 = _dataset()
    frame1 = _dataset()

    with (
        patch("core.dicom_organizer.is_multiframe", return_value=True),
        patch("core.dicom_organizer.get_frame_count", return_value=2),
        patch("core.dicom_organizer.create_frame_dataset", side_effect=[frame0, frame1]),
        patch("core.dicom_organizer.classify_frame_type", return_value=FrameType.TEMPORAL),
    ):
        studies = organizer.organize([original], file_paths=["/tmp/multiframe.dcm"])

    frames = studies[STUDY_UID][SERIES_UID]
    assert [frame._frame_index for frame in frames] == [0, 1]
    assert all(frame._original_dataset is original for frame in frames)
    assert organizer.get_file_path(STUDY_UID, SERIES_UID, 40000) == "/tmp/multiframe.dcm"
    assert organizer.get_file_path(STUDY_UID, SERIES_UID, 40001) == "/tmp/multiframe.dcm"
    assert organizer.get_series_multiframe_info(STUDY_UID, SERIES_UID) == MultiFrameSeriesInfo(
        instance_count=1,
        max_frame_count=2,
        frame_type=FrameType.TEMPORAL,
    )


def test_compute_series_multiframe_info_deduplicates_wrappers_and_marks_mixed_types_unknown() -> None:
    organizer = DICOMOrganizer()
    original = _dataset(SOPInstanceUID="1.2.3")
    frame0 = _dataset()
    frame0._original_dataset = original
    frame0._frame_index = 0
    frame1 = _dataset()
    frame1._original_dataset = original
    frame1._frame_index = 1
    single = _dataset(SOPInstanceUID="9.9.9")

    with (
        patch("core.dicom_organizer.get_frame_count", side_effect=lambda ds: 7 if ds is original else 1),
        patch(
            "core.dicom_organizer.classify_frame_type",
            side_effect=lambda ds: FrameType.TEMPORAL if ds is original else FrameType.SPATIAL,
        ),
    ):
        info = organizer._compute_series_multiframe_info([frame0, frame1, single])

    assert info.instance_count == 2
    assert info.max_frame_count == 7
    assert info.frame_type == FrameType.UNKNOWN


def test_compute_series_multiframe_info_returns_empty_defaults_for_empty_series() -> None:
    organizer = DICOMOrganizer()

    info = organizer._compute_series_multiframe_info([])

    assert info == MultiFrameSeriesInfo(
        instance_count=0,
        max_frame_count=1,
        frame_type=FrameType.UNKNOWN,
    )


def test_update_and_build_series_multiframe_info_map_cover_empty_and_populated_series() -> None:
    organizer = DICOMOrganizer()
    populated = _dataset(SOPInstanceUID="1.2.3")
    organizer.studies = {"study": {"empty": [], "filled": [populated]}}

    with (
        patch("core.dicom_organizer.get_frame_count", return_value=3),
        patch("core.dicom_organizer.classify_frame_type", return_value=FrameType.SPATIAL),
    ):
        organizer._update_series_multiframe_info("study", "empty")
        organizer._update_series_multiframe_info("study", "filled")
        info_map = organizer._build_series_multiframe_info_map(organizer.studies)

    assert organizer.get_series_multiframe_info("study", "empty") is None
    assert organizer.get_series_multiframe_info("study", "filled") == MultiFrameSeriesInfo(
        instance_count=1,
        max_frame_count=3,
        frame_type=FrameType.SPATIAL,
    )
    assert info_map[("study", "empty")].instance_count == 0
    assert info_map[("study", "filled")].frame_type == FrameType.SPATIAL


def test_get_multiframe_display_context_handles_guard_paths_and_full_diffusion_context() -> None:
    organizer = DICOMOrganizer()
    original1 = _dataset(SOPInstanceUID="1.2.1")
    original2 = _dataset(SOPInstanceUID="1.2.2")
    frame0 = _dataset()
    frame0._original_dataset = original1
    frame0._frame_index = 0
    frame1 = _dataset()
    frame1._original_dataset = original1
    frame1._frame_index = 1
    frame2 = _dataset()
    frame2._original_dataset = original2
    frame2._frame_index = 0
    organizer.studies = {"study": {"series": [frame0, frame1, frame2]}}
    organizer.series_multiframe_info = {
        ("study", "series"): MultiFrameSeriesInfo(
            instance_count=2,
            max_frame_count=3,
            frame_type=FrameType.DIFFUSION,
        )
    }

    with (
        patch("core.dicom_organizer.get_frame_count", return_value=3),
        patch("core.dicom_organizer.get_frame_trigger_time_ms", return_value=125.0),
        patch("core.dicom_organizer.get_frame_nominal_cardiac_trigger_time_ms", return_value=250.0),
        patch("core.dicom_organizer.get_frame_diffusion_b_value", return_value=800.0),
        patch("core.dicom_organizer.get_frame_content_time", return_value="101010.123"),
    ):
        context = organizer.get_multiframe_display_context("study", "series", frame1)

    assert organizer.get_multiframe_display_context("study", "series", None) is None
    assert organizer.get_multiframe_display_context("study", "series", _dataset()) is None
    assert organizer.get_multiframe_display_context("missing", "series", frame1) is None
    assert context == {
        "instance_index": 1,
        "total_instances": 2,
        "frame_index": 2,
        "total_frames": 3,
        "frame_type": "diffusion",
        "trigger_time_ms": 125.0,
        "nominal_cardiac_trigger_time_ms": 250.0,
        "diffusion_b_value": 800.0,
        "content_time": "101010.123",
    }


def test_get_multiframe_display_context_returns_none_when_instance_missing_or_single_frame() -> None:
    organizer = DICOMOrganizer()
    original = _dataset(SOPInstanceUID="1.2.3")
    frame = _dataset()
    frame._original_dataset = original
    frame._frame_index = 0

    organizer.studies = {"study": {"series": []}}
    with patch("core.dicom_organizer.get_frame_count", return_value=2):
        assert organizer.get_multiframe_display_context("study", "series", frame) is None

    organizer.studies = {"study": {"series": [frame]}}
    other_frame = _dataset()
    other_frame._original_dataset = _dataset(SOPInstanceUID="9.9.9")
    other_frame._frame_index = 0
    with patch("core.dicom_organizer.get_frame_count", return_value=2):
        assert organizer.get_multiframe_display_context("study", "series", other_frame) is None

    with patch("core.dicom_organizer.get_frame_count", return_value=1):
        assert organizer.get_multiframe_display_context("study", "series", frame) is None


def test_get_multiframe_display_context_uses_unknown_type_and_omits_optional_fields() -> None:
    organizer = DICOMOrganizer()
    original = _dataset(SOPInstanceUID="1.2.3")
    frame = _dataset()
    frame._original_dataset = original
    frame._frame_index = 0
    organizer.studies = {"study": {"series": [frame]}}

    with (
        patch("core.dicom_organizer.get_frame_count", return_value=2),
        patch("core.dicom_organizer.get_frame_trigger_time_ms", return_value=None),
        patch("core.dicom_organizer.get_frame_nominal_cardiac_trigger_time_ms", return_value=None),
        patch("core.dicom_organizer.get_frame_content_time", return_value=None),
    ):
        context = organizer.get_multiframe_display_context("study", "series", frame)

    assert context == {
        "instance_index": 1,
        "total_instances": 1,
        "frame_index": 1,
        "total_frames": 2,
        "frame_type": "unknown",
    }


def test_sort_slices_handles_multiframe_and_invalid_numeric_fallbacks() -> None:
    organizer = DICOMOrganizer()
    original = SimpleNamespace(InstanceNumber="bad")
    frame1 = _dataset()
    frame1._original_dataset = original
    frame1._frame_index = 1
    frame0 = _dataset()
    frame0._original_dataset = original
    frame0._frame_index = 0
    by_short_ipp = SimpleNamespace(ImagePositionPatient=[1.0, 2.0])
    by_bad_ipp = SimpleNamespace(ImagePositionPatient=[1.0, 2.0, "bad-z"])

    result = organizer._sort_slices(
        [(frame1, "frame1"), (by_short_ipp, "short"), (frame0, "frame0"), (by_bad_ipp, "bad")]
    )

    labels = [item[1] for item in result]
    assert labels.index("frame0") < labels.index("frame1")
    assert set(labels[-2:]) == {"frame1", "bad"} or set(labels[-2:]) == {"short", "bad"}


def test_sort_slices_handles_invalid_single_frame_instance_and_slice_location_values() -> None:
    organizer = DICOMOrganizer()
    bad_instance = SimpleNamespace(InstanceNumber="bad", SliceLocation="bad-slice")
    valid_ipp = _dataset(ImagePositionPatient=[0.0, 0.0, 1.5])

    result = organizer._sort_slices([(bad_instance, "bad"), (valid_ipp, "good")])

    assert [item[1] for item in result] == ["good", "bad"]


def test_get_instance_identifier_uses_frame_wrapper_encoding() -> None:
    organizer = DICOMOrganizer()
    original = _dataset(InstanceNumber=4)
    frame = _dataset()
    frame._original_dataset = original
    frame._frame_index = 2

    assert organizer._get_instance_identifier(frame, idx_fallback=0) == 40002
    assert organizer._get_instance_identifier(_dataset(InstanceNumber=9), idx_fallback=0) == 9


def test_get_tag_value_returns_default_for_missing_none_and_exception() -> None:
    organizer = DICOMOrganizer()

    class Exploding:
        def __getattr__(self, _name: str) -> object:
            raise RuntimeError("boom")

    assert organizer._get_tag_value(_dataset(PatientName="Alice"), "PatientName", "missing") == "Alice"
    assert organizer._get_tag_value(_dataset(PatientName=None), "PatientName", "missing") == "missing"
    assert organizer._get_tag_value(_dataset(), "PatientName", "missing") == "missing"
    assert organizer._get_tag_value(Exploding(), "PatientName", "missing") == "missing"


def test_merge_batch_handles_empty_new_series_append_skip_and_disambiguation() -> None:
    organizer = DICOMOrganizer()
    empty_result = organizer.merge_batch([])
    assert empty_result == organizer.merge_batch([])

    first = _dataset(StudyInstanceUID=STUDY_UID, SeriesInstanceUID=SERIES_UID, InstanceNumber=2)
    append = _dataset(StudyInstanceUID=STUDY_UID, SeriesInstanceUID=SERIES_UID, InstanceNumber=1)
    duplicate = _dataset(StudyInstanceUID=STUDY_UID, SeriesInstanceUID=SERIES_UID, InstanceNumber=9)
    disambiguated = _dataset(StudyInstanceUID=STUDY_UID, SeriesInstanceUID=SERIES_UID, InstanceNumber=3)

    first_result = organizer.merge_batch([first], ["/tmp/first.dcm"], source_dir="/source/a")
    append_result = organizer.merge_batch([append], ["/tmp/append.dcm"], source_dir="/source/a")
    skip_result = organizer.merge_batch([duplicate], ["/tmp/append.dcm"], source_dir="/source/a")
    disambiguated_result = organizer.merge_batch([disambiguated], ["/tmp/other.dcm"], source_dir="/source/b")

    assert first_result.new_series == [(STUDY_UID, SERIES_UID)]
    assert first_result.appended_series == []
    assert first_result.skipped_file_count == 0
    assert first_result.added_file_count == 1

    assert append_result.new_series == []
    assert append_result.appended_series == [(STUDY_UID, SERIES_UID)]
    assert [ds.InstanceNumber for ds in organizer.studies[STUDY_UID][SERIES_UID]] == [1, 2]

    assert skip_result.skipped_file_count == 1
    assert skip_result.added_file_count == 0

    assert disambiguated_result.new_series == [(STUDY_UID, f"{SERIES_UID}_v2")]
    assert organizer.series_source_dirs[(STUDY_UID, SERIES_UID)] == "/source/a"
    assert organizer.series_source_dirs[(STUDY_UID, f"{SERIES_UID}_v2")] == "/source/b"
    assert organizer.file_paths[(STUDY_UID, f"{SERIES_UID}_v2", 3)] == "/tmp/other.dcm"
    assert organizer._disambiguation_counters[(STUDY_UID, SERIES_UID)] == 3


def test_merge_batch_without_file_paths_tracks_studies_but_not_loaded_paths() -> None:
    organizer = DICOMOrganizer()
    ds = _dataset(StudyInstanceUID=STUDY_UID, SeriesInstanceUID=OTHER_SERIES_UID, InstanceNumber=1)

    result = organizer.merge_batch([ds], None, source_dir="/source/a")

    assert result.new_series == [(STUDY_UID, OTHER_SERIES_UID)]
    assert result.added_file_count == 0
    assert organizer.loaded_file_paths == set()
    assert organizer.get_file_path(STUDY_UID, OTHER_SERIES_UID, 1) is None


def test_remove_series_cleans_paths_loaded_state_and_study_if_last_series() -> None:
    organizer = DICOMOrganizer()
    organizer.studies = {"study": {"series": [_dataset()]}}
    organizer.file_paths = {("study", "series", 1): "/tmp/one.dcm"}
    organizer.loaded_file_paths = {os.path.normpath(os.path.abspath("/tmp/one.dcm"))}
    organizer.series_source_dirs = {("study", "series"): "/tmp"}
    organizer.series_multiframe_info = {("study", "series"): object()}
    organizer.presentation_states = {"study": [_dataset()]}
    organizer.key_objects = {"study": [_dataset()]}
    organizer._disambiguation_counters = {("study", "series"): 2}

    organizer.remove_series("study", "series")

    assert "study" not in organizer.studies
    assert organizer.file_paths == {}
    assert organizer.loaded_file_paths == set()
    assert organizer.series_source_dirs == {}
    assert organizer.series_multiframe_info == {}
    assert organizer.presentation_states == {}
    assert organizer.key_objects == {}
    assert organizer._disambiguation_counters == {}


def test_remove_series_and_remove_study_are_noops_for_unknown_ids() -> None:
    organizer = DICOMOrganizer()
    organizer.studies = {"study": {"series": [_dataset()]}}
    snapshot = organizer.studies.copy()

    organizer.remove_series("study", "missing")
    organizer.remove_series("missing", "series")
    organizer.remove_study("missing")

    assert organizer.studies == snapshot


def test_remove_study_cleans_all_associated_state() -> None:
    organizer = DICOMOrganizer()
    organizer.studies = {"study": {"series1": [_dataset()], "series2": [_dataset()]}}
    organizer.file_paths = {
        ("study", "series1", 1): "/tmp/one.dcm",
        ("study", "series2", 2): "/tmp/two.dcm",
    }
    organizer.loaded_file_paths = {
        os.path.normpath(os.path.abspath("/tmp/one.dcm")),
        os.path.normpath(os.path.abspath("/tmp/two.dcm")),
    }
    organizer.series_source_dirs = {
        ("study", "series1"): "/tmp",
        ("study", "series2"): "/tmp",
    }
    organizer.series_multiframe_info = {
        ("study", "series1"): object(),
        ("study", "series2"): object(),
    }
    organizer.presentation_states = {"study": [_dataset()]}
    organizer.key_objects = {"study": [_dataset()]}
    organizer._disambiguation_counters = {
        ("study", "series1"): 2,
        ("study", "series2"): 3,
    }

    organizer.remove_study("study")

    assert organizer.studies == {}
    assert organizer.file_paths == {}
    assert organizer.loaded_file_paths == set()
    assert organizer.series_source_dirs == {}
    assert organizer.series_multiframe_info == {}
    assert organizer.presentation_states == {}
    assert organizer.key_objects == {}
    assert organizer._disambiguation_counters == {}


def test_clear_and_read_only_getters_return_current_state() -> None:
    organizer = DICOMOrganizer()
    ds1 = _dataset()
    ds2 = _dataset()
    organizer.studies = {"study1": {"series1": [ds1]}, "study2": {"series2": [ds2]}}
    organizer.file_paths = {("study1", "series1", 7): "/tmp/one.dcm"}
    organizer.presentation_states = {"study1": [_dataset()]}
    organizer.key_objects = {"study1": [_dataset()]}

    assert organizer.get_studies() is organizer.studies
    assert organizer.get_series_list("study1") == [("study1", "series1")]
    assert set(organizer.get_series_list()) == {("study1", "series1"), ("study2", "series2")}
    assert organizer.get_series_list("missing") == []
    assert organizer.get_slice_count("study1", "series1") == 1
    assert organizer.get_slice_count("study1", "missing") == 0
    assert organizer.get_file_path("study1", "series1", 7) == "/tmp/one.dcm"
    assert organizer.get_file_path("study1", "series1", 99) is None
    assert len(organizer.get_presentation_states("study1")) == 1
    assert len(organizer.get_key_objects("study1")) == 1
    assert organizer.get_series_multiframe_info("study1", "series1") is None

    organizer.clear()

    assert organizer.studies == {}
    assert organizer.file_paths == {}
    assert organizer.series_multiframe_info == {}
    assert organizer.presentation_states == {}
    assert organizer.key_objects == {}
    assert organizer.loaded_file_paths == set()
    assert organizer.series_source_dirs == {}
    assert organizer._disambiguation_counters == {}
