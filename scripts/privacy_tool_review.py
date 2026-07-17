#!/usr/bin/env python3
"""Run local-only privacy scanner and asset-review workflows.

Statuses and exit codes: CLEAN=0, FINDINGS=1, ERROR=2, SKIP=3. A SKIP is
explicitly not a passing security result. Scanner output is reduced to counts
and categories; matched values, OCR text, image crops, and raw reports are
deleted from protected temporary storage after every run. Media admission still
requires a human visual review before separately updating the reviewed manifest.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.privacy_tools.common import PrivacyToolResult, ToolStatus
from scripts.privacy_tools.dicom import run_dicom_review
from scripts.privacy_tools.hounddog import run_hounddog
from scripts.privacy_tools.media import run_media_review
from scripts.privacy_tools.phiscan import run_phiscan

EXIT_CODES = {
    ToolStatus.CLEAN: 0,
    ToolStatus.FINDINGS: 1,
    ToolStatus.ERROR: 2,
    ToolStatus.SKIP: 3,
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    hounddog_parser = subparsers.add_parser(
        "hounddog", help="Local advisory source/sink dataflow scan"
    )
    hounddog_parser.add_argument("--timeout", type=float, default=300)
    phiscan_parser = subparsers.add_parser(
        "phiscan", help="Scan only staged data-like Git blobs"
    )
    phiscan_parser.add_argument("--timeout", type=float, default=300)
    media_parser = subparsers.add_parser(
        "media", help="Review metadata and OCR; human confirmation remains required"
    )
    media_parser.add_argument("path", type=Path)
    media_parser.add_argument("--timeout", type=float, default=300)
    dicom_parser = subparsers.add_parser(
        "dicom", help="On-demand DICOM tag and pixel review"
    )
    dicom_parser.add_argument("path", type=Path)
    dicom_parser.add_argument("--timeout", type=float, default=600)
    args = parser.parse_args()

    result: PrivacyToolResult
    if args.command == "hounddog":
        result = run_hounddog(
            ROOT,
            config_path=ROOT / "security" / "hounddog-project.json",
            timeout=args.timeout,
        )
    elif args.command == "phiscan":
        result = run_phiscan(ROOT, timeout=args.timeout)
    elif args.command == "media":
        result = run_media_review(args.path, timeout=args.timeout)
    else:
        result = run_dicom_review(args.path, timeout=args.timeout)
    print(result.summary())
    return EXIT_CODES[result.status]


if __name__ == "__main__":
    raise SystemExit(main())
