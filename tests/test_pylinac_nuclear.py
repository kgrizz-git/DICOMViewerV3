"""
Unit tests for the pylinac.nuclear runner (PlanarUniformity first slice).

No DICOM fixtures: the missing-pylinac branch is forced by blocking the import,
and the success/failure branches use a fake pylinac.nuclear module injected into
sys.modules so tests stay deterministic and fast.

Covers (plan T11):
    - missing pylinac -> user-readable failure with nuclear provenance
    - mocked success -> per-frame metrics + raw payload + nuclear profile
    - non-NM modality -> preflight warning, still runs
    - multiple input files -> warning, uses first
    - no input file -> failure
    - analyze() raising -> user-readable error
    - unknown nuclear analysis_type via run_nuclear_analysis
"""

from __future__ import annotations

import builtins
import sys
import types

from qa.analysis_types import (
    CenterOfRotationOptions,
    FourBarResolutionOptions,
    MaxCountRateOptions,
    PlanarUniformityOptions,
    QARequest,
    QAResult,
    QuadrantResolutionOptions,
    SimpleSensitivityOptions,
    TomographicContrastOptions,
    TomographicResolutionOptions,
    TomographicUniformityOptions,
)
from qa.pylinac_nuclear import (
    _nonfinite_metric_paths,
    _warn_on_nonfinite_metrics,
    run_center_of_rotation_analysis,
    run_four_bar_resolution_analysis,
    run_max_count_rate_analysis,
    run_nuclear_analysis,
    run_planar_uniformity_analysis,
    run_quadrant_resolution_analysis,
    run_simple_sensitivity_analysis,
    run_tomographic_contrast_analysis,
    run_tomographic_uniformity_analysis,
)

_real_import = builtins.__import__

_PLANAR_TYPE = "nuclear_planar_uniformity"

_FAKE_FRAMES = {
    "Frame 1": {
        "ufov_integral_uniformity": 3.1,
        "ufov_differential_uniformity": 2.0,
        "cfov_integral_uniformity": 2.5,
        "cfov_differential_uniformity": 1.8,
    },
    "Frame 2": {
        "ufov_integral_uniformity": 3.4,
        "ufov_differential_uniformity": 2.2,
        "cfov_integral_uniformity": 2.7,
        "cfov_differential_uniformity": 1.9,
    },
}


class _FakePlanarUniformity:
    """Stand-in for pylinac.nuclear.PlanarUniformity."""

    last_instance: _FakePlanarUniformity | None = None

    def __init__(self, path):
        self.path = path
        self.analyze_kwargs: dict | None = None
        _FakePlanarUniformity.last_instance = self

    def analyze(self, **kwargs):
        self.analyze_kwargs = kwargs

    def results_data(self, as_dict=False):
        return dict(_FAKE_FRAMES)


class _RaisingPlanarUniformity(_FakePlanarUniformity):
    def analyze(self, **kwargs):
        raise ValueError("phantom not found in image")


def _install_fake_pylinac(monkeypatch, cls=_FakePlanarUniformity, version="3.43.2"):
    """Inject fake ``pylinac`` and ``pylinac.nuclear`` modules."""
    fake_pylinac = types.ModuleType("pylinac")
    fake_pylinac.__version__ = version
    fake_nuclear = types.ModuleType("pylinac.nuclear")
    fake_nuclear.PlanarUniformity = cls
    fake_pylinac.nuclear = fake_nuclear
    monkeypatch.setitem(sys.modules, "pylinac", fake_pylinac)
    monkeypatch.setitem(sys.modules, "pylinac.nuclear", fake_nuclear)


def _planar_request(**overrides) -> QARequest:
    kwargs = {
        "analysis_type": _PLANAR_TYPE,
        "dicom_paths": ["planar.dcm"],
        "modality": "NM",
        "study_uid": "1.2.3",
        "series_uid": "4.5.6",
        "nuclear_options": PlanarUniformityOptions(),
    }
    kwargs.update(overrides)
    return QARequest(**kwargs)


def _block_pylinac(name, *args, **kwargs):
    if name.split(".", 1)[0] == "pylinac":
        raise ImportError("blocked for unit test")
    return _real_import(name, *args, **kwargs)


def test_missing_pylinac_returns_readable_failure() -> None:
    req = _planar_request()
    builtins.__import__ = _block_pylinac
    try:
        result = run_planar_uniformity_analysis(req)
    finally:
        builtins.__import__ = _real_import
    assert result.success is False
    assert any("pylinac is not installed" in e for e in result.errors)
    assert result.pylinac_analysis_profile["module"] == "pylinac.nuclear"
    assert result.pylinac_analysis_profile["engine"] == "(pylinac not installed)"


def test_mocked_success_normalizes_per_frame(monkeypatch) -> None:
    _install_fake_pylinac(monkeypatch)
    result = run_planar_uniformity_analysis(_planar_request())
    assert result.success is True
    assert result.num_images == 1
    assert result.pylinac_version == "3.43.2"
    assert result.metrics["frame_count"] == 2
    assert result.metrics["frames"] == _FAKE_FRAMES
    assert result.raw_pylinac == _FAKE_FRAMES
    # analyze() received the default PlanarUniformity kwargs
    assert _FakePlanarUniformity.last_instance.analyze_kwargs == {
        "ufov_ratio": 0.95,
        "cfov_ratio": 0.75,
        "window_size": 5,
        "threshold": 0.75,
    }
    profile = result.pylinac_analysis_profile
    assert profile["nuclear_analysis_class"] == "PlanarUniformity"
    assert profile["vanilla_equivalent"] is True
    assert profile["input_path"] == "planar.dcm"


def test_non_default_params_flagged_not_vanilla(monkeypatch) -> None:
    _install_fake_pylinac(monkeypatch)
    opts = PlanarUniformityOptions(threshold=0.6)
    result = run_planar_uniformity_analysis(_planar_request(nuclear_options=opts))
    assert result.success is True
    assert result.pylinac_analysis_profile["vanilla_equivalent"] is False
    assert _FakePlanarUniformity.last_instance.analyze_kwargs["threshold"] == 0.6


def test_non_nm_modality_warns_but_runs(monkeypatch) -> None:
    _install_fake_pylinac(monkeypatch)
    result = run_planar_uniformity_analysis(_planar_request(modality="CT"))
    assert result.success is True
    assert any("targets NM" in w for w in result.warnings)


def test_multiple_files_warns_and_uses_first(monkeypatch) -> None:
    _install_fake_pylinac(monkeypatch)
    req = _planar_request(dicom_paths=["a.dcm", "b.dcm"])
    result = run_planar_uniformity_analysis(req)
    assert result.success is True
    assert _FakePlanarUniformity.last_instance.path == "a.dcm"
    assert any("uses only the first" in w for w in result.warnings)


def test_no_input_file_fails(monkeypatch) -> None:
    _install_fake_pylinac(monkeypatch)
    result = run_planar_uniformity_analysis(_planar_request(dicom_paths=[]))
    assert result.success is False
    assert any("No DICOM file" in e for e in result.errors)


def test_analyze_exception_is_user_readable(monkeypatch) -> None:
    _install_fake_pylinac(monkeypatch, cls=_RaisingPlanarUniformity)
    result = run_planar_uniformity_analysis(_planar_request())
    assert result.success is False
    assert any("PlanarUniformity analysis failed" in e for e in result.errors)
    assert any("phantom not found" in e for e in result.errors)


def test_unknown_nuclear_type_dispatch_fails() -> None:
    req = QARequest(analysis_type="nuclear_bogus", dicom_paths=["x.dcm"])
    result = run_nuclear_analysis(req)
    assert result.success is False
    assert any("Unsupported nuclear analysis type" in e for e in result.errors)
    assert result.pylinac_analysis_profile["module"] == "pylinac.nuclear"


# ---------------------------------------------------------------------------
# FourBarResolution (flat single result)
# ---------------------------------------------------------------------------

_FOURBAR_TYPE = "nuclear_four_bar_resolution"

_FAKE_FOURBAR = {
    "x_fwhm": 7.66,
    "y_fwhm": 7.60,
    "x_fwtm": 13.96,
    "y_fwtm": 13.85,
    "x_measured_pixel_size": 1.043,
    "y_measured_pixel_size": 1.040,
    "x_pixel_size_difference": 1.049,
    "y_pixel_size_difference": 0.714,
}


class _FakeFourBar:
    last_instance: _FakeFourBar | None = None

    def __init__(self, path):
        self.path = path
        self.analyze_kwargs: dict | None = None
        _FakeFourBar.last_instance = self

    def analyze(self, **kwargs):
        self.analyze_kwargs = kwargs

    def results_data(self, as_dict=False):
        return dict(_FAKE_FOURBAR)


def _install_fake_fourbar(monkeypatch, cls=_FakeFourBar, version="3.43.2"):
    fake_pylinac = types.ModuleType("pylinac")
    fake_pylinac.__version__ = version
    fake_nuclear = types.ModuleType("pylinac.nuclear")
    fake_nuclear.FourBarResolution = cls
    fake_pylinac.nuclear = fake_nuclear
    monkeypatch.setitem(sys.modules, "pylinac", fake_pylinac)
    monkeypatch.setitem(sys.modules, "pylinac.nuclear", fake_nuclear)


def _fourbar_request(**overrides) -> QARequest:
    kwargs = {
        "analysis_type": _FOURBAR_TYPE,
        "dicom_paths": ["fourbar.dcm"],
        "modality": "NM",
        "nuclear_options": FourBarResolutionOptions(),
    }
    kwargs.update(overrides)
    return QARequest(**kwargs)


def test_fourbar_missing_pylinac_fails() -> None:
    builtins.__import__ = _block_pylinac
    try:
        result = run_four_bar_resolution_analysis(_fourbar_request())
    finally:
        builtins.__import__ = _real_import
    assert result.success is False
    assert any("pylinac is not installed" in e for e in result.errors)
    assert result.pylinac_analysis_profile["nuclear_analysis_class"] == "FourBarResolution"


def test_fourbar_mocked_success_flat_result(monkeypatch) -> None:
    _install_fake_fourbar(monkeypatch)
    result = run_four_bar_resolution_analysis(_fourbar_request())
    assert result.success is True
    assert result.num_images == 1
    assert result.metrics["analysis_class"] == "FourBarResolution"
    assert "frames" not in result.metrics  # flat, not per-frame
    assert result.metrics["results"] == _FAKE_FOURBAR
    assert result.raw_pylinac == _FAKE_FOURBAR
    assert _FakeFourBar.last_instance.analyze_kwargs == {
        "separation_mm": 100.0,
        "roi_width_mm": 10.0,
    }
    assert result.pylinac_analysis_profile["vanilla_equivalent"] is True


def test_fourbar_non_default_params_not_vanilla(monkeypatch) -> None:
    _install_fake_fourbar(monkeypatch)
    opts = FourBarResolutionOptions(separation_mm=50.0)
    result = run_four_bar_resolution_analysis(_fourbar_request(nuclear_options=opts))
    assert result.success is True
    assert result.pylinac_analysis_profile["vanilla_equivalent"] is False
    assert _FakeFourBar.last_instance.analyze_kwargs["separation_mm"] == 50.0


def test_fourbar_routes_through_dispatcher(monkeypatch) -> None:
    _install_fake_fourbar(monkeypatch)
    result = run_nuclear_analysis(_fourbar_request())
    assert result.success is True
    assert result.metrics["analysis_class"] == "FourBarResolution"


def test_fourbar_no_input_fails(monkeypatch) -> None:
    _install_fake_fourbar(monkeypatch)
    result = run_four_bar_resolution_analysis(_fourbar_request(dicom_paths=[]))
    assert result.success is False
    assert any("No DICOM file" in e for e in result.errors)


# ---------------------------------------------------------------------------
# QuadrantResolution (per-quadrant nested result)
# ---------------------------------------------------------------------------

_QUADRANT_TYPE = "nuclear_quadrant_resolution"

_FAKE_QUADRANTS = {
    "1": {"mtf": 0.65, "fwhm": 2.96, "lpmm": 0.118, "spacing": 4.23},
    "2": {"mtf": 0.47, "fwhm": 2.93, "lpmm": 0.157, "spacing": 3.18},
    "3": {"mtf": 0.30, "fwhm": 2.93, "lpmm": 0.197, "spacing": 2.54},
    "4": {"mtf": 0.20, "fwhm": 2.84, "lpmm": 0.236, "spacing": 2.12},
}


class _FakeQuadrant:
    last_instance: _FakeQuadrant | None = None

    def __init__(self, path):
        self.path = path
        self.analyze_kwargs: dict | None = None
        _FakeQuadrant.last_instance = self

    def analyze(self, **kwargs):
        self.analyze_kwargs = kwargs

    def results_data(self, as_dict=False):
        return {"quadrants": dict(_FAKE_QUADRANTS)}


def _install_fake_quadrant(monkeypatch, cls=_FakeQuadrant, version="3.43.2"):
    fake_pylinac = types.ModuleType("pylinac")
    fake_pylinac.__version__ = version
    fake_nuclear = types.ModuleType("pylinac.nuclear")
    fake_nuclear.QuadrantResolution = cls
    fake_pylinac.nuclear = fake_nuclear
    monkeypatch.setitem(sys.modules, "pylinac", fake_pylinac)
    monkeypatch.setitem(sys.modules, "pylinac.nuclear", fake_nuclear)


def _quadrant_request(**overrides) -> QARequest:
    kwargs = {
        "analysis_type": _QUADRANT_TYPE,
        "dicom_paths": ["quad.dcm"],
        "modality": "NM",
        "nuclear_options": QuadrantResolutionOptions(),
    }
    kwargs.update(overrides)
    return QARequest(**kwargs)


def test_quadrant_mocked_success_nested_result(monkeypatch) -> None:
    _install_fake_quadrant(monkeypatch)
    result = run_quadrant_resolution_analysis(_quadrant_request())
    assert result.success is True
    assert result.metrics["analysis_class"] == "QuadrantResolution"
    assert result.metrics["quadrants"] == _FAKE_QUADRANTS
    assert "frames" not in result.metrics and "results" not in result.metrics
    # bar_widths default (phantom-specific) passed as a 4-element list.
    assert _FakeQuadrant.last_instance.analyze_kwargs["bar_widths"] == [
        4.23,
        3.18,
        2.54,
        2.12,
    ]
    assert _FakeQuadrant.last_instance.analyze_kwargs["roi_diameter_mm"] == 70.0
    # ROI geometry at defaults -> vanilla_equivalent (bar_widths excluded).
    assert result.pylinac_analysis_profile["vanilla_equivalent"] is True


def test_quadrant_non_default_geometry_not_vanilla(monkeypatch) -> None:
    _install_fake_quadrant(monkeypatch)
    opts = QuadrantResolutionOptions(roi_diameter_mm=60.0)
    result = run_quadrant_resolution_analysis(_quadrant_request(nuclear_options=opts))
    assert result.success is True
    assert result.pylinac_analysis_profile["vanilla_equivalent"] is False


def test_quadrant_routes_through_dispatcher(monkeypatch) -> None:
    _install_fake_quadrant(monkeypatch)
    result = run_nuclear_analysis(_quadrant_request())
    assert result.success is True
    assert result.metrics["analysis_class"] == "QuadrantResolution"


# ---------------------------------------------------------------------------
# Tier 1 SPECT/dynamic tests (flat results via _run_flat_nuclear_analysis)
# ---------------------------------------------------------------------------


def _make_flat_fake(class_name, payload):
    captured = {}

    class _Fake:
        def __init__(self, path):
            captured["path"] = path

        def analyze(self, **kwargs):
            captured["kwargs"] = kwargs

        def results_data(self, as_dict=False):
            return dict(payload)

    def install(monkeypatch):
        fake_pylinac = types.ModuleType("pylinac")
        fake_pylinac.__version__ = "3.43.2"
        fake_nuclear = types.ModuleType("pylinac.nuclear")
        setattr(fake_nuclear, class_name, _Fake)
        fake_pylinac.nuclear = fake_nuclear
        monkeypatch.setitem(sys.modules, "pylinac", fake_pylinac)
        monkeypatch.setitem(sys.modules, "pylinac.nuclear", fake_nuclear)

    return install, captured


def test_center_of_rotation_flat_success(monkeypatch) -> None:
    install, captured = _make_flat_fake(
        "CenterOfRotation", {"x_deviation_mm": 0.14, "y_deviation_mm": 0.13}
    )
    install(monkeypatch)
    req = QARequest(
        analysis_type="nuclear_center_of_rotation",
        dicom_paths=["cor.dcm"],
        modality="NM",
        nuclear_options=CenterOfRotationOptions(),
    )
    result = run_center_of_rotation_analysis(req)
    assert result.success is True
    assert result.metrics["analysis_class"] == "CenterOfRotation"
    assert result.metrics["results"] == {"x_deviation_mm": 0.14, "y_deviation_mm": 0.13}
    assert captured["kwargs"] == {}  # no analyze params


def test_tomographic_resolution_routes_through_dispatcher(monkeypatch) -> None:
    install, _ = _make_flat_fake(
        "TomographicResolution",
        {"x_fwhm": 22.3, "y_fwhm": 22.3, "z_fwhm": 22.5,
         "x_fwtm": 40.7, "y_fwtm": 40.7, "z_fwtm": 41.0},
    )
    install(monkeypatch)
    req = QARequest(
        analysis_type="nuclear_tomographic_resolution",
        dicom_paths=["tomo.dcm"],
        modality="NM",
        nuclear_options=TomographicResolutionOptions(),
    )
    result = run_nuclear_analysis(req)
    assert result.success is True
    assert set(result.metrics["results"]) == {
        "x_fwhm", "y_fwhm", "z_fwhm", "x_fwtm", "y_fwtm", "z_fwtm"
    }


def test_max_count_rate_strips_sums_from_results(monkeypatch) -> None:
    payload = {
        "max_countrate": 358437.0,
        "max_frame": 15,
        "frame_duration": 1.0,
        "sums": {"0": 159846.0, "1": 161895.0},
    }
    install, captured = _make_flat_fake("MaxCountRate", payload)
    install(monkeypatch)
    req = QARequest(
        analysis_type="nuclear_max_count_rate",
        dicom_paths=["mcr.dcm"],
        modality="NM",
        nuclear_options=MaxCountRateOptions(frame_duration=2.5),
    )
    result = run_max_count_rate_analysis(req)
    assert result.success is True
    # sums dropped from the headline metrics...
    assert "sums" not in result.metrics["results"]
    assert set(result.metrics["results"]) == {"max_countrate", "max_frame", "frame_duration"}
    # ...but kept in the raw payload.
    assert "sums" in result.raw_pylinac
    assert captured["kwargs"] == {"frame_duration": 2.5}
    assert result.pylinac_analysis_profile["vanilla_equivalent"] is False  # 2.5 != 1.0


def test_tier1_missing_pylinac_fails() -> None:
    req = QARequest(
        analysis_type="nuclear_center_of_rotation",
        dicom_paths=["cor.dcm"],
        modality="NM",
        nuclear_options=CenterOfRotationOptions(),
    )
    builtins.__import__ = _block_pylinac
    try:
        result = run_center_of_rotation_analysis(req)
    finally:
        builtins.__import__ = _real_import
    assert result.success is False
    assert any("pylinac is not installed" in e for e in result.errors)


# ---------------------------------------------------------------------------
# Tier 2 SPECT tests (TomographicUniformity flat; TomographicContrast spheres)
# ---------------------------------------------------------------------------


def test_tomographic_uniformity_flat_success(monkeypatch) -> None:
    install, captured = _make_flat_fake(
        "TomographicUniformity",
        {"cfov_integral_uniformity": 13.2, "ufov_integral_uniformity": 15.5,
         "center_border_ratio": 0.99, "first_frame": 1, "last_frame": 45},
    )
    install(monkeypatch)
    req = QARequest(
        analysis_type="nuclear_tomographic_uniformity",
        dicom_paths=["jasz.dcm"],
        modality="NM",
        nuclear_options=TomographicUniformityOptions(),
    )
    result = run_tomographic_uniformity_analysis(req)
    assert result.success is True
    assert result.metrics["analysis_class"] == "TomographicUniformity"
    assert "center_border_ratio" in result.metrics["results"]
    # all 7 analyze kwargs forwarded
    assert set(captured["kwargs"]) == {
        "first_frame", "last_frame", "ufov_ratio", "cfov_ratio",
        "center_ratio", "threshold", "window_size",
    }


_FAKE_SPHERES = {
    "1": {"x": 78.5, "y": 58.5, "z": 13.0, "radius": 4.6, "mean": 633.9,
          "mean_contrast": 35.8, "max_contrast": 72.3},
    "2": {"x": 69.7, "y": 47.4, "z": 14.0, "radius": 3.9, "mean": 828.8,
          "mean_contrast": 23.6, "max_contrast": 52.9},
}


class _FakeContrast:
    last_instance = None

    def __init__(self, path):
        self.path = path
        self.analyze_kwargs = None
        _FakeContrast.last_instance = self

    def analyze(self, **kwargs):
        self.analyze_kwargs = kwargs

    def results_data(self, as_dict=False):
        return {"uniformity_baseline": 1341.28, "spheres": dict(_FAKE_SPHERES)}


def _install_fake_contrast(monkeypatch):
    fake_pylinac = types.ModuleType("pylinac")
    fake_pylinac.__version__ = "3.43.2"
    fake_nuclear = types.ModuleType("pylinac.nuclear")
    fake_nuclear.TomographicContrast = _FakeContrast
    fake_pylinac.nuclear = fake_nuclear
    monkeypatch.setitem(sys.modules, "pylinac", fake_pylinac)
    monkeypatch.setitem(sys.modules, "pylinac.nuclear", fake_nuclear)


def test_tomographic_contrast_nested_spheres(monkeypatch) -> None:
    _install_fake_contrast(monkeypatch)
    req = QARequest(
        analysis_type="nuclear_tomographic_contrast",
        dicom_paths=["jasz.dcm"],
        modality="NM",
        nuclear_options=TomographicContrastOptions(),
    )
    result = run_tomographic_contrast_analysis(req)
    assert result.success is True
    assert result.metrics["analysis_class"] == "TomographicContrast"
    assert result.metrics["spheres"] == _FAKE_SPHERES
    assert result.metrics["uniformity_baseline"] == 1341.28
    assert "frames" not in result.metrics and "results" not in result.metrics
    assert result.raw_pylinac["uniformity_baseline"] == 1341.28
    # sphere geometry forwarded as lists
    assert len(result.pylinac_analysis_profile["analysis_parameters"]["sphere_diameters_mm"]) == 6


def test_tomographic_contrast_routes_through_dispatcher(monkeypatch) -> None:
    _install_fake_contrast(monkeypatch)
    req = QARequest(
        analysis_type="nuclear_tomographic_contrast",
        dicom_paths=["jasz.dcm"],
        modality="NM",
        nuclear_options=TomographicContrastOptions(),
    )
    result = run_nuclear_analysis(req)
    assert result.success is True
    assert result.metrics["analysis_class"] == "TomographicContrast"


# ---------------------------------------------------------------------------
# Tier 3: SimpleSensitivity (two-file + Nuclide enum + required activity)
# ---------------------------------------------------------------------------

_FAKE_SENSITIVITY = {
    "phantom_cps": 2446.9,
    "background_cps": 17.6,
    "sensitivity_mbq": 244.1,
    "sensitivity_uci": 541.9,
}


class _FakeNuclide:
    """Stand-in for pylinac.nuclear.Nuclide with the real member names."""

    Tc99m = "Tc99m"
    Ga67 = "Ga67"


class _FakeSensitivity:
    last_instance = None

    def __init__(self, phantom_path, background_path=None):
        self.phantom_path = phantom_path
        self.background_path = background_path
        self.analyze_kwargs = None
        _FakeSensitivity.last_instance = self

    def analyze(self, **kwargs):
        self.analyze_kwargs = kwargs

    def results_data(self, as_dict=False):
        return dict(_FAKE_SENSITIVITY)


def _install_fake_sensitivity(monkeypatch):
    fake_pylinac = types.ModuleType("pylinac")
    fake_pylinac.__version__ = "3.43.2"
    fake_nuclear = types.ModuleType("pylinac.nuclear")
    fake_nuclear.SimpleSensitivity = _FakeSensitivity
    fake_nuclear.Nuclide = _FakeNuclide
    fake_pylinac.nuclear = fake_nuclear
    monkeypatch.setitem(sys.modules, "pylinac", fake_pylinac)
    monkeypatch.setitem(sys.modules, "pylinac.nuclear", fake_nuclear)


def _sensitivity_request(**overrides) -> QARequest:
    opts = overrides.pop("nuclear_options", None) or SimpleSensitivityOptions(
        activity_mbq=10.0, nuclide="Tc99m"
    )
    kwargs = {
        "analysis_type": "nuclear_simple_sensitivity",
        "dicom_paths": ["phantom.dcm"],
        "modality": "NM",
        "nuclear_options": opts,
    }
    kwargs.update(overrides)
    return QARequest(**kwargs)


def test_sensitivity_success_with_background(monkeypatch) -> None:
    _install_fake_sensitivity(monkeypatch)
    opts = SimpleSensitivityOptions(
        activity_mbq=10.0, nuclide="Tc99m", background_path="bg.dcm"
    )
    result = run_simple_sensitivity_analysis(_sensitivity_request(nuclear_options=opts))
    assert result.success is True
    assert result.metrics["analysis_class"] == "SimpleSensitivity"
    assert result.metrics["results"]["sensitivity_mbq"] == 244.1
    assert result.num_images == 2
    inst = _FakeSensitivity.last_instance
    assert inst.background_path == "bg.dcm"  # constructor arg
    assert inst.analyze_kwargs == {"activity_mbq": 10.0, "nuclide": "Tc99m"}  # enum mapped


def test_sensitivity_no_background_single_image(monkeypatch) -> None:
    _install_fake_sensitivity(monkeypatch)
    result = run_simple_sensitivity_analysis(_sensitivity_request())
    assert result.success is True
    assert result.num_images == 1
    assert _FakeSensitivity.last_instance.background_path is None


def test_sensitivity_zero_activity_fails(monkeypatch) -> None:
    _install_fake_sensitivity(monkeypatch)
    opts = SimpleSensitivityOptions(activity_mbq=0.0, nuclide="Tc99m")
    result = run_simple_sensitivity_analysis(_sensitivity_request(nuclear_options=opts))
    assert result.success is False
    assert any("activity" in e.lower() for e in result.errors)


def test_sensitivity_unknown_nuclide_fails(monkeypatch) -> None:
    _install_fake_sensitivity(monkeypatch)
    opts = SimpleSensitivityOptions(activity_mbq=10.0, nuclide="Xx999")
    result = run_simple_sensitivity_analysis(_sensitivity_request(nuclear_options=opts))
    assert result.success is False
    assert any("nuclide" in e.lower() for e in result.errors)


def test_sensitivity_routes_through_dispatcher(monkeypatch) -> None:
    _install_fake_sensitivity(monkeypatch)
    result = run_nuclear_analysis(_sensitivity_request())
    assert result.success is True
    assert result.metrics["analysis_class"] == "SimpleSensitivity"


def test_nonfinite_metric_paths_finds_nan_and_inf() -> None:
    metrics = {
        "ok": 1.0,
        "spheres": {"s1": {"contrast": float("nan")}, "s2": {"contrast": 0.5}},
        "frames": [0.1, float("inf"), 0.3],
        "flag": True,  # must not be treated as a float
    }
    paths = _nonfinite_metric_paths(metrics)
    assert "spheres.s1.contrast" in paths
    assert "frames[1]" in paths
    assert all("s2" not in p and "flag" not in p for p in paths)
    assert len(paths) == 2


def test_warn_on_nonfinite_metrics_appends_warning() -> None:
    res = QAResult(
        success=True,
        analysis_type="nuclear_tomographic_contrast",
        metrics={"uniformity": float("nan"), "value": 2.0},
    )
    _warn_on_nonfinite_metrics(res)
    assert len(res.warnings) == 1
    assert "Non-finite" in res.warnings[0]
    assert "uniformity" in res.warnings[0]


def test_warn_on_nonfinite_metrics_silent_when_all_finite() -> None:
    res = QAResult(
        success=True,
        analysis_type="nuclear_tomographic_contrast",
        metrics={"uniformity": 0.9, "value": 2.0},
    )
    _warn_on_nonfinite_metrics(res)
    assert res.warnings == []


def test_warn_on_nonfinite_metrics_skips_failed_result() -> None:
    res = QAResult(
        success=False,
        analysis_type="nuclear_tomographic_contrast",
        metrics={"uniformity": float("nan")},
    )
    _warn_on_nonfinite_metrics(res)
    assert res.warnings == []
