#!/usr/bin/env python3
"""Build a source-derived PS3.15 Table E.1-1 inventory from Annex E HTML.

The input must be a locally retained copy of an official DICOM PS3.15 Annex E
page.  The script deliberately does not download standards content: callers
must record their retrieval separately and pass the resulting file explicitly.
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

_TAG_PATTERN = re.compile(
    r"^\((?:[0-9A-F]{4}|[0-9A-F]{2}xx|xxxx|gggg),(?:[0-9A-F]{4}|[0-9A-F]{2}xx|xxxx|eeee)\)(?: .+)?$",
    re.IGNORECASE,
)
_EXPECTED_HEADER = (
    "Attribute Name",
    "Tag",
    "Retd. (from PS3.6)",
    "In Std. Comp. IOD (from PS3.3)",
    "Basic Prof.",
)


def _normalise_text(value: str) -> str:
    without_format_controls = "".join(
        character for character in value if unicodedata.category(character) != "Cf"
    )
    return " ".join(without_format_controls.split())


class _TableParser(HTMLParser):
    """Minimal HTML-table parser for the stable DocBook HTML table structure."""

    def __init__(self) -> None:
        super().__init__()
        self.tables: list[list[list[str]]] = []
        self._table: list[list[str]] | None = None
        self._row: list[str] | None = None
        self._cell: list[str] | None = None
        self._ignored_content_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style"}:
            self._ignored_content_depth += 1
            return
        del attrs
        if tag == "table":
            self._table = []
        elif tag == "tr" and self._table is not None:
            self._row = []
        elif tag in {"td", "th"} and self._row is not None:
            self._cell = []

    def handle_data(self, data: str) -> None:
        if self._cell is not None and self._ignored_content_depth == 0:
            self._cell.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style"} and self._ignored_content_depth:
            self._ignored_content_depth -= 1
        elif tag in {"td", "th"} and self._cell is not None and self._row is not None:
            self._row.append(_normalise_text("".join(self._cell)))
            self._cell = None
        elif tag == "tr" and self._row is not None and self._table is not None:
            self._table.append(self._row)
            self._row = None
        elif tag == "table" and self._table is not None:
            self.tables.append(self._table)
            self._table = None


@dataclass(frozen=True)
class InventorySource:
    """Provenance values that identify one retrieved standard edition."""

    edition: str
    source_url_current: str
    edition_url_candidate: str
    edition_url_status: str
    retrieved_at_utc: str


def _find_e1_table(tables: list[list[list[str]]]) -> list[list[str]]:
    matches = [
        table
        for table in tables
        if table and tuple(table[0][: len(_EXPECTED_HEADER)]) == _EXPECTED_HEADER
    ]
    if len(matches) != 1:
        raise ValueError(
            "Expected exactly one PS3.15 Table E.1-1 matching the known header; "
            f"found {len(matches)}"
        )
    return matches[0]


def extract_inventory(html: str) -> tuple[list[str], list[dict[str, Any]]]:
    """Extract Table E.1-1 rows without interpreting its IOD-dependent actions."""
    parser = _TableParser()
    parser.feed(html)
    parser.close()
    table = _find_e1_table(parser.tables)
    header = table[0]
    if len(header) < len(_EXPECTED_HEADER):
        raise ValueError("PS3.15 Table E.1-1 header is unexpectedly short")

    rows: list[dict[str, Any]] = []
    for row_number, cells in enumerate(table[1:], start=1):
        if len(cells) != len(header):
            raise ValueError(
                f"PS3.15 Table E.1-1 row {row_number} has {len(cells)} cells; "
                f"expected {len(header)}. The source table layout may have changed "
                "(for example, unsupported rowspan or colspan)."
            )
        tag = cells[1]
        if not _TAG_PATTERN.fullmatch(tag):
            raise ValueError(f"PS3.15 Table E.1-1 row {row_number} has invalid DICOM tag pattern {tag!r}")
        values = dict(zip(header, cells, strict=True))
        rows.append(
            {
                "stable_id": f"E1-T-{row_number:03d}",
                "source_table_row_number": row_number,
                "attribute_name": values.pop("Attribute Name"),
                "tag_gggg_eeee": values.pop("Tag"),
                "retired_from_ps3_6": values.pop("Retd. (from PS3.6)"),
                "in_standard_composite_iod": values.pop("In Std. Comp. IOD (from PS3.3)"),
                "action_code_base": values.pop("Basic Prof."),
                "option_overrides": values,
            }
        )
    if not rows:
        raise ValueError("PS3.15 Table E.1-1 has no data rows")
    return header, rows


def build_inventory_document(source: InventorySource, source_bytes: bytes) -> dict[str, Any]:
    """Return an auditable, source-derived inventory document."""
    header, rows = extract_inventory(source_bytes.decode("utf-8"))
    requirements_sha256 = hashlib.sha256(
        json.dumps(rows, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return {
        "schema_version": 1,
        "source": {
            "organization": "National Electrical Manufacturers Association (NEMA)",
            "dicom_edition": source.edition,
            "part": "PS3.15",
            "chapter_section": "Annex E, Table E.1-1",
            "source_url_current": source.source_url_current,
            "edition_url_candidate": source.edition_url_candidate,
            "edition_url_status": source.edition_url_status,
            "retrieved_at_utc": source.retrieved_at_utc,
            "content_sha256": hashlib.sha256(source_bytes).hexdigest(),
            "content_bytes": len(source_bytes),
            "content_fingerprint_method": "sha256 of retrieved HTML bytes",
        },
        "extraction": {
            "script": "scripts/build_ps315_e1_inventory.py",
            "table_header": header,
            "row_count": len(rows),
            "requirements_sha256": requirements_sha256,
            "interpretation_note": (
                "Raw Table E.1-1 values only. IOD Type and option-dependent action "
                "resolution remains a separate assessment step."
            ),
        },
        "requirements": rows,
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
    parser.add_argument("--input", type=Path, required=True, help="Retrieved Annex E HTML file")
    parser.add_argument("--output", type=Path, required=True, help="Inventory JSON output path")
    parser.add_argument("--edition", required=True, help="DICOM edition identified by the retrieved page")
    parser.add_argument("--retrieved-at-utc", required=True, help="ISO-8601 retrieval timestamp")
    parser.add_argument(
        "--source-url-current",
        default="https://dicom.nema.org/medical/dicom/current/output/chtml/part15/chapter_E.html",
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
