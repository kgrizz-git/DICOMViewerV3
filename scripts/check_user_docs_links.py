#!/usr/bin/env python3
"""
Verify documentation references resolve: relative Markdown links, and inline
code paths pointing into `src/`, `scripts/`, and `tests/`.

Blocking coverage is user-docs/, the root README.md and ARCHITECTURE.md,
AGENTS.md, the top level of dev-docs/, dev-docs/info/, and the **active** plan
tree (dev-docs/plans/*.md and dev-docs/plans/supporting/**/*.md). Active plans are
live work documents that someone is implementing from right now, so a broken
link in one is a real defect.

Historical material is deliberately excluded, in three groups: completed plans,
the dated files in ``HISTORICAL_RECORD_FILES``, and the generated-assessment
directories in ``SNAPSHOT_SUBDIRS``. All three describe the tree as it was when
they were written, so a link to a file later renamed is an *accurate* record
rather than a defect; repairing those would rewrite history to match a present
the document never described.

``MAINTENANCE_LOG.md`` is in that set on specific evidence rather than a general
claim about logs: its references to ``grype.yml``/``semgrep.yml`` appear inside
the entry that documents the workflow consolidation, in the sentence explaining
that the old backlog item named files "which no longer exist". Those are
deliberate back-references. The forward-looking cost is accepted knowingly --
that file is appended to on most PRs, so a newly written entry naming a
nonexistent workflow is advisory rather than blocking, exactly as for
``CHANGELOG.md``.

Because the exclusion hides whole subtrees, ``--include-completed-plans`` makes
them visible: that mode reports historical rot as **advisory** output and still
exits 0, so the debt can be measured without becoming a gate. It is a report,
not a policy change; a large backlog in historical records is expected and is
not a failure.

Note that the snapshot directories are scanned *and* advisory. Outside the
scanned set entirely, a reviewer cannot distinguish "checked and clean" from
"never looked at", which is a worse failure than measurable debt.

Two checks run over the covered files:

1. **Relative Markdown links.** Scans inline links of the form [text](url). Skips
    http(s), mailto, and bare fragment-only targets. Resolves each relative URL
    against the source file's directory and fails if the target does not exist.
    For files under ``user-docs/``, a relative link whose resolved target falls
    outside ``user-docs/`` also fails, even if the target exists elsewhere in the
    repository. Absolute ``https://github.com/.../blob/...`` links under
    ``user-docs/`` must share the ``GITHUB_BLOB_BASE`` prefix from
    ``src/utils/doc_urls.py`` (so forks/tags stay aligned with in-app Help).
2. **Inline `src|scripts|tests/...py` code paths.** A path written in backticks, such as
    `src/core/mpr_controller.py`, must exist. This catches the failure mode where a
    module moves between packages and prose that names it silently goes stale; a
    core/ to gui/ move left 17 such references wrong across the living docs before
    this check existed.

Usage (from repository root):
    python scripts/check_user_docs_links.py
    python scripts/check_user_docs_links.py --include-completed-plans  # advisory

Exit code: 0 if all blocking links resolve, 1 if any are broken (prints details).

Inputs: Markdown files on disk under the repo; ``GITHUB_BLOB_BASE`` from
``src/utils/doc_urls.py``.
Outputs: stdout messages; non-zero exit on failure.
Requirements: Python 3.9+; repository ``src/`` importable for ``utils.doc_urls``.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# [any](path) — path may include #anchor; exclude images ![alt](url) by requiring [ not preceded by !
LINK_PATTERN = re.compile(r"(?<!!)\[([^\]]*)\]\(([^)]+)\)")
# `src/pkg/module.py` written as inline code, optionally with a `:line` or
# `:line-range` suffix, which is how this repository cites code. Only .py paths,
# so prose naming a directory or a glob is not treated as a claim about one exact
# file. Path segments may not contain dots, which keeps illustrative prose such as
# `src/...py` from being read as a claim that a file exists.
#
# Note the deliberate limit: a name written as inline code is read as a claim that
# the file exists *now*. Prose proposing a file to create ("add `src/my_thing.py`")
# will be flagged. Write such names as a directory, a glob, or plain prose.
#: Inline paths to code a plan may legitimately *propose* and therefore not yet
#: have. ``scripts/`` and ``tests/`` belong here for the same reason ``src/`` does:
#: ``AGENTS.md`` and the plans routinely name a gate script or a test file as work
#: still to be written, so plan-exempting them is what keeps the gate green.
CODE_PATH_PATTERN = re.compile(
    r"`((?:src|scripts|tests)/(?:[A-Za-z0-9_-]+/)*[A-Za-z0-9_-]+\.py)"
    r"(?::\d+(?:[-,]\d+)*)?`"
)
# Well-known repository files named as inline code. A doc that says
# ``.github/workflows/grype.yml`` is asserting that file exists now, exactly as
# ``src/core/foo.py`` is — and unlike a module, a workflow or a requirements file
# is never something a plan *proposes to create*. That makes this class safe to
# check in the plan tree too, which is the point: three workflows were
# consolidated into ``ci.yml`` and the references went stale unnoticed because
# nothing looked at non-``src`` paths. Deliberately a closed set of prefixes
# rather than "any path-looking token", which would false-positive on prose.
KNOWN_REPO_PATH_PATTERN = re.compile(
    r"`((?:\.github/workflows/[\w.-]+\.ya?ml"
    r"|requirements[-\w]*\.txt"
    r"|pytest\.ini|ruff\.toml|\.coveragerc"
    r"|\.githooks/[\w.-]+)"
    r")(?::\d+)?`"
)
# Absolute GitHub blob links under user-docs/ must share GITHUB_BLOB_BASE.
GITHUB_BLOB_LINK_HINT = re.compile(r"https://github\.com/[^)\s]+/blob/")


def _completed_plans_root(repo_root: Path) -> Path:
    """Return the excluded ``dev-docs/plans/completed`` subtree.

    Resolved before use so a symlink in dev-docs/ cannot pull historical content
    back into the blocking set.
    """
    return (repo_root / "dev-docs" / "plans" / "completed").resolve()


#: Dated point-in-time records. They describe the tree as it was, so a reference
#: to a since-renamed file is an accurate record rather than rot, and "fixing" it
#: would rewrite the past. ``MAINTENANCE_LOG.md`` is a dated log by the repo's own
#: convention; ``SECURITY_IMPLEMENTATION_SUMMARY.md`` is a dated, completed summary.
#: Dated generated-assessment directories under ``dev-docs/``. Scanned, but
#: advisory only. ``templates-generalized/`` is included here because it is a
#: template rather than a snapshot, but it is not a *living* doc: the refs it
#: carries are illustrative examples in fenced code blocks that agents copy when
#: generating a scan, so its current text is a worked example, not a live claim.
SNAPSHOT_SUBDIRS = (
    "safety-scans",
    "security-assessments",
    "doc-assessments",
    "refactor-assessments",
    "templates-generalized",
    # Dated investigation and assessment records. Found by comparing every
    # ``dev-docs/**`` subdirectory against the scanned set rather than trusting
    # the set itself: these seven were not excluded on purpose, they had simply
    # never been added, which hid 12 stale ``src/`` references across four files.
    # Advisory for the same reason as the rest: a 2026 bug investigation naming
    # the modules as they were is an accurate record, and correcting it to match
    # today's layout would be rewriting history.
    "bug-investigations",
    "investigations",
    "ux-assessments",
    "assessments",
    "code-assessments",
    "testing-assessments",
    # ``orchestration/`` holds live agent instructions rather than a dated record,
    # but it is a generated checklist of the same shape as the rest and carries no
    # inline path claims of its own, so advisory keeps it measured without letting
    # a stale checklist block. Revisit if it ever grows real claims.
    "orchestration",
)

HISTORICAL_RECORD_FILES = (
    "CHANGELOG.md",
    "dev-docs/MAINTENANCE_LOG.md",
    "dev-docs/SECURITY_IMPLEMENTATION_SUMMARY.md",
)


def _is_excluded(candidate: Path, repo_root: Path) -> bool:
    """True for files outside the blocking set: historical records (see above)."""
    resolved = candidate.resolve()
    if resolved.is_relative_to(_completed_plans_root(repo_root)):
        return True
    for subdir in SNAPSHOT_SUBDIRS:
        if resolved.is_relative_to(repo_root / "dev-docs" / subdir):
            return True
    return resolved in {(repo_root / rel).resolve() for rel in HISTORICAL_RECORD_FILES}


def _markdown_under(directory: Path, recursive: bool = True) -> list[Path]:
    """Markdown files in *directory*, empty when it does not exist."""
    if not directory.is_dir():
        return []
    return sorted(directory.rglob("*.md") if recursive else directory.glob("*.md"))


#: Directories whose Markdown is project documentation and therefore scanned.
#: ``.agents/``, ``.claude/`` and ``.cursor/`` are deliberately absent: they are
#: agent tooling configuration owned by other tools, not documentation of this
#: project, and scanning them would couple the gate to their file formats.
DOC_SUBDIRS = (
    ".github",
    "security",
    "tools",
    "tests",
)
#: Under a protected data root. The PHI artifact gate owns that tree; the link
#: checker does not duplicate it.
DOC_SUBDIRS_EXCLUDED = ("sample-phantom-data-committed",)


def _repo_wide_doc_files(repo_root: Path) -> list[Path]:
    """Root-level and project Markdown outside dev-docs/, user-docs/ and tests-of-plans.

    Found by comparing every tracked ``*.md`` against the scanned set: 16 files
    were invisible, including ``SECURITY.md``, ``DESIGN.md``,
    ``CODE_OF_CONDUCT.md``, ``.github/CONTRIBUTING.md``,
    ``.github/PULL_REQUEST_TEMPLATE.md``, ``tests/README.md``, the five
    ``tests/fixtures/*/README.md`` and ``security/pip-audit-exceptions.md``.
    Most are living documents, which is the same "absent rather than excluded on
    purpose" gap as the unscanned dev-docs directories and nested AGENTS.md files.
    """
    found = _markdown_under(repo_root, recursive=False)
    for subdir in DOC_SUBDIRS:
        found.extend(_markdown_under(repo_root / subdir))
    for subdir in DOC_SUBDIRS_EXCLUDED:
        found.extend(
            f
            for f in _markdown_under(repo_root / subdir)
            if f not in found
        )
    return found


def _active_plan_files(repo_root: Path) -> list[Path]:
    """Live plan documents: the top level plus supporting/ recursively.

    Recursive because ``supporting/research/`` holds live analysis, and a
    non-recursive glob silently hid a stale workflow reference there.
    """
    plans_root = repo_root / "dev-docs" / "plans"
    return [
        *_markdown_under(plans_root, recursive=False),
        *_markdown_under(plans_root / "supporting"),
    ]


def _living_dev_doc_files(repo_root: Path) -> list[Path]:
    """Top-level dev docs plus ``info/``, minus historical records.

    Resolved before excluding so a symlink under ``dev-docs/`` cannot pull
    excluded content back in.
    """
    # Recursive, with the living/historical split delegated entirely to
    # ``_is_excluded``. This used to enumerate ``dev-docs`` and ``dev-docs/info``
    # explicitly while ``_is_excluded`` treated *everything* unlisted as live --
    # two rules describing the same universe, which is precisely how seven
    # subdirectories could be absent from the scan yet not excluded from blocking.
    # One predicate now decides and the scan follows it, so a new directory is
    # classified rather than silently skipped.
    return [
        candidate
        for candidate in _markdown_under(repo_root / "dev-docs", recursive=True)
        if not _is_excluded(candidate, repo_root)
    ]


def _root_doc_files(repo_root: Path) -> list[Path]:
    return [
        candidate
        for rel in ("README.md", "ARCHITECTURE.md", "AGENTS.md")
        if (candidate := repo_root / rel).is_file()
    ]


def _nested_agents_files(repo_root: Path) -> list[Path]:
    """Nested ``AGENTS.md`` instruction files under ``src/``.

    These are *live* agent instructions, not history, so they belong in the
    blocking set: the root ``AGENTS.md`` tells agents to run named scripts, and a
    nested instruction file that names one which no longer exists sends the next
    agent to a command that cannot run. Found by comparing every tracked
    ``AGENTS.md`` against the scanned set rather than trusting the set -- the
    seventh instance of a file being absent from scanning rather than excluded
    from it on purpose.
    """
    return sorted(
        candidate
        for candidate in (repo_root / "src").rglob("AGENTS.md")
        if candidate.is_file()
    )


def _historical_files(repo_root: Path) -> list[Path]:
    """Everything the advisory pass adds: completed plans, dated records, snapshots.

    ``_is_excluded`` only *drops* a file from the candidate list; it never
    introduces one. So the flag has to add the historical set back explicitly --
    otherwise it claims coverage it does not have, which is the same
    reads-as-configured-while-doing-nothing shape it exists to avoid.
    """
    # Recursive, deliberately matching the exclusion rule: ``_is_excluded`` covers
    # the whole ``completed/`` subtree via ``is_relative_to``, so a non-recursive
    # glob here would leave nested plans excluded from blocking *and* unscanned in
    # the advisory pass -- invisible rather than merely advisory. Correct today only
    # because no subdirectory exists yet, which is exactly how the dead
    # ``.githooks/`` arm and the non-recursive ``supporting/`` glob both survived.
    found: list[Path] = _markdown_under(repo_root / "dev-docs" / "plans" / "completed")
    found.extend(
        candidate
        for rel in HISTORICAL_RECORD_FILES
        if (candidate := repo_root / rel).is_file()
    )
    for subdir in SNAPSHOT_SUBDIRS:
        found.extend(_markdown_under(repo_root / "dev-docs" / subdir))
    return found


def iter_markdown_files(
    repo_root: Path, include_completed_plans: bool = False
) -> list[Path]:
    """Markdown files to validate.

    Blocking set: user docs, the living dev docs, and the **active** plan tree
    (``dev-docs/plans/*.md`` plus ``dev-docs/plans/supporting/**/*.md``).
    Historical material -- ``dev-docs/plans/completed/``, the dated files in
    ``HISTORICAL_RECORD_FILES``, and the generated-assessment directories in
    ``SNAPSHOT_SUBDIRS`` -- is excluded because it describes the tree as it was;
    pass ``include_completed_plans=True`` to include it in an advisory pass.

    NB: ``SNAPSHOT_SUBDIRS`` are deliberately not added to the blocking set. They
    are advisory -- a dated generated assessment, not a living claim -- so they
    belong to the advisory pass alone. Adding them unconditionally made the
    default run report them while the flag's help claimed it was what brought
    them in; code and documented contract have to agree.
    """
    paths = [
        *_markdown_under(repo_root / "user-docs"),
        *_active_plan_files(repo_root),
        *_living_dev_doc_files(repo_root),
        *_root_doc_files(repo_root),
        *_nested_agents_files(repo_root),
        *_repo_wide_doc_files(repo_root),
    ]
    if include_completed_plans:
        paths.extend(_historical_files(repo_root))
    return sorted(set(paths))


def is_historical_record(md_path: Path, repo_root: Path) -> bool:
    """True when a file is in the advisory-only historical set."""
    return _is_excluded(md_path, repo_root)


def is_plan_document(md_path: Path, repo_root: Path) -> bool:
    """True when a file is a plan (active or completed) under ``dev-docs/plans/``.

    Plans get relative-link checking but not the inline code-path existence
    check, because a plan may name a module it intends to create. See
    :func:`check_code_paths` for that contract.

    The exemption is plans only, deliberately. ``TO_DO.md`` and
    ``FUTURE_WORK_DETAIL_NOTES.md`` were briefly exempted here too, reasoning that
    a backlog proposes files just as a plan does. That was the wrong instrument:
    those two files hold 17 code-path references of which 13 exist today and are
    descriptive, so the exemption let 13 real claims rot silently to save four
    prose edits. The checker's own contract already prescribes the narrower fix --
    "prose proposing a file to create will be flagged; write such names as a
    directory, a glob, or plain prose" -- and those four proposals now follow it.
    """

    plans_root = (repo_root / "dev-docs" / "plans").resolve()
    try:
        return md_path.resolve().is_relative_to(plans_root)
    except OSError:  # pragma: no cover - defensive
        return False


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


def check_code_paths(md_path: Path, repo_root: Path) -> list[str]:
    """Return errors for inline ``src|scripts|tests/...py`` paths that do not exist.

    Plan-exempt: a plan may name a module, gate script or test file it intends to
    create.
    """
    return _check_inline_paths(md_path, repo_root, CODE_PATH_PATTERN, "code file")


def check_known_repo_paths(md_path: Path, repo_root: Path) -> list[str]:
    """Return errors for inline well-known repo paths (workflows, requirements).

    Kept separate from :func:`check_code_paths` because it is **not** exempt for
    plans: naming a workflow or a requirements file is always a claim that it
    exists now, so a plan proposing a new ``src/core/thing.py`` does not create
    false positives here the way it would for the ``src/`` pattern.
    """
    return _check_inline_paths(md_path, repo_root, KNOWN_REPO_PATH_PATTERN, "repository file")


def _check_inline_paths(
    md_path: Path, repo_root: Path, pattern: re.Pattern[str], kind: str
) -> list[str]:
    """Return errors for inline code paths matching *pattern* that do not exist."""
    errors: list[str] = []
    text = md_path.read_text(encoding="utf-8")
    for path in pattern.findall(text):
        if not exists_with_exact_case(repo_root, path):
            errors.append(
                f"{md_path.relative_to(repo_root)}: names a {kind} that does "
                f"not exist: {path!r}"
            )
    return errors


def split_anchor(url: str) -> tuple[str, str]:
    if "#" in url:
        base, _, frag = url.partition("#")
        return base, frag
    return url, ""


def load_github_blob_base(repo_root: Path) -> str:
    """Return ``GITHUB_BLOB_BASE`` from ``src/utils/doc_urls.py`` (no trailing slash)."""
    src_root = str(repo_root / "src")
    if src_root not in sys.path:
        sys.path.insert(0, src_root)
    from utils.doc_urls import GITHUB_BLOB_BASE

    return GITHUB_BLOB_BASE.rstrip("/")


def check_github_blob_base_alignment(
    md_path: Path, repo_root: Path, blob_base: str
) -> list[str]:
    """Fail user-docs GitHub blob links that diverge from ``GITHUB_BLOB_BASE``."""
    errors: list[str] = []
    text = md_path.read_text(encoding="utf-8")
    for _label, raw_url in LINK_PATTERN.findall(text):
        url = raw_url.strip()
        if not GITHUB_BLOB_LINK_HINT.match(url):
            continue
        path_part, _anchor = split_anchor(url)
        if path_part == blob_base or path_part.startswith(blob_base + "/"):
            continue
        errors.append(
            f"{md_path.relative_to(repo_root)}: GitHub blob link {raw_url!r} "
            f"does not use GITHUB_BLOB_BASE ({blob_base!r})"
        )
    return errors


def check_file(md_path: Path, repo_root: Path, is_user_doc: bool = False) -> list[str]:
    """Return list of error messages for broken links in one file.

    When ``is_user_doc`` is True (the file lives under ``user-docs/``), relative
    links whose resolved target is outside ``user-docs/`` are rejected, even when
    the target exists elsewhere in the repository. Absolute ``https://``,
    ``http://``, ``mailto:``, and bare fragment-only targets remain allowed.
    """
    errors: list[str] = []
    text = md_path.read_text(encoding="utf-8")
    base_dir = md_path.parent
    user_docs_root = (repo_root / "user-docs").resolve()

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
        if is_user_doc:
            try:
                target.relative_to(user_docs_root)
            except ValueError:
                errors.append(
                    f"{md_path.relative_to(repo_root)}: link escapes user-docs/: {raw_url!r}"
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
    parser.add_argument(
        "--include-completed-plans",
        action="store_true",
        help=(
            "Also report link rot in the historical set: dev-docs/plans/completed/, "
            "the files in HISTORICAL_RECORD_FILES, and the dated snapshot "
            "directories in SNAPSHOT_SUBDIRS. Historical rot is reported but never "
            "affects the exit status, so it is measurable without becoming a merge "
            "gate. This flag does NOT guarantee exit 0: broken references in live "
            "documents (user-docs/, the living dev-docs/, the active plan tree) "
            "still exit 1 in this mode. Both lists are reported when both are "
            "non-empty."
        ),
    )
    args = parser.parse_args()
    repo_root: Path = args.root.resolve()

    if not (repo_root / "user-docs").is_dir():
        print("error: user-docs/ was not found under the repository root", file=sys.stderr)
        return 1

    user_docs_root = repo_root / "user-docs"
    doc_urls_path = repo_root / "src" / "utils" / "doc_urls.py"
    blob_base = (
        load_github_blob_base(repo_root) if doc_urls_path.is_file() else None
    )
    blocking: list[str] = []
    advisory: list[str] = []
    files = iter_markdown_files(repo_root, args.include_completed_plans)
    for md in files:
        is_user_doc = md.is_relative_to(user_docs_root)
        errors = check_file(md, repo_root, is_user_doc=is_user_doc)
        # The inline code-path check asserts that a backticked path names a file
        # that exists *now*, which is true of descriptive docs but false of
        # proposals: a plan or backlog item legitimately names modules, gate
        # scripts or test files it intends to create
        # ("add `src/core/image_pairing.py`"), and the checker's own contract
        # says such prose should be written as a glob or plain text instead.
        # Applying it to the plan tree would report 17 distinct proposed
        # modules as broken alongside the 16 genuinely-stale ones, so a gate
        # would be permanently red for a reason no edit can fix. Plans are
        # therefore link-checked only; the stale refs are swept separately.
        if not is_plan_document(md, repo_root):
            errors.extend(check_code_paths(md, repo_root))
        # Not plan-exempt, unlike the src/ check above: a workflow or a
        # requirements file is never something a plan proposes to create, so
        # this class is safe to enforce in the plan tree too. It is the class
        # that went stale unnoticed when three workflows were consolidated into
        # ci.yml and nothing looked at non-src paths.
        errors.extend(check_known_repo_paths(md, repo_root))
        if is_user_doc and blob_base is not None:
            errors.extend(
                check_github_blob_base_alignment(md, repo_root, blob_base)
            )
        # Only rot in historical records is demoted; a broken link in a live
        # document blocks even during an advisory pass.
        if is_historical_record(md, repo_root):
            advisory.extend(errors)
        else:
            blocking.extend(errors)

    n_files = len(files)
    scope = (
        "user-docs/, the living dev-docs/, the active plan tree (including "
        "supporting/research/), README.md, ARCHITECTURE.md, and AGENTS.md"
    )
    # Report blocking findings but do NOT return yet. Returning here used to
    # discard the advisory list entirely, so an advisory run that also found live
    # rot printed no historical figure at all -- which is precisely when the debt
    # number is worth having, and it made the advisory CI step go silent on
    # exactly the runs where a reader was most likely to be looking. Status is
    # decided last, from both lists.
    if blocking:
        print("Broken documentation references:", file=sys.stderr)
        for line in blocking:
            print(f"  {line}", file=sys.stderr)

    if advisory:
        # No "OK:" prefix here. Moving the advisory report ahead of the status
        # decision (so historical debt is still reported when live rot exists)
        # meant this banner could follow a "Broken documentation references"
        # block, reading as success on a run that exits 1. Both sections go to
        # stderr, so a log scraper keys off the exit status -- but a human
        # skimming should not have to.
        banner = (
            f"Checked {n_files} Markdown file(s) ({scope}). "
            f"Advisory only - {len(advisory)} broken reference(s) in historical "
            "records (dev-docs/plans/completed/, the dated files in "
            "HISTORICAL_RECORD_FILES, and the generated-assessment directories "
            "in SNAPSHOT_SUBDIRS), which are excluded by policy because they "
            "describe the tree as it was. Note templates-generalized/ carries "
            "its example paths in fenced code comments rather than backticks, so "
            "the inline check does not see them:"
        )
        print(f"{banner}{' (live-document rot above is blocking)' if blocking else ''}:",
              file=sys.stderr)
        for line in advisory:
            print(f"  {line}", file=sys.stderr)
    elif not blocking:
        print(
            f"OK: checked links and src/scripts/tests code paths in {n_files} "
            f"Markdown file(s) ({scope})."
        )
    # Live-document rot blocks; historical rot never affects the exit status.
    return 1 if blocking else 0


if __name__ == "__main__":
    raise SystemExit(main())
