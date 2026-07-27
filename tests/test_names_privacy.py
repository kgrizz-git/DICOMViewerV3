"""Unit tests for patient name and identifier filename/content scanning."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from scripts.privacy_checks.names import (
    IDENTIFIER_CONTENT_PATTERN,
    NAME_CONTENT_PATTERN,
    PATIENT_IDENTIFIER_PATTERN,
    PATIENT_NAME_TOKENS,
    SAFE_NAME_COMPOUNDS,
    PathCarveoutPattern,
    name_in_path,
)

# Dynamically import check_no_phi_artifacts as phi
_SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "check_no_phi_artifacts.py"
_spec = importlib.util.spec_from_file_location("check_no_phi_artifacts", _SCRIPT)
assert _spec and _spec.loader
phi = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(phi)


@pytest.mark.parametrize("name", sorted(PATIENT_NAME_TOKENS))
def test_name_tokens_block_as_basename_token(name: str) -> None:
    """Each seed name in PATIENT_NAME_TOKENS blocks when it appears as a basename token."""
    assert name_in_path(f"{name}_report.txt") == "patient-name-in-filename"
    assert name_in_path(f"{name.upper()}_export.csv") == "patient-name-in-filename"
    assert name_in_path(f"{name}-study.json") == "patient-name-in-filename"
    assert name_in_path(f"prefix.{name}.suffix") == "patient-name-in-filename"


def test_safe_name_compounds() -> None:
    """Each SAFE_NAME_COMPOUNDS stem does NOT block, and non-token stems do not block."""
    for compound in SAFE_NAME_COMPOUNDS:
        assert name_in_path(f"{compound}.py") is None
        assert name_in_path(f"some/dir/{compound}_refactoring.txt") is None

    # Stems that never split into a listed token do not block
    assert name_in_path("jackknife.txt") is None
    assert name_in_path("davidson_profile.csv") is None


def test_identifier_patterns() -> None:
    """Structured identifier patterns match valid IDs and reject false positives."""
    positives = [
        "MRN_1234567",
        "acc-1234567",
        "MRN007",
        "PID-001",
        "studyid_423",
        "encounter-999",
        "caseid_100",
        "acc-12345",
    ]
    for case in positives:
        assert name_in_path(case) == "patient-identifier-in-filename"

    negatives = [
        "accidentally.txt",
        "master_mr.txt",
        "acc-2024",  # 4 digits (acc floor is 5)
        "account_balance.csv",
        "studyid_42",  # 2 digits (floor is 3)
    ]
    for case in negatives:
        assert name_in_path(case) is None


def test_content_reasons() -> None:
    """_content_reasons returns new categories for embedded names/identifiers."""
    # Test identifier match
    reasons = phi._content_reasons("patient record: MRN_1234567")
    assert "patient-identifier-in-content" in reasons

    # Test name match
    reasons = phi._content_reasons("referred by Dr. Smith for scan")
    assert "patient-name-in-content" in reasons

    # Mixed-case
    reasons = phi._content_reasons("Name: SMITH, JOHN")
    assert "patient-name-in-content" in reasons


def test_content_reasons_path_carveout() -> None:
    """The content lane skips name/identifier rules on documentation paths.

    PathCarveoutPattern.search walks the call stack for a local named ``path``.
    The wrapper below provides that local in frame 1, exactly as ``check_contents``
    does via its ``for path in paths:`` loop.
    """

    def _search(pattern: PathCarveoutPattern, text: str, path: str) -> bool:
        # ``path`` is a local here — frame walker finds it at frame 1.
        return pattern.search(text) is not None

    # dev-docs/ — skipped
    assert not _search(NAME_CONTENT_PATTERN, "referred by Smith", "dev-docs/plans/foo.md")
    assert not _search(IDENTIFIER_CONTENT_PATTERN, "MRN_1234567", "dev-docs/plans/foo.md")

    # user-docs/ — skipped
    assert not _search(NAME_CONTENT_PATTERN, "referred by Smith", "user-docs/guide.md")
    assert not _search(IDENTIFIER_CONTENT_PATTERN, "MRN_1234567", "user-docs/guide.md")

    # src/utils/privacy/ — skipped (schema/infrastructure, not patient data)
    assert not _search(NAME_CONTENT_PATTERN, "kind: mark", "src/utils/privacy/schema_v1.json")

    # Root-level markdown docs — skipped
    assert not _search(NAME_CONTENT_PATTERN, "authored by Mark", "CHANGELOG.md")
    assert not _search(NAME_CONTENT_PATTERN, "authored by Mark", "DESIGN.md")

    # Other paths — NOT skipped
    assert _search(NAME_CONTENT_PATTERN, "referred by Smith", "tests/fixtures/data.csv")
    assert _search(IDENTIFIER_CONTENT_PATTERN, "MRN_1234567", "tests/fixtures/data.csv")


def test_allowance_asymmetry(tmp_path: Path) -> None:
    """Filenames have no allowance bypass even when registered as text exceptions."""
    # Setup test file in tmp repo
    # check_paths does not check APPROVED_TEXT_EXCEPTIONS_MANIFEST
    # Smith_report.csv has Smith in filename, which must block regardless of manifest.
    path = "Smith_report.csv"
    reasons = phi.path_reasons(path)
    assert "patient-name-in-filename" in reasons


def test_directory_name_scope() -> None:
    """The name lane scans every path component, with directory allowlist controls."""
    # Bare patient-named directory blocks
    assert name_in_path("data/smith/results.csv") == "patient-name-in-filename"
    assert name_in_path("exports/smith^john/img001.dcm") == "patient-name-in-filename"

    # Reviewed org directory does not block itself
    assert name_in_path("data/smith_lab/results.csv") is None

    # Basename still blocks even in reviewed org directory
    assert name_in_path("data/smith_lab/smith.txt") == "patient-name-in-filename"

    # Directory patient-identifier blocks
    assert name_in_path("data/mrn-12345/results.csv") == "patient-identifier-in-filename"

    # Nested path checks
    assert name_in_path("data/cohorts/smith/john.txt") == "patient-name-in-filename"
    assert name_in_path("data/MRN-12345/x") == "patient-identifier-in-filename"
    assert name_in_path("data/gupta/x.csv") == "patient-name-in-filename"


def test_word_boundary_cases() -> None:
    """Name pattern handles boundaries correctly, refusing initials and subwords."""
    # Positive boundary cases
    assert NAME_CONTENT_PATTERN.search("smith,") is not None
    assert NAME_CONTENT_PATTERN.search("smith.") is not None
    assert NAME_CONTENT_PATTERN.search("smith-") is not None
    assert NAME_CONTENT_PATTERN.search("smith_") is not None
    assert NAME_CONTENT_PATTERN.search("patient_smith_id") is not None
    assert NAME_CONTENT_PATTERN.search("SMITH") is not None
    assert NAME_CONTENT_PATTERN.search("report smith end") is not None

    # Negative boundary/subword cases
    assert NAME_CONTENT_PATTERN.search("smithson") is None
    assert NAME_CONTENT_PATTERN.search("goldsmith") is None
    assert NAME_CONTENT_PATTERN.search("smith2") is None


def test_lookbehind_cases() -> None:
    """Identifier pattern lookbehind handles separators and boundaries."""
    # Positive cases
    assert PATIENT_IDENTIFIER_PATTERN.search("MRN-123") is not None
    assert PATIENT_IDENTIFIER_PATTERN.search("MRN_123") is not None
    assert PATIENT_IDENTIFIER_PATTERN.search("MRN.123") is not None
    assert PATIENT_IDENTIFIER_PATTERN.search("MRN 123") is not None
    assert PATIENT_IDENTIFIER_PATTERN.search("MRN123") is not None

    # Negative cases
    assert PATIENT_IDENTIFIER_PATTERN.search("MRN-12") is None  # needs 3 digits
    assert PATIENT_IDENTIFIER_PATTERN.search("acc-1234") is None  # acc needs 5 digits
    assert PATIENT_IDENTIFIER_PATTERN.search("accidentally-19999") is None  # keyword not delimited
    assert PATIENT_IDENTIFIER_PATTERN.search("my_mrn_123") is not None  # lookbehind matches _
    assert PATIENT_IDENTIFIER_PATTERN.search("mymrn_123") is None  # lookbehind doesn't match y
