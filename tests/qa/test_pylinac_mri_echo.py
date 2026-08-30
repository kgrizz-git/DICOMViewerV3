"""Unit tests for MRI echo auto-highest resolution (no live pylinac analyze)."""

from __future__ import annotations

from pathlib import Path

from pydicom.dataset import FileDataset, FileMetaDataset
from pydicom.uid import ExplicitVRLittleEndian, MRImageStorage, generate_uid

from qa.analysis_types import QARequest, build_pylinac_analysis_profile
from qa.pylinac_mri_echo import (
    coerce_echo_number,
    highest_echo_number_from_paths,
    resolve_mri_analyze_echo_number,
    stamp_analyzed_echo_on_profile,
    stamp_resolved_echo_on_profile,
)


def _write_echo_file(
    path: Path, echo: int | None, *, series_uid: str | None = None
) -> None:
    """Minimal non-PHI MR header; *echo* None omits EchoNumbers."""
    sop = generate_uid()
    file_meta = FileMetaDataset()
    file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
    file_meta.MediaStorageSOPClassUID = MRImageStorage
    file_meta.MediaStorageSOPInstanceUID = sop
    dataset = FileDataset(str(path), {}, file_meta=file_meta, preamble=b"\0" * 128)
    dataset.is_little_endian = True
    dataset.is_implicit_VR = False
    dataset.SOPClassUID = MRImageStorage
    dataset.SOPInstanceUID = sop
    dataset.Modality = "MR"
    if echo is not None:
        dataset.EchoNumbers = echo
    if series_uid:
        dataset.SeriesInstanceUID = series_uid
    dataset.save_as(str(path), write_like_original=False)


def test_coerce_echo_number_parses_int_and_skips_junk() -> None:
    assert coerce_echo_number(2) == 2
    assert coerce_echo_number("3") == 3
    assert coerce_echo_number([1, 2]) == 2
    assert coerce_echo_number(None) is None
    assert coerce_echo_number("not-an-echo") is None
    assert coerce_echo_number(0) is None
    assert coerce_echo_number(-1) is None


def test_highest_echo_number_from_dual_echo_files(tmp_path: Path) -> None:
    echo1 = tmp_path / "e1.dcm"
    echo2 = tmp_path / "e2.dcm"
    _write_echo_file(echo1, 1)
    _write_echo_file(echo2, 2)
    assert highest_echo_number_from_paths([str(echo1), str(echo2)]) == 2


def test_resolve_explicit_echo_does_not_scan_missing_files() -> None:
    request = QARequest(
        analysis_type="acr_mri_large",
        dicom_paths=["missing-1.dcm"],
        echo_number=1,
    )
    assert resolve_mri_analyze_echo_number(request) == 1


def test_resolve_non_positive_explicit_echo_returns_none() -> None:
    request = QARequest(
        analysis_type="acr_mri_large",
        dicom_paths=["missing-1.dcm"],
        echo_number=0,
    )
    assert resolve_mri_analyze_echo_number(request) is None


def test_resolve_none_uses_highest_echo_from_series(tmp_path: Path) -> None:
    echo1 = tmp_path / "e1.dcm"
    echo2 = tmp_path / "e2.dcm"
    _write_echo_file(echo1, 1)
    _write_echo_file(echo2, 2)
    request = QARequest(
        analysis_type="acr_mri_large",
        dicom_paths=[str(echo1), str(echo2)],
        echo_number=None,
    )
    assert resolve_mri_analyze_echo_number(request) == 2


def test_resolve_none_without_echo_tags_returns_none(tmp_path: Path) -> None:
    path = tmp_path / "no-echo.dcm"
    sop = generate_uid()
    file_meta = FileMetaDataset()
    file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
    file_meta.MediaStorageSOPClassUID = MRImageStorage
    file_meta.MediaStorageSOPInstanceUID = sop
    dataset = FileDataset(str(path), {}, file_meta=file_meta, preamble=b"\0" * 128)
    dataset.is_little_endian = True
    dataset.is_implicit_VR = False
    dataset.SOPClassUID = MRImageStorage
    dataset.SOPInstanceUID = sop
    dataset.Modality = "MR"
    dataset.save_as(str(path), write_like_original=False)
    request = QARequest(
        analysis_type="acr_mri_large",
        dicom_paths=[str(path)],
        echo_number=None,
    )
    assert resolve_mri_analyze_echo_number(request) is None


def test_resolve_none_scans_nested_folder(tmp_path: Path) -> None:
    nested = tmp_path / "series" / "echo-files"
    nested.mkdir(parents=True)
    _write_echo_file(nested / "e1.dcm", 1)
    _write_echo_file(nested / "e2.dcm", 2)
    request = QARequest(
        analysis_type="acr_mri_large",
        folder_path=str(tmp_path),
        echo_number=None,
    )
    assert resolve_mri_analyze_echo_number(request) == 2


def test_build_profile_does_not_stamp_unresolved_echo_number() -> None:
    request = QARequest(analysis_type="acr_mri_large", echo_number=None)
    profile = build_pylinac_analysis_profile(request, engine="ACRMRILargeForViewer")
    assert "echo_number" not in profile
    stamp_analyzed_echo_on_profile(profile, request, 2)
    assert profile["echo_number"] == 2


def test_stamp_analyzed_echo_on_profile_records_auto_highest() -> None:
    profile: dict[str, object] = {}
    request = QARequest(analysis_type="acr_mri_large", echo_number=None)
    stamp_analyzed_echo_on_profile(profile, request, 2)
    assert profile["echo_number"] == 2
    assert profile["echo_number_requested"] is None
    assert profile["echo_number_auto_highest"] is True
    assert profile["vanilla_equivalent"] is False


def test_stamp_auto_highest_none_is_not_auto_highest() -> None:
    profile: dict[str, object] = {"vanilla_equivalent": True}
    request = QARequest(analysis_type="acr_mri_large", echo_number=None)
    stamp_analyzed_echo_on_profile(profile, request, None)
    assert profile["echo_number"] is None
    assert profile["echo_number_auto_highest"] is False
    assert profile["vanilla_equivalent"] is True


def test_resolved_echo_clears_stock_vanilla_equivalent() -> None:
    request = QARequest(
        analysis_type="acr_mri_large",
        echo_number=None,
        vanilla_pylinac=True,
    )
    profile = build_pylinac_analysis_profile(request, engine="ACRMRILarge")
    assert profile["vanilla_equivalent"] is True
    stamp_analyzed_echo_on_profile(profile, request, 2)
    assert profile["vanilla_equivalent"] is False


def test_folder_mixed_series_does_not_auto_highest(tmp_path: Path) -> None:
    series_a = "1.2.840.999.10.1"
    series_b = "1.2.840.999.10.2"
    _write_echo_file(tmp_path / "a.dcm", 1, series_uid=series_a)
    _write_echo_file(tmp_path / "b.dcm", 4, series_uid=series_b)
    request = QARequest(
        analysis_type="acr_mri_large",
        folder_path=str(tmp_path),
        echo_number=None,
    )
    assert resolve_mri_analyze_echo_number(request) is None


def test_folder_mixed_series_rejects_when_second_series_has_no_echo(
    tmp_path: Path,
) -> None:
    series_a = "1.2.840.999.12.1"
    series_b = "1.2.840.999.12.2"
    _write_echo_file(tmp_path / "a.dcm", 2, series_uid=series_a)
    _write_echo_file(tmp_path / "b.dcm", None, series_uid=series_b)
    request = QARequest(
        analysis_type="acr_mri_large",
        folder_path=str(tmp_path),
        echo_number=None,
    )
    assert resolve_mri_analyze_echo_number(request) is None


def test_folder_filters_to_requested_series(tmp_path: Path) -> None:
    series_a = "1.2.840.999.11.1"
    series_b = "1.2.840.999.11.2"
    _write_echo_file(tmp_path / "a.dcm", 1, series_uid=series_a)
    _write_echo_file(tmp_path / "b.dcm", 4, series_uid=series_b)
    request = QARequest(
        analysis_type="acr_mri_large",
        folder_path=str(tmp_path),
        series_uid=series_a,
        echo_number=None,
    )
    assert resolve_mri_analyze_echo_number(request) == 1


def test_stamp_resolved_echo_on_profile_uses_explicit_request() -> None:
    profile: dict[str, object] = {}
    request = QARequest(analysis_type="acr_mri_large", echo_number=3)
    analyzed = stamp_resolved_echo_on_profile(profile, request)
    assert analyzed == 3
    assert profile["echo_number"] == 3
    assert profile["echo_number_requested"] == 3
    assert profile["echo_number_auto_highest"] is False
