#!/usr/bin/env python3
"""
Build the offline documentation bundle shipped inside frozen executables.

Release-time use: run this script before PyInstaller so the freshly built
site is staged under ``resources/help/docs/``. The existing
``('resources', 'resources')`` datas entry in ``DICOMViewerV3.spec`` then
bundles the pages into the frozen app with no spec changes, where the
in-app Help dialogs resolve them via ``resources/help/``.

``zensical build`` supports ``--strict`` and ``--config-file/-f`` but not a
``--site-dir`` flag, so this script builds normally to ``site/`` and then
copies that tree into ``resources/help/docs/`` (cleaned first, so stale
pages cannot linger).

Usage (from repository root):
    python scripts/build_offline_docs.py

Exit code: 0 when the strict build succeeds and every ``mkdocs.yml`` nav
target is present in the output; non-zero otherwise (prints details).
The script fails loudly on any strict-build warning.

Inputs: ``user-docs/`` sources plus ``mkdocs.yml``; ``zensical`` importable
under the running interpreter (``python -m zensical``), or a ``zensical``
executable on ``PATH`` as fallback.
Outputs: ``site/`` (normal build output, gitignored) and
``resources/help/docs/`` (generated bundle, gitignored).
Requirements: Python 3.10+ (zensical declares ``requires-python >= 3.10``);
zensical (see ``requirements-dev.txt`` pin).
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path

# Nav entries name Markdown sources (e.g. ``- Home: index.md``); the .md
# suffix match is enough to enumerate the expected pages without a YAML
# dependency.
NAV_SOURCE_PATTERN = re.compile(r"([A-Za-z0-9_-]+\.md)")


def find_zensical_command() -> list[str]:
    """Locate zensical for the running interpreter first, ``PATH`` second.

    Callers (launchers, CI) install the pinned zensical into an environment
    and invoke this script with that environment's python, so
    ``sys.executable -m zensical`` is the version they mean; a global binary
    on ``PATH`` may be any version and is only a fallback.
    """
    probe = subprocess.run(
        [sys.executable, "-m", "zensical", "--version"],
        capture_output=True,
        text=True,
    )
    if probe.returncode == 0:
        return [sys.executable, "-m", "zensical"]
    on_path = shutil.which("zensical")
    if on_path:
        return [on_path]
    print(
        "error: no 'zensical' on PATH and "
        f"'{sys.executable} -m zensical' is not usable "
        "(install the requirements-dev.txt zensical pin)",
        file=sys.stderr,
    )
    raise SystemExit(1)


def nav_sources(repo_root: Path) -> list[str]:
    """Return the ``.md`` sources listed under ``nav:`` in ``mkdocs.yml``."""
    text = (repo_root / "mkdocs.yml").read_text(encoding="utf-8")
    nav_start = text.find("nav:")
    if nav_start < 0:
        return []
    return NAV_SOURCE_PATTERN.findall(text[nav_start:])


def expected_output_relatives(sources: list[str]) -> list[str]:
    """Map each nav ``.md`` source to its built HTML path (descriptive label).

    ``use_directory_urls: false`` is pinned in ``mkdocs.yml``, so the offline
    build emits flat ``FOO.html`` (``index.md`` as ``index.html``); the
    directory-URL form is accepted defensively in case a builder default
    ever changes.
    """
    relatives: list[str] = []
    for source in sources:
        stem = source[: -len(".md")]
        if stem.lower() == "index":
            relatives.append("index.html")
        else:
            relatives.append(f"{stem}.html")
    return relatives


def page_present(output_dir: Path, relative: str) -> bool:
    """True when a built page exists in flat or directory-URL form."""
    if (output_dir / relative).is_file():
        return True
    if relative.endswith(".html") and relative != "index.html":
        directory = output_dir / relative[: -len(".html")] / "index.html"
        return directory.is_file()
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parent.parent,
        help="Repository root (default: parent of scripts/).",
    )
    args = parser.parse_args()
    repo_root: Path = args.root.resolve()

    mkdocs_yml = repo_root / "mkdocs.yml"
    if not mkdocs_yml.is_file():
        print("error: mkdocs.yml was not found under the repository root", file=sys.stderr)
        return 1

    zensical = find_zensical_command()

    version_proc = subprocess.run(
        [*zensical, "--version"], capture_output=True, text=True, cwd=repo_root
    )
    zensical_version = (
        (version_proc.stdout or version_proc.stderr).strip().splitlines()
    )
    version_label = zensical_version[0] if zensical_version else "unknown"

    build = subprocess.run(
        [*zensical, "build", "--strict"], cwd=repo_root
    )
    if build.returncode != 0:
        print(
            f"error: 'zensical build --strict' failed (exit {build.returncode}); "
            "offline bundle not staged",
            file=sys.stderr,
        )
        return build.returncode or 1

    site_dir = repo_root / "site"
    if not (site_dir / "index.html").is_file():
        print("error: site/index.html missing after a successful build", file=sys.stderr)
        return 1

    output_dir = repo_root / "resources" / "help" / "docs"
    if output_dir.exists():
        shutil.rmtree(output_dir)
    shutil.copytree(site_dir, output_dir)

    sources = nav_sources(repo_root)
    expected = expected_output_relatives(sources)
    missing = [rel for rel in expected if not page_present(output_dir, rel)]
    if missing:
        print("error: built bundle is missing expected pages:", file=sys.stderr)
        for rel in missing:
            print(f"  {rel}", file=sys.stderr)
        return 1

    page_count = sum(1 for _ in output_dir.rglob("*.html"))
    # The output path is fixed by design, so print the literal instead of the
    # Path variable (the privacy gate treats `*_dir` names as sensitive).
    print(
        f"OK: zensical {version_label} built {len(expected)} nav page(s) "
        f"({page_count} HTML files total) into resources/help/docs/."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
