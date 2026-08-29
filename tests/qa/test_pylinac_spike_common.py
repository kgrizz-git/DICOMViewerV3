"""Unit tests for pylinac ACR dump redaction (no live analyze, no real paths)."""

from __future__ import annotations

import importlib.util
from pathlib import Path

_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "pylinac_spike_common.py"
_SPEC = importlib.util.spec_from_file_location("pylinac_spike_common", _SCRIPT)
assert _SPEC is not None and _SPEC.loader is not None
_common = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_common)

redact_results_dump = _common.redact_results_dump


def test_dump_redacts_absolute_paths_and_keeps_repo_relative() -> None:
    tree = {
        "phantom_model": "ACR CT",
        "notes": "ran from sample-DICOM-gitignored/CT-phantoms/series",
        "source": str(Path("/Users") / "example" / "secret" / "phantom.dcm"),
    }
    redacted = redact_results_dump(tree)
    assert redacted["phantom_model"] == "ACR CT"
    assert "sample-DICOM-gitignored/CT-phantoms/series" in redacted["notes"]
    assert redacted["source"] == "<redacted-path>"
    assert "/Users/" not in str(redacted)


def test_dump_drops_institution_address_and_station_keys() -> None:
    tree = {
        "phantom_model": "ACR MRI Large",
        "piu": 99.1,
        "InstitutionName": "Example Site",
        "InstitutionAddress": "1 Main Street",
        "StationName": "MRI1",
        "InstitutionalDepartmentName": "Imaging",
        "DeviceSerialNumber": "1.2.840.999.1",
        "SeriesInstanceUID": "1.2.840.999.2",
        "nested": {"StationName": "MRI1", "psg": 0.4},
    }
    redacted = redact_results_dump(tree)
    assert redacted["phantom_model"] == "ACR MRI Large"
    assert redacted["piu"] == 99.1
    assert "InstitutionName" not in redacted
    assert "InstitutionAddress" not in redacted
    assert "StationName" not in redacted
    assert "InstitutionalDepartmentName" not in redacted
    assert "SeriesInstanceUID" not in redacted
    assert "DeviceSerialNumber" not in redacted
    assert "StationName" not in redacted["nested"]
    assert redacted["nested"]["psg"] == 0.4
    blob = str(redacted)
    assert "Example Site" not in blob
    assert "1 Main Street" not in blob
    assert "MRI1" not in blob
