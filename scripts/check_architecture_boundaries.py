#!/usr/bin/env python3
"""
Check incremental architecture import boundaries for DICOM Viewer V3.

This is intentionally small: it catches the highest-risk import drift described
in ARCHITECTURE.md without trying to model every valid local edge.

Usage (from repository root):
    python scripts/check_architecture_boundaries.py
    python scripts/check_architecture_boundaries.py --refresh-baseline

Exit code: 0 if all scanned imports respect the configured boundaries, 1 if
non-baselined violations are found.
"""

from __future__ import annotations

import argparse
import ast
import sys
from dataclasses import dataclass
from pathlib import Path

try:
    from scripts.privacy_console import (
        print_architecture_baseline_written,
        print_architecture_violation,
    )
except ModuleNotFoundError:
    import privacy_console  # pyright: ignore[reportImplicitRelativeImport]

    print_architecture_baseline_written = (
        privacy_console.print_architecture_baseline_written
    )
    print_architecture_violation = privacy_console.print_architecture_violation

SRC_DIRNAME = "src"
DEFAULT_BASELINE = Path("dev-docs/architecture_boundary_baseline.txt")


@dataclass(frozen=True)
class ImportViolation:
    """One import edge that violates an architecture boundary."""

    path: Path
    line: int
    imported_module: str
    reason: str

    def format(self, repo_root: Path) -> str:
        rel = self.path.relative_to(repo_root).as_posix()
        return f"{rel}:{self.line}: {self.reason} ({self.imported_module})"


def top_level_package(module_name: str) -> str:
    """Return the first package segment, handling ``src.<pkg>`` imports."""
    parts = [part for part in module_name.split(".") if part]
    if not parts:
        return ""
    if parts[0] == SRC_DIRNAME and len(parts) > 1:
        return parts[1]
    return parts[0]


def module_for_file(path: Path, src_root: Path) -> str:
    """Return dotted module path under ``src`` for a Python file."""
    rel = path.relative_to(src_root).with_suffix("")
    if rel.name == "__init__":
        rel = rel.parent
    return ".".join(rel.parts)


def importing_domain(path: Path, src_root: Path) -> str:
    """Return the source domain for a file: ``core``, ``gui``, etc."""
    rel = path.relative_to(src_root)
    if len(rel.parts) == 1:
        return "main" if rel.parts[0] == "main.py" else ""
    return rel.parts[0]


def resolve_relative_import(node: ast.ImportFrom, current_module: str) -> str:
    """Resolve simple relative import targets to a best-effort absolute module."""
    if node.level == 0:
        return node.module or ""
    parts = current_module.split(".")
    if parts and parts[-1] != "__init__":
        parts = parts[:-1]
    keep = max(0, len(parts) - (node.level - 1))
    base_parts = parts[:keep]
    if node.module:
        base_parts.extend(node.module.split("."))
    return ".".join(part for part in base_parts if part)


def is_type_checking_guard(test: ast.expr) -> bool:
    """Return True if an ``if`` test is ``TYPE_CHECKING`` or ``typing.TYPE_CHECKING``."""
    if isinstance(test, ast.Name):
        return test.id == "TYPE_CHECKING"
    if isinstance(test, ast.Attribute):
        return test.attr == "TYPE_CHECKING"
    return False


def imported_modules(tree: ast.AST, current_module: str) -> list[tuple[int, str]]:
    """Collect imported module names with line numbers.

    Imports inside ``if TYPE_CHECKING:`` blocks are skipped: they never execute
    at runtime and are the standard idiom for type-hint-only references that
    avoid real circular imports, so they carry no architectural coupling.
    """
    imports: list[tuple[int, str]] = []

    def visit(node: ast.AST) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.If) and is_type_checking_guard(child.test):
                continue
            if isinstance(child, ast.Import):
                for alias in child.names:
                    imports.append((child.lineno, alias.name))
            elif isinstance(child, ast.ImportFrom):
                module = resolve_relative_import(child, current_module)
                if module:
                    imports.append((child.lineno, module))
            visit(child)

    visit(tree)
    return imports


def violation_reason(importer_domain: str, imported_top: str) -> str | None:
    """Return a violation reason for a forbidden import edge, if any."""
    if importer_domain == "core" and imported_top == "gui":
        return "core modules must not import gui; move UI work to gui or a facade"
    if importer_domain == "utils" and imported_top in {"gui", "core", "main", "roi", "metadata", "tools"}:
        return "utils modules must not import app/UI domains"
    if importer_domain == "gui" and imported_top == "main":
        return "gui modules must not import main; use callbacks, signals, or facades"
    if importer_domain in {"roi", "metadata"} and imported_top == "main":
        return f"{importer_domain} modules must not import main; use injected app services"
    return None


def check_file(path: Path, src_root: Path) -> list[ImportViolation]:
    """Parse one Python file and return boundary violations."""
    text = path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(text, filename=str(path))
    except SyntaxError as exc:
        return [
            ImportViolation(
                path=path,
                line=exc.lineno or 1,
                imported_module="<syntax>",
                reason=f"could not parse Python file: {exc.msg}",
            )
        ]

    importer = importing_domain(path, src_root)
    current_module = module_for_file(path, src_root)
    violations: list[ImportViolation] = []
    for line, module_name in imported_modules(tree, current_module):
        reason = violation_reason(importer, top_level_package(module_name))
        if reason:
            violations.append(
                ImportViolation(
                    path=path,
                    line=line,
                    imported_module=module_name,
                    reason=reason,
                )
            )
    return violations


def iter_python_files(src_root: Path) -> list[Path]:
    """Return project Python files under ``src``."""
    if not src_root.is_dir():
        return []
    return sorted(path for path in src_root.rglob("*.py") if path.is_file())


def read_baseline(path: Path | None) -> set[str]:
    """Read baseline violation lines, ignoring blanks and comments."""
    if path is None or not path.is_file():
        return set()
    return {
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }


def write_baseline(path: Path, violations: list[ImportViolation], repo_root: Path) -> None:
    """Write the current violation set as the architecture baseline."""
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Known architecture-boundary violations.",
        "# Generated by: python scripts/check_architecture_boundaries.py --refresh-baseline",
        "# Remove entries as modules are refactored toward ARCHITECTURE.md.",
        "",
    ]
    lines.extend(sorted(violation.format(repo_root) for violation in violations))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _violation_category(violation: ImportViolation) -> str:
    if violation.reason.startswith("core modules"):
        return "core-gui"
    if violation.reason.startswith("utils modules"):
        return "utils-domain"
    if violation.reason.startswith("gui modules"):
        return "gui-main"
    if violation.reason.startswith(("roi modules", "metadata modules")):
        return "domain-main"
    return "syntax"


def _print_violation(violation: ImportViolation, repo_root: Path) -> None:
    category = _violation_category(violation)
    repository_path = violation.path.relative_to(repo_root).as_posix()
    if category == "core-gui":
        print_architecture_violation(
            "core-gui",
            module=violation.imported_module,
            repository_path=repository_path,
            line=violation.line,
            file=sys.stderr,
        )
        print("core modules must not import gui", file=sys.stderr)
    elif category == "utils-domain":
        print_architecture_violation(
            "utils-domain",
            module=violation.imported_module,
            repository_path=repository_path,
            line=violation.line,
            file=sys.stderr,
        )
        print("utils modules must not import app/UI domains", file=sys.stderr)
    elif category == "gui-main":
        print_architecture_violation(
            "gui-main",
            module=violation.imported_module,
            repository_path=repository_path,
            line=violation.line,
            file=sys.stderr,
        )
        print("gui modules must not import main", file=sys.stderr)
    elif category == "domain-main":
        print_architecture_violation(
            "domain-main",
            module=violation.imported_module,
            repository_path=repository_path,
            line=violation.line,
            file=sys.stderr,
        )
        print("domain modules must not import main", file=sys.stderr)
    else:
        print_architecture_violation(
            "syntax",
            module=violation.imported_module,
            repository_path=repository_path,
            line=violation.line,
            file=sys.stderr,
        )
        print("Python source could not be parsed", file=sys.stderr)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parent.parent,
        help="Repository root (default: parent of scripts/).",
    )
    parser.add_argument(
        "--baseline",
        type=Path,
        default=None,
        help=(
            "Known-violation baseline. Defaults to "
            "dev-docs/architecture_boundary_baseline.txt if it exists."
        ),
    )
    parser.add_argument(
        "--refresh-baseline",
        action="store_true",
        help="Write the current violation set to the baseline and exit 0.",
    )
    args = parser.parse_args()
    repo_root = args.root.resolve()
    src_root = repo_root / SRC_DIRNAME
    baseline_path = (
        args.baseline.resolve()
        if args.baseline is not None
        else (repo_root / DEFAULT_BASELINE).resolve()
    )

    violations: list[ImportViolation] = []
    for path in iter_python_files(src_root):
        violations.extend(check_file(path, src_root))

    if args.refresh_baseline:
        write_baseline(baseline_path, violations, repo_root)
        print_architecture_baseline_written(count=len(violations))
        return 0

    baseline = read_baseline(baseline_path)
    new_violations = [
        violation
        for violation in violations
        if violation.format(repo_root) not in baseline
    ]
    stale_baseline = baseline - {violation.format(repo_root) for violation in violations}

    if new_violations:
        print("Architecture boundary check failed:", file=sys.stderr)
        for violation in new_violations:
            _print_violation(violation, repo_root)
        if stale_baseline:
            print(
                f"  note: {len(stale_baseline)} stale baseline entrie(s) can be removed",
                file=sys.stderr,
            )
        return 1

    baseline_note = f", baseline={len(baseline)}" if baseline else ""
    stale_note = f", stale_baseline={len(stale_baseline)}" if stale_baseline else ""
    python_file_count = len(iter_python_files(src_root))
    print(
        "OK: architecture boundaries "
        f"({python_file_count} Python file(s) scanned, "
        f"violations={len(violations)}{baseline_note}{stale_note})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
