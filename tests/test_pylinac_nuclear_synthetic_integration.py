"""Non-optional real-pylinac coverage using wholly synthetic NM DICOM files.

The fixtures cover stable planar input contracts only. The separately gated
IAEA suite remains the acceptance-oriented integration check for all nuclear
analyses.
"""

from __future__ import annotations

from pathlib import Path

import pydicom
import pytest

from qa.analysis_types import (
    FourBarResolutionOptions,
    PlanarUniformityOptions,
    QARequest,
)
from qa.pylinac_nuclear import (
    run_four_bar_resolution_analysis,
    run_planar_uniformity_analysis,
)

_FIXTURE_DIR = Path(__file__).parent / "fixtures" / "dicom_nuclear"
_PLANAR = _FIXTURE_DIR / "synthetic_nm_planar_uniformity.dcm"
_FOURBAR = _FIXTURE_DIR / "synthetic_nm_four_bar_resolution.dcm"


@pytest.mark.parametrize("path", (_PLANAR, _FOURBAR))
def test_synthetic_nm_fixtures_are_static_nonidentifying_images(path: Path) -> None:
    """Guard the synthetic fixture privacy and baseline DICOM contract."""
    dataset = pydicom.dcmread(path)

    assert dataset.Modality == "NM"
    assert dataset.NumberOfFrames == 1
    assert dataset.BurnedInAnnotation == "NO"
    assert str(dataset.PatientName) == "Synthetic^NuclearFixture"
    assert dataset.PatientID == "SYNTHETIC-NM-001"
    assert not getattr(dataset, "AccessionNumber", "")
    assert not getattr(dataset, "InstitutionName", "")
    assert not getattr(dataset, "StationName", "")
    assert not any(element.tag.is_private for element in dataset.iterall())
    assert dataset.pixel_array.dtype.name == "uint16"


def test_synthetic_planar_uniformity_runs_through_real_pylinac() -> None:
    """A synthetic full field yields one finite, low-uniformity result frame."""
    request = QARequest(
        analysis_type="nuclear_planar_uniformity",
        dicom_paths=[str(_PLANAR)],
        modality="NM",
        nuclear_options=PlanarUniformityOptions(),
    )

    result = run_planar_uniformity_analysis(request)

    assert result.success is True, result.errors
    assert result.metrics["frame_count"] == 1
    frame = result.metrics["frames"]["Frame 1"]
    assert set(frame) == {
        "ufov_integral_uniformity",
        "ufov_differential_uniformity",
        "cfov_integral_uniformity",
        "cfov_differential_uniformity",
    }
    assert all(isinstance(value, float) and 0 <= value < 1 for value in frame.values())


def test_synthetic_four_bar_runs_through_real_pylinac() -> None:
    """Known 100 mm peak spacing yields a measured 1 mm pixel size on both axes."""
    request = QARequest(
        analysis_type="nuclear_four_bar_resolution",
        dicom_paths=[str(_FOURBAR)],
        modality="NM",
        nuclear_options=FourBarResolutionOptions(),
    )

    result = run_four_bar_resolution_analysis(request)

    assert result.success is True, result.errors
    values = result.metrics["results"]
    assert values["x_measured_pixel_size"] == pytest.approx(1.0, abs=0.01)
    assert values["y_measured_pixel_size"] == pytest.approx(1.0, abs=0.01)
    assert values["x_fwhm"] == pytest.approx(values["y_fwhm"], abs=0.01)
    assert values["x_fwtm"] == pytest.approx(values["y_fwtm"], abs=0.01)
