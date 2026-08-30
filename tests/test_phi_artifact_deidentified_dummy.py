"""Tests for the exact de-id dummy allowed by the PHI artifact gate.

The gate must accept identifier tags whose entire value is ``ANONYMIZED`` and
must still flag extra suffix, case variants, and real names.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

_SCRIPT = (
    Path(__file__).resolve().parent.parent / "scripts" / "check_no_phi_artifacts.py"
)
_spec = importlib.util.spec_from_file_location("check_no_phi_artifacts", _SCRIPT)
assert _spec and _spec.loader
phi = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(phi)


def test_exact_anonymized_dummy_is_allowed_on_dicom_identifiers() -> None:
    from pydicom.dataset import Dataset

    dataset = Dataset()
    dataset.PatientName = "ANONYMIZED"
    dataset.PatientID = "ANONYMIZED"
    dataset.PatientSex = "ANONYMIZED"
    assert phi._check_dicom_dataset("sample-phantom-data-committed/x.dcm", dataset) == []


def test_anonymized_dummy_must_be_the_entire_value() -> None:
    from pydicom.dataset import Dataset

    dataset = Dataset()
    dataset.PatientName = "ANONYMIZED^Extra"
    problems = phi._check_dicom_dataset("sample-phantom-data-committed/x.dcm", dataset)
    assert problems
    assert any("PatientName" in item for item in problems)


def test_anonymized_dummy_is_case_sensitive() -> None:
    from pydicom.dataset import Dataset

    dataset = Dataset()
    dataset.PatientID = "anonymized"
    problems = phi._check_dicom_dataset("sample-phantom-data-committed/x.dcm", dataset)
    assert problems


def test_json_patient_tag_anonymized_dummy_is_allowed() -> None:
    reasons = phi._content_reasons('{"PatientName": "ANONYMIZED"}')
    assert "populated DICOM patient tag" not in reasons


def test_json_dummy_then_real_patient_tag_on_same_line_is_flagged() -> None:
    reasons = phi._content_reasons(
        '{"PatientName": "ANONYMIZED", "PatientID": "SYN-GATE-001"}'
    )
    assert "populated DICOM patient tag" in reasons


def test_json_patient_tag_still_flags_real_values() -> None:
    reasons = phi._content_reasons('{"PatientName": "DOE^JANE"}')
    assert "populated DICOM patient tag" in reasons
