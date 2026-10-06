"""Projection + deep-anonymize export: preview paths, fail-closed paths, and file contents."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pydicom
from pydicom.dataset import Dataset, FileMetaDataset
from pydicom.uid import CTImageStorage, ExplicitVRLittleEndian, generate_uid

from core.multiframe_handler import create_frame_dataset
from gui import export_manager as export_manager_module
from gui.export_manager import ExportManager, ExportSelectedRequest, ExportSliceRequest
from utils.deep_anonymizer import DeepAnonymizerOptions

STUDY = generate_uid()
SERIES = generate_uid()


class _NoopProgress:
    def __init__(self, *_args) -> None:
        pass

    def setWindowModality(self, _modality) -> None:
        pass

    def setMinimumDuration(self, _duration) -> None:
        pass

    def wasCanceled(self) -> bool:
        return False

    def setValue(self, _value: int) -> None:
        pass

    def close(self) -> None:
        pass


def _slice(number: int, values: list[list[int]]) -> Dataset:
    ds = Dataset()
    ds.file_meta = FileMetaDataset()
    ds.file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
    ds.file_meta.MediaStorageSOPClassUID = CTImageStorage
    ds.SOPClassUID = CTImageStorage
    ds.SOPInstanceUID = generate_uid()
    ds.file_meta.MediaStorageSOPInstanceUID = ds.SOPInstanceUID
    ds.is_little_endian = True
    ds.is_implicit_VR = False
    ds.PatientName = "Doe^Jane"
    ds.PatientID = "SRC-PID-77"
    ds.StudyDate = "20260101"
    ds.StudyDescription = "Synthetic Study"
    ds.SeriesDescription = "Synthetic"
    ds.SeriesNumber = 2
    ds.InstanceNumber = number
    ds.StudyInstanceUID = STUDY
    ds.SeriesInstanceUID = SERIES
    ds.Modality = "CT"
    ds.PhotometricInterpretation = "MONOCHROME2"
    ds.SamplesPerPixel = 1
    ds.BitsAllocated = ds.BitsStored = 16
    ds.HighBit = 15
    ds.PixelRepresentation = 0
    arr = np.array(values, dtype=np.uint16)
    ds.Rows, ds.Columns = arr.shape
    ds.PixelData = arr.tobytes()
    return ds


def _selection(n: int = 3):
    slices = [_slice(i + 1, [[i, 9], [3, 4]]) for i in range(n)]
    selected = {(STUDY, SERIES, i): s for i, s in enumerate(slices)}
    return slices, selected, {STUDY: {SERIES: slices}}


def _request(selected, studies, out: Path, items=None, **kw) -> ExportSelectedRequest:
    return ExportSelectedRequest(
        selected,
        str(out),
        "DICOM",
        studies=studies,
        deep_anonymize=True,
        deep_anonymizer_options=DeepAnonymizerOptions(),
        projection_enabled=True,
        projection_type="mip",
        projection_slice_count=2,
        deep_anonymized_items=items,
        **kw,
    )


def _all_text(ds: Dataset) -> str:
    parts: list[str] = []

    def walk(d: Dataset) -> None:
        for elem in d:
            if elem.VR == "SQ":
                for item in elem.value:
                    walk(item)
            elif elem.tag != 0x7FE00010:
                parts.append(str(elem.value))

    walk(ds)
    walk(ds.file_meta)
    return "\n".join(parts)


def test_preview_paths_equal_written_paths(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(export_manager_module, "QProgressDialog", _NoopProgress)
    slices, selected, studies = _selection()
    options = DeepAnonymizerOptions()
    batch = ExportManager.build_anonymized_projections_for_selection(
        selected, studies, "mip", 2, False, options
    )
    preview = ExportManager.get_export_paths_for_selection(
        selected, str(tmp_path), "DICOM", projection_enabled=True, projection_type="mip",
        projection_slice_count=2, deep_anonymize=True, deep_anonymizer_options=options,
        deep_anonymized_items=batch, studies=studies,
    )
    exported, _ = ExportManager().export_selected(_request(selected, studies, tmp_path, batch))
    written = sorted(str(p) for p in tmp_path.rglob("*.dcm"))
    assert exported == 3
    assert sorted(preview) == written
    assert all("_MIP_2slices" in p for p in written)


def test_written_files_have_no_source_identifiers(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(export_manager_module, "QProgressDialog", _NoopProgress)
    slices, selected, studies = _selection()
    ExportManager().export_selected(_request(selected, studies, tmp_path))
    files = sorted(tmp_path.rglob("*.dcm"))
    assert len(files) == 3
    source_uids = {STUDY, SERIES} | {s.SOPInstanceUID for s in slices}
    series_uids = set()
    for path in files:
        back = pydicom.dcmread(path)
        text = _all_text(back)
        assert "Doe" not in text
        assert "SRC-PID-77" not in text
        assert not any(uid in text for uid in source_uids)
        assert "SRC-PID-77" not in str(path)
        assert "Doe" not in str(path)
        series_uids.add(back.SeriesInstanceUID)
    assert len(series_uids) == 1
    assert sorted(pydicom.dcmread(p).InstanceNumber for p in files) == [1, 2, 3]


def test_failed_projection_writes_nothing_and_is_not_counted(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(export_manager_module, "QProgressDialog", _NoopProgress)
    slices, selected, studies = _selection(2)
    # Item 0 fails: the slab's second slice has no readable pixels.
    del slices[1].PixelData
    exported, _ = ExportManager().export_selected(_request(selected, studies, tmp_path))
    files = list(tmp_path.rglob("*.dcm"))
    # Item 1 is a single-slice slab (last slice) and still builds.
    assert exported == 1
    assert len(files) == 1
    batch = ExportManager.build_anonymized_projections_for_selection(
        selected, studies, "mip", 2, False
    )
    assert (STUDY, SERIES, 0) not in batch


def test_failed_projection_without_anonymization_writes_nothing(tmp_path: Path) -> None:
    slices, selected, studies = _selection(2)
    del slices[1].PixelData
    ok, _ = ExportManager().export_slice(
        ExportSliceRequest(
            slices[0], str(tmp_path / "x.dcm"), "DICOM", study_uid=STUDY, series_uid=SERIES,
            slice_index=0, projection_enabled=True, projection_type="mip",
            projection_slice_count=2, studies=studies,
        )
    )
    assert ok is False
    assert not (tmp_path / "x.dcm").exists()


def test_frame_wrapper_failure_writes_no_raw_source(tmp_path: Path) -> None:
    mf = _slice(1, [[0, 0], [0, 0]])
    mf.NumberOfFrames = 2
    mf.PixelData = np.zeros((2, 2, 2), dtype=np.uint16).tobytes()
    mf.PerFrameFunctionalGroupsSequence = pydicom.Sequence([Dataset(), Dataset()])
    frames = [create_frame_dataset(mf, i) for i in range(2)]
    frames[0]._frame_index = 99  # pixel read fails
    studies = {STUDY: {SERIES: frames}}
    ok, _ = ExportManager().export_slice(
        ExportSliceRequest(
            frames[0], str(tmp_path / "f.dcm"), "DICOM", study_uid=STUDY, series_uid=SERIES,
            slice_index=0, projection_enabled=True, projection_type="mip",
            projection_slice_count=2, studies=studies,
        )
    )
    assert ok is False
    assert not (tmp_path / "f.dcm").exists()


def test_anonymized_projection_without_prebuilt_dataset_is_refused(tmp_path: Path) -> None:
    slices, selected, studies = _selection()
    ok, _ = ExportManager().export_slice(
        ExportSliceRequest(
            slices[0], str(tmp_path / "raw.dcm"), "DICOM", study_uid=STUDY, series_uid=SERIES,
            slice_index=0, projection_enabled=True, projection_type="mip",
            projection_slice_count=2, studies=studies, dataset_pre_anonymized=True,
        )
    )
    assert ok is False
    assert not (tmp_path / "raw.dcm").exists()


def test_export_selected_fails_closed_when_batch_lacks_a_key(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(export_manager_module, "QProgressDialog", _NoopProgress)
    slices, selected, studies = _selection()
    batch = ExportManager.build_anonymized_projections_for_selection(
        selected, studies, "mip", 2, False
    )
    del batch[(STUDY, SERIES, 1)]
    exported, _ = ExportManager().export_selected(_request(selected, studies, tmp_path, batch))
    assert exported == 2
    for path in tmp_path.rglob("*.dcm"):
        assert "SRC-PID-77" not in _all_text(pydicom.dcmread(path))
