#!/usr/bin/env python3
"""
Verify documentation references resolve: relative Markdown links, and inline
code paths pointing into src/.

Covered files are user-docs/, the root README.md and ARCHITECTURE.md, AGENTS.md,
the top level of dev-docs/, and dev-docs/info/. dev-docs/plans/ is deliberately
excluded: completed and supporting plans are historical records that describe the
tree as it was when they were written, so link rot there is expected rather than a
defect.

Two checks run over those files:

1. **Relative Markdown links.** Scans inline links of the form [text](url). Skips
   http(s), mailto, and bare fragment-only targets. Resolves each relative URL
   against the source file's directory and fails if the target does not exist.
2. **Inline `src/...py` code paths.** A path written in backticks, such as
   `src/core/mpr_controller.py`, must exist. This catches the failure mode where a
   module moves between packages and prose that names it silently goes stale; a
   core/ to gui/ move left 17 such references wrong across the living docs before
   this check existed.

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
# `src/pkg/module.py` written as inline code. Only .py paths, so prose naming a
# directory or a glob is not treated as a claim about one exact file. Path
# segments may not contain dots, which keeps illustrative prose such as
# `src/...py` from being read as a claim that a file exists.
SRC_PATH_PATTERN = re.compile(r"`(src/(?:[A-Za-z0-9_-]+/)*[A-Za-z0-9_-]+\.py)`")


def iter_markdown_files(repo_root: Path) -> list[Path]:
    """Markdown files to validate (user docs plus the living developer docs)."""
    paths: list[Path] = []
    user_docs = repo_root / "user-docs"
    if user_docs.is_dir():
        paths.extend(sorted(user_docs.rglob("*.md")))
    # Living dev docs only. dev-docs/plans/ is history and is not checked.
    for subdir in ("dev-docs", "dev-docs/info"):
        directory = repo_root / subdir
        if directory.is_dir():
            paths.extend(sorted(directory.glob("*.md")))
    for rel in ("README.md", "ARCHITECTURE.md", "AGENTS.md"):
        candidate = repo_root / rel
        if candidate.is_file():
            paths.append(candidate)
    return sorted(set(paths))


def exists_with_exact_case(repo_root: Path, relative: str) -> bool:
    """True when ``relative`` names a file that exists with exactly this casing.

    ``Path.is_file()`` follows the filesystem, which is case-insensitive on macOS
    and Windows. A doc naming ``src/GUI/main_window.py`` would therefore pass the
    pre-commit hook on a developer's Mac and then fail the same check on Linux
    CI. Comparing each component against the real directory listing makes local
    and CI agree.
    """
    current = repo_root
    for part in Path(relative).parts:
        try:
            names = {entry.name for entry in current.iterdir()}
        except (NotADirectoryError, PermissionError, FileNotFoundError):
            return False
        if part not in names:
            return False
        current = current / part
    return current.is_file()


def check_src_paths(md_path: Path, repo_root: Path) -> list[str]:
    """Return errors for inline `src/....py` paths that do not exist."""
    errors: list[str] = []
    text = md_path.read_text(encoding="utf-8")
    for src_path in SRC_PATH_PATTERN.findall(text):
        if not exists_with_exact_case(repo_root, src_path):
            errors.append(
                f"{md_path.relative_to(repo_root)}: names a source file that does "
                f"not exist: {src_path!r}"
            )
    return errors


def split_anchor(url: str) -> tuple[str, str]:
    if "#" in url:
        base, _, frag = url.partition("#")
        return base, frag
    return url, ""


def check_file(md_path: Path, repo_root: Path, is_user_doc: bool = False) -> list[str]:
    """Return list of error messages for broken links in one file.

    When ``is_user_doc`` is True (the file lives under ``user-docs/``), links
    that resolve into ``dev-docs/plans/`` or ``dev-docs/TO_DO.md`` are rejected.
    Links into ``dev-docs/info/`` and other ``dev-docs/`` root-level files are
    allowed (they contain useful reference material for advanced users).
    """
    errors: list[str] = []
    text = md_path.read_text(encoding="utf-8")
    base_dir = md_path.parent
    dev_docs_root = repo_root / "dev-docs"

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
        if is_user_doc and target.is_relative_to(dev_docs_root.resolve()):
            rel = target.relative_to(dev_docs_root.resolve())
            if (rel.parts and rel.parts[0] == "plans") or rel == Path("TO_DO.md"):
                label = rel.parts[0] if rel.parts else "TO_DO.md"
                errors.append(
                    f"{md_path.relative_to(repo_root)}: user-docs must not link into dev-docs/{label}: {raw_url!r}"
                )
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
        print("error: user-docs/ was not found under the repository root", file=sys.stderr)
        return 1

    user_docs_root = repo_root / "user-docs"
    all_errors: list[str] = []
    for md in iter_markdown_files(repo_root):
        is_user_doc = md.is_relative_to(user_docs_root)
        all_errors.extend(check_file(md, repo_root, is_user_doc=is_user_doc))
        all_errors.extend(check_src_paths(md, repo_root))

    if all_errors:
        print("Broken documentation references:", file=sys.stderr)
        for line in all_errors:
            print(f"  {line}", file=sys.stderr)
        return 1

    n_files = len(iter_markdown_files(repo_root))
    print(
        f"OK: checked links and src/ code paths in {n_files} Markdown file(s) "
        "under user-docs/, the living dev-docs/, README.md, ARCHITECTURE.md, "
        "and AGENTS.md."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
