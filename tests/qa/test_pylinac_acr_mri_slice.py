"""Tests for ACR MRI analysis helpers (mocked; no patient data)."""

from __future__ import annotations

from qa.analysis_types import QARequest
from qa.pylinac_acr_mri import _missing_pylinac_result


def test_missing_pylinac_result_is_failure() -> None:
    req = QARequest(analysis_type="acr_mri_large", dicom_paths=["/tmp/synthetic.dcm"])
    result = _missing_pylinac_result(req)
    assert result.success is False
    assert result.analysis_type == "acr_mri_large"
    assert result.errors
