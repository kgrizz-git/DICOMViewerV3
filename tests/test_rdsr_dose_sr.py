"""
Unit tests for ``core.rdsr_dose_sr`` using **in-repo fixtures only** (``tests/fixtures/dicom_rdsr/``).
"""

from __future__ import annotations

from pathlib import Path

import pydicom
import pytest
from pydicom.dataset import Dataset
from pydicom.uid import CTImageStorage, generate_uid

from core.rdsr_dose_sr import (
    CtRadiationDoseSummary,
    RadiationDoseSrParseError,
    is_radiation_dose_sr,
    parse_ct_radiation_dose_summary,
)

_FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "dicom_rdsr"


def _fixture_path(name: str) -> Path:
    return _FIXTURE_DIR / name


@pytest.fixture(scope="module")
def xray_rdsr_ds() -> Dataset:
    path = _fixture_path("synthetic_ct_dose_xray_rdsr.dcm")
    assert path.is_file(), f"missing fixture {path}"
    return pydicom.dcmread(path)


@pytest.fixture(scope="module")
def comprehensive_sr_ds() -> Dataset:
    path = _fixture_path("synthetic_ct_dose_comprehensive_sr.dcm")
    assert path.is_file(), f"missing fixture {path}"
    return pydicom.dcmread(path)


def test_is_radiation_dose_sr_xray_rdsr_fixture(xray_rdsr_ds: Dataset) -> None:
    assert is_radiation_dose_sr(xray_rdsr_ds) is True


def test_is_radiation_dose_sr_comprehensive_fixture(comprehensive_sr_ds: Dataset) -> None:
    assert is_radiation_dose_sr(comprehensive_sr_ds) is True


def test_parse_xray_rdsr_fixture_values(xray_rdsr_ds: Dataset) -> None:
    summary = parse_ct_radiation_dose_summary(xray_rdsr_ds)
    assert isinstance(summary, CtRadiationDoseSummary)
    assert summary.ctdi_vol_mgy == pytest.approx(12.5)
    assert summary.dlp_mgy_cm == pytest.approx(450.0)
    assert summary.ssde_mgy == pytest.approx(8.2)
    assert summary.irradiation_event_count == 2
    assert summary.manufacturer == "SyntheticFixture"
    assert summary.manufacturer_model_name == "RDSR-Gen"
    assert summary.device_serial_number == "SER-SYN-1"
    assert summary.study_instance_uid
    assert summary.series_instance_uid
    assert summary.sop_instance_uid


def test_parse_comprehensive_fixture_values(comprehensive_sr_ds: Dataset) -> None:
    summary = parse_ct_radiation_dose_summary(comprehensive_sr_ds)
    assert summary.ctdi_vol_mgy == pytest.approx(12.5)
    assert summary.dlp_mgy_cm == pytest.approx(450.0)
    assert summary.irradiation_event_count == 2


def test_parse_rejects_non_dose_ct() -> None:
    ds = Dataset()
    ds.SOPClassUID = CTImageStorage
    ds.SOPInstanceUID = generate_uid()
    ds.Modality = "CT"
    assert is_radiation_dose_sr(ds) is False
    with pytest.raises(RadiationDoseSrParseError):
        parse_ct_radiation_dose_summary(ds)


def test_parse_node_cap_flag(xray_rdsr_ds: Dataset) -> None:
    summary = parse_ct_radiation_dose_summary(xray_rdsr_ds, max_nodes=3, max_depth=24)
    assert summary.parse_node_cap_hit is True


def test_fixture_readme_documents_generator() -> None:
    readme = _FIXTURE_DIR / "README.md"
    assert readme.is_file()
    text = readme.read_text(encoding="utf-8")
    assert "generate_rdsr_dose_sr_fixtures.py" in text
    assert "512 KiB" in text or "512" in text


def test_fixture_files_small_policy() -> None:
    for name in (
        "synthetic_ct_dose_xray_rdsr.dcm",
        "synthetic_ct_dose_comprehensive_sr.dcm",
    ):
        p = _fixture_path(name)
        assert p.stat().st_size <= 512 * 1024
