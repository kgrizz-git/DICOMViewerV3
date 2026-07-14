"""Round-trip tests for path-addressed nested tag editing."""

from __future__ import annotations

import pydicom
from pydicom.dataset import Dataset, FileDataset, FileMetaDataset
from pydicom.sequence import Sequence
from pydicom.tag import Tag
from pydicom.uid import (
    ExplicitVRLittleEndian,
    SecondaryCaptureImageStorage,
    generate_uid,
)

from core.dicom_editor import DICOMEditor

DEID_SEQ = Tag(0x0012, 0x0064)
CODE_MEANING = Tag(0x0008, 0x0104)
NESTED_KEY = "(0012, 0064)[0].(0008, 0104)"


def _file_dataset(nested_value: str = "Original nested meaning") -> FileDataset:
    sop_instance_uid = generate_uid()
    file_meta = FileMetaDataset()
    file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
    file_meta.MediaStorageSOPClassUID = SecondaryCaptureImageStorage
    file_meta.MediaStorageSOPInstanceUID = sop_instance_uid
    file_meta.ImplementationClassUID = generate_uid()

    ds = FileDataset(None, {}, file_meta=file_meta, preamble=b"\0" * 128)
    ds.SOPClassUID = SecondaryCaptureImageStorage
    ds.SOPInstanceUID = sop_instance_uid
    ds.PatientName = "Roundtrip^Patient"

    item = Dataset()
    item.add_new(CODE_MEANING, "LO", nested_value)
    ds.add_new(DEID_SEQ, "SQ", Sequence([item]))
    return ds


def test_nested_edit_survives_save_reload_without_creating_root_tag(tmp_path) -> None:
    ds = _file_dataset()
    editor = DICOMEditor(ds)

    assert editor.update_tag(NESTED_KEY, "Reloaded nested meaning", vr="LO") is True

    path = tmp_path / "nested-edit.dcm"
    ds.save_as(path, write_like_original=False)
    reloaded = pydicom.dcmread(path)

    assert CODE_MEANING not in reloaded
    assert reloaded[DEID_SEQ].value[0][CODE_MEANING].value == "Reloaded nested meaning"


def test_nested_edit_on_frame_wrapper_survives_save_reload(tmp_path) -> None:
    original = _file_dataset("Original graph value")
    wrapper = _file_dataset("Wrapper graph value")
    wrapper._original_dataset = original
    editor = DICOMEditor(wrapper)

    assert editor.update_tag(NESTED_KEY, "Changed through wrapper", vr="LO") is True

    path = tmp_path / "nested-edit-wrapper.dcm"
    original.save_as(path, write_like_original=False)
    reloaded = pydicom.dcmread(path)

    assert CODE_MEANING not in reloaded
    assert reloaded[DEID_SEQ].value[0][CODE_MEANING].value == "Changed through wrapper"
    assert wrapper[DEID_SEQ].value[0][CODE_MEANING].value == "Changed through wrapper"
