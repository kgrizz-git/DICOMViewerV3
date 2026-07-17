#!/usr/bin/env python3
"""Run local advisory privacy tools only when staged content warrants them.

This command is intentionally non-blocking.  It scans exact Git-index blobs,
not possibly different working-tree files, and never prints repository paths or
matched values.  The blocking artifact/manifest gate remains authoritative.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.privacy_tools.common import protected_workspace

DATA_SUFFIXES = frozenset(
    {".cfg", ".csv", ".fhir", ".hl7", ".html", ".ini", ".json", ".md", ".ndjson", ".tsv", ".txt", ".xml", ".yaml", ".yml"}
)
DATA_PREFIXES = ("data/", "resources/", "tests/data/", "tests/fixtures/")
DICOM_SUFFIXES = frozenset({".dcm", ".dicom", ".ima"})
OCR_SUFFIXES = frozenset({".bmp", ".jpeg", ".jpg", ".png", ".tif", ".tiff"})


def staged_paths(root: Path) -> list[str]:
    completed = subprocess.run(
        ["git", "diff", "--cached", "--name-only", "-z", "--diff-filter=ACM"],
        cwd=root,
        capture_output=True,
        check=True,
    )
    return [
        item.decode("utf-8", errors="surrogateescape")
        for item in completed.stdout.split(b"\0")
        if item
    ]


def isolated_python(root: Path) -> Path | None:
    for candidate in (
        root / ".phi-tools" / "Scripts" / "python.exe",
        root / ".phi-tools" / "bin" / "python",
    ):
        if candidate.is_file():
            return candidate
    return None


def _run_wrapper(python: Path, *arguments: str) -> None:
    completed = subprocess.run(
        [str(python), str(ROOT / "scripts" / "privacy_tool_review.py"), *arguments],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
        timeout=600,
    )
    summary = completed.stdout.strip().splitlines()
    if summary:
        print(summary[-1])
    elif completed.returncode:
        print("privacy-review ERROR scanned=0 findings=0 categories=none reason=wrapper-error")


def materialize_index_blob(root: Path, path: str, destination: Path) -> bool:
    completed = subprocess.run(
        ["git", "show", f":{path}"],
        cwd=root,
        capture_output=True,
        check=False,
    )
    if completed.returncode:
        return False
    destination.write_bytes(completed.stdout)
    destination.chmod(0o600)
    return True


def main() -> int:
    try:
        paths = staged_paths(ROOT)
    except (OSError, subprocess.SubprocessError):
        print("privacy-review ERROR scanned=0 findings=0 categories=none reason=git-index-error")
        return 0

    phi_python = isolated_python(ROOT)
    needs_phiscan = any(
        path.startswith(DATA_PREFIXES) and Path(path).suffix.lower() in DATA_SUFFIXES
        for path in paths
    )
    if needs_phiscan:
        if phi_python is None:
            print("phiscan SKIP scanned=0 findings=0 categories=none reason=isolated-environment-missing")
        else:
            _run_wrapper(phi_python, "phiscan")

    media_paths = [path for path in paths if Path(path).suffix.lower() in OCR_SUFFIXES]
    dicom_paths = [path for path in paths if Path(path).suffix.lower() in DICOM_SUFFIXES]
    if not media_paths and not dicom_paths:
        return 0

    with protected_workspace("dvv-staged-review-") as workspace:
        for index, path in enumerate(media_paths):
            target = workspace / f"media-{index:04d}{Path(path).suffix.lower()}"
            if materialize_index_blob(ROOT, path, target):
                _run_wrapper(phi_python or Path(sys.executable), "media", str(target))
            else:
                print("media-review ERROR scanned=0 findings=0 categories=none reason=git-index-error")
        for index, path in enumerate(dicom_paths):
            if phi_python is None:
                print("dicom-review SKIP scanned=0 findings=0 categories=none reason=isolated-environment-missing")
                break
            target = workspace / f"dicom-{index:04d}{Path(path).suffix.lower()}"
            if materialize_index_blob(ROOT, path, target):
                _run_wrapper(phi_python, "dicom", str(target))
            else:
                print("dicom-review ERROR scanned=0 findings=0 categories=none reason=git-index-error")
    return 0


if __name__ == "__main__":
    os.environ.setdefault("PYTHONUTF8", "1")
    raise SystemExit(main())
