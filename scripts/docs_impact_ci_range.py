"""
CI diff-range resolution for ``check_docs_impact``.

Selects the git diff range used by the advisory docs-impact GitHub Actions
step. Push events prefer ``github.event.before``; all-zero before uses the empty
tree; unavailable before tips are fetched when possible, then fall back to the
local ``origin/<default_branch>`` ref (error if that ref is also missing — never
silent SKIP). No remote fetch of the default branch is attempted.

Inputs: repository root + CI event fields. Outputs: ``(status, range, message)``
with status ``ok`` / ``skip`` / ``error``. Requirements: Python 3.9+; ``git`` on
``PATH``.
"""

from __future__ import annotations

import subprocess
from pathlib import Path


def is_all_zero_oid(value: str) -> bool:
    """Return True for Git's all-zero OID (new-branch / missing before tip)."""
    return bool(value) and set(value) == {"0"} and len(value) in {40, 64}


def _git_ok(repo_root: Path, args: list[str]) -> bool:
    """Return True when a git command exits 0."""
    result = subprocess.run(
        ["git", *args],
        cwd=repo_root,
        check=False,
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


def git_commit_exists(repo_root: Path, oid: str) -> bool:
    """Return True if ``oid`` resolves to a commit object locally."""
    return _git_ok(repo_root, ["cat-file", "-e", f"{oid}^{{commit}}"])


def git_merge_base_exists(repo_root: Path, a: str, b: str = "HEAD") -> bool:
    """Return True if ``git merge-base`` succeeds for ``a`` and ``b``."""
    return _git_ok(repo_root, ["merge-base", a, b])


def git_rev_parse_ok(repo_root: Path, ref: str) -> bool:
    """Return True if ``ref`` resolves via ``git rev-parse --verify``."""
    return _git_ok(repo_root, ["rev-parse", "--verify", ref])


def git_empty_tree_oid(repo_root: Path) -> str:
    """Return the empty-tree OID for root comparisons on first pushes."""
    result = subprocess.run(
        ["git", "hash-object", "-t", "tree", "/dev/null"],
        cwd=repo_root,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError("git hash-object failed for empty tree")
    return (result.stdout or "").strip()


def try_fetch_commit(repo_root: Path, oid: str) -> bool:
    """Best-effort fetch of ``oid`` from origin; return True if it then exists."""
    if git_commit_exists(repo_root, oid):
        return True
    subprocess.run(
        ["git", "fetch", "--no-tags", "--depth=1", "origin", oid],
        cwd=repo_root,
        check=False,
        capture_output=True,
        text=True,
    )
    return git_commit_exists(repo_root, oid)


def _resolve_pull_request(
    repo_root: Path, pr_base_sha: str
) -> tuple[str, str | None, str]:
    """Resolve range for ``pull_request`` events."""
    base = (pr_base_sha or "").strip()
    if not base:
        return "skip", None, "missing PR base SHA"
    if not git_commit_exists(repo_root, base):
        return "skip", None, "PR base SHA not present in checkout"
    if not git_merge_base_exists(repo_root, base):
        return "skip", None, "no merge-base with PR base SHA"
    return "ok", f"{base}...HEAD", "PR base SHA"


def _fallback_origin_default(
    repo_root: Path, default_branch: str, *, why: str
) -> tuple[str, str | None, str]:
    """Fall back to ``origin/<default>...HEAD`` or error if unavailable."""
    origin_default = f"origin/{default_branch}"
    if not git_rev_parse_ok(repo_root, origin_default):
        return "error", None, f"{why} and missing {origin_default} fallback"
    if not git_merge_base_exists(repo_root, origin_default):
        return (
            "error",
            None,
            f"{why} and no merge-base with {origin_default}",
        )
    return (
        "ok",
        f"{origin_default}...HEAD",
        f"{why}; fell back to {origin_default}...HEAD",
    )


def _resolve_push(
    repo_root: Path, push_before_sha: str, default_branch: str
) -> tuple[str, str | None, str]:
    """Resolve range for ``push`` events (before SHA / empty tree / fallback)."""
    before = (push_before_sha or "").strip()
    if not before or is_all_zero_oid(before):
        try:
            empty = git_empty_tree_oid(repo_root)
        except RuntimeError as exc:
            return "error", None, str(exc)
        return "ok", f"{empty}..HEAD", "first push / empty before (empty tree)"
    if not try_fetch_commit(repo_root, before):
        return _fallback_origin_default(
            repo_root,
            default_branch,
            why="push before SHA unavailable",
        )
    if not git_merge_base_exists(repo_root, before):
        return "error", None, "no merge-base with push before SHA"
    return "ok", f"{before}...HEAD", "push before SHA"


def _resolve_scheduled(
    repo_root: Path, default_branch: str
) -> tuple[str, str | None, str]:
    """Resolve range for ``schedule`` / ``workflow_dispatch``."""
    origin_default = f"origin/{default_branch}"
    if not git_rev_parse_ok(repo_root, origin_default):
        return "skip", None, f"missing {origin_default}"
    if not git_merge_base_exists(repo_root, origin_default):
        return "skip", None, f"no merge-base with {origin_default}"
    return "ok", f"{origin_default}...HEAD", f"{origin_default} tip"


def resolve_ci_diff_range(
    repo_root: Path,
    *,
    event_name: str,
    pr_base_sha: str = "",
    push_before_sha: str = "",
    default_branch: str = "main",
) -> tuple[str, str | None, str]:
    """Resolve the git diff range for CI docs-impact.

    Returns:
        ``(status, diff_range_or_none, message)`` where status is
        ``ok``, ``skip``, or ``error``.
    """
    event = (event_name or "").strip()
    branch = (default_branch or "main").strip() or "main"

    if event == "pull_request":
        return _resolve_pull_request(repo_root, pr_base_sha)
    if event == "push":
        return _resolve_push(repo_root, push_before_sha, branch)
    if event in {"schedule", "workflow_dispatch"}:
        return _resolve_scheduled(repo_root, branch)
    return "skip", None, f"unsupported event: {event or '(empty)'}"
