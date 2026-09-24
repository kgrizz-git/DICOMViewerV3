"""MprResult carries the source series' photometric interpretation, including across the cache.

The cache round-trip is the load-bearing test: if the field is not persisted, a cache hit renders
with the wrong polarity while a cold build renders correctly, so the bug only appears once the
cache is warm.
"""

from __future__ import annotations

import json
import pathlib
import tempfile

import numpy as np
import pytest
from pydicom.dataset import Dataset, FileMetaDataset
from pydicom.uid import ExplicitVRLittleEndian, generate_uid

from core.mpr_builder import MprBuilder, MprResult
from core.mpr_cache import MprCache, make_result_key
from core.mpr_volume import MprVolume

# Built locally rather than imported from tests/test_mpr_core.py: reaching that module needs a
# sys.path insertion, which changes module resolution for the whole xdist worker and breaks an
# unrelated frozen-path test.


def _axial_volume(photometric_interpretation: str, n_slices: int = 3) -> list[Dataset]:
    """Minimal pixel-bearing axial series with the requested photometric interpretation."""
    study_uid, series_uid = generate_uid(), generate_uid()
    datasets: list[Dataset] = []
    for i in range(n_slices):
        arr = np.full((4, 5), i * 100, dtype=np.uint16)
        ds = Dataset()
        ds.file_meta = FileMetaDataset()
        ds.file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
        ds.SOPClassUID = generate_uid()
        ds.SOPInstanceUID = generate_uid()
        ds.StudyInstanceUID = study_uid
        ds.SeriesInstanceUID = series_uid
        ds.Modality = "CT"
        ds.Rows, ds.Columns = 4, 5
        ds.SamplesPerPixel = 1
        ds.PhotometricInterpretation = photometric_interpretation
        ds.PixelRepresentation = 0
        ds.BitsAllocated = ds.BitsStored = 16
        ds.HighBit = 15
        ds.ImagePositionPatient = [0.0, 0.0, float(i)]
        ds.ImageOrientationPatient = [1, 0, 0, 0, 1, 0]
        ds.PixelSpacing = [1.0, 1.0]
        ds.SliceThickness = 1.0
        ds.InstanceNumber = i + 1
        ds.RescaleSlope, ds.RescaleIntercept = 1.0, -1024.0
        ds.PixelData = arr.tobytes()
        datasets.append(ds)
    return datasets


def _worker(photometric_interpretation: str):
    volume = MprVolume.from_datasets(_axial_volume(photometric_interpretation))
    return MprBuilder.create_worker(
        source_volume=volume,
        output_plane=MprBuilder.standard_planes()["sagittal"],
        output_spacing_mm=1.0,
        output_thickness_mm=1.0,
        interpolation="nearest",
    )


def _build(photometric_interpretation: str) -> MprResult:
    return _worker(photometric_interpretation)._build()


def test_default_is_empty_string():
    """Existing construction sites that omit the field keep working."""
    assert MprResult.__dataclass_fields__["photometric_interpretation"].default == ""


@pytest.mark.parametrize(
    ("stored", "expected"),
    [("MONOCHROME1", "MONOCHROME1"), ("MONOCHROME2", "MONOCHROME2"), ("monochrome1", "MONOCHROME1")],
)
def test_builder_reads_photometric_interpretation_from_source(stored, expected):
    assert _build(stored).photometric_interpretation == expected


def test_builder_returns_empty_string_without_source_datasets():
    """The only reachable "" case: pydicom cannot decode pixels without the tag at all, so a
    volume always has one. The empty-list guard mirrors _get_rescale_params."""
    worker = _worker("MONOCHROME1")
    worker._volume.source_datasets = []
    assert worker._get_photometric_interpretation() == ""


def test_slices_are_not_inverted_by_the_field():
    """Invariant 4: the field is display metadata; the resampled arrays stay stored-value."""
    mono1 = _build("MONOCHROME1")
    mono2 = _build("MONOCHROME2")
    assert mono1.photometric_interpretation != mono2.photometric_interpretation
    for a, b in zip(mono1.slices, mono2.slices, strict=True):
        np.testing.assert_allclose(a, b)


def test_photometric_interpretation_survives_the_disk_cache():
    """A cache hit must not render at a different polarity than a cold build."""
    result = _build("MONOCHROME1")
    with tempfile.TemporaryDirectory() as tmpdir:
        cache = MprCache(cache_dir=tmpdir, max_size_mb=50)
        assert cache.save(result)
        loaded = cache.load(make_result_key(result))
        assert loaded is not None
        _, _, meta = loaded
        assert meta.get("photometric_interpretation") == "MONOCHROME1"


def test_legacy_cache_entry_on_disk_reads_back_as_empty():
    """An entry written before this change has no such key; loading it must not fail, and the
    reconstruction must fall back to "", which is the pre-change (MONOCHROME2) behaviour."""
    result = _build("MONOCHROME1")
    with tempfile.TemporaryDirectory() as tmpdir:
        cache = MprCache(cache_dir=tmpdir, max_size_mb=50)
        assert cache.save(result)
        key = make_result_key(result)

        # Rewrite the on-disk meta as a pre-change entry.
        meta_path = pathlib.Path(tmpdir) / (key + "_meta.json")
        stored = json.loads(meta_path.read_text(encoding="utf-8"))
        del stored["photometric_interpretation"]
        meta_path.write_text(json.dumps(stored), encoding="utf-8")

        loaded = cache.load(key)
        assert loaded is not None
        slices, stack, meta = loaded
        assert "photometric_interpretation" not in meta

        # Same reconstruction the controller performs on a cache hit.
        rebuilt = MprResult(
            slices=slices,
            slice_stack=stack,
            output_spacing_mm=tuple(meta["output_spacing_mm"]),
            output_thickness_mm=float(meta["output_thickness_mm"]),
            source_volume=result.source_volume,
            interpolation=meta["interpolation"],
            rescale_slope=meta.get("rescale_slope"),
            rescale_intercept=meta.get("rescale_intercept"),
            photometric_interpretation=meta.get("photometric_interpretation", ""),
        )
        assert rebuilt.photometric_interpretation == ""
