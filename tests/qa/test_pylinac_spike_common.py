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


def test_dump_redacts_embedded_windows_unc_paths() -> None:
    tree = {"source": r"source=\\pacs\private\scan"}
    redacted = redact_results_dump(tree)
    assert redacted["source"] == "source=<redacted-path>"
    assert "pacs" not in str(redacted)
    assert "private" not in str(redacted)


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


def test_dump_redacts_uid_shaped_strings_for_roots_0_1_and_2() -> None:
    uid_like = _common._UID_LIKE
    assert uid_like.search("0.1.2.3")
    assert uid_like.search("1.2.840.999.1")
    assert uid_like.search("2.16.840.1.113883")
    assert uid_like.search("2.25.123456789012345678901234567890123")
    tree = {
        "notes": "ref 1.2.840.999.8.8.8 leftover",
        "uuid_style": "2.25.123456789012345678901234567890123",
        "root_zero": "0.1.2.3.4",
        "nested": {"misc_uid": "1.2.840.999.7"},
    }
    redacted = redact_results_dump(tree)
    blob = str(redacted)
    assert "<redacted-uid>" in redacted["notes"]
    assert redacted["uuid_style"] == "<redacted-uid>"
    assert redacted["root_zero"] == "<redacted-uid>"
    assert redacted["nested"]["misc_uid"] == "<redacted-uid>"
    assert "1.2.840" not in blob
    assert "2.25." not in blob
    assert "0.1.2.3" not in blob


def test_dump_uid_context_is_suffix_not_substring_and_nests() -> None:
    tree = {
        "guid": "keep-guid-token",
        "customUID": {"value": "nested-under-uid-key"},
    }
    redacted = redact_results_dump(tree)
    assert redacted["guid"] == "keep-guid-token"
    assert redacted["customUID"]["value"] == "<redacted-uid>"


def test_analyze_folder_with_extent_retry_skips_strict_then_succeeds() -> None:
    """Viewer-style 0 → 1 mm retry without loading DICOM (P0 dump regeneration)."""
    constructed: list[float] = []

    class FakeAnalyzer:
        def __init__(self, folder: str, check_uid: bool = False) -> None:
            self.folder = folder
            self.check_uid = check_uid
            self._scan_extent_tolerance_mm = 0.0
            constructed.append(self._scan_extent_tolerance_mm)

        def analyze(self, **kwargs: object) -> None:
            if float(self._scan_extent_tolerance_mm) < 1.0:
                raise ValueError("physical scan extent does not cover")

    analyzer = _common.analyze_folder_with_extent_retry(
        FakeAnalyzer,
        Path("sample-phantom-data-committed/deid-phantoms/ct/series-001"),
        check_uid=False,
    )
    assert analyzer._scan_extent_tolerance_mm == 1.0
    assert len(constructed) == 2
