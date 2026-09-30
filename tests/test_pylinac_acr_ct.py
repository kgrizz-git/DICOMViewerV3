"""
Unit tests for the ACR CT pylinac runner.

These tests avoid real pylinac and DICOM fixtures by injecting lightweight
fake modules into ``sys.modules``. The goal is to exercise normalization,
diagnostics, and failure handling branches.
"""

from __future__ import annotations

import builtins
import sys
import types
import warnings

import pytest

from qa.analysis_types import QARequest
from qa.pylinac_acr_ct import (
    _acr_ct_stack_diagnostic_lines,
    _image_count,
    _jsonable,
    run_acr_ct_analysis,
)

_real_import = builtins.__import__


class _LenRaises:
    def __len__(self):
        raise RuntimeError("bad len")


class _FakeMeta:
    def __init__(self, z: float) -> None:
        self.z = z


class _FakeStack(list):
    def __init__(self, items, *, spacing: float | None = None, metas=None) -> None:
        super().__init__(items)
        self.slice_spacing = spacing
        self.metadatas = metas or []


class _FakeAnalyzer:
    last_instance: _FakeAnalyzer | None = None

    def __init__(self, input_value, *, check_uid=True) -> None:
        self.input_value = input_value
        self.check_uid = check_uid
        self._scan_extent_tolerance_mm = None
        self.dicom_stack = _FakeStack([1, 2, 3], spacing=2.5)
        self.analyze_kwargs: dict[str, object] | None = None
        self.publish_pdf_calls: list[str] = []
        _FakeAnalyzer.last_instance = self

    def analyze(self, **kwargs) -> None:
        self.analyze_kwargs = kwargs

    def results_data(self, as_dict=False):
        return {
            "num_images": 3,
            "phantom_roll": 0.25,
            "catphan_model": "ACR",
            "origin_slice": 9,
            "nested": {"a": [1, object()]},
        }

    def publish_pdf(self, path: str) -> None:
        self.publish_pdf_calls.append(path)


class _FakeAnalyzerObjectResults(_FakeAnalyzer):
    def results_data(self, as_dict=False):
        return types.SimpleNamespace(kind="object")

    def publish_pdf(self, path: str) -> None:
        raise OSError("pdf disabled")


class _FakeAnalyzerWithMtf(_FakeAnalyzer):
    def __init__(self, input_value, *, check_uid=True) -> None:
        super().__init__(input_value, check_uid=check_uid)
        self.spatial_resolution_module = types.SimpleNamespace(
            mtf=types.SimpleNamespace(relative_resolution=lambda percent: 0.42 if percent == 50 else 0.0)
        )


class _FakeAnalyzerWithMtfAndCnr(_FakeAnalyzerWithMtf):
    def __init__(self, input_value, *, check_uid=True) -> None:
        super().__init__(input_value, check_uid=check_uid)
        self.low_contrast_module = types.SimpleNamespace(
            cnr=lambda: 3.0,
            rois={"ROI": types.SimpleNamespace(
                mean=13.0, pixel_value=13.0, contrast_to_noise=3.0
            )},
            background_rois={"ROI": types.SimpleNamespace(
                mean=10.0, pixel_value=10.0, std=1.0
            )},
        )

    def results_data(self, as_dict=False):
        return {"low_contrast_module": {"cnr": 4.0}}


class _FakeAnalyzerWithExtrapolatedMtf(_FakeAnalyzerWithMtf):
    def __init__(self, input_value, *, check_uid=True) -> None:
        super().__init__(input_value, check_uid=check_uid)

        def resolution(_percent):
            warnings.warn(
                "MTF resolution wasn't calculated for 50% that was asked for. "
                "The value returned is an extrapolation.",
                UserWarning,
                stacklevel=2,
            )
            return 0.52

        self.spatial_resolution_module.mtf.relative_resolution = resolution
        self.spatial_resolution_module.mtf.spacings = [0.1, 0.4]


class _FakeAnalyzerWithMatchingCnr(_FakeAnalyzerWithMtfAndCnr):
    def results_data(self, as_dict=False):
        return {"low_contrast_module": {"cnr": 3.0}}


class _FakeAnalyzerAnalyzeRaises(_FakeAnalyzer):
    def __init__(self, input_value, *, check_uid=True) -> None:
        super().__init__(input_value, check_uid=check_uid)
        self.dicom_stack = _FakeStack(
            [1, 2, 3],
            spacing=1.5,
            metas=[_FakeMeta(10.0), _FakeMeta(15.0), _FakeMeta(20.0)],
        )

    def analyze(self, **kwargs) -> None:
        raise ValueError("origin slice beyond the image extent")


def _request(**overrides) -> QARequest:
    kwargs = {
        "analysis_type": "acr_ct",
        "dicom_paths": ["ct1.dcm", "ct2.dcm"],
        "study_uid": "1.2.3",
        "series_uid": "4.5.6",
        "modality": "CT",
        "check_uid": False,
    }
    kwargs.update(overrides)
    return QARequest(**kwargs)


def _install_fake_pylinac(monkeypatch, analyzer_cls=_FakeAnalyzer, version="3.43.2") -> None:
    fake_pylinac = types.ModuleType("pylinac")
    fake_pylinac.__version__ = version
    fake_pylinac.ACRCT = analyzer_cls
    fake_pylinac.ACRMRILarge = analyzer_cls

    fake_core = types.ModuleType("pylinac.core")
    fake_image = types.ModuleType("pylinac.core.image")
    fake_image.z_position = lambda meta: meta.z

    monkeypatch.setitem(sys.modules, "pylinac", fake_pylinac)
    monkeypatch.setitem(sys.modules, "pylinac.core", fake_core)
    monkeypatch.setitem(sys.modules, "pylinac.core.image", fake_image)

    fake_extent = types.ModuleType("qa.pylinac_extent_subclasses")
    fake_extent.ACRCTForViewer = analyzer_cls
    monkeypatch.setitem(sys.modules, "qa.pylinac_extent_subclasses", fake_extent)


def _block_pylinac(name, *args, **kwargs):
    if name.split(".", 1)[0] == "pylinac":
        raise ImportError("blocked for unit test")
    return _real_import(name, *args, **kwargs)


def test_jsonable_and_image_count_helpers() -> None:
    converted = _jsonable({"x": [1, object()], "y": (True, None)})
    assert converted["x"][0] == 1
    assert isinstance(converted["x"][1], str)
    assert converted["y"] == [True, None]

    req = _request(dicom_paths=["a", "b", "c"])
    assert _image_count(types.SimpleNamespace(dicom_stack=[1, 2]), req) == 2
    assert _image_count(types.SimpleNamespace(dicom_stack=_LenRaises()), req) == 3
    assert _image_count(types.SimpleNamespace(), req) == 3


def test_stack_diagnostics_include_context(monkeypatch) -> None:
    _install_fake_pylinac(monkeypatch)
    analyzer = types.SimpleNamespace(
        dicom_stack=_FakeStack(
            [1, 2, 3],
            spacing=2.0,
            metas=[_FakeMeta(1.0), _FakeMeta(4.5), _FakeMeta(7.0)],
        )
    )

    lines = _acr_ct_stack_diagnostic_lines(analyzer)

    assert any("Images in stack (pylinac): 3" in line for line in lines)
    assert any("slice_spacing" in line for line in lines)
    assert any("ImagePositionPatient Z" in line for line in lines)
    assert any("Typical causes" in line for line in lines)


def test_missing_pylinac_returns_readable_failure() -> None:
    builtins.__import__ = _block_pylinac
    try:
        result = run_acr_ct_analysis(_request())
    finally:
        builtins.__import__ = _real_import

    assert result.success is False
    assert any("pylinac is not installed" in error for error in result.errors)
    assert result.num_images == 2
    assert result.pylinac_analysis_profile["engine"] == "(pylinac not installed)"


def test_no_inputs_returns_failure(monkeypatch) -> None:
    _install_fake_pylinac(monkeypatch)

    result = run_acr_ct_analysis(_request(dicom_paths=[], folder_path=None))

    assert result.success is False
    assert result.errors == ["No DICOM paths or folder were provided."]
    assert result.pylinac_version == "3.43.2"


def test_success_with_folder_path_and_vanilla_warning(monkeypatch) -> None:
    _install_fake_pylinac(monkeypatch, analyzer_cls=_FakeAnalyzerObjectResults)

    result = run_acr_ct_analysis(
        _request(
            dicom_paths=[],
            folder_path="/tmp/acr-ct",
            output_pdf_path="/tmp/out.pdf",
            origin_slice=7,
            scan_extent_tolerance_mm=2.0,
            vanilla_pylinac=True,
        )
    )

    analyzer = _FakeAnalyzerObjectResults.last_instance
    assert analyzer is not None
    assert analyzer.input_value == "/tmp/acr-ct"
    assert analyzer.analyze_kwargs == {"origin_slice": 7}
    assert result.success is True
    assert result.num_images == 3
    assert result.pdf_report_path is None
    assert result.raw_pylinac == {"results_data": "namespace(kind='object')"}
    assert result.metrics["input_count"] == 0
    assert result.metrics["origin_slice_override"] == 7
    assert result.metrics["scan_extent_tolerance_mm"] == 0.0
    assert result.metrics["scan_extent_tolerance_requested_mm"] == 2.0
    assert result.metrics["vanilla_pylinac"] is True
    assert any("ignored in stock pylinac mode" in w for w in result.warnings)
    assert result.pylinac_analysis_profile["engine"] == "ACRCT"


def test_success_with_viewer_class_serializes_results_and_publishes_pdf(monkeypatch) -> None:
    _install_fake_pylinac(monkeypatch)

    result = run_acr_ct_analysis(
        _request(
            output_pdf_path="/tmp/report.pdf",
            origin_slice=9,
            scan_extent_tolerance_mm=1.5,
        )
    )

    analyzer = _FakeAnalyzer.last_instance
    assert analyzer is not None
    assert analyzer.input_value == ["ct1.dcm", "ct2.dcm"]
    assert analyzer.check_uid is False
    assert analyzer._scan_extent_tolerance_mm == 1.5
    assert analyzer.analyze_kwargs == {"origin_slice": 9}
    assert analyzer.publish_pdf_calls == ["/tmp/report.pdf"]
    assert result.success is True
    assert result.pdf_report_path == "/tmp/report.pdf"
    assert result.metrics["num_images"] == 3
    assert result.metrics["phantom_roll"] == 0.25
    assert result.metrics["catphan_model"] == "ACR"
    assert result.metrics["origin_slice"] == 9
    assert result.raw_pylinac["nested"]["a"][0] == 1
    assert isinstance(result.raw_pylinac["nested"]["a"][1], str)
    assert result.pylinac_analysis_profile["engine"] == "ACRCTForViewer"
    assert result.pylinac_analysis_profile["relaxed_image_extent"] is True


def test_ct_harvests_live_mtf_without_rewriting_raw_results(monkeypatch) -> None:
    _install_fake_pylinac(monkeypatch, analyzer_cls=_FakeAnalyzerWithMtf)

    result = run_acr_ct_analysis(_request())

    assert result.success is True
    assert result.metrics["acr_ct_mtf50_lpmm"] == 0.42
    assert "acr_ct_mtf50_lpmm" not in result.raw_pylinac
    assert not any("MTF@50%" in warning for warning in result.warnings)


def test_ct_missing_mtf_warns_without_failing(monkeypatch) -> None:
    _install_fake_pylinac(monkeypatch)

    result = run_acr_ct_analysis(_request())

    assert result.success is True
    assert "acr_ct_mtf50_lpmm" not in result.metrics
    assert any("MTF@50%" in warning for warning in result.warnings)


def test_ct_mtf_extrapolation_is_recorded_in_run_warnings(monkeypatch) -> None:
    _install_fake_pylinac(monkeypatch, analyzer_cls=_FakeAnalyzerWithExtrapolatedMtf)

    with pytest.warns(UserWarning, match="MTF resolution wasn't calculated"):
        result = run_acr_ct_analysis(_request())

    assert result.success is True
    assert result.metrics["acr_ct_mtf50_lpmm"] == 0.52
    assert "CT MTF@50% was extrapolated by pylinac." in result.warnings


def test_ct_runner_warns_when_roi_based_and_structured_cnr_disagree(monkeypatch) -> None:
    _install_fake_pylinac(monkeypatch, analyzer_cls=_FakeAnalyzerWithMtfAndCnr)

    result = run_acr_ct_analysis(_request())

    assert result.success is True
    assert result.metrics["low_contrast_cnr"]["cnr"] == 3.0
    assert result.metrics["low_contrast_cnr"]["mean_based_cnr"] == 3.0
    assert any("CNR differs" in warning for warning in result.warnings)


def test_ct_runner_accepts_matching_roi_based_cnr(monkeypatch) -> None:
    _install_fake_pylinac(monkeypatch, analyzer_cls=_FakeAnalyzerWithMatchingCnr)

    result = run_acr_ct_analysis(_request())

    assert result.success is True
    assert not any("CNR differs" in warning for warning in result.warnings)


def test_analysis_failure_appends_extent_diagnostics(monkeypatch) -> None:
    _install_fake_pylinac(monkeypatch, analyzer_cls=_FakeAnalyzerAnalyzeRaises)

    result = run_acr_ct_analysis(_request())

    assert result.success is False
    assert result.num_images == 3
    error = result.errors[0]
    assert "ACR CT analysis failed: origin slice beyond the image extent" in error
    assert "Images in stack (pylinac): 3" in error
    assert "ImagePositionPatient Z" in error
