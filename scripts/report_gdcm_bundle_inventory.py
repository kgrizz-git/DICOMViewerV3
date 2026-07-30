"""Report a privacy-safe inventory of GDCM assets in a frozen application bundle.

Write the JSON report outside the checkout as release evidence. It deliberately
uses paths relative to the supplied bundle and does not infer licenses from file
names; the release/compliance owner must reconcile the result with the exact
wheel and upstream notice materials.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _relative_paths(bundle: Path) -> list[Path]:
    return sorted(
        path.relative_to(bundle)
        for path in bundle.rglob("*")
        if path.is_file()
        and (
            "gdcm" in path.name.lower()
            or "_gdcm" in path.relative_to(bundle).parts
        )
    )


def build_inventory(bundle: Path) -> dict[str, object]:
    """Return GDCM assets and potential removed-plugin paths with relative names only."""
    gdcm_assets = _relative_paths(bundle)
    all_files = [path.relative_to(bundle) for path in bundle.rglob("*") if path.is_file()]
    removed_plugin_paths = sorted(
        str(path)
        for path in all_files
        if "pylibjpeg_libjpeg" in str(path).lower()
        or "pylibjpeg-libjpeg" in str(path).lower()
    )
    other_libjpeg_paths = sorted(
        str(path)
        for path in all_files
        if path.name.lower().startswith("libjpeg") and "gdcm" not in path.name.lower()
    )
    return {
        "gdcm_assets": [
            {"path": str(path), "sha256": _sha256(bundle / path)} for path in gdcm_assets
        ],
        "pylibjpeg_libjpeg_paths": removed_plugin_paths,
        "other_libjpeg_paths_requiring_component_review": other_libjpeg_paths,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", type=Path, help="Frozen app bundle directory")
    args = parser.parse_args()
    bundle = args.bundle.resolve()
    if not bundle.is_dir():
        parser.error("bundle must be an existing directory")
    print(json.dumps(build_inventory(bundle), sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
