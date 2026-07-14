"""Tests for RDSR dose summary JSON/CSV export helpers."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from core.rdsr_dose_sr import (
    CtRadiationDoseSummary,
    dose_summary_to_export_dict,
    write_dose_summary_csv,
    write_dose_summary_json,
)


def test_dose_summary_export_dict_anonymize_masks_strings() -> None:
    s = CtRadiationDoseSummary(
        study_instance_uid="1.2.3",
        series_instance_uid="4.5.6",
        sop_instance_uid="7.8.9",
        manufacturer="ACME",
        manufacturer_model_name="ModelX",
        device_serial_number="SN1",
        ctdi_vol_mgy=12.5,
        dlp_mgy_cm=100.0,
        ssde_mgy=None,
        irradiation_event_count=2,
        parse_node_cap_hit=False,
    )
    d_anon = dose_summary_to_export_dict(s, anonymize=True)
    assert d_anon["study_instance_uid"] == "***"
    assert d_anon["ctdi_vol_mgy"] == 12.5
    d_raw = dose_summary_to_export_dict(s, anonymize=False)
    assert d_raw["study_instance_uid"] == "1.2.3"


def test_write_json_csv_roundtrip(tmp_path: Path) -> None:
    s = CtRadiationDoseSummary(
        ctdi_vol_mgy=1.0,
        dlp_mgy_cm=2.0,
        irradiation_event_count=1,
    )
    jp = tmp_path / "d.json"
    cp = tmp_path / "d.csv"
    write_dose_summary_json(jp, s, anonymize=True)
    write_dose_summary_csv(cp, s, anonymize=True)
    data = json.loads(jp.read_text(encoding="utf-8"))
    assert data["dose_summary_version"] == "1"
    assert data["ctdi_vol_mgy"] == 1.0
    rows = list(csv.DictReader(cp.open(encoding="utf-8")))
    assert len(rows) == 1
    assert float(rows[0]["ctdi_vol_mgy"]) == pytest.approx(1.0)


def test_write_csv_escapes_formula_like_cells(tmp_path: Path) -> None:
    s = CtRadiationDoseSummary(
        manufacturer="=malicious",
        ctdi_vol_mgy=1.0,
        dlp_mgy_cm=2.0,
        irradiation_event_count=1,
    )
    cp = tmp_path / "dose.csv"
    write_dose_summary_csv(cp, s, anonymize=False)
    rows = list(csv.DictReader(cp.open(encoding="utf-8")))
    assert rows[0]["manufacturer"] == "'=malicious"
