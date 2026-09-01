"""Regression tests for the reproducible PS3.15 Table E.1-1 extractor."""

from __future__ import annotations

import hashlib
import json
import unicodedata
from pathlib import Path

import pytest

from scripts.build_ps315_e1_inventory import (
    InventorySource,
    _validate_utc_timestamp,
    build_inventory_document,
    extract_inventory,
)

_COMMITTED_INVENTORY = (
    Path(__file__).resolve().parents[1] / "dev-docs/plans/supporting/ps315_e1_inventory.json"
)
_RETAINED_SOURCE = Path(__file__).resolve().parents[1] / "tmp/ps315-assessment/PS3.15-current-Annex-E.html"


def _annex_table(rows: str) -> str:
    return f"""
    <table>
      <tr>
        <th>Attribute Name</th><th>Tag</th><th>Retd. (from PS3.6)</th>
        <th>In Std. Comp. IOD (from PS3.3)</th><th>Basic Prof.</th>
        <th>Rtn. UIDs Opt.</th>
      </tr>
      {rows}
    </table>
    """


def test_extract_inventory_preserves_raw_action_and_option_columns() -> None:
    html = _annex_table(
        "<tr><td>Patient's Name</td><td>(0010,0010)</td><td>N</td><td>Y</td><td>Z</td><td></td></tr>"
        "<tr><td>SOP Instance UID</td><td>(0008,0018)</td><td>N</td><td>Y</td><td>U</td><td>K</td></tr>"
    )

    header, rows = extract_inventory(html)

    assert header[-1] == "Rtn. UIDs Opt."
    assert rows == [
        {
            "stable_id": "E1-T-001",
            "source_table_row_number": 1,
            "attribute_name": "Patient's Name",
            "tag_gggg_eeee": "(0010,0010)",
            "retired_from_ps3_6": "N",
            "in_standard_composite_iod": "Y",
            "action_code_base": "Z",
            "option_overrides": {"Rtn. UIDs Opt.": ""},
        },
        {
            "stable_id": "E1-T-002",
            "source_table_row_number": 2,
            "attribute_name": "SOP Instance UID",
            "tag_gggg_eeee": "(0008,0018)",
            "retired_from_ps3_6": "N",
            "in_standard_composite_iod": "Y",
            "action_code_base": "U",
            "option_overrides": {"Rtn. UIDs Opt.": "K"},
        },
    ]


def test_build_inventory_document_records_source_fingerprint() -> None:
    source_bytes = _annex_table(
        "<tr><td>Patient's Name</td><td>(0010,0010)</td><td>N</td><td>Y</td><td>Z</td><td></td></tr>"
    ).encode()

    document = build_inventory_document(
        InventorySource(
            edition="2026c",
            source_url_current="https://example.test/current",
            edition_url_candidate="https://example.test/2026c",
            edition_url_status="not published (HTTP 404)",
            retrieved_at_utc="2026-08-31T12:34:56Z",
        ),
        source_bytes,
    )

    assert document["source"]["content_sha256"] == hashlib.sha256(source_bytes).hexdigest()
    assert document["source"]["content_bytes"] == len(source_bytes)
    assert document["source"]["edition_url_status"] == "not published (HTTP 404)"
    assert document["extraction"]["row_count"] == 1


def test_extract_inventory_accepts_standard_repeating_group_patterns() -> None:
    html = _annex_table(
        "<tr><td>Curve Data</td><td>(50xx,3000)</td><td>Y</td><td>N</td><td>X</td><td></td></tr>"
    )

    _, rows = extract_inventory(html)

    assert rows[0]["tag_gggg_eeee"] == "(50xx,3000)"


def test_extract_inventory_accepts_private_attribute_pattern_notes() -> None:
    html = _annex_table(
        "<tr><td>Private Attributes</td><td>(gggg,eeee) where gggg is odd</td>"
        "<td>N</td><td>N</td><td>X</td><td></td></tr>"
    )

    _, rows = extract_inventory(html)

    assert rows[0]["tag_gggg_eeee"] == "(gggg,eeee) where gggg is odd"


def test_extract_inventory_removes_format_controls_and_ignores_embedded_style_content() -> None:
    html = _annex_table(
        "<tr><td>Wave\u200bform<style>ignored { content: 'noise'; }</style> Filter</td>"
        "<td>(0010,0010)</td><td>N</td><td>Y</td><td>Z</td><td></td></tr>"
    )

    _, rows = extract_inventory(html)

    assert rows[0]["attribute_name"] == "Waveform Filter"


def test_extract_inventory_rejects_ambiguous_matching_tables() -> None:
    html = _annex_table(
        "<tr><td>Patient's Name</td><td>(0010,0010)</td><td>N</td><td>Y</td><td>Z</td><td></td></tr>"
    ) * 2

    with pytest.raises(ValueError, match="exactly one"):
        extract_inventory(html)


def test_extract_inventory_rejects_mismatched_cells_with_layout_diagnostic() -> None:
    html = _annex_table(
        "<tr><td>Patient's Name</td><td>(0010,0010)</td><td>N</td><td>Y</td><td>Z</td></tr>"
    )

    with pytest.raises(ValueError, match="unsupported rowspan or colspan"):
        extract_inventory(html)


def test_extract_inventory_rejects_header_only_table() -> None:
    with pytest.raises(ValueError, match="no data rows"):
        extract_inventory(_annex_table(""))


@pytest.mark.parametrize(
    ("timestamp", "error"),
    [
        ("not-a-timestamp", "ISO-8601"),
        ("2026-08-31T22:58:12+00:00", "must use UTC"),
    ],
)
def test_validate_utc_timestamp_rejects_invalid_or_non_zulu_values(timestamp: str, error: str) -> None:
    with pytest.raises(ValueError, match=error):
        _validate_utc_timestamp(timestamp)


def test_validate_utc_timestamp_accepts_zulu_timestamp() -> None:
    _validate_utc_timestamp("2026-08-31T22:58:12Z")


def test_committed_inventory_has_complete_numbered_source_rows() -> None:
    inventory = json.loads(_COMMITTED_INVENTORY.read_text(encoding="utf-8"))
    requirements = inventory["requirements"]

    assert inventory["source"]["dicom_edition"] == "2026c"
    assert len(inventory["source"]["content_sha256"]) == 64
    assert inventory["extraction"]["row_count"] == 656
    requirements_digest = hashlib.sha256(
        json.dumps(requirements, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    assert inventory["extraction"]["requirements_sha256"] == requirements_digest
    assert [requirement["source_table_row_number"] for requirement in requirements] == list(
        range(1, 657)
    )
    assert len({requirement["stable_id"] for requirement in requirements}) == 656
    assert all(
        unicodedata.category(character) != "Cf"
        for requirement in requirements
        for character in requirement["attribute_name"]
    )


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


@pytest.mark.parametrize("tag", ["0010,0010", "(0010,001X)"])
def test_extract_inventory_rejects_invalid_dicom_tags(tag: str) -> None:
    html = _annex_table(f"<tr><td>Patient's Name</td><td>{tag}</td><td>N</td><td>Y</td><td>Z</td><td></td></tr>")

    with pytest.raises(ValueError, match="invalid DICOM tag pattern"):
        extract_inventory(html)
