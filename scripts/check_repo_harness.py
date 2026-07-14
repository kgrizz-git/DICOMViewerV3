#!/usr/bin/env python3
"""
Validate repository harness documentation and structure.

Checks required harness files, AGENTS.md size/shape, TO_DO freshness metadata,
maintenance-log presence, plan paths referenced from TO_DO.md, and relative
links in harness markdown.
Optional ``--doc-garden`` prints a non-blocking documentation hygiene report.

Usage (from repository root):
    python scripts/check_repo_harness.py

Exit code: 0 if all checks pass, 1 otherwise.
"""

from __future__ import annotations

import argparse
import re
import sys
from datetime import date, datetime
from pathlib import Path

LINK_PATTERN = re.compile(r"(?<!!)\[([^\]]*)\]\(([^)]+)\)")
LAST_UPDATED_PATTERN = re.compile(
    r"\*\*Last updated:\*\*\s*(\d{4}-\d{2}-\d{2})",
    re.IGNORECASE,
)
PLAN_LINK_PATTERN = re.compile(
    r"(?:\]\(|^|\s)(plans/[^\s\)\]#]+\.md)",
    re.IGNORECASE,
)

# Harness docs scanned for broken relative links (in addition to user-docs checker).
HARNESS_MARKDOWN = (
    "AGENTS.md",
    "ARCHITECTURE.md",
    "dev-docs/README.md",
    "dev-docs/HARNESS.md",
    "dev-docs/SOURCE_LAYOUT.md",
)

REQUIRED_FILES = (
    "AGENTS.md",
    "ARCHITECTURE.md",
    "dev-docs/HARNESS.md",
    "dev-docs/SOURCE_LAYOUT.md",
    "dev-docs/architecture_boundary_baseline.txt",
    "dev-docs/README.md",
    "dev-docs/TO_DO.md",
    "dev-docs/MAINTENANCE_LOG.md",
    "src/utils/debug_flags.py",
    "scripts/check_repo_harness.py",
    "scripts/check_architecture_boundaries.py",
    "scripts/agent_smoke_harness.py",
    "scripts/check_user_docs_links.py",
)

AGENTS_MAX_LINES = 130
AGENTS_FORBIDDEN_SECTION = "## Source module structure"
TODO_STALE_DAYS = 120
DOC_GARDEN_STALE_DAYS = 180

# Topic guides that must exist and be linked from user-docs/USER_GUIDE.md (hub Topics table).
REQUIRED_USER_DOC_TOPICS = (
    "CONFIGURATION.md",
    "USER_GUIDE_MPR.md",
    "USER_GUIDE_3D.md",
    "USER_GUIDE_QA_PYLINAC.md",
    "USER_GUIDE_LAYOUTS.md",
    "USER_GUIDE_ANNOTATIONS.md",
    "USER_GUIDE_EXPORT.md",
    "USER_GUIDE_TAGS.md",
    "USER_GUIDE_SHORTCUTS.md",
    "USER_GUIDE_ANONYMIZATION.md",
    "IMAGE_FUSION_TECHNICAL_DOCUMENTATION.md",
)


def split_anchor(url: str) -> tuple[str, str]:
    if "#" in url:
        base, _, frag = url.partition("#")
        return base, frag
    return url, ""


def check_links_in_file(md_path: Path, repo_root: Path) -> list[str]:
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
            errors.append(f"{md_path.name}: link escapes repo: {raw_url!r}")
            continue
        if not target.exists():
            rel = md_path.relative_to(repo_root)
            errors.append(f"{rel}: broken link {raw_url!r}")
    return errors


def parse_last_updated(text: str) -> date | None:
    match = LAST_UPDATED_PATTERN.search(text)
    if not match:
        return None
    return datetime.strptime(match.group(1), "%Y-%m-%d").date()


def check_required_files(repo_root: Path) -> list[str]:
    errors: list[str] = []
    for rel in REQUIRED_FILES:
        if not (repo_root / rel).is_file():
            errors.append(f"missing required harness file: {rel}")
    return errors


def check_agents_md(repo_root: Path) -> list[str]:
    errors: list[str] = []
    path = repo_root / "AGENTS.md"
    lines = path.read_text(encoding="utf-8").splitlines()
    if len(lines) > AGENTS_MAX_LINES:
        errors.append(
            f"AGENTS.md has {len(lines)} lines (max {AGENTS_MAX_LINES}); "
            "move detail to ARCHITECTURE.md or dev-docs/SOURCE_LAYOUT.md"
        )
    if AGENTS_FORBIDDEN_SECTION in path.read_text(encoding="utf-8"):
        errors.append(
            "AGENTS.md must not contain '## Source module structure'; "
            "use dev-docs/SOURCE_LAYOUT.md"
        )
    return errors


def check_todo_freshness(repo_root: Path) -> list[str]:
    errors: list[str] = []
    path = repo_root / "dev-docs" / "TO_DO.md"
    text = path.read_text(encoding="utf-8")
    updated = parse_last_updated(text)
    if updated is None:
        errors.append("dev-docs/TO_DO.md: missing **Last updated:** YYYY-MM-DD near top")
    else:
        age = (date.today() - updated).days
        if age > TODO_STALE_DAYS:
            errors.append(
                f"dev-docs/TO_DO.md: Last updated {updated} is {age} days ago "
                f"(stale threshold {TODO_STALE_DAYS} days)"
            )
    return errors


def check_todo_backlog_policy(repo_root: Path) -> list[str]:
    """Ensure TO_DO.md stays an active backlog, not a completion/history log."""
    errors: list[str] = []
    path = repo_root / "dev-docs" / "TO_DO.md"
    text = path.read_text(encoding="utf-8")
    for lineno, line in enumerate(text.splitlines(), start=1):
        stripped = line.lstrip()
        if stripped.startswith("**Changes:**"):
            errors.append(
                "dev-docs/TO_DO.md: remove top-level **Changes:** history; "
                "use dev-docs/MAINTENANCE_LOG.md or CHANGELOG.md"
            )
        if stripped.startswith("- [x]"):
            errors.append(
                f"dev-docs/TO_DO.md:{lineno}: remove completed task row; "
                "capture durable history in CHANGELOG.md, MAINTENANCE_LOG.md, "
                "or a plan/info/bug-investigation note"
            )
    return errors


def check_user_guide_hub_topics(repo_root: Path) -> list[str]:
    """Ensure shipped feature topic guides exist and USER_GUIDE.md links to them."""
    errors: list[str] = []
    user_docs = repo_root / "user-docs"
    hub = user_docs / "USER_GUIDE.md"
    if not hub.is_file():
        errors.append("missing user-docs/USER_GUIDE.md")
        return errors
    hub_text = hub.read_text(encoding="utf-8")
    for filename in REQUIRED_USER_DOC_TOPICS:
        topic_path = user_docs / filename
        if not topic_path.is_file():
            errors.append(f"missing required user doc topic: user-docs/{filename}")
            continue
        if filename not in hub_text:
            errors.append(
                f"user-docs/USER_GUIDE.md does not reference user-docs/{filename} "
                "(add a Topics table row or link)"
            )
    return errors


def check_plan_links_in_todo(repo_root: Path) -> list[str]:
    errors: list[str] = []
    todo_path = repo_root / "dev-docs" / "TO_DO.md"
    text = todo_path.read_text(encoding="utf-8")
    dev_docs = repo_root / "dev-docs"
    seen: set[str] = set()
    for rel in PLAN_LINK_PATTERN.findall(text):
        if rel in seen:
            continue
        seen.add(rel)
        target = (dev_docs / rel).resolve()
        if not target.is_file():
            errors.append(f"dev-docs/TO_DO.md: plan not found: dev-docs/{rel}")
    return errors


def iter_markdown_files(repo_root: Path) -> list[Path]:
    """Return repository documentation files for report-only doc gardening."""
    docs: list[Path] = []
    for rel in ("AGENTS.md", "ARCHITECTURE.md", "CHANGELOG.md"):
        path = repo_root / rel
        if path.is_file():
            docs.append(path)
    for folder in ("dev-docs", "user-docs"):
        root = repo_root / folder
        if root.is_dir():
            docs.extend(sorted(root.rglob("*.md")))
    return docs


def count_open_todo_items(todo_text: str) -> int:
    """Count unchecked Markdown task items in TO_DO.md."""
    return sum(1 for line in todo_text.splitlines() if line.lstrip().startswith("- [ ]"))


def count_duplicate_changelog_sections(changelog_text: str) -> int:
    """Count duplicate third-level headings inside the Unreleased section."""
    match = re.search(r"## \[Unreleased\](.*?)(?:\n## \[|$)", changelog_text, re.S)
    if not match:
        return 0
    seen: set[str] = set()
    duplicates = 0
    for heading in re.findall(r"^###\s+(.+)$", match.group(1), re.M):
        normalized = heading.strip().lower()
        if normalized in seen:
            duplicates += 1
        seen.add(normalized)
    return duplicates


def scan_doc_dates(
    paths: list[Path], repo_root: Path, today: date
) -> tuple[list[str], list[str]]:
    """Return (missing-date, stale) doc lists for the given markdown files.

    A doc is "stale" when its **Last updated:** date is older than
    ``DOC_GARDEN_STALE_DAYS``; "missing" when it has no such date line at all.
    """
    missing: list[str] = []
    stale: list[str] = []
    for path in paths:
        if not path.is_file():
            continue
        updated = parse_last_updated(path.read_text(encoding="utf-8"))
        rel = path.relative_to(repo_root).as_posix()
        if updated is None:
            missing.append(rel)
        elif (today - updated).days > DOC_GARDEN_STALE_DAYS:
            stale.append(f"{rel} ({updated})")
    return missing, stale


def build_doc_garden_report(repo_root: Path) -> list[str]:
    """Build a non-blocking documentation hygiene report."""
    docs = iter_markdown_files(repo_root)
    harness_docs = [repo_root / rel for rel in HARNESS_MARKDOWN if (repo_root / rel).is_file()]
    today = date.today()

    missing_dates, stale_docs = scan_doc_dates(harness_docs, repo_root, today)

    # User-facing topic guides: the hub plus every required topic guide.
    user_docs = repo_root / "user-docs"
    guide_paths = [user_docs / "USER_GUIDE.md"] + [
        user_docs / name for name in REQUIRED_USER_DOC_TOPICS
    ]
    guide_missing, guide_stale = scan_doc_dates(guide_paths, repo_root, today)

    todo_path = repo_root / "dev-docs" / "TO_DO.md"
    todo_text = todo_path.read_text(encoding="utf-8") if todo_path.is_file() else ""
    changelog_path = repo_root / "CHANGELOG.md"
    changelog_text = changelog_path.read_text(encoding="utf-8") if changelog_path.is_file() else ""

    report = [
        "Doc garden report:",
        f"  markdown files scanned: {len(docs)}",
        f"  harness markdown files: {len(harness_docs)}",
        f"  harness docs missing Last updated: {len(missing_dates)}",
        f"  harness docs stale > {DOC_GARDEN_STALE_DAYS} days: {len(stale_docs)}",
        f"  user guides missing Last updated: {len(guide_missing)}",
        f"  user guides stale > {DOC_GARDEN_STALE_DAYS} days: {len(guide_stale)}",
        f"  open TO_DO items: {count_open_todo_items(todo_text)}",
        f"  duplicate CHANGELOG [Unreleased] section headings: {count_duplicate_changelog_sections(changelog_text)}",
    ]
    if missing_dates:
        report.append("  missing-date docs: " + ", ".join(missing_dates))
    if stale_docs:
        report.append("  stale docs: " + ", ".join(stale_docs))
    if guide_missing:
        report.append("  user guides missing date: " + ", ".join(guide_missing))
    if guide_stale:
        report.append("  stale user guides: " + ", ".join(guide_stale))
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parent.parent,
        help="Repository root",
    )
    parser.add_argument(
        "--doc-garden",
        action="store_true",
        help="Print a non-blocking documentation hygiene report.",
    )
    args = parser.parse_args()
    repo_root: Path = args.root.resolve()

    all_errors: list[str] = []
    all_errors.extend(check_required_files(repo_root))
    all_errors.extend(check_agents_md(repo_root))
    all_errors.extend(check_todo_freshness(repo_root))
    all_errors.extend(check_todo_backlog_policy(repo_root))
    all_errors.extend(check_plan_links_in_todo(repo_root))
    all_errors.extend(check_user_guide_hub_topics(repo_root))

    for rel in HARNESS_MARKDOWN:
        md = repo_root / rel
        if md.is_file():
            all_errors.extend(check_links_in_file(md, repo_root))

    if all_errors:
        print("Repo harness check failed:", file=sys.stderr)
        for line in all_errors:
            print(f"  {line}", file=sys.stderr)
        return 1

    print(
        "OK: repo harness "
        f"({len(REQUIRED_FILES)} required files, AGENTS.md <= {AGENTS_MAX_LINES} lines, "
        "TO_DO active-backlog policy + TO_DO plans + harness links + "
        f"{len(REQUIRED_USER_DOC_TOPICS)} user-guide topics)"
    )
    if args.doc_garden:
        print()
        for line in build_doc_garden_report(repo_root):
            print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
