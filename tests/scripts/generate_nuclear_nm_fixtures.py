"""Generate small, wholly synthetic NM DICOM fixtures for pylinac tests.

The fixtures exercise only two simple planar workflows:

* ``synthetic_nm_planar_uniformity.dcm``: a uniform, circular field.
* ``synthetic_nm_four_bar_resolution.dcm``: perpendicular two-peak profiles
  with a known 100 mm separation.

They contain no patient, institution, acquisition, or private metadata.  The
fixed UIDs and pixel arrays make the committed binary fixtures reproducible.
Run from the repository root with the project virtual environment activated::

    python tests/scripts/generate_nuclear_nm_fixtures.py
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
from pydicom.dataset import Dataset, FileMetaDataset
from pydicom.filewriter import dcmwrite
from pydicom.uid import (
    PYDICOM_IMPLEMENTATION_UID,
    ExplicitVRLittleEndian,
    NuclearMedicineImageStorage,
)

try:
    from scripts.privacy_console import print_redacted
except ModuleNotFoundError:
    from privacy_console import print_redacted

_OUT_DIR = Path("tests/fixtures/dicom_nuclear")
_SYNTHETIC_UID_ROOT = "2.25.30000000000000000000000000000000000"


def _base_dataset(*, sop_instance_suffix: int, pixels: np.ndarray) -> Dataset:
    """Return a minimal static NM image with intentionally synthetic metadata."""
    if pixels.dtype != np.uint16 or pixels.ndim != 2:
        raise ValueError("NM fixture pixels must be a 2D uint16 array")

    ds = Dataset()
    ds.SpecificCharacterSet = "ISO_IR 100"
    ds.SOPClassUID = NuclearMedicineImageStorage
    ds.SOPInstanceUID = f"{_SYNTHETIC_UID_ROOT}.{sop_instance_suffix}"
    ds.StudyInstanceUID = f"{_SYNTHETIC_UID_ROOT}.100"
    ds.SeriesInstanceUID = f"{_SYNTHETIC_UID_ROOT}.200"
    ds.PatientName = "Synthetic^NuclearFixture"
    ds.PatientID = "SYNTHETIC-NM-001"
    ds.StudyDate = "20000101"
    ds.StudyTime = "000000"
    ds.Modality = "NM"
    ds.Manufacturer = "DICOMViewerV3"
    ds.ManufacturerModelName = "SyntheticFixtureGenerator"
    ds.DeviceSerialNumber = "SYNTHETIC-ONLY"
    ds.SeriesDescription = "Synthetic NM test fixture"
    ds.SeriesNumber = 1
    ds.InstanceNumber = sop_instance_suffix
    ds.ImageType = ["DERIVED", "PRIMARY", "STATIC", "EMISSION"]
    ds.BurnedInAnnotation = "NO"
    ds.NumberOfFrames = 1
    ds.Rows, ds.Columns = pixels.shape
    ds.SamplesPerPixel = 1
    ds.PhotometricInterpretation = "MONOCHROME2"
    ds.PixelSpacing = [1.0, 1.0]
    ds.BitsAllocated = 16
    ds.BitsStored = 16
    ds.HighBit = 15
    ds.PixelRepresentation = 0
    ds.PixelData = pixels.tobytes()

    file_meta = FileMetaDataset()
    file_meta.MediaStorageSOPClassUID = ds.SOPClassUID
    file_meta.MediaStorageSOPInstanceUID = ds.SOPInstanceUID
    file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
    file_meta.ImplementationClassUID = PYDICOM_IMPLEMENTATION_UID
    ds.file_meta = file_meta
    ds.is_implicit_VR = False
    ds.is_little_endian = True
    return ds


def planar_uniformity_pixels() -> np.ndarray:
    """Return a full field with a small deterministic intensity gradient."""
    size = 256
    yy, xx = np.indices((size, size))
    # A sub-1% gradient avoids a degenerate all-equal profile while remaining
    # comfortably within the intended uniformity range.
    return (10000 + ((xx + yy) % 17) * 4).astype(np.uint16)


def four_bar_resolution_pixels() -> np.ndarray:
    """Return perpendicular Gaussian peak pairs 100 pixels (100 mm) apart."""
    # FourBar samples a 200-pixel central profile for the default 100 mm
    # separation. A 256-pixel image leaves room for it while keeping the
    # committed fixture small.
    size = 256
    yy, xx = np.indices((size, size), dtype=float)
    center = (size - 1) / 2
    offset = 50.0
    sigma = 4.0
    horizontal = np.exp(-((xx - (center - offset)) ** 2) / (2 * sigma**2))
    horizontal += np.exp(-((xx - (center + offset)) ** 2) / (2 * sigma**2))
    vertical = np.exp(-((yy - (center - offset)) ** 2) / (2 * sigma**2))
    vertical += np.exp(-((yy - (center + offset)) ** 2) / (2 * sigma**2))
    return np.rint(100 + 20000 * (horizontal + vertical)).astype(np.uint16)


def generate(out_dir: Path) -> list[Path]:
    """Write both fixtures and return their paths."""
    out_dir.mkdir(parents=True, exist_ok=True)
    fixtures = (
        ("synthetic_nm_planar_uniformity.dcm", 1, planar_uniformity_pixels()),
        ("synthetic_nm_four_bar_resolution.dcm", 2, four_bar_resolution_pixels()),
    )
    paths = []
    for name, suffix, pixels in fixtures:
        path = out_dir / name
        dcmwrite(path, _base_dataset(sop_instance_suffix=suffix, pixels=pixels), write_like_original=False)
        paths.append(path)
    return paths


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, default=_OUT_DIR)
    args = parser.parse_args()
    for path in generate(args.out_dir):
        print_redacted(f"Wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
