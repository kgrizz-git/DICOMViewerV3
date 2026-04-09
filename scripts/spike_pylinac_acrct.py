"""
Stage 1 pylinac spike script for ACR CT datasets.

Usage:
    python scripts/spike_pylinac_acrct.py --folder "C:/path/to/acr_ct_folder" [--pdf-out "C:/out/report.pdf"]

This script is intentionally minimal and runs outside the Qt app so dependency
and API compatibility can be validated before wiring deeper UI flows.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

# Match the GUI runner: use viewer subclass (relaxed image index bounds).
_SRC_ROOT = Path(__file__).resolve().parents[1] / "src"
if str(_SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(_SRC_ROOT))


def _jsonable(value: Any) -> Any:
    """Convert pylinac output to JSON-friendly values."""
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    return str(value)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run an ACRCT pylinac spike.")
    parser.add_argument("--folder", required=True, help="Folder containing ACR CT DICOM files.")
    parser.add_argument("--pdf-out", default="", help="Optional output PDF report path.")
    args = parser.parse_args()

    folder = Path(args.folder).expanduser().resolve()
    if not folder.exists() or not folder.is_dir():
        print(f"Folder not found: {folder}")
        return 2

    try:
        import pylinac  # type: ignore[import-not-found]

        from qa.pylinac_extent_subclasses import ACRCTForViewer  # type: ignore[import-not-found]
    except Exception as exc:
        print(f"Failed to import pylinac / viewer subclass: {exc}")
        return 3

    print(f"Running ACRCTForViewer on: {folder}")
    print(f"pylinac version: {getattr(pylinac, '__version__', 'unknown')}")

    try:
        analyzer = ACRCTForViewer.from_folder(str(folder))
        analyzer.analyze()
        results_data = analyzer.results_data()
        payload = _jsonable(results_data if isinstance(results_data, dict) else {"results_data": results_data})
        print(json.dumps(payload, indent=2))
    except Exception as exc:
        print(f"Analysis failed: {exc}")
        return 4

    if args.pdf_out:
        try:
            analyzer.publish_pdf(args.pdf_out)
            print(f"PDF written: {args.pdf_out}")
        except Exception as exc:
            print(f"PDF generation failed: {exc}")
            return 5

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

