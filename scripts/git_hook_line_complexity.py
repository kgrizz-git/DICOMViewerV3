#!/usr/bin/env python3
"""Pre-commit hook: block staged files that exceed line-count or complexity thresholds.

Thresholds:
  - File line count: warn at 600, block at 750
  - Function cyclomatic complexity (CCN): block at 20

Grandfathering:
  Files and functions already over the threshold at the time of hook
  installation are recorded in scripts/line_complexity_grandfather.json
  with their measured line count or CCN. Items at or below that recorded
  baseline produce a warning but do NOT block the commit. Any increase
  above the recorded baseline is a regression and blocks the commit.
  New violations (not in the grandfather list) also block the commit.
  When a staged check finds a grandfathered item has improved (smaller
  size/CCN), the recorded cap is automatically ratcheted down (or removed
  if the item falls under the block threshold) and the updated JSON is
  staged so it lands in the same commit — preventing later climbs back up.
  Regenerating the baseline (``--generate-grandfather``) rewrites the
  list from scratch, so entries for files that have since shrunk below
  the threshold are dropped.

Requires the ``lizard`` package from ``requirements-dev.txt``.

Usage:
    python scripts/git_hook_line_complexity.py --staged
    python scripts/git_hook_line_complexity.py --all
    python scripts/git_hook_line_complexity.py --all --generate-grandfather

``--staged`` reads blobs from the Git index (correct for pre-commit).
``--all`` reads the worktree on disk (visibility / baseline generation).
Prefer ``--all --generate-grandfather`` when refreshing the baseline so every
tracked Python file under ``src/``, ``scripts/``, and ``tests/`` is included.
"""

from __future__ import annotations

import argparse
import ast
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

WARN_LINES = 600
BLOCK_LINES = 750
BLOCK_CCN = 20

GRANDFATHER_PATH = Path(__file__).resolve().parent / "line_complexity_grandfather.json"

# Grandfather allowlist shape: per-file and per-function recorded baselines.
GrandfatherData = dict[str, dict[str, int]]


@dataclass
class Violation:
    """One line-count or cyclomatic-complexity finding for a repository path."""

    relpath: str
    kind: str
    label: str
    value: int
    threshold: int
    blocking: bool
    grandfathered: bool
    regressed: bool = False
    baseline: int | None = None

    def format(self) -> str:
        """Return a repo-relative, human-readable one-line summary."""

        if self.regressed and self.baseline is not None:
            tag = f" [regression: was {self.baseline}]"
        elif self.grandfathered:
            tag = " [grandfathered]"
        else:
            tag = ""
        if self.kind == "file_lines":
            return (
                f"{self.relpath}: {self.value} lines "
                f"(threshold {self.threshold}){tag}"
            )
        return (
            f"{self.relpath}: {self.label} CCN={self.value} "
            f"(threshold {self.threshold}){tag}"
        )


def repo_root() -> Path:
    """Return the Git repository root for the current working directory."""

    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
        check=True,
        encoding="utf-8",
    )
    return Path(result.stdout.strip())


def staged_python_files(root: Path) -> list[str]:
    """Return staged ``*.py`` paths (Added/Copied/Modified/Renamed), repo-relative.

    Includes ``R`` so a pure rename of an over-threshold file is still checked
    under its new path (``--name-only`` reports the destination).
    """

    result = subprocess.run(
        [
            "git",
            "-C",
            str(root),
            "diff",
            "--cached",
            "--name-only",
            "--diff-filter=ACMR",
            "--",
            "*.py",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if result.returncode != 0:
        detail = (result.stderr or "").strip() or f"exit {result.returncode}"
        raise RuntimeError(f"git diff --cached failed: {detail}")
    return sorted(
        line.strip()
        for line in result.stdout.splitlines()
        if line.strip()
    )


def all_python_files(root: Path) -> list[str]:
    """Return repo-relative Python paths under ``src``, ``scripts``, and ``tests``."""

    result: list[str] = []
    for base in ("src", "scripts", "tests"):
        base_path = root / base
        if not base_path.is_dir():
            continue
        for path in sorted(base_path.rglob("*.py")):
            rel = path.relative_to(root).as_posix()
            if "/__pycache__/" in f"/{rel}":
                continue
            result.append(rel)
    return result


def staged_file_content(root: Path, relpath: str) -> str | None:
    """Return the staged (index) blob for ``relpath``, or ``None`` if missing."""

    result = subprocess.run(
        ["git", "-C", str(root), "show", f":{relpath}"],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return result.stdout if result.returncode == 0 else None


def worktree_file_content(root: Path, relpath: str) -> str | None:
    """Return worktree file text for ``relpath``, or ``None`` if unreadable."""

    path = root / relpath
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def load_grandfather(path: Path | None = None) -> GrandfatherData:
    """Load the grandfather JSON allowlist (empty structure when missing)."""

    grandfather_path = path or GRANDFATHER_PATH
    if not grandfather_path.exists():
        return {"files": {}, "functions": {}}
    with grandfather_path.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_grandfather(data: GrandfatherData, path: Path | None = None) -> None:
    """Write the grandfather JSON allowlist with stable formatting."""

    grandfather_path = path or GRANDFATHER_PATH
    grandfather_path.parent.mkdir(parents=True, exist_ok=True)
    with grandfather_path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, sort_keys=True)
        f.write("\n")


def require_lizard():
    """Import lizard or raise ``ImportError`` with an actionable install message.

    Callers that are process entry points should catch this and exit non-zero;
    library/test callers see a normal import failure instead of ``SystemExit``.
    """

    try:
        # requirements-dev / CI installs lizard; keep pyright ignore for editors
        # that resolve against requirements.txt alone.
        import lizard  # type: ignore  # pyright: ignore[reportMissingImports]
    except ImportError as exc:
        raise ImportError(
            "the 'lizard' package is required. "
            "Install developer deps: pip install -r requirements-dev.txt"
        ) from exc
    return lizard


def analyze_content(
    relpath: str, content: str, *, lizard_module=None
) -> tuple[list[Violation], bool]:
    """Analyze one file's text for line-count and CCN violations.

    Args:
        relpath: Repository-relative path used in reports and lizard input name.
        content: Full source text to analyze.
        lizard_module: Optional pre-imported lizard module (tests / callers that
            already called :func:`require_lizard`).

    Returns:
        ``(violations, lizard_ok)`` where ``lizard_ok`` is False when lizard
        could not parse the file. Callers must not ratchet grandfather caps
        when ``lizard_ok`` is False (missing function findings would look like
        improvements and delete allowlist entries).
    """

    lizard = lizard_module or require_lizard()
    violations: list[Violation] = []
    lines = len(content.splitlines())

    if lines > WARN_LINES:
        blocking = lines > BLOCK_LINES
        violations.append(
            Violation(
                relpath=relpath,
                kind="file_lines",
                label=relpath,
                value=lines,
                threshold=BLOCK_LINES if blocking else WARN_LINES,
                blocking=blocking,
                grandfathered=False,
            )
        )

    # Real lizard often returns an empty function_list on syntax errors without
    # raising. Reject unparseable Python first so ratchet does not treat "no
    # functions found" as an improvement and delete grandfather caps.
    try:
        ast.parse(content, filename=relpath)
    except SyntaxError:
        print(
            f"[line-complexity] WARN: could not analyze {relpath} "
            "(syntax error or parse failure)",
            file=sys.stderr,
        )
        return violations, False

    try:
        analysis = lizard.analyze_file.analyze_source_code(relpath, content)
    except Exception:
        # Use repo-relative ``relpath`` (not ``path``) so privacy AST checks
        # accept the diagnostic while still identifying the file.
        print(
            f"[line-complexity] WARN: could not analyze {relpath} "
            "(syntax error or parse failure)",
            file=sys.stderr,
        )
        return violations, False

    for func in analysis.function_list:
        if func.cyclomatic_complexity > BLOCK_CCN:
            violations.append(
                Violation(
                    relpath=relpath,
                    kind="function_ccn",
                    label=func.name,
                    value=func.cyclomatic_complexity,
                    threshold=BLOCK_CCN,
                    blocking=True,
                    grandfathered=False,
                )
            )
    return violations, True


def mark_grandfathered(violations: list[Violation], data: GrandfatherData) -> None:
    """Record blocking violations into a grandfather dict (in place)."""

    for v in violations:
        if not v.blocking:
            continue
        if v.kind == "file_lines":
            data["files"].setdefault(v.relpath, v.value)
        else:
            data["functions"].setdefault(f"{v.relpath}::{v.label}", v.value)


def _grandfather_baseline(data: GrandfatherData, violation: Violation) -> int | None:
    """Return the recorded baseline for ``violation``, or ``None`` if absent."""

    if violation.kind == "file_lines":
        raw = data.get("files", {}).get(violation.relpath)
    else:
        raw = data.get("functions", {}).get(f"{violation.relpath}::{violation.label}")
    if raw is None:
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def apply_grandfather(violations: list[Violation], data: GrandfatherData) -> list[Violation]:
    """Apply grandfather baselines: allow at/below recorded value; block growth.

    When a finding is listed in the grandfather JSON:
      - ``value <= baseline`` → grandfathered (warn only for otherwise-blocking items)
      - ``value > baseline`` → regression (always blocking)
    Findings not listed keep their original blocking flag.
    """

    for v in violations:
        baseline = _grandfather_baseline(data, v)
        if baseline is None:
            v.grandfathered = False
            v.regressed = False
            v.baseline = None
            continue
        v.baseline = baseline
        if v.value > baseline:
            # Growth past the recorded hotspot size/CCN is never allowed.
            v.grandfathered = False
            v.regressed = True
            v.blocking = True
        else:
            v.grandfathered = True
            v.regressed = False
    return violations


def ratchet_grandfather(
    data: GrandfatherData, relpath: str, violations: list[Violation]
) -> list[str]:
    """Lower or drop grandfather caps for one file based on current metrics.

    Call with violations from :func:`analyze_content` (before or after
    :func:`apply_grandfather`; uses ``kind`` / ``value`` / ``blocking`` only).

    Returns:
        Human-readable descriptions of each change (empty if unchanged).
    """

    changes: list[str] = []
    files = data.setdefault("files", {})
    functions = data.setdefault("functions", {})

    file_hit = next((v for v in violations if v.kind == "file_lines"), None)
    if relpath in files:
        try:
            recorded = int(files[relpath])
        except (TypeError, ValueError):
            print(
                "[line-complexity] WARN: skipping malformed file grandfather "
                "entry (non-integer cap).",
                file=sys.stderr,
            )
        else:
            if file_hit is None or not file_hit.blocking:
                del files[relpath]
                changes.append(f"{relpath}: removed file cap (was {recorded})")
            elif file_hit.value < recorded:
                files[relpath] = file_hit.value
                changes.append(
                    f"{relpath}: file cap {recorded} -> {file_hit.value}"
                )

    prefix = f"{relpath}::"
    current_funcs = {
        f"{v.relpath}::{v.label}": v.value
        for v in violations
        if v.kind == "function_ccn" and v.blocking
    }
    for key in [k for k in functions if k.startswith(prefix)]:
        try:
            recorded = int(functions[key])
        except (TypeError, ValueError):
            print(
                "[line-complexity] WARN: skipping malformed function grandfather "
                "entry (non-integer cap).",
                file=sys.stderr,
            )
            continue
        if key not in current_funcs:
            del functions[key]
            changes.append(f"{key}: removed function cap (was {recorded})")
        elif current_funcs[key] < recorded:
            functions[key] = current_funcs[key]
            changes.append(
                f"{key}: function cap {recorded} -> {current_funcs[key]}"
            )

    return changes


def stage_grandfather_file(root: Path, grandfather_path: Path) -> bool:
    """``git add`` the grandfather JSON so a ratchet lands in the same commit.

    Returns:
        True when ``git add`` succeeds; False (with a stderr warning) otherwise.
    """

    try:
        rel = grandfather_path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        rel = str(grandfather_path)
    result = subprocess.run(
        ["git", "-C", str(root), "add", "--", rel],
        capture_output=True,
        text=True,
        check=False,
        encoding="utf-8",
    )
    if result.returncode != 0:
        print(
            "[line-complexity] WARN: git add failed for grandfather JSON "
            "(ratchet may not be staged into this commit).",
            file=sys.stderr,
        )
        return False
    return True


def generate_grandfather(
    root: Path,
    files: list[str],
    *,
    grandfather_path: Path | None = None,
    lizard_module=None,
) -> int:
    """Rebuild the grandfather baseline from the given worktree files."""

    lizard = lizard_module or require_lizard()
    data: GrandfatherData = {"files": {}, "functions": {}}
    for relpath in files:
        content = worktree_file_content(root, relpath)
        if content is None:
            continue
        violations, lizard_ok = analyze_content(
            relpath, content, lizard_module=lizard
        )
        if not lizard_ok:
            continue
        mark_grandfathered(violations, data)
    save_grandfather(data, path=grandfather_path)
    print(
        "[line-complexity] Grandfather file written. "
        f"files: {len(data['files'])}  functions: {len(data['functions'])}"
    )
    return 0


def _partition_violations(
    all_violations: list[Violation],
) -> tuple[list[Violation], list[Violation]]:
    """Split findings into blocking vs warn-only lists."""

    blocking: list[Violation] = []
    warning: list[Violation] = []
    for v in all_violations:
        if v.regressed or (v.blocking and not v.grandfathered):
            blocking.append(v)
        else:
            warning.append(v)
    return blocking, warning


def _print_violation_groups(
    warning: list[Violation], blocking: list[Violation]
) -> None:
    """Emit WARN / FAIL sections for partitioned findings."""

    if warning:
        print("[line-complexity] WARN (not blocking):")
        for v in warning:
            print(f"  - {v.format()}")
    if blocking:
        print(
            "[line-complexity] FAIL — new violations or grandfather "
            "regressions block the commit:"
        )
        for v in blocking:
            print(f"  - {v.format()}")


def _persist_ratchet(
    root: Path,
    gf_path: Path,
    data: GrandfatherData,
    notes: list[str],
    *,
    from_index: bool,
) -> None:
    """Write ratcheted grandfather JSON and optionally stage it."""

    if not notes:
        return
    save_grandfather(data, path=gf_path)
    staged_ok = True
    if from_index:
        staged_ok = stage_grandfather_file(root, gf_path)
    print("[line-complexity] Ratcheted grandfather caps downward:")
    for note in notes:
        print(f"  - {note}")
    if from_index and not staged_ok:
        print(
            "[line-complexity] WARN: grandfather caps were updated on disk but "
            "not staged into this commit.",
            file=sys.stderr,
        )


def check_files(
    root: Path,
    files: list[str],
    *,
    from_index: bool = True,
    grandfather_path: Path | None = None,
    lizard_module=None,
    ratchet: bool | None = None,
) -> int:
    """Check files and return process exit code (0 ok, 1 new blocking findings).

    Args:
        root: Repository root.
        files: Repo-relative Python paths to inspect.
        from_index: When True, read staged index blobs (pre-commit). When False,
            read the worktree (``--all`` visibility mode).
        grandfather_path: Optional override for the allowlist JSON path.
        lizard_module: Optional pre-imported lizard module.
        ratchet: When True, lower/drop grandfather caps that improved and persist
            the JSON (and ``git add`` it when ``from_index``). Defaults to True
            for staged checks and False for ``--all``.
    """

    if ratchet is None:
        ratchet = from_index

    lizard = lizard_module or require_lizard()
    gf_path = grandfather_path or GRANDFATHER_PATH
    data = load_grandfather(gf_path)
    all_violations: list[Violation] = []
    ratchet_notes: list[str] = []
    reader = staged_file_content if from_index else worktree_file_content
    for relpath in files:
        content = reader(root, relpath)
        if content is None:
            continue
        violations, lizard_ok = analyze_content(
            relpath, content, lizard_module=lizard
        )
        if ratchet and lizard_ok:
            # Skip ratchet when lizard failed — empty function findings would
            # incorrectly look like CCN improvements and drop grandfather caps.
            ratchet_notes.extend(ratchet_grandfather(data, relpath, violations))
        all_violations.extend(apply_grandfather(violations, data))

    if ratchet:
        _persist_ratchet(
            root, gf_path, data, ratchet_notes, from_index=from_index
        )

    if not all_violations:
        print("[line-complexity] OK — no new line-count or complexity violations.")
        return 0

    blocking, warning = _partition_violations(all_violations)
    _print_violation_groups(warning, blocking)
    return 1 if blocking else 0


def main(argv: list[str] | None = None) -> int:
    """CLI entry: parse args, resolve file set, generate or check."""

    parser = argparse.ArgumentParser(
        description="Line-count and complexity pre-commit gate."
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--staged", action="store_true", help="check staged Python files (index)"
    )
    mode.add_argument(
        "--all",
        action="store_true",
        help="check all Python files in the worktree (visibility / baseline)",
    )
    parser.add_argument(
        "--generate-grandfather",
        action="store_true",
        help="regenerate the grandfather baseline from current worktree files",
    )
    parser.add_argument(
        "--ratchet",
        action=argparse.BooleanOptionalAction,
        default=None,
        help=(
            "lower/drop improved grandfather caps and save the JSON "
            "(default: on for --staged, off for --all)"
        ),
    )
    args = parser.parse_args(argv)

    try:
        lizard = require_lizard()
    except ImportError:
        print(
            "[line-complexity] FAIL: the 'lizard' package is required. "
            "Install developer deps: pip install -r requirements-dev.txt",
            file=sys.stderr,
        )
        return 1

    root = repo_root()
    try:
        files = staged_python_files(root) if args.staged else all_python_files(root)
    except RuntimeError:
        print(
            "[line-complexity] FAIL: could not list staged Python files "
            "(git diff --cached failed).",
            file=sys.stderr,
        )
        return 1

    if not files:
        print("[line-complexity] No Python files to check.")
        return 0

    if args.generate_grandfather:
        if args.staged:
            print(
                "[line-complexity] WARN: generating grandfather from --staged "
                "only includes staged files; prefer --all --generate-grandfather.",
                file=sys.stderr,
            )
        return generate_grandfather(root, files, lizard_module=lizard)

    return check_files(
        root,
        files,
        from_index=args.staged,
        lizard_module=lizard,
        ratchet=args.ratchet,
    )


if __name__ == "__main__":
    raise SystemExit(main())
