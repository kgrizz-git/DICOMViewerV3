"""Git-index and filesystem path discovery for privacy checks."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path, PurePosixPath
from typing import Any, Final

_SUBPROCESS_TEXT: Final[dict[str, Any]] = {"encoding": "utf-8"}

_DOC_PATH_SUFFIXES: Final[tuple[str, ...]] = (
    ".md",
    ".txt",
    ".rst",
    ".yml",
    ".yaml",
)
_PATH_CHECK_SCRIPT_SUFFIXES: Final[tuple[str, ...]] = (
    ".py",
    ".sh",
    ".ps1",
    ".bat",
)
_EXTERNAL_DATA_TEST_NAMES: Final[frozenset[str]] = frozenset(
    {
        "fusion_blind_verification.py",
        "generate_rdsr_dose_sr_fixtures.py",
    }
)


def repo_root() -> Path:
    """Return the current Git worktree root."""

    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
        check=True,
        **_SUBPROCESS_TEXT,
    )
    return Path(result.stdout.strip())


def _staged_paths(root: Path) -> list[str]:
    result = subprocess.run(
        [
            "git",
            "-C",
            str(root),
            "diff",
            "--cached",
            "--name-only",
            "--diff-filter=ACM",
        ],
        capture_output=True,
        text=True,
        check=True,
        **_SUBPROCESS_TEXT,
    )
    return sorted(
        {
            line.strip().replace("\\", "/")
            for line in result.stdout.splitlines()
            if line.strip()
        }
    )


def _is_external_data_test(relpath: str) -> bool:
    path = PurePosixPath(relpath)
    if not relpath.startswith("tests/") or path.suffix != ".py":
        return False
    return (
        path.name.startswith("fusion_audit")
        or path.name in _EXTERNAL_DATA_TEST_NAMES
        or path.parts[:2] == ("tests", "scripts")
    )


def is_python_scan_path(relpath: str) -> bool:
    """Return whether a Python path can process application/external data."""

    if not relpath.endswith(".py") or "/__pycache__/" in f"/{relpath}":
        return False
    if relpath.startswith("src/"):
        return "/backups/" not in relpath
    return relpath.startswith("scripts/") or _is_external_data_test(relpath)


def staged_python_scan_paths(root: Path) -> list[str]:
    """Return staged Python paths covered by sink enforcement."""

    return [path for path in _staged_paths(root) if is_python_scan_path(path)]


def all_python_scan_paths(root: Path) -> list[str]:
    """Return all worktree Python paths covered by sink enforcement."""

    roots = (root / "src", root / "scripts", root / "tests")
    paths: set[str] = set()
    for scan_root in roots:
        if not scan_root.is_dir():
            continue
        for path in scan_root.rglob("*.py"):
            relpath = path.relative_to(root).as_posix()
            if is_python_scan_path(relpath):
                paths.add(relpath)
    return sorted(paths)


def staged_doc_like_paths(root: Path) -> list[str]:
    """Return staged documentation/config text paths (compatibility API)."""

    return [
        path
        for path in _staged_paths(root)
        if not path.endswith(".py") and path.lower().endswith(_DOC_PATH_SUFFIXES)
    ]


def staged_absolute_path_check_paths(root: Path) -> list[str]:
    """Return staged docs/config and scripts that may embed developer paths."""

    paths: list[str] = []
    for relpath in _staged_paths(root):
        if relpath.startswith("tests/"):
            continue
        suffix = PurePosixPath(relpath).suffix.lower()
        if suffix in _DOC_PATH_SUFFIXES or suffix in _PATH_CHECK_SCRIPT_SUFFIXES:
            paths.append(relpath)
    return paths


def git_show_staged(root: Path, relpath: str) -> str | None:
    """Read one staged blob as UTF-8 without using the worktree copy."""

    result = subprocess.run(
        ["git", "-C", str(root), "show", f":{relpath}"],
        capture_output=True,
        text=True,
        **_SUBPROCESS_TEXT,
    )
    return result.stdout if result.returncode == 0 else None


def git_diff_cached(root: Path, relpath: str) -> str:
    """Return a zero-context staged diff for one repository path."""

    result = subprocess.run(
        ["git", "-C", str(root), "diff", "--cached", "-U0", "--", relpath],
        capture_output=True,
        text=True,
        check=False,
        **_SUBPROCESS_TEXT,
    )
    return result.stdout or ""


def parse_added_line_numbers(diff_text: str) -> set[int]:
    """Return 1-based new-file line numbers introduced by a unified diff."""

    added: set[int] = set()
    current_new: int | None = None
    for line in diff_text.splitlines():
        if line.startswith("@@"):
            match = re.search(r"\+(\d+)(?:,(\d+))?", line)
            current_new = int(match.group(1)) if match else None
            continue
        if current_new is None or line.startswith(("+++ ", "--- ")):
            continue
        if line.startswith("+"):
            added.add(current_new)
            current_new += 1
        elif line.startswith(" "):
            current_new += 1
    return added
