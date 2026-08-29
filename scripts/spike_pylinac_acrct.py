"""
Stage 1 pylinac spike script for ACR CT datasets.

Usage (repo-relative folder; never commit the folder or dump paths):

    python scripts/spike_pylinac_acrct.py --folder sample-DICOM-gitignored/CT-phantoms/<series>
    python scripts/spike_pylinac_acrct.py --folder sample-DICOM-gitignored/CT-phantoms/<series> \\
        --dump-json ~/private-qa-dumps/acr_ct_results_data.json

Dump path must be outside the source checkout (assert_safe_internal_path).
Copy reviewed dumps into tests/fixtures/qa/ before commit (see tests/fixtures/qa/README.md).
Console output never includes the folder or dump destination path.

This script is intentionally minimal and runs outside the Qt app so dependency
and API compatibility can be validated before wiring deeper UI flows.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

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
        print_redacted("Folder not found")
        return 2

    try:
        import pylinac  # pyright: ignore[reportMissingTypeStubs]

        from qa.pylinac_extent_subclasses import (  # type: ignore[import-not-found]
            ACRCTForViewer,
        )
    except Exception as exc:
        print_redacted(f"Failed to import pylinac / viewer subclass: {exc}")
        return 3

    print_redacted("Running ACRCTForViewer on a local folder")
    print(f"pylinac version: {getattr(pylinac, '__version__', 'unknown')}")

    try:
        analyzer = ACRCTForViewer.from_folder(str(folder))  # pyright: ignore[reportAttributeAccessIssue]
        analyzer.analyze()
        print_redacted("Analysis succeeded")
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
            write_redacted_results_dump(analyzer, dump_path)
            print_redacted("Wrote redacted results_data dump")
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
