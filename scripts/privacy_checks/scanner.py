"""Mode-aware orchestration for the modular privacy checks."""

from __future__ import annotations

from pathlib import Path

from .ast_rules import check_python_ast
from .git_paths import (
    all_python_scan_paths,
    git_diff_cached,
    git_show_staged,
    parse_added_line_numbers,
    staged_absolute_path_check_paths,
    staged_python_scan_paths,
)
from .models import Violation
from .schema_contract import (
    SCHEMA_RELATIVE_PATH,
    StructuralEventSchema,
    StructuralSchemaError,
    load_structural_event_schema,
)
from .text_rules import (
    check_absolute_path_in_doc_line,
    check_dialog_raw_exception,
    check_path_literal_in_logger_line,
    check_patient_fields_in_log_line,
    check_traceback_print_exc,
)


def check_staged_python_file(
    root: Path,
    relpath: str,
    *,
    schema: StructuralEventSchema | None = None,
) -> list[Violation]:
    """Check one staged Python blob, restricting new AST rules to added lines."""

    source = git_show_staged(root, relpath)
    if source is None:
        return [Violation("git-read", relpath, 0)]
    added = parse_added_line_numbers(git_diff_cached(root, relpath))
    violations = check_traceback_print_exc(relpath, source)
    violations.extend(check_python_ast(relpath, source, added, schema=schema))

    lines = source.splitlines()
    for line_number in sorted(added):
        if not 1 <= line_number <= len(lines):
            continue
        line = lines[line_number - 1]
        violations.extend(check_patient_fields_in_log_line(relpath, line, line_number))
        violations.extend(check_path_literal_in_logger_line(relpath, line, line_number))
        violations.extend(check_dialog_raw_exception(relpath, line, line_number))
    return _deduplicate(violations)


def check_staged_doc_file(root: Path, relpath: str) -> list[Violation]:
    """Check added lines in one staged documentation/config/script blob."""

    source = git_show_staged(root, relpath)
    if source is None:
        return [Violation("git-read", relpath, 0)]
    added = parse_added_line_numbers(git_diff_cached(root, relpath))
    lines = source.splitlines()
    violations: list[Violation] = []
    for line_number in sorted(added):
        if 1 <= line_number <= len(lines):
            violations.extend(
                check_absolute_path_in_doc_line(
                    relpath, lines[line_number - 1], line_number
                )
            )
    return violations


def scan_staged(root: Path) -> list[Violation]:
    """Scan staged Python sinks and legacy machine-path text rules."""

    try:
        schema = load_scan_schema(root, staged=True)
    except StructuralSchemaError:
        return [Violation("structural-schema", SCHEMA_RELATIVE_PATH, 0)]
    violations: list[Violation] = []
    python_paths = staged_python_scan_paths(root)
    schema_changed = bool(git_diff_cached(root, SCHEMA_RELATIVE_PATH))
    if schema_changed:
        for relpath in all_python_scan_paths(root):
            source = git_show_staged(root, relpath)
            if source is None:
                try:
                    source = (root / relpath).read_text(encoding="utf-8")
                except (OSError, UnicodeError):
                    violations.append(Violation("file-read", relpath, 0))
                    continue
            violations.extend(check_python_ast(relpath, source, schema=schema))
    else:
        for relpath in python_paths:
            violations.extend(
                check_staged_python_file(root, relpath, schema=schema)
            )
    for relpath in staged_absolute_path_check_paths(root):
        if relpath not in python_paths:
            violations.extend(check_staged_doc_file(root, relpath))
    return _deduplicate(violations)


def scan_all(root: Path) -> list[Violation]:
    """Scan all covered Python worktree files."""

    try:
        schema = load_scan_schema(root, staged=False)
    except StructuralSchemaError:
        return [Violation("structural-schema", SCHEMA_RELATIVE_PATH, 0)]
    violations: list[Violation] = []
    for relpath in all_python_scan_paths(root):
        try:
            source = (root / relpath).read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            violations.append(Violation("file-read", relpath, 0))
            continue
        violations.extend(check_python_ast(relpath, source, schema=schema))
    return _deduplicate(violations)


def load_scan_schema(root: Path, *, staged: bool) -> StructuralEventSchema:
    """Load the candidate index schema for staged scans, otherwise the worktree."""

    if staged:
        staged_content = git_show_staged(root, SCHEMA_RELATIVE_PATH)
        if staged_content is not None:
            return load_structural_event_schema(content=staged_content)
    return load_structural_event_schema(root / SCHEMA_RELATIVE_PATH)


def _deduplicate(violations: list[Violation]) -> list[Violation]:
    return sorted(set(violations), key=lambda item: (item.path, item.line, item.rule))
