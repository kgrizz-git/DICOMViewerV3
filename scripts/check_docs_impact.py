#!/usr/bin/env python3
"""
Advisory documentation-impact check for UI/help-sensitive diffs.

When a change touches paths that often imply user-visible documentation work
(menus, GUI, settings, Help HTML, ``doc_urls``), this script **warns** unless
the same diff also updates user-facing docs **or** the PR/commit body declares
an explicit waiver:

    docs-impact: not needed — <multi-word reason>

Path matching is intentionally coarse (e.g. a comment-only edit under
``src/gui/`` still warns). That is acceptable while the check remains advisory.

Usage (from repository root)::

    python scripts/check_docs_impact.py
    python scripts/check_docs_impact.py --staged
    python scripts/check_docs_impact.py --diff-range origin/main...HEAD
    python scripts/check_docs_impact.py --pr-body-file /tmp/pr-body.txt
    python scripts/check_docs_impact.py --strict
    python scripts/check_docs_impact.py --with-feature-coverage

Exit code: **0** by default (warnings only). Under ``--strict``, exit **1** when
docs-risk paths are present without a docs change or a valid waiver.

Environment:
    ``GITHUB_PR_BODY`` — optional PR body text (CI). Overridden by
    ``--pr-body-file`` when that flag is set.

Inputs: git name-only diff (or ``--changed-files-file`` for tests), optional
PR body. Outputs: stdout report. Requirements: Python 3.9+ standard library;
``git`` on ``PATH`` when reading a real diff.
"""

from __future__ import annotations

import argparse
import fnmatch
import os
import re
import subprocess
import sys
from pathlib import Path

try:
    from scripts.stdio_utf8 import ensure_stdout_utf8
except ModuleNotFoundError as exc:
    # Only fall back when the package path is unavailable (script invoked as
    # ``python scripts/...``). Do not mask errors inside stdio_utf8 itself.
    if exc.name not in {"scripts", "scripts.stdio_utf8"}:
        raise
    from stdio_utf8 import ensure_stdout_utf8

# Paths that often imply end-user doc updates (coarse; advisory).
DOCS_RISK_PREFIXES: tuple[str, ...] = (
    "src/gui/",
    "src/utils/config/",
    "resources/help/",
)
DOCS_RISK_EXACT: frozenset[str] = frozenset(
    {
        "src/utils/doc_urls.py",
        "src/gui/main_window_menu_builder.py",
    }
)
DOCS_RISK_GLOBS: tuple[str, ...] = (
    "src/main_app_*.py",
    "**/main_window_menu_builder.py",
)

# Same-diff paths that satisfy the “docs were considered” side of the check.
# ``resources/help/`` is intentionally both risk and satisfaction: editing Help
# HTML in the same change counts as addressing docs impact for UI work.
DOCS_SATISFACTION_PREFIXES: tuple[str, ...] = (
    "user-docs/",
    "resources/help/",
)
DOCS_SATISFACTION_EXACT: frozenset[str] = frozenset({"CHANGELOG.md"})

# Require a reason with at least two same-line whitespace-separated tokens.
# Use [ \t] (not \s) between tokens so a newline cannot complete the reason.
# Optional trailing \\r before end-of-line covers CRLF PR bodies explicitly.
DOCS_IMPACT_WAIVER = re.compile(
    r"(?m)^docs-impact:[ \t]*not needed[ \t]*[—\-–][ \t]+\S+[ \t]+\S+[^\r\n]*\r?$",
    re.IGNORECASE,
)

# Paths that trigger the optional feature-coverage report (UI surface).
UI_FEATURE_COVERAGE_PREFIXES: tuple[str, ...] = (
    "src/gui/",
)
UI_FEATURE_COVERAGE_GLOBS: tuple[str, ...] = (
    "src/main_app_*.py",
    "**/main_window_menu_builder.py",
)


def normalize_repo_path(path: str) -> str:
    """Normalize a git path to forward slashes without a leading ``./`` prefix."""
    normalized = path.replace("\\", "/")
    while normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized


def is_docs_risk_path(path: str) -> bool:
    """Return True if ``path`` is in the coarse docs-risk set."""
    path = normalize_repo_path(path)
    if path in DOCS_RISK_EXACT:
        return True
    if any(path.startswith(prefix) for prefix in DOCS_RISK_PREFIXES):
        return True
    return any(fnmatch.fnmatch(path, pattern) for pattern in DOCS_RISK_GLOBS)


def is_docs_satisfaction_path(path: str) -> bool:
    """Return True if ``path`` counts as a documentation update in the same diff."""
    path = normalize_repo_path(path)
    if path in DOCS_SATISFACTION_EXACT:
        return True
    return any(path.startswith(prefix) for prefix in DOCS_SATISFACTION_PREFIXES)


def triggers_feature_coverage(path: str) -> bool:
    """Return True if ``path`` should surface ``check_doc_feature_coverage``."""
    path = normalize_repo_path(path)
    if any(path.startswith(prefix) for prefix in UI_FEATURE_COVERAGE_PREFIXES):
        return True
    return any(fnmatch.fnmatch(path, pattern) for pattern in UI_FEATURE_COVERAGE_GLOBS)


def has_docs_impact_waiver(text: str) -> bool:
    """Return True if ``text`` contains a valid ``docs-impact: not needed — …`` line."""
    return bool(DOCS_IMPACT_WAIVER.search(text or ""))


def load_pr_body(pr_body_file: Path | None, env: dict[str, str] | None = None) -> str:
    """Load PR/commit body from ``--pr-body-file`` or ``GITHUB_PR_BODY``."""
    if pr_body_file is not None:
        return pr_body_file.read_text(encoding="utf-8")
    environ = env if env is not None else os.environ
    return environ.get("GITHUB_PR_BODY", "")


# Include deletions: removing UI/help surfaces still warrants a docs decision.
_GIT_DIFF_NAME_FILTER = "ACMRD"


def changed_files_from_git(
    repo_root: Path,
    *,
    staged: bool = False,
    diff_range: str | None = None,
) -> list[str]:
    """Return name-only paths from git for staged files or a diff range."""
    if staged:
        cmd = [
            "git",
            "diff",
            "--cached",
            "--name-only",
            f"--diff-filter={_GIT_DIFF_NAME_FILTER}",
        ]
    elif diff_range:
        cmd = [
            "git",
            "diff",
            "--name-only",
            f"--diff-filter={_GIT_DIFF_NAME_FILTER}",
            diff_range,
        ]
    else:
        raise ValueError("Either staged=True or diff_range must be set")

    result = subprocess.run(
        cmd,
        cwd=repo_root,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        err = (result.stderr or result.stdout or "").strip()
        raise RuntimeError(f"git diff failed ({result.returncode}): {err}")
    return [
        normalize_repo_path(line)
        for line in result.stdout.splitlines()
        if line.strip()
    ]


def default_diff_range(repo_root: Path) -> str | None:
    """Pick ``origin/<default>...HEAD`` (or local fallbacks) when those refs exist."""
    candidates: list[str] = []
    sym = subprocess.run(
        ["git", "symbolic-ref", "--quiet", "refs/remotes/origin/HEAD"],
        cwd=repo_root,
        check=False,
        capture_output=True,
        text=True,
    )
    if sym.returncode == 0:
        ref = (sym.stdout or "").strip()
        # refs/remotes/origin/main -> origin/main
        if ref.startswith("refs/remotes/"):
            remote_branch = ref[len("refs/remotes/") :]
            candidates.append(f"{remote_branch}...HEAD")
            if "/" in remote_branch:
                candidates.append(f"{remote_branch.split('/', 1)[1]}...HEAD")
    for name in (
        "origin/main",
        "main",
        "origin/master",
        "master",
        "origin/develop",
        "develop",
    ):
        candidate = f"{name}...HEAD"
        if candidate not in candidates:
            candidates.append(candidate)

    for candidate in candidates:
        base = candidate.split("...", 1)[0]
        probe = subprocess.run(
            ["git", "rev-parse", "--verify", base],
            cwd=repo_root,
            check=False,
            capture_output=True,
            text=True,
        )
        if probe.returncode == 0:
            return candidate
    return None


def evaluate_docs_impact(
    changed_files: list[str],
    pr_body: str,
) -> tuple[list[str], list[str], bool, bool, bool]:
    """Classify the change set.

    Returns:
        risk_paths, satisfaction_paths, waived, needs_attention, want_feature_coverage
    """
    risk = sorted({p for p in changed_files if is_docs_risk_path(p)})
    satisfaction = sorted({p for p in changed_files if is_docs_satisfaction_path(p)})
    waived = has_docs_impact_waiver(pr_body)
    needs_attention = bool(risk) and not satisfaction and not waived
    want_coverage = any(triggers_feature_coverage(p) for p in risk)
    return risk, satisfaction, waived, needs_attention, want_coverage


def run_feature_coverage_report(repo_root: Path) -> list[str]:
    """Return report lines from ``check_doc_feature_coverage`` (no fail-under)."""
    script = repo_root / "scripts" / "check_doc_feature_coverage.py"
    if not script.is_file():
        return [f"(skip feature coverage: missing {script.as_posix()})"]
    cmd = [sys.executable, str(script), "--root", str(repo_root)]
    result = subprocess.run(
        cmd,
        cwd=repo_root,
        check=False,
        capture_output=True,
        text=True,
    )
    out = (result.stdout or "").rstrip()
    lines = out.splitlines() if out else []
    if result.returncode != 0:
        lines.append(
            f"(feature coverage failed: exit {result.returncode}; "
            f"cmd={' '.join(cmd)})"
        )
        # Do not merge stderr into the report (noise / privacy); stdout only.
    return lines or ["(feature coverage produced no output)"]


def format_report(
    *,
    risk: list[str],
    satisfaction: list[str],
    waived: bool,
    needs_attention: bool,
    feature_coverage_lines: list[str] | None,
    mode_label: str,
) -> list[str]:
    """Build human-readable report lines."""
    lines = [
        "Docs-impact report:",
        f"  mode: {mode_label}",
        f"  docs-risk paths: {len(risk)}",
    ]
    for path in risk:
        lines.append(f"    - {path}")
    lines.append(f"  docs-satisfaction paths: {len(satisfaction)}")
    for path in satisfaction:
        lines.append(f"    - {path}")
    lines.append(f"  docs-impact waiver present: {'yes' if waived else 'no'}")

    if not risk:
        lines.append("  status: OK (no docs-risk paths in this change set)")
        return lines

    if satisfaction:
        lines.append("  status: OK (docs-risk paths accompany documentation updates)")
    elif waived:
        lines.append("  status: OK (docs-risk paths waived via docs-impact declaration)")
    elif needs_attention:
        lines.append("  status: ATTENTION — docs-risk paths without docs update or waiver")
        lines.append(
            "  request: update user-docs/, resources/help/, or CHANGELOG.md in this"
        )
        lines.append(
            "           change, or add: docs-impact: not needed — <multi-word reason>"
        )
        lines.append(
            "  local tip: pass --pr-body-file with that line when no PR body exists"
        )
    else:
        lines.append("  status: OK")

    if feature_coverage_lines is not None:
        lines.append("  feature-coverage (UI paths touched; report-only):")
        for cover_line in feature_coverage_lines:
            lines.append(f"    {cover_line}" if cover_line else "    ")

    return lines


def main(argv: list[str] | None = None) -> int:
    """CLI entry point. Returns 0 unless ``--strict`` and attention is needed."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parent.parent,
        help="Repository root",
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--staged",
        action="store_true",
        help="Inspect staged files only (git diff --cached)",
    )
    mode.add_argument(
        "--diff-range",
        metavar="RANGE",
        help="Git diff range (e.g. origin/main...HEAD). Default when not --staged.",
    )
    mode.add_argument(
        "--changed-files-file",
        type=Path,
        help="Read changed paths from a file (one per line). For tests/CI injection.",
    )
    parser.add_argument(
        "--pr-body-file",
        type=Path,
        help="PR or commit body file containing an optional docs-impact waiver",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit 1 when docs-risk paths lack docs updates and lack a waiver",
    )
    parser.add_argument(
        "--with-feature-coverage",
        action="store_true",
        help="When UI docs-risk paths are present, also print feature-coverage report",
    )
    args = parser.parse_args(argv)
    repo_root: Path = args.root.resolve()

    # Em dashes / non-ASCII in reports; avoid mojibake on a cp1252 console.
    ensure_stdout_utf8()

    mode_label: str
    if args.changed_files_file is not None:
        text = args.changed_files_file.read_text(encoding="utf-8")
        changed = [normalize_repo_path(line) for line in text.splitlines() if line.strip()]
        mode_label = f"changed-files-file={args.changed_files_file.as_posix()}"
    elif args.staged:
        changed = changed_files_from_git(repo_root, staged=True)
        mode_label = "staged"
    else:
        diff_range = args.diff_range or default_diff_range(repo_root)
        if not diff_range:
            print(
                "Docs-impact report:\n"
                "  status: SKIP (no diff range; pass --diff-range, --staged, "
                "or --changed-files-file)",
                file=sys.stderr,
            )
            return 0
        try:
            changed = changed_files_from_git(repo_root, diff_range=diff_range)
        except RuntimeError:
            print(
                "Docs-impact report:\n"
                "  status: ERROR (git diff failed; check --diff-range / refs)",
                file=sys.stderr,
            )
            return 1 if args.strict else 0
        mode_label = f"diff-range={diff_range}"

    pr_body = load_pr_body(args.pr_body_file)
    risk, satisfaction, waived, needs_attention, want_coverage = evaluate_docs_impact(
        changed, pr_body
    )

    feature_lines: list[str] | None = None
    if args.with_feature_coverage and want_coverage:
        feature_lines = run_feature_coverage_report(repo_root)

    for line in format_report(
        risk=risk,
        satisfaction=satisfaction,
        waived=waived,
        needs_attention=needs_attention,
        feature_coverage_lines=feature_lines,
        mode_label=mode_label,
    ):
        print(line)

    if args.strict and needs_attention:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
