"""
Stage 1 pylinac spike script for ACR MRI Large datasets.

Usage:
    python scripts/spike_pylinac_acrmri.py --folder "/path/to/acr_mri_folder"
    python scripts/spike_pylinac_acrmri.py --folder "/path/to/acr_mri_folder" \\
        --dump-json tmp/acr_mri_results_data.json

Copy reviewed dumps into tests/fixtures/qa/ before commit (see tests/fixtures/qa/README.md).

Runs outside the Qt app. Use ``--dump-json`` to emit a redacted ``results_data``
fixture for Phase 0 (maintainer-only; requires local gitignored phantom data).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

try:
    from scripts.privacy_console import print_redacted
    from scripts.pylinac_spike_common import write_redacted_results_dump
except ModuleNotFoundError:
    import privacy_console  # pyright: ignore[reportImplicitRelativeImport]
    import pylinac_spike_common  # pyright: ignore[reportImplicitRelativeImport]

    print_redacted = privacy_console.print_redacted
    write_redacted_results_dump = pylinac_spike_common.write_redacted_results_dump

_SRC_ROOT = Path(__file__).resolve().parents[1] / "src"
if str(_SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(_SRC_ROOT))

from utils.privacy.safe_storage import (
    assert_safe_internal_path,
    ensure_private_directory,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run an ACR MRI Large pylinac spike.")
    parser.add_argument("--folder", required=True, help="Folder containing ACR MRI DICOM files.")
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
            ACRMRILargeForViewer,
        )
    except Exception as exc:
        print_redacted(f"Failed to import pylinac / viewer subclass: {exc}")
        return 3

    print_redacted(f"Running ACRMRILargeForViewer on: {folder}")
    print(f"pylinac version: {getattr(pylinac, '__version__', 'unknown')}")

    try:
        analyzer = ACRMRILargeForViewer.from_folder(str(folder))  # pyright: ignore[reportAttributeAccessIssue]
        analyzer.analyze()
    except Exception as exc:
        print_redacted(f"Analysis failed: {exc}")
        return 4

    if args.dump_json:
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
