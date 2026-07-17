#!/usr/bin/env python3
"""Blocking redacted Gitleaks scan of the Git index."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.gitleaks_privacy_scan import main

if __name__ == "__main__":
    raise SystemExit(main(["staged", *sys.argv[1:]]))
