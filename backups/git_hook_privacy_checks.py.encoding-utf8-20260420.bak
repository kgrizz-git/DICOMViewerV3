#!/usr/bin/env python3
"""
Staged-file privacy and logging checks for local Git pre-commit.

Runs on staged Python sources under src/ only. Uses the staged index
(`git show :path`) so checks match what will be committed.

Rules (see dev-docs/QUICK_REFERENCE_SECURITY.md):
  - No traceback.print_exc() calls in staged files (entire blob; use sanitized logging).
    Matches outside STRING/COMMENT tokens only so docstrings may mention the API.
  - On added lines: patient tag names from PATIENT_PII_FIELDS in log/print without
    sanitize_message / sanitize_exception.
  - On added lines: conservative path-like literals in logger calls without sanitizer.
  - On added lines: QMessageBox (or .critical/.warning/.information) with raw
    exception text patterns.
  - On added lines: logger.* calls whose first message argument is non-trivial
    (f-string / %-format / .format) must pass through sanitize_message or
    sanitize_exception in that argument subtree.

Environment:
  DICOMVIEWER_PRIVACY_HOOK=warn  — print violations but exit 0.

Inputs: git index (staged changes), repo root from git rev-parse.
Outputs: stderr/stdout messages; exit 0 or 1.
Requirements: stdlib + git; imports PATIENT_PII_FIELDS from src when running
checks (sys.path includes repo/src for hook runs from repo root).
"""

from __future__ import annotations

import argparse
import ast
import io
import os
import re
import subprocess
import sys
import tokenize
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class Violation:
    rule: str
    path: str
    line: int
    message: str


ALLOW_PRINT_EXC = "privacy-hook: allow-print_exc"
ALLOW_LINE = "privacy-hook: allow"


def repo_root() -> Path:
    r = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
        check=True,
    )
    return Path(r.stdout.strip())


def staged_python_src_paths(root: Path) -> list[str]:
    proc = subprocess.run(
        ["git", "-C", str(root), "diff", "--cached", "--name-only", "--diff-filter=ACM"],
        capture_output=True,
        text=True,
        check=True,
    )
    out: list[str] = []
    for line in proc.stdout.splitlines():
        rel = line.strip().replace("\\", "/")
        if not rel.endswith(".py"):
            continue
        if not (rel.startswith("src/")):
            continue
        if rel.startswith("src/") and "/backups/" in rel:
            continue
        out.append(rel)
    return sorted(set(out))


def git_show_staged(root: Path, relpath: str) -> str | None:
    proc = subprocess.run(
        ["git", "-C", str(root), "show", f":{relpath}"],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        return None
    return proc.stdout


def git_diff_cached(root: Path, relpath: str) -> str:
    proc = subprocess.run(
        ["git", "-C", str(root), "diff", "--cached", "-U0", "--", relpath],
        capture_output=True,
        text=True,
        check=False,
    )
    return proc.stdout or ""


def parse_added_line_numbers(diff_text: str) -> set[int]:
    """Return 1-based new-file line numbers introduced by '+' lines in a unified diff."""
    added: set[int] = set()
    current_new: int | None = None
    for line in diff_text.splitlines():
        if line.startswith("@@"):
            m = re.search(r"\+(\d+)(?:,(\d+))?", line)
            if m:
                current_new = int(m.group(1))
            else:
                current_new = None
            continue
        if current_new is None:
            continue
        if line.startswith("+++ ") or line.startswith("--- "):
            continue
        if line.startswith("+"):
            added.add(current_new)
            current_new += 1
        elif line.startswith(" "):
            current_new += 1
        elif line.startswith("-"):
            pass
    return added


def _line_allowed(line: str) -> bool:
    s = line.strip()
    return ALLOW_LINE in s or ALLOW_PRINT_EXC in s


def _string_and_comment_intervals(source: str) -> list[tuple[tuple[int, int], tuple[int, int]]]:
    """Half-open (start, end) spans as (line, col) with 1-based lines, 0-based columns (tokenize convention)."""
    intervals: list[tuple[tuple[int, int], tuple[int, int]]] = []
    try:
        for tok in tokenize.generate_tokens(io.StringIO(source).readline):
            if tok.type in (tokenize.STRING, tokenize.COMMENT):
                intervals.append((tok.start, tok.end))
    except tokenize.TokenError:
        pass
    return intervals


def _pos_ge_start(pos: tuple[int, int], start: tuple[int, int]) -> bool:
    return pos[0] > start[0] or (pos[0] == start[0] and pos[1] >= start[1])


def _pos_lt_end(pos: tuple[int, int], end: tuple[int, int]) -> bool:
    return pos[0] < end[0] or (pos[0] == end[0] and pos[1] < end[1])


def _pos_inside_any_interval(pos: tuple[int, int], intervals: list[tuple[tuple[int, int], tuple[int, int]]]) -> bool:
    for start, end in intervals:
        if _pos_ge_start(pos, start) and _pos_lt_end(pos, end):
            return True
    return False


_PRINT_EXC_RE = re.compile(r"traceback\.print_exc\(", re.IGNORECASE)


def check_traceback_print_exc(relpath: str, staged: str) -> list[Violation]:
    intervals = _string_and_comment_intervals(staged)
    out: list[Violation] = []
    for i, line in enumerate(staged.splitlines(), start=1):
        if _PRINT_EXC_RE.search(line) is None:
            continue
        if line.lstrip().startswith("#"):
            continue
        if ALLOW_PRINT_EXC in line or _line_allowed(line):
            continue
        bad_outside = False
        for m in _PRINT_EXC_RE.finditer(line):
            pos = (i, m.start())
            if not _pos_inside_any_interval(pos, intervals):
                bad_outside = True
                break
        if bad_outside:
            out.append(
                Violation(
                    "no-traceback-print-exc",
                    relpath,
                    i,
                    "Use logging with sanitize_exception(traceback.format_exc()) instead of traceback.print_exc().",
                )
            )
    return out


def _load_patient_fields(repo: Path | None = None) -> frozenset[str]:
    root = repo or repo_root()
    src = root / "src"
    sp = str(src.resolve())
    if sp not in sys.path:
        sys.path.insert(0, sp)
    from utils.log_sanitizer import PATIENT_PII_FIELDS  # type: ignore

    return frozenset(PATIENT_PII_FIELDS)


_PATIENT_FIELDS: frozenset[str] | None = None


def patient_fields(repo: Path | None = None) -> frozenset[str]:
    global _PATIENT_FIELDS
    if _PATIENT_FIELDS is None:
        _PATIENT_FIELDS = _load_patient_fields(repo)
    return _PATIENT_FIELDS


def reset_patient_fields_cache() -> None:
    """Test helper: clear cached PATIENT_PII_FIELDS."""
    global _PATIENT_FIELDS
    _PATIENT_FIELDS = None


_LOG_CALL_RE = re.compile(
    r"\b(logger\.(debug|info|warning|error|exception)|print)\s*\(",
    re.IGNORECASE,
)


def check_patient_fields_in_log_line(relpath: str, line: str, lineno: int) -> list[Violation]:
    if _line_allowed(line):
        return []
    if not _LOG_CALL_RE.search(line):
        return []
    if "sanitize_message" in line or "sanitize_exception" in line:
        return []
    out: list[Violation] = []
    for field in patient_fields():
        if field in line:
            out.append(
                Violation(
                    "patient-field-in-log",
                    relpath,
                    lineno,
                    f"Log/print line references {field}; wrap message with sanitize_message() or omit.",
                )
            )
    return out


_PATH_HINT_RE = re.compile(
    r"(?:[A-Za-z]:\\\\|/Users/|/home/|\\\\Users\\\\|Documents\\\\|Downloads\\\\|Desktop\\\\)",
    re.IGNORECASE,
)


def check_path_literal_in_logger_line(relpath: str, line: str, lineno: int) -> list[Violation]:
    if _line_allowed(line):
        return []
    if not re.search(r"\blogger\.(debug|info|warning|error|exception)\s*\(", line, re.I):
        return []
    if "sanitize_message" in line or "redact_paths=True" in line:
        return []
    if not _PATH_HINT_RE.search(line):
        return []
    return [
        Violation(
            "path-in-log",
            relpath,
            lineno,
            "Logger line may embed a path; use sanitize_message(..., redact_paths=True) or avoid logging paths.",
        )
    ]


_DIALOG_RAW_RE = re.compile(
    r"(?:str\s*\(\s*e\s*\)|repr\s*\(\s*e\s*\)|\{e\}|\{e!|traceback\.|format_exc|print_exc)",
    re.IGNORECASE,
)


def check_dialog_raw_exception(relpath: str, line: str, lineno: int) -> list[Violation]:
    if _line_allowed(line):
        return []
    if "QMessageBox" not in line and not re.search(
        r"\.(critical|warning|information)\s*\(", line
    ):
        return []
    if not _DIALOG_RAW_RE.search(line):
        return []
    if "sanitize_message" in line:
        return []
    return [
        Violation(
            "dialog-raw-exception",
            relpath,
            lineno,
            "Do not show raw exception text in QMessageBox; use sanitize_message() with a generic user message.",
        )
    ]


def _expr_has_sanitize_call(node: ast.AST) -> bool:
    for child in ast.walk(node):
        if isinstance(child, ast.Call):
            fn = child.func
            if isinstance(fn, ast.Name) and fn.id in ("sanitize_message", "sanitize_exception"):
                return True
            if isinstance(fn, ast.Attribute) and fn.attr in ("sanitize_message", "sanitize_exception"):
                return True
    return False


def _is_logger_call(node: ast.Call) -> bool:
    if not isinstance(node.func, ast.Attribute):
        return False
    if node.func.attr not in ("debug", "info", "warning", "error", "exception"):
        return False
    val = node.func.value
    if isinstance(val, ast.Name) and val.id == "logger":
        return True
    if isinstance(val, ast.Attribute) and val.attr == "logger":
        return True
    return False


def _first_log_message_arg(node: ast.Call) -> ast.AST | None:
    if not node.args:
        return None
    return node.args[0]


def _logger_call_needs_sanitize(node: ast.Call) -> bool:
    """True if any logged payload could include PHI/paths (non-literal-only)."""
    if not node.args:
        return False
    if len(node.args) > 1:
        # logger.info("tpl %s", value) — values may contain paths/PHI
        return True
    arg = node.args[0]
    if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
        return False
    if isinstance(arg, ast.JoinedStr):
        return True
    if isinstance(arg, ast.BinOp) and isinstance(arg.op, (ast.Mod, ast.Add)):
        return True
    if isinstance(arg, ast.Call):
        if isinstance(arg.func, ast.Attribute) and arg.func.attr == "format":
            return True
    if isinstance(arg, (ast.Name, ast.Attribute, ast.Subscript)):
        return True
    return True


def check_logger_sanitize_ast(
    relpath: str, staged: str, added_lines: set[int]
) -> list[Violation]:
    if not added_lines:
        return []
    try:
        tree = ast.parse(staged)
    except SyntaxError as e:
        return [
            Violation(
                "syntax",
                relpath,
                getattr(e, "lineno", 1) or 1,
                f"Cannot parse staged file for logger checks: {e}",
            )
        ]

    out: list[Violation] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not _is_logger_call(node):
            continue
        lineno = getattr(node, "lineno", None)
        if lineno is None:
            continue
        end = getattr(node, "end_lineno", lineno)
        span = set(range(lineno, end + 1))
        if not span.intersection(added_lines):
            continue
        if not _logger_call_needs_sanitize(node):
            continue
        msg = _first_log_message_arg(node)
        if msg is None:
            continue
        if _expr_has_sanitize_call(msg):
            continue
        # Multi-arg: sanitize can wrap any arg; accept if any arg subtree has it
        if len(node.args) > 1:
            if any(_expr_has_sanitize_call(a) for a in node.args):
                continue
        out.append(
            Violation(
                "logger-needs-sanitize",
                relpath,
                lineno,
                "Logger call with non-literal message should pass the message through sanitize_message() or sanitize_exception().",
            )
        )
    return out


def check_staged_file(root: Path, relpath: str) -> list[Violation]:
    staged = git_show_staged(root, relpath)
    if staged is None:
        return [
            Violation(
                "git",
                relpath,
                0,
                "Could not read staged blob (git show :path failed).",
            )
        ]

    violations: list[Violation] = []
    violations.extend(check_traceback_print_exc(relpath, staged))

    diff = git_diff_cached(root, relpath)
    added = parse_added_line_numbers(diff)
    lines = staged.splitlines()
    for lineno in sorted(added):
        if lineno < 1 or lineno > len(lines):
            continue
        line = lines[lineno - 1]
        if _line_allowed(line):
            continue
        violations.extend(check_patient_fields_in_log_line(relpath, line, lineno))
        violations.extend(check_path_literal_in_logger_line(relpath, line, lineno))
        violations.extend(check_dialog_raw_exception(relpath, line, lineno))

    violations.extend(check_logger_sanitize_ast(relpath, staged, added))
    return violations


def format_violations(vs: Iterable[Violation]) -> str:
    lines = []
    for v in vs:
        lines.append(f"{v.path}:{v.line}: [{v.rule}] {v.message}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Privacy checks for staged src/*.py")
    parser.parse_args(argv)

    warn_only = os.environ.get("DICOMVIEWER_PRIVACY_HOOK", "").strip().lower() in (
        "warn",
        "warning",
        "1-soft",
    )

    root = repo_root()
    paths = staged_python_src_paths(root)
    all_v: list[Violation] = []
    for rel in paths:
        all_v.extend(check_staged_file(root, rel))

    if not all_v:
        return 0

    text = format_violations(all_v)
    if warn_only:
        print(f"[privacy hook] WARN ({len(all_v)} issue(s)):\n{text}", file=sys.stderr)
        return 0

    print(f"[privacy hook] FAIL ({len(all_v)} issue(s)):\n{text}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
