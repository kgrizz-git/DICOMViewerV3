#!/usr/bin/env bash
# Report disk usage for a PyInstaller macOS .app bundle (same idea as CI "Log distribution sizes").
# Usage: from repo root after `pyinstaller DICOMViewerV3.spec`, run:
#   bash scripts/report-macos-bundle-size.sh
# Optional first argument: path to the .app (default: dist/DICOMViewerV3.app).

set -euo pipefail

APP="${1:-dist/DICOMViewerV3.app}"

if [[ ! -d "$APP" ]]; then
  echo "error: not a directory: $APP" >&2
  echo "Build first (e.g. pyinstaller DICOMViewerV3.spec) or pass the .app path." >&2
  exit 1
fi

echo "=== Total ==="
du -sh "$APP"

if [[ -d "$APP/Contents" ]]; then
  echo "=== Contents/* (sorted by size) ==="
  du -sh "$APP/Contents"/* 2>/dev/null | sort -h || true
fi
if [[ -d "$APP/Contents/MacOS" ]]; then
  echo "=== Contents/MacOS/* (sorted by size) ==="
  du -sh "$APP/Contents/MacOS"/* 2>/dev/null | sort -h || true
fi
if [[ -d "$APP/Contents/Frameworks" ]]; then
  echo "=== Top 10 under Frameworks/ (largest first) ==="
  du -sh "$APP/Contents/Frameworks"/* 2>/dev/null | sort -hr | head -10 || true
fi
if [[ -d "$APP/Contents/Resources" ]]; then
  echo "=== Top 10 under Resources/ (largest first) ==="
  du -sh "$APP/Contents/Resources"/* 2>/dev/null | sort -hr | head -10 || true
fi
