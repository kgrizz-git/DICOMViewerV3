#!/usr/bin/env python3
"""Build a source-derived PS3.16 CID 7050 inventory from official HTML.

The input must be a locally retained copy of the official DICOM PS3.16 CID
7050 page. This script never downloads standards content; retrieval and the
source fingerprint are recorded separately in the generated document.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

_EXPECTED_HEADER = ("Coding Scheme Designator", "Code Value", "Code Meaning")
_CONTEXT_FIELDS = ("Keyword", "FHIR Keyword", "Type", "Version", "UID")
_EDITION_PATTERN = re.compile(
    r'<span[^>]+class="documentreleaseinformation"[^>]*>\s*DICOM PS3\.16\s+([^\s<]+)\s+-',
    re.IGNORECASE,
)


def _normalise_text(value: str) -> str:
    without_format_controls = "".join(
        character for character in value if unicodedata.category(character) != "Cf"
    )
    return " ".join(without_format_controls.split())


class _CidPageParser(HTMLParser):
    """Extract the CID table and context metadata from stable DocBook HTML."""

    def __init__(self) -> None:
        super().__init__()
        self.tables: list[list[list[str]]] = []
        self.context_fields: dict[str, str] = {}
        self._table: list[list[str]] | None = None
        self._row: list[str] | None = None
        self._cell: list[str] | None = None
        self._definition_term: list[str] | None = None
        self._definition_value: list[str] | None = None
        self._current_term: str | None = None
        self._ignored_content_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        del attrs
        if tag in {"script", "style"}:
            self._ignored_content_depth += 1
            return
        if tag == "table":
            self._table = []
        elif tag == "tr" and self._table is not None:
            self._row = []
        elif tag in {"td", "th"} and self._row is not None:
            self._cell = []
        elif tag == "dt":
            self._definition_term = []
        elif tag == "dd":
            self._definition_value = []

    def handle_data(self, data: str) -> None:
        if self._ignored_content_depth:
            return
        if self._cell is not None:
            self._cell.append(data)
        if self._definition_term is not None:
            self._definition_term.append(data)
        if self._definition_value is not None:
            self._definition_value.append(data)

    def handle_endtag(self, tag: str) -> None:
        if self._finish_ignored_content(tag):
            return
        if self._finish_table_cell(tag):
            return
        if self._finish_table_row(tag):
            return
        if self._finish_table(tag):
            return
        if self._finish_definition_term(tag):
            return
        self._finish_definition_value(tag)

    def _finish_ignored_content(self, tag: str) -> bool:
        if tag in {"script", "style"} and self._ignored_content_depth:
            self._ignored_content_depth -= 1
            return True
        return False

    def _finish_table_cell(self, tag: str) -> bool:
        if tag in {"td", "th"} and self._cell is not None and self._row is not None:
            self._row.append(_normalise_text("".join(self._cell)))
            self._cell = None
            return True
        return False

    def _finish_table_row(self, tag: str) -> bool:
        if tag == "tr" and self._row is not None and self._table is not None:
            self._table.append(self._row)
            self._row = None
            return True
        return False

    def _finish_table(self, tag: str) -> bool:
        if tag == "table" and self._table is not None:
            self.tables.append(self._table)
            self._table = None
            return True
        return False

    def _finish_definition_term(self, tag: str) -> bool:
        if tag == "dt" and self._definition_term is not None:
            self._current_term = _normalise_text("".join(self._definition_term)).rstrip(":")
            self._definition_term = None
            return True
        return False

    def _finish_definition_value(self, tag: str) -> None:
        if tag == "dd" and self._definition_value is not None:
            if self._current_term is not None:
                self.context_fields[self._current_term] = _normalise_text(
                    "".join(self._definition_value)
                )
            self._definition_value = None


@dataclass(frozen=True)
class InventorySource:
    """Provenance values that identify one retrieved DICOM standard edition."""

    edition: str
    source_url_current: str
    edition_url_candidate: str
    edition_url_status: str
    retrieved_at_utc: str


def _find_cid_table(tables: list[list[list[str]]]) -> list[list[str]]:
    matches = [table for table in tables if table and tuple(table[0]) == _EXPECTED_HEADER]
    if len(matches) != 1:
        raise ValueError(
            "Expected exactly one CID 7050 table matching the known header; "
            f"found {len(matches)}"
        )
    return matches[0]


def _extract_page_edition(html: str) -> str:
    editions = set(_EDITION_PATTERN.findall(html))
    if len(editions) != 1:
        raise ValueError(
            "Expected exactly one PS3.16 edition in document release information; "
            f"found {len(editions)}"
        )
    return editions.pop()


def extract_inventory(html: str) -> tuple[list[str], dict[str, str], list[dict[str, Any]]]:
    """Extract raw CID 7050 entries and its page-provided context metadata."""
    parser = _CidPageParser()
    parser.feed(html)
    parser.close()
    table = _find_cid_table(parser.tables)
    header = table[0]
    missing_context_fields = [field for field in _CONTEXT_FIELDS if not parser.context_fields.get(field)]
    if missing_context_fields:
        raise ValueError(
            "CID 7050 page is missing context metadata: " + ", ".join(missing_context_fields)
        )

    codes: list[dict[str, Any]] = []
    for row_number, cells in enumerate(table[1:], start=1):
        if len(cells) != len(header):
            raise ValueError(
                f"CID 7050 row {row_number} has {len(cells)} cells; expected {len(header)}. "
                "The source table layout may have changed (for example, unsupported rowspan or colspan)."
            )
        scheme, code_value, code_meaning = cells
        if not scheme or not code_value.isdigit() or not code_meaning:
            raise ValueError(f"CID 7050 row {row_number} has invalid code fields")
        codes.append(
            {
                "stable_id": f"CID7050-{row_number:03d}",
                "source_table_row_number": row_number,
                "coding_scheme_designator": scheme,
                "code_value": code_value,
                "code_meaning": code_meaning,
            }
        )
    if not codes:
        raise ValueError("CID 7050 has no code rows")
    return header, {field: parser.context_fields[field] for field in _CONTEXT_FIELDS}, codes


def build_inventory_document(source: InventorySource, source_bytes: bytes) -> dict[str, Any]:
    """Return an auditable, source-derived CID 7050 inventory document."""
    html = source_bytes.decode("utf-8")
    page_edition = _extract_page_edition(html)
    if source.edition != page_edition:
        raise ValueError(
            f"--edition {source.edition!r} does not match the retrieved page edition {page_edition!r}"
        )
    if source.edition not in source.edition_url_candidate:
        raise ValueError("--edition-url-candidate must identify the supplied --edition")
    header, context_fields, codes = extract_inventory(html)
    codes_sha256 = hashlib.sha256(
        json.dumps(codes, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return {
        "schema_version": 1,
        "source": {
            "organization": "National Electrical Manufacturers Association (NEMA)",
            "dicom_edition": source.edition,
            "part": "PS3.16",
            "chapter_section": "Chapter B, CID 7050, Table CID 7050",
            "context_group": {"cid": 7050, **context_fields},
            "source_url_current": source.source_url_current,
            "edition_url_candidate": source.edition_url_candidate,
            "edition_url_status": source.edition_url_status,
            "retrieved_at_utc": source.retrieved_at_utc,
            "content_sha256": hashlib.sha256(source_bytes).hexdigest(),
            "content_bytes": len(source_bytes),
            "content_fingerprint_method": "sha256 of retrieved HTML bytes",
        },
        "extraction": {
            "script": "scripts/build_ps316_cid7050_inventory.py",
            "table_header": header,
            "row_count": len(codes),
            "codes_sha256": codes_sha256,
            "interpretation_note": (
                "Raw CID 7050 code values and meanings only. This inventory does not assert "
                "that any application behavior applies the profile or an option."
            ),
        },
        "codes": codes,
    }


def _validate_utc_timestamp(value: str) -> None:
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("--retrieved-at-utc must be an ISO-8601 timestamp") from exc
    if not value.endswith("Z"):
        raise ValueError("--retrieved-at-utc must use UTC and end in 'Z'")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True, help="Retrieved CID 7050 HTML file")
    parser.add_argument("--output", type=Path, required=True, help="Inventory JSON output path")
    parser.add_argument("--edition", required=True, help="DICOM edition identified by the retrieved page")
    parser.add_argument("--retrieved-at-utc", required=True, help="ISO-8601 retrieval timestamp")
    parser.add_argument(
        "--source-url-current",
        default="https://dicom.nema.org/medical/dicom/current/output/chtml/part16/sect_CID_7050.html",
    )
    parser.add_argument(
        "--edition-url-candidate",
        required=True,
        help="Expected edition-specific URL, retained even if the publisher has not exposed it",
    )
    parser.add_argument(
        "--edition-url-status",
        required=True,
        help="Retrieval result for --edition-url-candidate (for example, 'not published (HTTP 404)')",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    try:
        _validate_utc_timestamp(args.retrieved_at_utc)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    document = build_inventory_document(
        InventorySource(
            edition=args.edition,
            source_url_current=args.source_url_current,
            edition_url_candidate=args.edition_url_candidate,
            edition_url_status=args.edition_url_status,
            retrieved_at_utc=args.retrieved_at_utc,
        ),
        args.input.read_bytes(),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(document, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
