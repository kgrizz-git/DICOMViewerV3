"""
Stage 1 pylinac spike script for ACR CT datasets.

Usage:
    python scripts/spike_pylinac_acrct.py --folder "C:/path/to/acr_ct_folder"
    python scripts/spike_pylinac_acrct.py --folder "C:/path/to/acr_ct_folder" \\
        --dump-json tmp/acr_ct_results_data.json

Copy reviewed dumps into tests/fixtures/qa/ before commit (see tests/fixtures/qa/README.md).

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
    from scripts.pylinac_spike_common import redact_paths_in_value, results_data_as_dict
except ModuleNotFoundError:
    import privacy_console  # pyright: ignore[reportImplicitRelativeImport]
    import pylinac_spike_common  # pyright: ignore[reportImplicitRelativeImport]

    print_redacted = privacy_console.print_redacted
    redact_paths_in_value = pylinac_spike_common.redact_paths_in_value
    results_data_as_dict = pylinac_spike_common.results_data_as_dict

# Match the GUI runner: use viewer subclass (relaxed image index bounds).
_SRC_ROOT = Path(__file__).resolve().parents[1] / "src"
if str(_SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(_SRC_ROOT))

from utils.privacy.safe_storage import (
    assert_safe_internal_path,
    ensure_private_directory,
)


def _jsonable(value: Any) -> Any:
    """Convert pylinac output to JSON-friendly values (console preview)."""
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
    parser.add_argument(
        "--dump-json",
        default="",
        help="Write redacted results_data(as_dict=True) JSON to this path (Phase 0 fixture).",
    )
    args = parser.parse_args()

    folder = Path(args.folder).expanduser().resolve()
    if not folder.exists() or not folder.is_dir():
        print_redacted(f"Folder not found: {folder}")
        return 2

    try:
        import pylinac  # pyright: ignore[reportMissingTypeStubs]

        from qa.pylinac_extent_subclasses import (  # type: ignore[import-not-found]
            ACRCTForViewer,
        )
    except Exception as exc:
        print_redacted(f"Failed to import pylinac / viewer subclass: {exc}")
        return 3

    print_redacted(f"Running ACRCTForViewer on: {folder}")
    print(f"pylinac version: {getattr(pylinac, '__version__', 'unknown')}")

    try:
        analyzer = ACRCTForViewer.from_folder(str(folder))  # pyright: ignore[reportAttributeAccessIssue]
        analyzer.analyze()
        payload = redact_paths_in_value(results_data_as_dict(analyzer))
        print_redacted(_jsonable(payload))
    except Exception as exc:
        print_redacted(f"Analysis failed: {exc}")
        return 4

    if args.dump_json:
        try:
            from scripts.pylinac_spike_common import write_redacted_results_dump
        except ModuleNotFoundError:
            import pylinac_spike_common  # pyright: ignore[reportImplicitRelativeImport]

            write_redacted_results_dump = pylinac_spike_common.write_redacted_results_dump
        try:
            dump_path = assert_safe_internal_path(
                Path(args.dump_json),
                source_root=_SRC_ROOT.parent,
            )
            written = write_redacted_results_dump(analyzer, dump_path)
            print_redacted(f"Wrote redacted results_data dump: {written}")
        except Exception as exc:
            print_redacted(f"JSON dump failed: {exc}")
            return 6

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
