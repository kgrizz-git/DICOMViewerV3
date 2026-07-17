"""
Stage 1 pylinac spike script for ACR CT datasets.

Usage:
    python scripts/spike_pylinac_acrct.py --folder "C:/path/to/acr_ct_folder" [--pdf-out "C:/out/report.pdf"]

This script is intentionally minimal and runs outside the Qt app so dependency
and API compatibility can be validated before wiring deeper UI flows.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

try:
    from scripts.privacy_console import print_redacted
except ModuleNotFoundError:
    import privacy_console  # pyright: ignore[reportImplicitRelativeImport]

    print_redacted = privacy_console.print_redacted

# Match the GUI runner: use viewer subclass (relaxed image index bounds).
_SRC_ROOT = Path(__file__).resolve().parents[1] / "src"
if str(_SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(_SRC_ROOT))

from utils.privacy.safe_storage import (
    assert_safe_internal_path,
    ensure_private_directory,
)


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
        print_redacted(f"Folder not found: {folder}")
        return 2

    try:
        import pylinac  # pyright: ignore[reportMissingTypeStubs]

        from qa.pylinac_extent_subclasses import (
            ACRCTForViewer,  # type: ignore[import-not-found]
        )
    except Exception as exc:
        print_redacted(f"Failed to import pylinac / viewer subclass: {exc}")
        return 3

    print_redacted(f"Running ACRCTForViewer on: {folder}")
    print(f"pylinac version: {getattr(pylinac, '__version__', 'unknown')}")

    try:
        analyzer = ACRCTForViewer.from_folder(str(folder))  # pyright: ignore[reportAttributeAccessIssue]
        analyzer.analyze()
        results_data = analyzer.results_data()
        payload = _jsonable(results_data if isinstance(results_data, dict) else {"results_data": results_data})
        print_redacted(payload)
    except Exception as exc:
        print_redacted(f"Analysis failed: {exc}")
        return 4

    if args.pdf_out:
        try:
            pdf_path = assert_safe_internal_path(Path(args.pdf_out), source_root=_SRC_ROOT.parent)
            ensure_private_directory(pdf_path.parent)
            analyzer.publish_pdf(str(pdf_path))
            print("PDF written to the explicitly selected protected directory")
        except Exception as exc:
            print_redacted(f"PDF generation failed: {exc}")
            return 5

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
