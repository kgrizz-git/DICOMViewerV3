"""
Generate tiny synthetic DICOM SR fixtures for RDSR / CT dose parser tests.

**Outputs:** writes into ``tests/fixtures/dicom_rdsr/`` (run from **repository root**):

- ``synthetic_ct_dose_xray_rdsr.dcm`` — ``SOPClassUID`` = X-Ray Radiation Dose SR Storage
- ``synthetic_ct_dose_comprehensive_sr.dcm`` — ``SOPClassUID`` = Comprehensive SR Storage
  with the same TID-style ``ContentSequence`` (detection via bounded content signature)

**Inputs:** none (uses ``pydicom.uid.generate_uid`` for synthetic UIDs).

**Requirements:** repository ``.venv`` with ``pydicom`` installed.

No PHI: placeholder **Patient Name** / **Patient ID** only; UIDs are freshly generated each run.
Re-run only when the SR template shape for tests must change; then update ``tests/test_rdsr_dose_sr.py`` if needed.
"""

from __future__ import annotations

import argparse
import os
import sys

from pydicom import Dataset
from pydicom.dataset import FileMetaDataset
from pydicom.filewriter import dcmwrite
from pydicom.sequence import Sequence
from pydicom.uid import (
    ComprehensiveSRStorage,
    ExplicitVRLittleEndian,
    PYDICOM_IMPLEMENTATION_UID,
    XRayRadiationDoseSRStorage,
    generate_uid,
)


def _code_item(code_value: str, scheme: str, meaning: str = "") -> Dataset:
    d = Dataset()
    d.CodeValue = str(code_value)
    d.CodingSchemeDesignator = scheme
    if meaning:
        d.CodeMeaning = meaning
    return d


def _num_item(code_value: str, scheme: str, value: float, unit_cv: str, unit_meaning: str) -> Dataset:
    d = Dataset()
    d.ValueType = "NUM"
    d.ConceptNameCodeSequence = Sequence([_code_item(code_value, scheme)])
    mv = Dataset()
    mv.NumericValue = str(value)
    uc = Dataset()
    uc.CodeValue = unit_cv
    uc.CodingSchemeDesignator = "UCUM"
    uc.CodeMeaning = unit_meaning
    mv.MeasurementUnitsCodeSequence = Sequence([uc])
    d.MeasuredValueSequence = Sequence([mv])
    d.RelationshipType = "CONTAINS"
    return d


def _irradiation_event_container() -> Dataset:
    d = Dataset()
    d.ValueType = "CONTAINER"
    d.ContinuityOfContent = "SEPARATE"
    d.ConceptNameCodeSequence = Sequence(
        [_code_item("113819", "DCM", "CT Irradiation Event Data")]
    )
    d.RelationshipType = "CONTAINS"
    d.ContentSequence = Sequence([])
    return d


def build_synthetic_ct_dose_sr(*, sop_class_uid: str) -> Dataset:
    """Build a minimal SR document with nested CT dose NUM items (TID 10001-style codes)."""
    ds = Dataset()
    ds.SpecificCharacterSet = "ISO_IR 100"
    ds.PatientName = "Synthetic^RDSR"
    ds.PatientID = "SYN-RDSR-001"
    ds.StudyInstanceUID = generate_uid()
    ds.SeriesInstanceUID = generate_uid()
    ds.StudyDate = "20200101"
    ds.StudyTime = "120000"
    ds.Modality = "SR"
    ds.Manufacturer = "SyntheticFixture"
    ds.ManufacturerModelName = "RDSR-Gen"
    ds.DeviceSerialNumber = "SER-SYN-1"
    ds.SeriesDescription = "Synthetic CT dose SR (test fixture)"
    ds.SeriesNumber = 1
    ds.SOPClassUID = sop_class_uid
    ds.SOPInstanceUID = generate_uid()
    ds.InstanceNumber = 1
    ds.CompletionFlag = "COMPLETE"
    ds.VerificationFlag = "UNVERIFIED"

    root = Dataset()
    root.ValueType = "CONTAINER"
    root.ContinuityOfContent = "SEPARATE"
    root.ConceptNameCodeSequence = Sequence(
        [_code_item("113701", "DCM", "CT Radiation Dose")]
    )
    root.RelationshipType = "CONTAINS"
    root.ContentSequence = Sequence(
        [
            _irradiation_event_container(),
            _irradiation_event_container(),
            _num_item("113830", "DCM", 12.5, "mGy", "milliGray"),
            _num_item("113838", "DCM", 450.0, "mGy.cm", "milliGray centimeter"),
            _num_item("113835", "DCM", 8.2, "mGy", "milliGray"),
        ]
    )
    ds.ContentSequence = Sequence([root])

    fm = FileMetaDataset()
    fm.MediaStorageSOPClassUID = ds.SOPClassUID
    fm.MediaStorageSOPInstanceUID = ds.SOPInstanceUID
    fm.TransferSyntaxUID = ExplicitVRLittleEndian
    fm.ImplementationClassUID = PYDICOM_IMPLEMENTATION_UID
    ds.file_meta = fm
    ds.is_implicit_VR = False
    ds.is_little_endian = True
    return ds


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out-dir",
        default="tests/fixtures/dicom_rdsr",
        help="Directory for .dcm outputs (relative to cwd)",
    )
    args = parser.parse_args()
    out_dir = os.path.abspath(args.out_dir)
    os.makedirs(out_dir, exist_ok=True)

    fixtures = [
        ("synthetic_ct_dose_xray_rdsr.dcm", str(XRayRadiationDoseSRStorage)),
        ("synthetic_ct_dose_comprehensive_sr.dcm", str(ComprehensiveSRStorage)),
    ]
    for name, sop in fixtures:
        ds = build_synthetic_ct_dose_sr(sop_class_uid=sop)
        path = os.path.join(out_dir, name)
        dcmwrite(path, ds, write_like_original=False)
        size = os.path.getsize(path)
        print(f"Wrote {path} ({size} bytes) SOPClassUID={sop}")
        if size > 512 * 1024:
            print("WARNING: file exceeds 512 KiB fixture policy", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
