"""
Optional integration smoke for the pylinac.nuclear PlanarUniformity runner.

Skips unless DICOMVIEWER_NMQC_SAMPLE_PATH points at a local copy of the IAEA
NMQC simulated images (not redistributed; see plan + local PROVENANCE note).
CI without the data simply skips — no download is performed here (plan T14).

Set, e.g.:
    $env:DICOMVIEWER_NMQC_SAMPLE_PATH = "<repo>/sample-DICOM-gitignored/nmqc/extracted/test images"
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from qa.analysis_types import (
    CenterOfRotationOptions,
    FourBarResolutionOptions,
    MaxCountRateOptions,
    PlanarUniformityOptions,
    QARequest,
    QuadrantResolutionOptions,
    SimpleSensitivityOptions,
    TomographicContrastOptions,
    TomographicResolutionOptions,
    TomographicUniformityOptions,
)
from qa.pylinac_nuclear import (
    run_center_of_rotation_analysis,
    run_four_bar_resolution_analysis,
    run_max_count_rate_analysis,
    run_planar_uniformity_analysis,
    run_quadrant_resolution_analysis,
    run_simple_sensitivity_analysis,
    run_tomographic_contrast_analysis,
    run_tomographic_resolution_analysis,
    run_tomographic_uniformity_analysis,
)

_SAMPLE_ROOT = os.environ.get("DICOMVIEWER_NMQC_SAMPLE_PATH")

pytestmark = pytest.mark.skipif(
    not _SAMPLE_ROOT or not Path(_SAMPLE_ROOT).exists(),
    reason="DICOMVIEWER_NMQC_SAMPLE_PATH not set to an existing NMQC sample folder",
)

# Relative paths within the IAEA Simulated_images set.
_SINGLE_FRAME = "Uniformity/UNIFORMIDAD_1_Ok.dcm"
_MULTI_FRAME = "Uniformity/Point_Source.dcm"
_FOURBAR = "PixelSz&Resolution/FourBar.dcm"
_QUADRANT = "PixelSz&Resolution/QuadrantBar.dcm"
_COR = "COR/COR_102.dcm"
_TOMORES = "TomoResolution.dcm"
_MAXCOUNT = "MaxCountRate.dcm"
_JASZACK = "Jaszack.dcm"
_SENS_PHANTOM = "sensitivity/PetriDish"
_SENS_BACKGROUND = "sensitivity/Background"


def _sample(rel: str) -> str:
    return str(Path(_SAMPLE_ROOT) / rel)


def _run(rel: str):
    path = _sample(rel)
    if not Path(path).exists():
        pytest.skip(f"sample file not present: {rel}")
    req = QARequest(
        analysis_type="nuclear_planar_uniformity",
        dicom_paths=[path],
        modality="NM",
        nuclear_options=PlanarUniformityOptions(),
    )
    return run_planar_uniformity_analysis(req)


def test_planar_uniformity_single_frame_real_data() -> None:
    result = _run(_SINGLE_FRAME)
    assert result.success is True, result.errors
    assert result.metrics["frame_count"] >= 1
    frame1 = result.metrics["frames"]["Frame 1"]
    assert set(frame1) == {
        "ufov_integral_uniformity",
        "ufov_differential_uniformity",
        "cfov_integral_uniformity",
        "cfov_differential_uniformity",
    }
    assert all(isinstance(v, float) for v in frame1.values())
    assert result.pylinac_version is not None


def test_planar_uniformity_multi_frame_real_data() -> None:
    result = _run(_MULTI_FRAME)
    assert result.success is True, result.errors
    assert result.metrics["frame_count"] >= 2
    # Each frame carries the four uniformity floats.
    for frame in result.metrics["frames"].values():
        assert len(frame) == 4


def test_render_single_frame_figure_real_data(tmp_path) -> None:
    from qa.pylinac_nuclear_plots import render_nuclear_figures

    path = _sample(_SINGLE_FRAME)
    if not Path(path).exists():
        pytest.skip(f"sample file not present: {_SINGLE_FRAME}")
    out = str(tmp_path / "fig.png")
    saved = render_nuclear_figures(
        path, analysis_class="PlanarUniformity", analyze_kwargs={}, out_path=out
    )
    assert len(saved) == 1
    assert Path(saved[0]).exists() and Path(saved[0]).stat().st_size > 0


def test_render_multi_frame_figures_real_data(tmp_path) -> None:
    from qa.pylinac_nuclear_plots import render_nuclear_figures

    path = _sample(_MULTI_FRAME)
    if not Path(path).exists():
        pytest.skip(f"sample file not present: {_MULTI_FRAME}")
    out = str(tmp_path / "fig.png")
    saved = render_nuclear_figures(
        path, analysis_class="PlanarUniformity", analyze_kwargs={}, out_path=out
    )
    assert len(saved) >= 2
    # Multi-frame inserts _Frame_<key> before the suffix.
    assert all("_Frame_" in p and Path(p).exists() for p in saved)


def test_four_bar_resolution_real_data() -> None:
    path = _sample(_FOURBAR)
    if not Path(path).exists():
        pytest.skip(f"sample file not present: {_FOURBAR}")
    req = QARequest(
        analysis_type="nuclear_four_bar_resolution",
        dicom_paths=[path],
        modality="NM",
        nuclear_options=FourBarResolutionOptions(),
    )
    result = run_four_bar_resolution_analysis(req)
    assert result.success is True, result.errors
    res = result.metrics["results"]
    assert set(res) == {
        "x_fwhm",
        "y_fwhm",
        "x_fwtm",
        "y_fwtm",
        "x_measured_pixel_size",
        "y_measured_pixel_size",
        "x_pixel_size_difference",
        "y_pixel_size_difference",
    }
    assert all(isinstance(v, float) for v in res.values())


def test_render_four_bar_figure_real_data(tmp_path) -> None:
    from qa.pylinac_nuclear_plots import render_nuclear_figures

    path = _sample(_FOURBAR)
    if not Path(path).exists():
        pytest.skip(f"sample file not present: {_FOURBAR}")
    out = str(tmp_path / "fourbar.png")
    saved = render_nuclear_figures(
        path, analysis_class="FourBarResolution", analyze_kwargs={}, out_path=out
    )
    # FourBar's plot() yields multiple panels (not frames); labeled by index.
    assert len(saved) >= 1
    assert all(Path(p).exists() and Path(p).stat().st_size > 0 for p in saved)
    assert all("_Frame_" not in p for p in saved)


def test_quadrant_resolution_real_data() -> None:
    path = _sample(_QUADRANT)
    if not Path(path).exists():
        pytest.skip(f"sample file not present: {_QUADRANT}")
    req = QARequest(
        analysis_type="nuclear_quadrant_resolution",
        dicom_paths=[path],
        modality="NM",
        nuclear_options=QuadrantResolutionOptions(),
    )
    result = run_quadrant_resolution_analysis(req)
    assert result.success is True, result.errors
    quadrants = result.metrics["quadrants"]
    assert set(quadrants) == {"1", "2", "3", "4"}
    for vals in quadrants.values():
        assert set(vals) >= {"mtf", "fwhm", "lpmm", "spacing"}


def test_center_of_rotation_real_data() -> None:
    path = _sample(_COR)
    if not Path(path).exists():
        pytest.skip(f"sample file not present: {_COR}")
    req = QARequest(
        analysis_type="nuclear_center_of_rotation",
        dicom_paths=[path],
        modality="NM",
        nuclear_options=CenterOfRotationOptions(),
    )
    result = run_center_of_rotation_analysis(req)
    assert result.success is True, result.errors
    assert set(result.metrics["results"]) == {"x_deviation_mm", "y_deviation_mm"}


def test_tomographic_resolution_real_data() -> None:
    path = _sample(_TOMORES)
    if not Path(path).exists():
        pytest.skip(f"sample file not present: {_TOMORES}")
    req = QARequest(
        analysis_type="nuclear_tomographic_resolution",
        dicom_paths=[path],
        modality="NM",
        nuclear_options=TomographicResolutionOptions(),
    )
    result = run_tomographic_resolution_analysis(req)
    assert result.success is True, result.errors
    assert set(result.metrics["results"]) == {
        "x_fwhm", "y_fwhm", "z_fwhm", "x_fwtm", "y_fwtm", "z_fwtm"
    }


def test_max_count_rate_real_data() -> None:
    path = _sample(_MAXCOUNT)
    if not Path(path).exists():
        pytest.skip(f"sample file not present: {_MAXCOUNT}")
    req = QARequest(
        analysis_type="nuclear_max_count_rate",
        dicom_paths=[path],
        modality="NM",
        nuclear_options=MaxCountRateOptions(),
    )
    result = run_max_count_rate_analysis(req)
    assert result.success is True, result.errors
    assert "sums" not in result.metrics["results"]
    assert "sums" in result.raw_pylinac
    assert "max_countrate" in result.metrics["results"]


def test_tomographic_uniformity_real_data() -> None:
    path = _sample(_JASZACK)
    if not Path(path).exists():
        pytest.skip(f"sample file not present: {_JASZACK}")
    req = QARequest(
        analysis_type="nuclear_tomographic_uniformity",
        dicom_paths=[path],
        modality="NM",
        nuclear_options=TomographicUniformityOptions(),
    )
    result = run_tomographic_uniformity_analysis(req)
    assert result.success is True, result.errors
    assert "cfov_integral_uniformity" in result.metrics["results"]
    assert "center_border_ratio" in result.metrics["results"]


def test_tomographic_contrast_real_data() -> None:
    path = _sample(_JASZACK)
    if not Path(path).exists():
        pytest.skip(f"sample file not present: {_JASZACK}")
    req = QARequest(
        analysis_type="nuclear_tomographic_contrast",
        dicom_paths=[path],
        modality="NM",
        nuclear_options=TomographicContrastOptions(),
    )
    result = run_tomographic_contrast_analysis(req)
    assert result.success is True, result.errors
    assert set(result.metrics["spheres"]) == {"1", "2", "3", "4", "5", "6"}
    assert result.metrics["uniformity_baseline"] is not None
    for vals in result.metrics["spheres"].values():
        assert set(vals) >= {"mean_contrast", "max_contrast", "radius"}


def test_simple_sensitivity_with_background_real_data() -> None:
    phantom = _sample(_SENS_PHANTOM)
    background = _sample(_SENS_BACKGROUND)
    if not Path(phantom).exists() or not Path(background).exists():
        pytest.skip("sensitivity sample files not present")
    req = QARequest(
        analysis_type="nuclear_simple_sensitivity",
        dicom_paths=[phantom],
        modality="NM",
        nuclear_options=SimpleSensitivityOptions(
            activity_mbq=10.0, nuclide="Tc99m", background_path=background
        ),
    )
    result = run_simple_sensitivity_analysis(req)
    assert result.success is True, result.errors
    assert result.num_images == 2
    res = result.metrics["results"]
    assert "sensitivity_mbq" in res and "sensitivity_uci" in res
    assert res["background_cps"] > 0  # background supplied


def test_simple_sensitivity_no_background_real_data() -> None:
    phantom = _sample(_SENS_PHANTOM)
    if not Path(phantom).exists():
        pytest.skip(f"sample file not present: {_SENS_PHANTOM}")
    req = QARequest(
        analysis_type="nuclear_simple_sensitivity",
        dicom_paths=[phantom],
        modality="NM",
        nuclear_options=SimpleSensitivityOptions(activity_mbq=10.0, nuclide="Tc99m"),
    )
    result = run_simple_sensitivity_analysis(req)
    assert result.success is True, result.errors
    assert result.num_images == 1
    assert result.metrics["results"]["background_cps"] == 0.0


def test_render_tomographic_contrast_figure_real_data(tmp_path) -> None:
    from qa.pylinac_nuclear_plots import render_nuclear_figures

    path = _sample(_JASZACK)
    if not Path(path).exists():
        pytest.skip(f"sample file not present: {_JASZACK}")
    out = str(tmp_path / "tc.png")
    saved = render_nuclear_figures(
        path, analysis_class="TomographicContrast", analyze_kwargs={}, out_path=out
    )
    assert len(saved) >= 1
    assert all(Path(p).exists() and Path(p).stat().st_size > 0 for p in saved)


def test_render_quadrant_figure_real_data(tmp_path) -> None:
    from qa.pylinac_nuclear_plots import render_nuclear_figures

    path = _sample(_QUADRANT)
    if not Path(path).exists():
        pytest.skip(f"sample file not present: {_QUADRANT}")
    out = str(tmp_path / "quad.png")
    saved = render_nuclear_figures(
        path,
        analysis_class="QuadrantResolution",
        analyze_kwargs={"bar_widths": [4.23, 3.18, 2.54, 2.12]},
        out_path=out,
    )
    assert len(saved) >= 1
    assert all(Path(p).exists() and Path(p).stat().st_size > 0 for p in saved)
