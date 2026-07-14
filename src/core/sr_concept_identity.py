"""
SR coded-concept identity helpers for template matching (dose events, dose summary walks).

**Purpose:** Normalize DICOM **coded entries** attached to SR content items so comparisons
tolerate common vendor variations: whitespace, ``CodingSchemeDesignator`` case for typical
short designators, and empty ``CodeValue`` when ``LongCodeValue`` (LO) carries the identifier.

**Inputs:** A **content item** ``Dataset`` (uses ``ConceptNameCodeSequence``) or a **coded entry**
``Dataset`` (single row of a code sequence).

**Outputs:** Normalized ``(code_value, coding_scheme_designator)`` pairs for equality tests.

**Requirements:** ``pydicom`` only.

**Equivalence policy (v1)**

- **Whitespace:** ``CodingSchemeDesignator`` and effective code value strings are **stripped**
  of leading/trailing spaces before comparison.
- **CodingSchemeDesignator case-folding:** If the stripped designator **does not** contain ``:``
  and **does not** start with ``urn`` (case-insensitive), it is folded with **ASCII uppercase**
  so ``dcm`` matches ``DCM``. Designators containing ``:`` or URN-like prefixes are compared
  **case-sensitively** after strip only, to avoid treating opaque scheme strings as equivalent.
- **CodeValue vs LongCodeValue:** For a coded entry, if ``CodeValue`` is empty after strip, the
  first non-empty trimmed **LongCodeValue** is used as the effective code value (DICOM LO).
- **CodingSchemeVersion** is **not** part of equality in v1; two codes with the same value and
  designator but different version fields still match (documented limitation).

See ``dev-docs/plans/supporting/SR_DOSE_EVENTS_NORMALIZATION_AND_HIGHDICOM_PLAN.md`` Phase 1.1.
"""

from __future__ import annotations

from typing import cast

from pydicom.dataset import Dataset
from pydicom.sequence import Sequence as DicomSequence


def normalize_coding_scheme_designator(raw: str) -> str:
    """Return a normalized designator string for comparisons (see module docstring)."""
    s = (raw or "").strip()
    if not s:
        return ""
    low = s.lower()
    if low.startswith("urn") or ":" in s:
        return s
    return s.upper()


def coded_entry_effective_code_value(coded: Dataset) -> str:
    """
    Effective code value for a coded entry: ``CodeValue`` (SH) when non-empty after strip,
    otherwise ``LongCodeValue`` (LO).
    """
    cv = getattr(coded, "CodeValue", None)
    if cv is not None:
        t = str(cv).strip()
        if t:
            return t
    lcv = getattr(coded, "LongCodeValue", None)
    if lcv is not None:
        return str(lcv).strip()
    return ""


def normalized_expected_tuple(expected: tuple[str, str]) -> tuple[str, str]:
    """Normalize a literal ``(CodeValue, CodingSchemeDesignator)`` pair used in code tables."""
    cv, scheme = expected
    return (str(cv).strip(), normalize_coding_scheme_designator(scheme))


def concept_name_identity_pair(content_item: Dataset) -> tuple[str, str]:
    """Normalized ``(code_value, designator)`` from the first **Concept Name Code** item."""
    cseq = getattr(content_item, "ConceptNameCodeSequence", None)
    if not cseq or len(cast(DicomSequence, cseq)) == 0:
        return ("", "")
    c0 = cast(DicomSequence, cseq)[0]
    cv = coded_entry_effective_code_value(c0)
    scheme = normalize_coding_scheme_designator(str(getattr(c0, "CodingSchemeDesignator", "") or ""))
    return (cv, scheme)


def concept_identity_matches(content_item: Dataset, expected: tuple[str, str]) -> bool:
    """True when the content item's concept name matches ``expected`` after normalization."""
    return concept_name_identity_pair(content_item) == normalized_expected_tuple(expected)
