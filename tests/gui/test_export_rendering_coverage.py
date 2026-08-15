"""Additional bounded coverage for the synthetic export-rendering boundary."""

from __future__ import annotations

import warnings
from types import SimpleNamespace

import numpy as np
import pytest
from PIL import Image
from pydicom.dataset import Dataset, FileMetaDataset

from gui import export_rendering as rendering


def _dataset(photometric: str = "MONOCHROME2") -> Dataset:
    dataset = Dataset()
    dataset.StudyInstanceUID = "1.2.3"
    dataset.SeriesInstanceUID = "1.2.3.4"
    dataset.PhotometricInterpretation = photometric
    dataset.Rows = 2
    dataset.Columns = 2
    dataset.BitsStored = 8
    dataset.BitsAllocated = 8
    dataset.PixelRepresentation = 0
    dataset.PixelData = np.array([[1, 2], [3, 4]], dtype=np.uint8).tobytes()
    return dataset


def _series(dataset: Dataset, count: int = 2) -> dict[str, dict[str, list[Dataset]]]:
    return {"1.2.3": {"1.2.3.4": [dataset] * count}}


def test_effective_scale_handles_invalid_dimensions_and_native_requests() -> None:
    assert rendering.effective_scale_for_image(0, 100, 4.0) == 1.0
    assert rendering.effective_scale_for_image(100, -1, 4.0) == 1.0
    assert rendering.effective_scale_for_image(100, 100, 0.5) == 1.0


def test_export_sizes_have_safe_minimums_and_font_cap() -> None:
    assert rendering.export_line_thickness_pixels(50, 0, 100) == 1
    assert rendering.export_text_size_pixels(50, 0, 100) == 8
    assert rendering.export_text_size_pixels(10_000, 4096, 4096, 4.0) == 72


@pytest.mark.parametrize(
    ("photometric", "expected"),
    [("PALETTE COLOR", "RGB"), ("unknown", "RGB")],
)
def test_process_image_normalizes_palette_and_unknown_modes(
    photometric: str, expected: str
) -> None:
    image = Image.new("RGBA", (2, 2), (1, 2, 3, 4))
    dataset = _dataset()
    if photometric == "unknown":
        # Exercise the defensive fallback without making synthetic fixture data
        # itself trigger pydicom's VR validation warning.
        object.__setattr__(dataset, "PhotometricInterpretation", photometric)
    else:
        dataset.PhotometricInterpretation = photometric
    result = rendering.process_image_by_photometric_interpretation(
        image, dataset
    )
    assert result.mode == expected


def test_process_image_rgb_uses_processor_channel_order_fix(monkeypatch) -> None:
    source = np.array([[[1, 2, 3]]], dtype=np.uint8)
    seen: dict[str, object] = {}

    def fix(array, **kwargs):
        seen.update(kwargs)
        return array[:, :, ::-1]

    monkeypatch.setattr(rendering.DICOMProcessor, "detect_and_fix_rgb_channel_order", fix)
    dataset = _dataset("RGB")
    dataset.file_meta = FileMetaDataset()
    dataset.file_meta.TransferSyntaxUID = "1.2.840.10008.1.2.1"
    result = rendering.process_image_by_photometric_interpretation(
        Image.fromarray(source, mode="RGB"), dataset
    )
    assert result.getpixel((0, 0)) == (3, 2, 1)
    assert seen == {
        "photometric_interpretation": "RGB",
        "transfer_syntax": "1.2.840.10008.1.2.1",
        "dataset": dataset,
    }


def test_process_image_ybr_uses_processor_conversion(monkeypatch) -> None:
    source = np.array([[[10, 20, 30]]], dtype=np.uint8)
    monkeypatch.setattr(
        rendering.DICOMProcessor,
        "convert_ybr_to_rgb",
        lambda array, **_kwargs: np.full_like(array, 99),
    )
    result = rendering.process_image_by_photometric_interpretation(
        Image.fromarray(source, mode="RGB"), _dataset("YBR_FULL")
    )
    assert result.getpixel((0, 0)) == (99, 99, 99)


def test_process_image_returns_original_after_processor_failure(monkeypatch) -> None:
    image = Image.new("RGB", (1, 1), (10, 20, 30))
    monkeypatch.setattr(
        rendering.DICOMProcessor,
        "detect_and_fix_rgb_channel_order",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("synthetic")),
    )
    result = rendering.process_image_by_photometric_interpretation(image, _dataset("RGB"))
    assert result is image


@pytest.mark.parametrize("projection_type", ["aip", "mip", "minip"])
def test_create_projection_normalizes_synthetic_projection(
    monkeypatch, projection_type: str
) -> None:
    dataset = _dataset()
    operations = {
        "aip": lambda _slices: np.array([[0.0, 10.0], [20.0, 30.0]], dtype=np.float32),
        "mip": lambda _slices: np.array([[30.0, 20.0], [10.0, 0.0]], dtype=np.float32),
        "minip": lambda _slices: np.array([[5.0, 5.0], [5.0, 5.0]], dtype=np.float32),
    }
    monkeypatch.setattr(
        rendering.DICOMProcessor,
        {
            "aip": "average_intensity_projection",
            "mip": "maximum_intensity_projection",
            "minip": "minimum_intensity_projection",
        }[projection_type],
        operations[projection_type],
    )
    result = rendering.create_projection_for_export(
        dataset,
        _series(dataset),
        "1.2.3",
        "1.2.3.4",
        0,
        projection_type,
        2,
        None,
        None,
        False,
    )
    assert result is not None
    assert result.mode == "L"
    assert result.size == (2, 2)


def test_create_projection_applies_rescale_and_window(monkeypatch) -> None:
    dataset = _dataset()
    monkeypatch.setattr(
        rendering.DICOMProcessor,
        "average_intensity_projection",
        lambda _slices: np.array([[1.0, 2.0]], dtype=np.float32),
    )
    monkeypatch.setattr(
        rendering.DICOMProcessor,
        "get_rescale_parameters",
        lambda _dataset: (2.0, 10.0, None),
    )
    seen: dict[str, object] = {}

    def window(array, center, width):
        seen.update(array=array, center=center, width=width)
        return np.array([[7, 8]], dtype=np.uint8)

    monkeypatch.setattr(rendering.DICOMProcessor, "apply_window_level", window)
    result = rendering.create_projection_for_export(
        dataset, _series(dataset), "1.2.3", "1.2.3.4", 0, "aip", 2, 20, 40, True
    )
    assert result is not None
    assert np.array_equal(np.asarray(result), np.array([[7, 8]], dtype=np.uint8))
    assert np.array_equal(seen["array"], np.array([[12.0, 14.0]], dtype=np.float32))


@pytest.mark.parametrize(
    "kwargs",
    [
        {"study_uid": "missing", "series_uid": "1.2.3.4"},
        {"study_uid": "1.2.3", "series_uid": "1.2.3.4", "projection_type": "bad"},
    ],
)
def test_create_projection_returns_none_for_guarded_inputs(kwargs) -> None:
    dataset = _dataset()
    values = {
        "dataset": dataset,
        "studies": _series(dataset),
        "study_uid": "1.2.3",
        "series_uid": "1.2.3.4",
        "slice_index": 0,
        "projection_type": "aip",
        "projection_slice_count": 2,
        "window_center": None,
        "window_width": None,
        "use_rescaled_values": False,
    }
    values.update(kwargs)
    assert rendering.create_projection_for_export(**values) is None


def test_create_projection_dataset_updates_pixels_and_metadata(monkeypatch) -> None:
    dataset = _dataset()
    dataset.ImageComments = "original"
    dataset.SeriesDescription = "synthetic"
    dataset.SpacingBetweenSlices = 2.0
    dataset.InstanceNumber = 3
    monkeypatch.setattr(
        rendering.DICOMProcessor,
        "maximum_intensity_projection",
        lambda _slices: np.array([[0.0, 400.0], [2.0, 3.0]], dtype=np.float32),
    )
    monkeypatch.setattr(
        rendering.DICOMProcessor,
        "get_pixel_array",
        lambda _dataset: np.zeros((2, 2), dtype=np.uint8),
    )
    result = rendering.create_projection_dataset(
        dataset, _series(dataset, 3), "1.2.3", "1.2.3.4", 1, "mip", 2, False
    )
    assert result is not None
    assert result.Rows == 2 and result.Columns == 2
    assert np.array_equal(np.frombuffer(result.PixelData, dtype=np.uint8), [0, 255, 2, 3])
    assert result.ImageType == ["DERIVED", "SECONDARY", "MIP"]
    assert result.SeriesDescription == "synthetic - MIP"
    assert result.InstanceNumber == 9001
    assert not hasattr(result, "SpacingBetweenSlices")
    assert result.SOPInstanceUID != getattr(dataset, "SOPInstanceUID", None)


def test_projection_dataset_image_type_values_are_dicom_cs_valid(monkeypatch) -> None:
    dataset = _dataset()
    monkeypatch.setattr(
        rendering.DICOMProcessor,
        "maximum_intensity_projection",
        lambda _slices: np.array([[1]], dtype=np.float32),
    )
    monkeypatch.setattr(
        rendering.DICOMProcessor,
        "get_pixel_array",
        lambda _dataset: np.zeros((1, 1), dtype=np.uint8),
    )
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        result = rendering.create_projection_dataset(
            dataset, _series(dataset), "1.2.3", "1.2.3.4", 0, "mip", 2, False
        )
    assert result is not None
    assert not any("maximum length of 16" in str(warning.message) for warning in caught)


def test_create_projection_dataset_keeps_single_slice_and_guards_missing_data() -> None:
    dataset = _dataset()
    result = rendering.create_projection_dataset(
        dataset, _series(dataset, 1), "1.2.3", "1.2.3.4", 0, "aip", 4, False
    )
    assert result is not None
    assert result.PixelData == dataset.PixelData
    assert "Derived from instance 1" in result.ImageComments
    assert rendering.create_projection_dataset(
        dataset, {}, "1.2.3", "1.2.3.4", 0, "aip", 2, False
    ) is None


def test_render_overlays_composes_roi_and_measurement_without_mutating_source() -> None:
    class Bounds:
        def left(self):
            return 1

        def top(self):
            return 1

        def right(self):
            return 5

        def bottom(self):
            return 5

    class ROI:
        def __init__(self):
            self.shape_type = "rectangle"
            self.statistics = {}
            self.visible_statistics = []
            self.statistics_overlay_visible = False

        def get_bounds(self):
            return Bounds()

    class Point:
        def __init__(self, x, y):
            self._x, self._y = x, y

        def x(self):
            return self._x

        def y(self):
            return self._y

    class ROIManager:
        def get_rois_for_slice(self, *_args):
            return [ROI()]

    class MeasurementTool:
        def __init__(self):
            self.measurements = {
                ("1.2.3", "1.2.3.4", 0): [
                    SimpleNamespace(
                        start_point=Point(0, 0),
                        end_relative=Point(3, 3),
                        distance_formatted="synthetic distance",
                    )
                ]
            }

    source = Image.new("L", (8, 8), 0)
    result = rendering.render_overlays_and_rois(
        rendering.RenderOverlaysRequest(
            image=source,
            dataset=_dataset(),
            roi_manager=ROIManager(),
            overlay_manager=None,
            measurement_tool=MeasurementTool(),
            config_manager=None,
            slice_index=0,
        )
    )
    assert source.mode == "L"
    assert result.mode == "RGB"
    assert result.tobytes() != source.convert("RGB").tobytes()


def test_annotation_collection_isolates_fetch_failures_and_aggregates() -> None:
    class BrokenText:
        def get_annotations_for_slice(self, *_args):
            raise RuntimeError("synthetic")

    class GoodArrow:
        def get_arrows_for_slice(self, *_args):
            return ["arrow"]

    result = rendering._collect_annotations(
        "study",
        "series",
        0,
        None,
        None,
        None,
        None,
        [
            {"text_annotation_tool": BrokenText()},
            {"arrow_annotation_tool": GoodArrow()},
        ],
        True,
    )
    assert result.rois == []
    assert result.measurements == []
    assert result.text_items == []
    assert result.arrow_items == ["arrow"]


def test_overlay_color_and_series_helpers_use_safe_defaults() -> None:
    assert rendering._normalize_rgb("bad", (1, 2, 3)) == (1, 2, 3)
    assert rendering._overlay_text_color(None) == (255, 255, 0)
    assert rendering._overlay_text_color((0, 0, 0)) == (255, 255, 255)
    dataset = _dataset()
    assert rendering._resolve_series_keys(dataset, "fallback-study", "fallback-series") == (
        "1.2.3",
        "1.2.3.4",
    )
