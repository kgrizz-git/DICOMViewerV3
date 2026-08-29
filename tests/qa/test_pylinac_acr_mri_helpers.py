"""Unit tests for ACR MRI helper behavior using lightweight fake analyzers."""

from __future__ import annotations

import builtins
import sys
import types
from pathlib import Path
from types import SimpleNamespace
from typing import ClassVar

import pytest

import qa.pylinac_acr_mri as acr_mri
from qa.analysis_types import LcRunConfig, QARequest
from qa.pylinac_acr_mri import (
    _build_mri_analyze_kwargs,
    _build_mri_analyzer,
    _build_mri_extra_warnings,
    _extract_lc_score,
    _image_count,
    _jsonable,
    run_acr_mri_large_analysis,
    run_acr_mri_large_batch,
)

_REAL_IMPORT = builtins.__import__


class _LenRaises:
    def __len__(self) -> int:
        raise RuntimeError("synthetic stack cannot be measured")


class _RecorderAnalyzer:
    def __init__(self, source: object, *, check_uid: bool) -> None:
        self.source = source
        self.check_uid = check_uid

    def analyze(
        self,
        *,
        echo_number: int | None = None,
        check_uid: bool = True,
        origin_slice: int | None = None,
        low_contrast_method: str = "",
        low_contrast_visibility_threshold: float = 0.0,
        low_contrast_visibility_sanity_multiplier: float = 0.0,
    ) -> None:
        """Signature-compatible fake; no analysis is performed."""


class _LegacyAnalyzer:
    def analyze(self, *, echo_number: int | None = None) -> None:
        """Represent a pylinac version with only the historical parameter."""


class _FakeMriAnalyzer:
    last_instance: ClassVar[_FakeMriAnalyzer | None] = None
    instances: ClassVar[list[_FakeMriAnalyzer]] = []

    def __init__(self, source: object, *, check_uid: bool) -> None:
        self.source = source
        self.check_uid = check_uid
        self.dicom_stack = [object(), object(), object()]
        self.analyze_kwargs: dict[str, object] | None = None
        self.publish_pdf_calls: list[tuple[str, list[str]]] = []
        # Live SNR harvest reads these after analyze(); list stack has no
        # InPlanePhaseEncodingDirection so harvest uses the ROW fallback
        # (Top/Bottom ghost-free ROIs when phase is along rows).
        self.uniformity_module = SimpleNamespace(
            rois={"Center": SimpleNamespace(pixel_value=200.0, std=1.0)},
            ghost_rois={
                "Top": SimpleNamespace(pixel_value=1.0, std=4.0),
                "Bottom": SimpleNamespace(pixel_value=1.0, std=6.0),
                "Left": SimpleNamespace(pixel_value=1.0, std=10.0),
                "Right": SimpleNamespace(pixel_value=1.0, std=10.0),
            },
        )
        _FakeMriAnalyzer.last_instance = self
        _FakeMriAnalyzer.instances.append(self)

    def analyze(
        self,
        *,
        echo_number: int | None = None,
        check_uid: bool = True,
        origin_slice: int | None = None,
        low_contrast_method: str = "",
        low_contrast_visibility_threshold: float = 0.0,
        low_contrast_visibility_sanity_multiplier: float = 0.0,
    ) -> None:
        self.analyze_kwargs = {
            "echo_number": echo_number,
            "check_uid": check_uid,
            "origin_slice": origin_slice,
            "low_contrast_method": low_contrast_method,
            "low_contrast_visibility_threshold": low_contrast_visibility_threshold,
            "low_contrast_visibility_sanity_multiplier": (
                low_contrast_visibility_sanity_multiplier
            ),
        }

    def results_data(self, *, as_dict: bool) -> dict[str, object]:
        assert as_dict is True
        return {
            "num_images": 3,
            "phantom_roll": 1.25,
            "has_sagittal_module": True,
            "origin_slice": 7,
            "low_contrast_multi_slice_module": {"score": "11"},
        }

    def publish_pdf(self, path: str, *, notes: list[str]) -> None:
        self.publish_pdf_calls.append((path, notes))


class _AnalyzeRaisesMriAnalyzer(_FakeMriAnalyzer):
    def analyze(self, **kwargs: object) -> None:
        raise RuntimeError("synthetic analysis failure")


class _PdfRaisesMriAnalyzer(_FakeMriAnalyzer):
    def publish_pdf(self, path: str, *, notes: list[str]) -> None:
        raise OSError("synthetic PDF write failure")


def _request(**overrides: object) -> QARequest:
    values: dict[str, object] = {
        "analysis_type": "acr_mri_large",
        "dicom_paths": ["synthetic-1.dcm", "synthetic-2.dcm"],
        "echo_number": 2,
        "check_uid": False,
        "origin_slice": 7,
    }
    values.update(overrides)
    return QARequest(**values)  # type: ignore[arg-type]


def _install_fake_pylinac(monkeypatch, analyzer_cls: type[_FakeMriAnalyzer]) -> None:
    """Make the runner's deferred pylinac imports resolve to a fake analyzer."""
    _FakeMriAnalyzer.last_instance = None
    _FakeMriAnalyzer.instances = []
    fake_pylinac = types.ModuleType("pylinac")
    fake_pylinac.__version__ = "test-version"
    fake_pylinac.ACRMRILarge = analyzer_cls
    monkeypatch.setitem(sys.modules, "pylinac", fake_pylinac)

    fake_extent = types.ModuleType("qa.pylinac_extent_subclasses")
    fake_extent.ACRMRILargeForViewer = analyzer_cls
    monkeypatch.setitem(sys.modules, "qa.pylinac_extent_subclasses", fake_extent)


def _block_pylinac_import(name: str, *args: object, **kwargs: object) -> object:
    if name.split(".", 1)[0] == "pylinac":
        raise ImportError("blocked for unit test")
    return _REAL_IMPORT(name, *args, **kwargs)


def _run_configs() -> list[LcRunConfig]:
    return [
        LcRunConfig("Threshold", "Weber", 0.001, 3.0),
        LcRunConfig("Contrast", "Ratio", 0.002, 4.0),
    ]


def test_jsonable_recursively_converts_containers_and_unknown_values() -> None:
    unknown = object()

    converted = _jsonable(
        {
            4: (True, None, {"unknown": unknown}),
            "numbers": [1, 2.5],
        }
    )

    assert converted == {
        "4": [True, None, {"unknown": str(unknown)}],
        "numbers": [1, 2.5],
    }


def test_image_count_prefers_analyzer_stack_and_falls_back_to_request() -> None:
    request = _request(dicom_paths=["one.dcm", "two.dcm", "three.dcm"])

    assert _image_count(SimpleNamespace(dicom_stack=[object(), object()]), request) == 2
    assert _image_count(SimpleNamespace(dicom_stack=_LenRaises()), request) == 3
    assert _image_count(SimpleNamespace(), request) == 3


def test_build_mri_analyzer_uses_dicom_paths_and_applies_viewer_tolerance() -> None:
    request = _request()

    analyzer = _build_mri_analyzer(
        request, cls=_RecorderAnalyzer, extent_tol_mm=2.75
    )

    assert analyzer.source == request.dicom_paths
    assert analyzer.check_uid is False
    assert analyzer._scan_extent_tolerance_mm == 2.75


def test_build_mri_analyzer_uses_folder_source_without_viewer_tolerance() -> None:
    request = _request(dicom_paths=[], folder_path="synthetic-folder")

    analyzer = _build_mri_analyzer(request, cls=_RecorderAnalyzer)

    assert analyzer.source == "synthetic-folder"
    assert analyzer.check_uid is False
    assert not hasattr(analyzer, "_scan_extent_tolerance_mm")


def test_build_mri_analyzer_rejects_missing_source() -> None:
    with pytest.raises(ValueError, match="No DICOM paths or folder"):
        _build_mri_analyzer(
            _request(dicom_paths=[], folder_path=None), cls=_RecorderAnalyzer
        )


def test_build_mri_analyze_kwargs_passes_only_supported_parameters() -> None:
    kwargs = _build_mri_analyze_kwargs(
        _RecorderAnalyzer([], check_uid=True),
        _request(),
        lc_method="Ratio",
        lc_vis=0.2,
        lc_sanity=4.5,
        echo_number=2,
    )

    assert kwargs == {
        "echo_number": 2,
        "check_uid": False,
        "origin_slice": 7,
        "low_contrast_method": "Ratio",
        "low_contrast_visibility_threshold": 0.2,
        "low_contrast_visibility_sanity_multiplier": 4.5,
    }


def test_build_mri_analyze_kwargs_omits_unsupported_and_optional_parameters() -> None:
    kwargs = _build_mri_analyze_kwargs(
        _LegacyAnalyzer(),
        _request(origin_slice=None),
        lc_method="Ratio",
        lc_vis=0.2,
        lc_sanity=4.5,
        echo_number=2,
    )

    assert kwargs == {"echo_number": 2}


def test_build_mri_extra_warnings_reports_each_unsupported_parameter() -> None:
    warnings = _build_mri_extra_warnings(_LegacyAnalyzer())

    assert len(warnings) == 4
    assert any("check_uid" in warning for warning in warnings)
    assert any("low_contrast_method" in warning for warning in warnings)
    assert any("low_contrast_visibility_threshold" in warning for warning in warnings)
    assert any(
        "low_contrast_visibility_sanity_multiplier" in warning for warning in warnings
    )


def test_build_mri_extra_warnings_is_empty_for_supported_signature() -> None:
    assert _build_mri_extra_warnings(_RecorderAnalyzer([], check_uid=True)) == []


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ({"low_contrast_score": "12"}, 12),
        (
            {
                "low_contrast_score": "not-a-score",
                "low_contrast_multi_slice_module": {"score": "9"},
            },
            9,
        ),
        ({"low_contrast_multi_slice": {"score": 4.8}}, 4),
        ({"low_contrast_multi_slice_module": {"score": None}}, None),
        ({}, None),
    ],
)
def test_extract_lc_score_supports_current_legacy_and_missing_shapes(
    raw: dict[str, object], expected: int | None
) -> None:
    assert _extract_lc_score(raw) == expected


def test_run_analysis_normalizes_successful_fake_analyzer_result(monkeypatch) -> None:
    _install_fake_pylinac(monkeypatch, _FakeMriAnalyzer)

    result = run_acr_mri_large_analysis(
        _request(
            scan_extent_tolerance_mm=1.5,
            low_contrast_method="Ratio",
            low_contrast_visibility_threshold=0.2,
            low_contrast_visibility_sanity_multiplier=4.5,
        )
    )

    analyzer = _FakeMriAnalyzer.last_instance
    assert analyzer is not None
    assert analyzer.source == ["synthetic-1.dcm", "synthetic-2.dcm"]
    assert analyzer.check_uid is False
    assert analyzer._scan_extent_tolerance_mm == 1.5
    assert analyzer.analyze_kwargs == {
        "echo_number": 2,
        "check_uid": False,
        "origin_slice": 7,
        "low_contrast_method": "Ratio",
        "low_contrast_visibility_threshold": 0.2,
        "low_contrast_visibility_sanity_multiplier": 4.5,
    }
    assert result.success is True
    assert result.num_images == 3
    assert result.metrics["low_contrast_score"] == 11
    assert result.metrics["phantom_roll"] == 1.25
    assert result.metrics["echo_number"] == 2
    assert result.metrics["echo_number_requested"] == 2
    assert "echo_number_auto_highest" not in result.metrics
    assert result.metrics["mri_snr"] == 40.0
    assert result.metrics["mri_snr_signal_mean"] == 200.0
    assert result.metrics["mri_snr_noise_mean"] == 5.0
    assert result.metrics["mri_snr_noise_roi_pair"] == "Top/Bottom"
    assert result.metrics["mri_snr_phase_encoding_fallback"] is True
    assert result.pylinac_analysis_profile["echo_number"] == 2
    assert result.pylinac_analysis_profile["echo_number_auto_highest"] is False
    assert result.raw_pylinac["has_sagittal_module"] is True
    assert result.pylinac_version == "test-version"
    assert result.pylinac_analysis_profile["engine"] == "ACRMRILargeForViewer"


def test_run_analysis_returns_validation_failure_before_fake_analysis(monkeypatch) -> None:
    _install_fake_pylinac(monkeypatch, _FakeMriAnalyzer)

    result = run_acr_mri_large_analysis(_request(dicom_paths=[], folder_path=None))

    assert result.success is False
    assert result.errors == ["No DICOM paths or folder were provided."]
    assert result.num_images == 0
    assert result.pylinac_version == "test-version"
    assert result.pylinac_analysis_profile["echo_number"] == 2
    assert result.pylinac_analysis_profile["echo_number_requested"] == 2
    assert result.pylinac_analysis_profile["echo_number_auto_highest"] is False


def test_run_analysis_returns_normalized_failure_when_analysis_raises(monkeypatch) -> None:
    _install_fake_pylinac(monkeypatch, _AnalyzeRaisesMriAnalyzer)

    result = run_acr_mri_large_analysis(_request())

    assert result.success is False
    assert result.num_images == 2
    assert result.errors == ["ACR MRI Large analysis failed: synthetic analysis failure"]
    assert result.pylinac_analysis_profile["engine"] == "ACRMRILargeForViewer"
    assert result.pylinac_analysis_profile["echo_number"] == 2
    assert result.pylinac_analysis_profile["echo_number_auto_highest"] is False


def test_run_analysis_keeps_success_when_optional_pdf_publish_fails(monkeypatch) -> None:
    _install_fake_pylinac(monkeypatch, _PdfRaisesMriAnalyzer)

    result = run_acr_mri_large_analysis(_request(output_pdf_path="synthetic-report.pdf"))

    assert result.success is True
    assert result.pdf_report_path is None
    assert result.metrics["low_contrast_score"] == 11


def test_run_batch_returns_one_missing_dependency_result_per_config(monkeypatch) -> None:
    monkeypatch.setattr(builtins, "__import__", _block_pylinac_import)
    configs = _run_configs()

    batch = run_acr_mri_large_batch(_request(), configs)

    assert batch.run_configs == configs
    assert len(batch.run_results) == 2
    assert all(result.success is False for result in batch.run_results)
    assert all(result.num_images == 2 for result in batch.run_results)
    assert all("pylinac is not installed" in result.errors[0] for result in batch.run_results)
    assert all(result.pylinac_analysis_profile["echo_number"] == 2 for result in batch.run_results)


def test_run_batch_preserves_run_order_and_propagates_each_config(monkeypatch) -> None:
    _install_fake_pylinac(monkeypatch, _FakeMriAnalyzer)
    configs = _run_configs()

    batch = run_acr_mri_large_batch(
        _request(scan_extent_tolerance_mm=1.5), configs, app_version="test-app"
    )

    assert [result.metrics["run_label"] for result in batch.run_results] == [
        "Threshold",
        "Contrast",
    ]
    assert [result.metrics["low_contrast_method"] for result in batch.run_results] == [
        "Weber",
        "Ratio",
    ]
    assert [
        result.metrics["low_contrast_visibility_threshold"]
        for result in batch.run_results
    ] == [0.001, 0.002]
    assert [
        result.pylinac_analysis_profile["low_contrast_visibility_sanity_multiplier"]
        for result in batch.run_results
    ] == [3.0, 4.0]
    assert len(_FakeMriAnalyzer.instances) == 2
    assert _FakeMriAnalyzer.instances[0].analyze_kwargs is not None
    assert _FakeMriAnalyzer.instances[0].analyze_kwargs["low_contrast_method"] == "Weber"
    assert _FakeMriAnalyzer.instances[1].analyze_kwargs is not None
    assert _FakeMriAnalyzer.instances[1].analyze_kwargs["low_contrast_method"] == "Ratio"
    assert batch.run_results[0].metrics["mri_snr"] == 40.0
    assert batch.run_results[0].metrics["echo_number"] == 2


def test_run_batch_leaves_pdf_path_empty_when_pdf_assembly_reports_failure(
    monkeypatch, tmp_path: Path
) -> None:
    _install_fake_pylinac(monkeypatch, _FakeMriAnalyzer)
    temp_dir = tmp_path / "compare-tmp"
    temp_dir.mkdir()
    calls: dict[str, object] = {}
    monkeypatch.setattr(acr_mri.tempfile, "mkdtemp", lambda **kwargs: str(temp_dir))
    monkeypatch.setattr(
        acr_mri,
        "_write_per_run_temp_pdf",
        lambda analyzer, path, label, config: None,
    )

    def _fake_summary(batch, summary_path, *, base_request, app_version) -> None:
        calls["summary"] = (batch, summary_path, base_request, app_version)

    def _fake_assemble(summary_path, run_pdf_paths, output_path) -> bool:
        calls["assembly"] = (summary_path, run_pdf_paths, output_path)
        return False

    monkeypatch.setattr(acr_mri, "build_mri_compare_summary_pdf", _fake_summary)
    monkeypatch.setattr(acr_mri, "assemble_mri_compare_pdf", _fake_assemble)

    batch = run_acr_mri_large_batch(
        _request(output_pdf_path="synthetic-combined.pdf"),
        _run_configs(),
        app_version="test-app",
    )

    assert len(batch.run_results) == 2
    assert all(result.success for result in batch.run_results)
    assert all(result.pdf_report_path is None for result in batch.run_results)
    assert calls["summary"][3] == "test-app"
    assert calls["assembly"][1] == [None, None]
    assert calls["assembly"][2] == Path("synthetic-combined.pdf")
    assert not temp_dir.exists()
