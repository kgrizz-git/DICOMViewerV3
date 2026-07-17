#!/usr/bin/env python3
"""Explicitly sync the project dev venv, or check its requirements stamp.

Direnv calls ``--check`` only. That mode is local, fast, and network-free.
Running without ``--check`` is an explicit request to install
``requirements-dev.txt`` and record the exact tracked requirements hash.
"""

from __future__ import annotations

import argparse
import hashlib
import subprocess
import sys
from pathlib import Path

try:
    from scripts.privacy_console import print_redacted
except ModuleNotFoundError:
    from privacy_console import print_redacted

REQUIREMENT_FILES = ("requirements.txt", "requirements-dev.txt")
STAMP_NAME = ".requirements-dev.sha256"


def requirements_digest(repo_root: Path) -> str:
    """Hash the names and exact bytes of the dev environment inputs."""
    digest = hashlib.sha256()
    for relative in REQUIREMENT_FILES:
        path = repo_root / relative
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def project_venv(repo_root: Path, prefix: Path | None = None) -> Path | None:
    """Return the active project venv, rejecting global or unrelated Python."""
    active = (prefix or Path(sys.prefix)).resolve()
    for name in (".venv", "venv"):
        candidate = (repo_root / name).resolve()
        if active == candidate:
            return candidate
    return None


def stamp_matches(venv: Path, expected: str) -> bool:
    """Return whether the successful-sync stamp matches current requirements."""
    try:
        return (venv / STAMP_NAME).read_text(encoding="ascii").strip() == expected
    except OSError:
        return False


def write_stamp(venv: Path, digest: str) -> None:
    """Atomically record a successful explicit dependency sync."""
    temporary = venv / f"{STAMP_NAME}.tmp"
    temporary.write_text(f"{digest}\n", encoding="ascii")
    temporary.replace(venv / STAMP_NAME)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Only check the local requirements stamp; never install or use the network.",
    )
    args = parser.parse_args()
    repo_root = Path(__file__).resolve().parent.parent
    venv = project_venv(repo_root)
    if venv is None:
        print(
            "DICOM Viewer dependency check: activate this repository's .venv or venv.",
            file=sys.stderr,
        )
        return 1
    try:
        digest = requirements_digest(repo_root)
    except OSError as exc:
        print_redacted(f"DICOM Viewer dependency check failed: {exc}", file=sys.stderr)
        return 1
    if stamp_matches(venv, digest):
        return 0
    if args.check:
        print(
            "DICOM Viewer dependencies changed or are not recorded. "
            "Run: python scripts/sync_dev_environment.py",
            file=sys.stderr,
        )
        return 1

    print("Synchronizing the project development environment...")
    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", "-r", "requirements-dev.txt"],
        cwd=repo_root,
    )
    if result.returncode != 0:
        print("Dependency installation failed; the sync stamp was not updated.", file=sys.stderr)
        return result.returncode or 1
    try:
        write_stamp(venv, digest)
    except OSError as exc:
        print_redacted(f"Dependencies installed but the sync stamp failed: {exc}", file=sys.stderr)
        return 1
    print("Development dependencies are synchronized.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
