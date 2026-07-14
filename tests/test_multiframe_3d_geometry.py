"""
Tests for multiframe 3D geometry synthesis and per-frame IPP/IOP extraction.

Covers:
- FrameDatasetWrapper extracting per-frame IPP from PerFrameFunctionalGroupsSequence
- FrameDatasetWrapper extracting shared IOP from SharedFunctionalGroupsSequence
- synthesize_frame_geometry adding IPP/IOP to datasets that lack them
- classify_multiframe_for_3d returning appropriate warnings
"""

import os
import sys

import numpy as np
import pytest

# Ensure src is on the path.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from pydicom.dataset import Dataset
from pydicom.sequence import Sequence

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_multiframe_dataset(
    num_frames: int = 5,
    per_frame_ipp: bool = True,
    shared_iop: bool = True,
    top_level_ipp: bool = False,
    top_level_iop: bool = False,
    add_temporal_tag: bool = False,
    slice_thickness: float | None = None,
):
    """Build a synthetic multiframe Dataset with optional functional groups."""
    ds = Dataset()
    ds.NumberOfFrames = num_frames
    ds.Rows = 64
    ds.Columns = 64
    ds.BitsAllocated = 16
    ds.BitsStored = 16
    ds.HighBit = 15
    ds.PixelRepresentation = 0
    ds.SamplesPerPixel = 1

    if top_level_ipp:
        ds.ImagePositionPatient = [0.0, 0.0, 0.0]
    if top_level_iop:
        ds.ImageOrientationPatient = [1.0, 0.0, 0.0, 0.0, 1.0, 0.0]
    if add_temporal_tag:
        ds.FrameTime = 33.3
    if slice_thickness is not None:
        ds.SliceThickness = slice_thickness

    # Build PerFrameFunctionalGroupsSequence
    per_frame_items = []
    for i in range(num_frames):
        fg = Dataset()
        if per_frame_ipp:
            plane_pos_item = Dataset()
            plane_pos_item.ImagePositionPatient = [0.0, 0.0, float(i) * 2.5]
            fg.PlanePositionSequence = Sequence([plane_pos_item])
        per_frame_items.append(fg)
    ds.PerFrameFunctionalGroupsSequence = Sequence(per_frame_items)

    # Build SharedFunctionalGroupsSequence
    if shared_iop:
        shared_fg = Dataset()
        plane_orient_item = Dataset()
        plane_orient_item.ImageOrientationPatient = [1.0, 0.0, 0.0, 0.0, 1.0, 0.0]
        shared_fg.PlaneOrientationSequence = Sequence([plane_orient_item])
        ds.SharedFunctionalGroupsSequence = Sequence([shared_fg])

    return ds


# ---------------------------------------------------------------------------
# FrameDatasetWrapper — per-frame IPP extraction
# ---------------------------------------------------------------------------

class TestFrameDatasetWrapperGeometry:
    """Test that FrameDatasetWrapper extracts per-frame IPP/IOP."""

    def test_extracts_per_frame_ipp(self):
        """Wrapper should have the per-frame IPP for each frame index."""
        from core.multiframe_handler import FrameDatasetWrapper

        ds = _make_multiframe_dataset(num_frames=5, per_frame_ipp=True, shared_iop=True)

        for i in range(5):
            wrapper = FrameDatasetWrapper(ds, i)
            ipp = wrapper.ImagePositionPatient
            assert ipp is not None, f"Frame {i} should have IPP"
            assert float(ipp[2]) == pytest.approx(float(i) * 2.5), (
                f"Frame {i} IPP Z should be {i * 2.5}, got {ipp[2]}"
            )

    def test_extracts_shared_iop(self):
        """Wrapper should pick up shared IOP when per-frame IOP is absent."""
        from core.multiframe_handler import FrameDatasetWrapper

        ds = _make_multiframe_dataset(num_frames=3, per_frame_ipp=True, shared_iop=True)
        wrapper = FrameDatasetWrapper(ds, 0)
        iop = wrapper.ImageOrientationPatient
        assert iop is not None, "Should have IOP from shared functional groups"
        assert len(iop) == 6

    def test_no_geometry_when_missing(self):
        """Wrapper should not fabricate IPP/IOP if not in functional groups."""
        from core.multiframe_handler import FrameDatasetWrapper

        ds = _make_multiframe_dataset(
            num_frames=3, per_frame_ipp=False, shared_iop=False,
            top_level_ipp=False, top_level_iop=False,
        )
        wrapper = FrameDatasetWrapper(ds, 0)
        # IPP and IOP should be None (not set on wrapper, not on original)
        assert wrapper.get('ImagePositionPatient') is None
        assert wrapper.get('ImageOrientationPatient') is None

    def test_top_level_ipp_overridden_by_per_frame(self):
        """Per-frame IPP should take precedence over top-level IPP."""
        from core.multiframe_handler import FrameDatasetWrapper

        ds = _make_multiframe_dataset(
            num_frames=3, per_frame_ipp=True, shared_iop=True,
            top_level_ipp=True,
        )
        wrapper = FrameDatasetWrapper(ds, 2)
        ipp = wrapper.ImagePositionPatient
        # Per-frame IPP for frame 2 = [0, 0, 5.0], not top-level [0, 0, 0]
        assert float(ipp[2]) == pytest.approx(5.0)

    @staticmethod
    def test_delegates_metadata_without_copying_pixel_data():
        """The wrapper is a metadata view with only frame-specific local tags."""
        from core.dicom_parser import DICOMParser
        from core.multiframe_handler import FrameDatasetWrapper

        ds = _make_multiframe_dataset(num_frames=2)
        ds.PatientName = "Viewer^Test"
        ds.PatientID = "12345"
        ds.PixelData = b"pixel-data-is-not-metadata"

        wrapper = FrameDatasetWrapper(ds, 1)

        assert wrapper.PatientName == "Viewer^Test"
        assert wrapper.get("PatientID") == "12345"
        assert wrapper["PatientName"].value == "Viewer^Test"
        assert "PatientName" in wrapper
        assert "PixelData" not in wrapper
        assert len(wrapper) >= len(ds) - 1
        assert all(element.tag != (0x7FE0, 0x0010) for element in wrapper)
        assert wrapper.NumberOfFrames == 1
        assert any(row["value"] == "Viewer^Test" for row in DICOMParser(wrapper).get_all_tags().values())

    @staticmethod
    def test_preserves_functional_group_display_values_and_frame_pixels():
        """Frame-derived display metadata and pixels remain frame-specific."""
        from core.multiframe_handler import FrameDatasetWrapper

        ds = _make_multiframe_dataset(num_frames=2, per_frame_ipp=True, shared_iop=True)
        shared = ds.SharedFunctionalGroupsSequence[0]
        measures = Dataset()
        measures.PixelSpacing = [0.7, 0.8]
        measures.SliceThickness = 1.5
        shared.PixelMeasuresSequence = Sequence([measures])
        transform = Dataset()
        transform.RescaleSlope = 2
        transform.RescaleIntercept = -1024
        transform.RescaleType = "HU"
        shared.PixelValueTransformationSequence = Sequence([transform])
        voi = Dataset()
        voi.WindowCenter = 40
        voi.WindowWidth = 400
        shared.FrameVOILUTSequence = Sequence([voi])
        ds._cached_pixel_array = np.array([[[1, 2]], [[3, 4]]], dtype=np.uint16)

        wrapper = FrameDatasetWrapper(ds, 1)

        assert list(wrapper.ImagePositionPatient) == [0.0, 0.0, 2.5]
        assert list(wrapper.ImageOrientationPatient) == [1.0, 0.0, 0.0, 0.0, 1.0, 0.0]
        assert list(wrapper.PixelSpacing) == [0.7, 0.8]
        assert float(wrapper.SliceThickness) == pytest.approx(1.5)
        assert float(wrapper.RescaleSlope) == pytest.approx(2.0)
        assert float(wrapper.RescaleIntercept) == pytest.approx(-1024.0)
        assert wrapper.RescaleType == "HU"
        assert float(wrapper.WindowCenter) == pytest.approx(40.0)
        assert float(wrapper.WindowWidth) == pytest.approx(400.0)
        assert np.array_equal(wrapper.pixel_array, np.array([[3, 4]], dtype=np.uint16))


# ---------------------------------------------------------------------------
# synthesize_frame_geometry
# ---------------------------------------------------------------------------

class TestSynthesizeFrameGeometry:
    """Test that synthesize_frame_geometry fills in missing IPP/IOP."""

    def _make_bare_datasets(self, count: int, slice_thickness: float | None = None):
        """Create simple datasets with no IPP/IOP."""
        datasets = []
        for i in range(count):
            ds = Dataset()
            ds.Rows = 64
            ds.Columns = 64
            if slice_thickness is not None:
                ds.SliceThickness = slice_thickness
            # Mark as multiframe wrapper for eligibility detection
            ds._original_dataset = Dataset()
            ds._frame_index = i
            datasets.append(ds)
        return datasets

    def test_adds_ipp_and_iop(self):
        """Should add axial IOP and sequential IPP to bare datasets."""
        from core.volume_render_eligibility import synthesize_frame_geometry

        datasets = self._make_bare_datasets(5)
        result = synthesize_frame_geometry(datasets)
        assert result is datasets  # modified in place

        for i, ds in enumerate(datasets):
            iop = ds.ImageOrientationPatient
            ipp = ds.ImagePositionPatient
            assert iop is not None
            assert ipp is not None
            assert list(iop) == [1.0, 0.0, 0.0, 0.0, 1.0, 0.0]
            assert float(ipp[0]) == 0.0
            assert float(ipp[1]) == 0.0
            # Default spacing = 1.0mm
            assert float(ipp[2]) == pytest.approx(float(i) * 1.0)

    def test_uses_slice_thickness(self):
        """Should use SliceThickness for spacing when available."""
        from core.volume_render_eligibility import synthesize_frame_geometry

        datasets = self._make_bare_datasets(4, slice_thickness=3.0)
        synthesize_frame_geometry(datasets)

        for i, ds in enumerate(datasets):
            assert float(ds.ImagePositionPatient[2]) == pytest.approx(float(i) * 3.0)

    def test_preserves_existing_geometry(self):
        """Should not modify datasets that already have valid geometry."""
        from core.volume_render_eligibility import synthesize_frame_geometry

        datasets = self._make_bare_datasets(4)
        for i, ds in enumerate(datasets):
            ds.ImagePositionPatient = [10.0, 20.0, float(i) * 5.0]
            ds.ImageOrientationPatient = [1.0, 0.0, 0.0, 0.0, 1.0, 0.0]

        synthesize_frame_geometry(datasets)

        # Should be unchanged
        for i, ds in enumerate(datasets):
            assert float(ds.ImagePositionPatient[0]) == pytest.approx(10.0)
            assert float(ds.ImagePositionPatient[2]) == pytest.approx(float(i) * 5.0)

    def test_empty_datasets(self):
        """Should handle empty list gracefully."""
        from core.volume_render_eligibility import synthesize_frame_geometry

        result = synthesize_frame_geometry([])
        assert result == []


# ---------------------------------------------------------------------------
# classify_multiframe_for_3d
# ---------------------------------------------------------------------------

class TestClassifyMultiframeFor3D:
    """Test classify_multiframe_for_3d returns appropriate warnings."""

    def test_non_multiframe_returns_false(self):
        """Non-multiframe datasets should return (False, '')."""
        from core.volume_render_eligibility import classify_multiframe_for_3d

        ds = Dataset()
        ds.Rows = 64
        assert classify_multiframe_for_3d([ds]) == (False, "")

    def test_spatial_multiframe_no_warning(self):
        """Spatial multiframe should return (True, '') — no warning."""
        from core.multiframe_handler import FrameDatasetWrapper
        from core.volume_render_eligibility import classify_multiframe_for_3d

        original = _make_multiframe_dataset(
            num_frames=5, per_frame_ipp=True, shared_iop=True,
        )
        # Add top-level IPP so classify_frame_type sees SPATIAL
        original.ImagePositionPatient = [0.0, 0.0, 0.0]
        wrapper = FrameDatasetWrapper(original, 0)

        is_mf, warning = classify_multiframe_for_3d([wrapper])
        assert is_mf is True
        assert warning == ""

    def test_temporal_multiframe_returns_warning(self):
        """Temporal multiframe should return (True, warning_string)."""
        from core.multiframe_handler import FrameDatasetWrapper
        from core.volume_render_eligibility import classify_multiframe_for_3d

        original = _make_multiframe_dataset(
            num_frames=5, per_frame_ipp=False, shared_iop=False,
            add_temporal_tag=True,
        )
        wrapper = FrameDatasetWrapper(original, 0)

        is_mf, warning = classify_multiframe_for_3d([wrapper])
        assert is_mf is True
        assert "temporal" in warning.lower()
        assert "not be anatomically meaningful" in warning
