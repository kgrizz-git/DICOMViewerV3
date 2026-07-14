#!/usr/bin/env python3
"""
Verify relative Markdown links under user-docs/ (and dev-docs/README.md).

Scans inline links of the form [text](url). Skips http(s), mailto, and bare
fragment-only targets. Resolves each relative URL against the source file's
directory and fails if the target path does not exist.

Usage (from repository root):
    python scripts/check_user_docs_links.py

Exit code: 0 if all links resolve, 1 if any are broken (prints details).

Inputs: Markdown files on disk under the repo.
Outputs: stdout messages; non-zero exit on failure.
Requirements: Python 3.9+ standard library only.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# [any](path) — path may include #anchor; exclude images ![alt](url) by requiring [ not preceded by !
LINK_PATTERN = re.compile(r"(?<!!)\[([^\]]*)\]\(([^)]+)\)")


def iter_markdown_files(repo_root: Path) -> list[Path]:
    """Markdown files to validate (user-facing + dev-docs index)."""
    paths: list[Path] = []
    user_docs = repo_root / "user-docs"
    if user_docs.is_dir():
        paths.extend(sorted(user_docs.rglob("*.md")))
    readme = repo_root / "dev-docs" / "README.md"
    if readme.is_file():
        paths.append(readme)
    return paths


def split_anchor(url: str) -> tuple[str, str]:
    if "#" in url:
        base, _, frag = url.partition("#")
        return base, frag
    return url, ""


def check_file(md_path: Path, repo_root: Path) -> list[str]:
    """Return list of error messages for broken links in one file."""
    errors: list[str] = []
    text = md_path.read_text(encoding="utf-8")
    base_dir = md_path.parent

    for _label, raw_url in LINK_PATTERN.findall(text):
        url = raw_url.strip()
        if not url or url.startswith(("#", "http://", "https://", "mailto:")):
            continue
        path_part, _anchor = split_anchor(url)
        if not path_part:
            continue
        target = (base_dir / path_part).resolve()
        try:
            target.relative_to(repo_root.resolve())
        except ValueError:
            errors.append(f"{md_path.relative_to(repo_root)}: link escapes repo: {raw_url!r}")
            continue
        if not target.exists():
            errors.append(
                f"{md_path.relative_to(repo_root)}: broken link {raw_url!r} -> {target.relative_to(repo_root)}"
            )
    return errors


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

    if not (repo_root / "user-docs").is_dir():
        print(f"error: user-docs/ not found under {repo_root}", file=sys.stderr)
        return 1

    all_errors: list[str] = []
    for md in iter_markdown_files(repo_root):
        all_errors.extend(check_file(md, repo_root))

    if all_errors:
        print("Broken relative Markdown links:", file=sys.stderr)
        for line in all_errors:
            print(f"  {line}", file=sys.stderr)
        return 1

    n_files = len(iter_markdown_files(repo_root))
    print(f"OK: checked links in {n_files} Markdown file(s) under user-docs/ and dev-docs/README.md.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
