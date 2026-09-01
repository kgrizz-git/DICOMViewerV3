"""Regression tests for the reproducible PS3.16 CID 7050 extractor."""

from __future__ import annotations

import hashlib
import json
import unicodedata
from pathlib import Path

import pytest

from scripts.build_ps316_cid7050_inventory import (
    _OFFICIAL_CID_7050_URL,
    InventorySource,
    _parse_args,
    _validate_utc_timestamp,
    build_inventory_document,
    extract_inventory,
)

_COMMITTED_INVENTORY = (
    Path(__file__).resolve().parents[1] / "dev-docs/plans/supporting/ps316_cid7050_inventory.json"
)
_RETAINED_SOURCE = Path(__file__).resolve().parents[1] / "tmp/ps315-assessment/PS3.16-current-CID-7050.html"
_EXPECTED_SOURCE_SHA256 = "115f4ec2c9d7c803fded4b204af2932baa4d55beac307a18ef0005f13d905c14"
_EXPECTED_SOURCE_BYTES = 21919


def _cid_page(rows: str, *, context: str | None = None) -> str:
    context = context or "".join(
        f"<dt><strong>{label}:</strong></dt><dd><strong>{value}</strong></dd>"
        for label, value in (
            ("Keyword", "DeidentificationMethod"),
            ("FHIR Keyword", "dicom-cid-7050-DeidentificationMethod"),
            ("Type", "Extensible"),
            ("Version", "20170914"),
            ("UID", "1.2.840.10008.6.1.925"),
        )
    )
    return f"""
    <span class="documentreleaseinformation">DICOM PS3.16 2026c - Content Mapping Resource</span>
    <dl>{context}</dl>
    <table>
      <tr><th>Coding Scheme Designator</th><th>Code Value</th><th>Code Meaning</th></tr>
      {rows}
    </table>
    """


def test_extract_inventory_preserves_context_and_raw_codes() -> None:
    html = _cid_page(
        "<tr><td>DCM</td><td>113100</td><td>Basic Application Confidentiality Profile</td></tr>"
        "<tr><td>DCM</td><td>113110</td><td>Retain UIDs Option</td></tr>"
    )

    header, context, codes = extract_inventory(html)

    assert header == ["Coding Scheme Designator", "Code Value", "Code Meaning"]
    assert context == {
        "Keyword": "DeidentificationMethod",
        "FHIR Keyword": "dicom-cid-7050-DeidentificationMethod",
        "Type": "Extensible",
        "Version": "20170914",
        "UID": "1.2.840.10008.6.1.925",
    }
    assert codes == [
        {
            "stable_id": "CID7050-001",
            "source_table_row_number": 1,
            "coding_scheme_designator": "DCM",
            "code_value": "113100",
            "code_meaning": "Basic Application Confidentiality Profile",
        },
        {
            "stable_id": "CID7050-002",
            "source_table_row_number": 2,
            "coding_scheme_designator": "DCM",
            "code_value": "113110",
            "code_meaning": "Retain UIDs Option",
        },
    ]


def test_extract_inventory_handles_hyperlinked_codes_and_ignores_format_controls() -> None:
    html = _cid_page(
        "<tr><td>DCM</td><td><a href='chapter_D.html#DCM_113100'>113100</a></td>"
        "<td>Basic\u200b<style>ignored { content: 'noise'; }</style> Application Confidentiality Profile</td></tr>"
    )

    _, _, codes = extract_inventory(html)

    assert codes[0]["code_value"] == "113100"
    assert codes[0]["code_meaning"] == "Basic Application Confidentiality Profile"


def test_build_inventory_document_records_source_fingerprint() -> None:
    source_bytes = _cid_page(
        "<tr><td>DCM</td><td>113100</td><td>Basic Application Confidentiality Profile</td></tr>"
    ).encode()

    document = build_inventory_document(
        InventorySource(
            edition="2026c",
            source_url_current=_OFFICIAL_CID_7050_URL,
            edition_url_candidate="https://example.test/2026c",
            edition_url_status="not published (HTTP 404 on 2026-09-01)",
            retrieved_at_utc="2026-09-01T04:29:46Z",
        ),
        source_bytes,
    )

    assert document["source"]["content_sha256"] == hashlib.sha256(source_bytes).hexdigest()
    assert document["source"]["content_bytes"] == len(source_bytes)
    assert document["extraction"]["row_count"] == 1
    assert document["source"]["context_group"]["cid"] == 7050


def test_build_inventory_document_rejects_mismatched_page_edition() -> None:
    source_bytes = _cid_page(
        "<tr><td>DCM</td><td>113100</td><td>Basic Application Confidentiality Profile</td></tr>"
    ).encode()

    with pytest.raises(ValueError, match="does not match the retrieved page edition"):
        build_inventory_document(
            InventorySource(
                edition="2024b",
                source_url_current=_OFFICIAL_CID_7050_URL,
                edition_url_candidate="https://example.test/2024b",
                edition_url_status="not published (HTTP 404 on 2026-09-01)",
                retrieved_at_utc="2026-09-01T04:29:46Z",
            ),
            source_bytes,
        )


def test_build_inventory_document_rejects_editionless_archive_url() -> None:
    source_bytes = _cid_page(
        "<tr><td>DCM</td><td>113100</td><td>Basic Application Confidentiality Profile</td></tr>"
    ).encode()

    with pytest.raises(ValueError, match="edition-url-candidate"):
        build_inventory_document(
            InventorySource(
                edition="2026c",
                source_url_current=_OFFICIAL_CID_7050_URL,
                edition_url_candidate="https://example.test/archive",
                edition_url_status="not published (HTTP 404 on 2026-09-01)",
                retrieved_at_utc="2026-09-01T04:29:46Z",
            ),
            source_bytes,
        )


def test_build_inventory_document_rejects_noncanonical_source_url() -> None:
    source_bytes = _cid_page(
        "<tr><td>DCM</td><td>113100</td><td>Basic Application Confidentiality Profile</td></tr>"
    ).encode()

    with pytest.raises(ValueError, match="official NEMA CID 7050 URL"):
        build_inventory_document(
            InventorySource(
                edition="2026c",
                source_url_current="https://example.test/current",
                edition_url_candidate="https://example.test/2026c",
                edition_url_status="not published (HTTP 404 on 2026-09-01)",
                retrieved_at_utc="2026-09-01T04:29:46Z",
            ),
            source_bytes,
        )


def test_extract_inventory_rejects_missing_context_metadata() -> None:
    html = _cid_page(
        "<tr><td>DCM</td><td>113100</td><td>Basic Application Confidentiality Profile</td></tr>",
        context="<dt><strong>Keyword:</strong></dt><dd><strong>DeidentificationMethod</strong></dd>",
    )

    with pytest.raises(ValueError, match="missing context metadata"):
        extract_inventory(html)


def test_extract_inventory_rejects_invalid_code_fields() -> None:
    html = _cid_page("<tr><td>DCM</td><td>not-a-code</td><td>Meaning</td></tr>")

    with pytest.raises(ValueError, match="invalid code fields"):
        extract_inventory(html)


def test_extract_inventory_rejects_ambiguous_matching_tables() -> None:
    table = _cid_page("<tr><td>DCM</td><td>113100</td><td>Meaning</td></tr>")

    with pytest.raises(ValueError, match="exactly one"):
        extract_inventory(table + table)


def test_extract_inventory_rejects_mismatched_cells_with_layout_diagnostic() -> None:
    html = _cid_page("<tr><td>DCM</td><td>113100</td></tr>")

    with pytest.raises(ValueError, match="unsupported rowspan or colspan"):
        extract_inventory(html)


def test_extract_inventory_rejects_header_only_table() -> None:
    with pytest.raises(ValueError, match="no code rows"):
        extract_inventory(_cid_page(""))


@pytest.mark.parametrize(
    ("timestamp", "error"),
    [
        ("not-a-timestamp", "ISO-8601"),
        ("2026-09-01T04:29:46+00:00", "must use UTC"),
    ],
)
def test_validate_utc_timestamp_rejects_invalid_or_non_zulu_values(timestamp: str, error: str) -> None:
    with pytest.raises(ValueError, match=error):
        _validate_utc_timestamp(timestamp)


def test_validate_utc_timestamp_accepts_zulu_timestamp() -> None:
    _validate_utc_timestamp("2026-09-01T04:29:46Z")


def test_parse_args_defaults_to_official_source_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "sys.argv",
        [
            "build_ps316_cid7050_inventory.py",
            "--input",
            "source.html",
            "--output",
            "inventory.json",
            "--edition",
            "2026c",
            "--retrieved-at-utc",
            "2026-09-01T04:29:46Z",
            "--edition-url-candidate",
            "https://example.test/2026c",
            "--edition-url-status",
            "not published (HTTP 404 on 2026-09-01)",
        ],
    )

    assert _parse_args().source_url_current == _OFFICIAL_CID_7050_URL


def test_committed_inventory_has_complete_cid_7050_codes() -> None:
    inventory = json.loads(_COMMITTED_INVENTORY.read_text(encoding="utf-8"))
    codes = inventory["codes"]

    assert inventory["source"]["dicom_edition"] == "2026c"
    assert inventory["source"]["part"] == "PS3.16"
    assert inventory["source"]["edition_url_status"] == "not published (HTTP 404 on 2026-09-01)"
    assert inventory["source"]["context_group"] == {
        "cid": 7050,
        "Keyword": "DeidentificationMethod",
        "FHIR Keyword": "dicom-cid-7050-DeidentificationMethod",
        "Type": "Extensible",
        "Version": "20170914",
        "UID": "1.2.840.10008.6.1.925",
    }
    assert inventory["source"]["content_sha256"] == _EXPECTED_SOURCE_SHA256
    assert inventory["source"]["content_bytes"] == _EXPECTED_SOURCE_BYTES
    assert inventory["extraction"]["row_count"] == 13
    codes_digest = hashlib.sha256(
        json.dumps(codes, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    assert inventory["extraction"]["codes_sha256"] == codes_digest
    assert [code["source_table_row_number"] for code in codes] == list(range(1, 14))
    assert len({code["stable_id"] for code in codes}) == 13
    assert all(code["coding_scheme_designator"] == "DCM" for code in codes)
    assert all(
        unicodedata.category(character) != "Cf"
        for code in codes
        for character in code["code_meaning"]
    )
    assert {(code["coding_scheme_designator"], code["code_value"], code["code_meaning"]) for code in codes} == {
        ("DCM", "113100", "Basic Application Confidentiality Profile"),
        ("DCM", "113101", "Clean Pixel Data Option"),
        ("DCM", "113102", "Clean Recognizable Visual Features Option"),
        ("DCM", "113103", "Clean Graphics Option"),
        ("DCM", "113104", "Clean Structured Content Option"),
        ("DCM", "113105", "Clean Descriptors Option"),
        ("DCM", "113106", "Retain Longitudinal Temporal Information Full Dates Option"),
        ("DCM", "113107", "Retain Longitudinal Temporal Information Modified Dates Option"),
        ("DCM", "113108", "Retain Patient Characteristics Option"),
        ("DCM", "113109", "Retain Device Identity Option"),
        ("DCM", "113110", "Retain UIDs Option"),
        ("DCM", "113111", "Retain Safe Private Option"),
        ("DCM", "113112", "Retain Institution Identity Option"),
    }


def test_retained_source_matches_committed_fingerprint_when_available() -> None:
    if not _RETAINED_SOURCE.is_file():
        pytest.skip("The ignored official-source retrieval artifact is unavailable")

    source_bytes = _RETAINED_SOURCE.read_bytes()

    assert len(source_bytes) == _EXPECTED_SOURCE_BYTES
    assert hashlib.sha256(source_bytes).hexdigest() == _EXPECTED_SOURCE_SHA256


def test_retained_source_regenerates_committed_inventory_when_available() -> None:
    if not _RETAINED_SOURCE.is_file():
        pytest.skip("The ignored official-source retrieval artifact is unavailable")
    inventory = json.loads(_COMMITTED_INVENTORY.read_text(encoding="utf-8"))
    source = inventory["source"]

    regenerated = build_inventory_document(
        InventorySource(
            edition=source["dicom_edition"],
            source_url_current=source["source_url_current"],
            edition_url_candidate=source["edition_url_candidate"],
            edition_url_status=source["edition_url_status"],
            retrieved_at_utc=source["retrieved_at_utc"],
        ),
        _RETAINED_SOURCE.read_bytes(),
    )

    assert regenerated == inventory
