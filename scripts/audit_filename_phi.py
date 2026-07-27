# python -m scripts.audit_filename_phi  (new, dev-only — not wired to hooks)
"""Audit existing tracked filenames for patient names and identifiers."""

from __future__ import annotations

import subprocess
import sys

from scripts.privacy_checks.names import PATIENT_IDENTIFIER_PATTERN, name_in_path


def main() -> int:
    files = subprocess.check_output(["git", "ls-files"], text=True).splitlines()
    hits = 0
    for path in files:
        reason = name_in_path(path)
        if reason:
            print(f"{path}: {reason}")  # privacy-check: allow[unsafe-print-argument] review=kgrizz-git
            hits += 1
            continue
        if PATIENT_IDENTIFIER_PATTERN.search(path):
            print(f"{path}: patient-identifier-in-path")  # privacy-check: allow[unsafe-print-argument] review=kgrizz-git
            hits += 1
    print(f"[audit] {hits} hit(s) across {len(files)} tracked files")
    return 1 if hits else 0


if __name__ == "__main__":
    sys.exit(main())
