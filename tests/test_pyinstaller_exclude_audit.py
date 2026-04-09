# test_pyinstaller_exclude_audit.py
#
# Guards PyInstaller macOS-only Qt excludes, matplotlib backend/writer excludes, and
# PIL Tk helper excludes: fails if application (or test) code imports a stripped module.
#
# Limits: AST import analysis only — does not scan site-packages (pylinac, etc.)
# or dynamic imports (importlib, string backend names to matplotlib.use()).

"""Audit imports against PyInstaller exclude lists (see scripts/pyinstaller_exclude_lists.py)."""

from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

# Project root (parent of tests/)
_ROOT = Path(__file__).resolve().parents[1]
_SCRIPTS = _ROOT / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from pyinstaller_exclude_lists import (  # noqa: E402
    MACOS_PYSIDE6_MODULE_EXCLUDES,
    MATPLOTLIB_BACKEND_AND_WRITER_EXCLUDES,
    PIL_TK_RELATED_EXCLUDES,
)


def _python_files_under(root: Path) -> list[Path]:
    return sorted(p for p in root.rglob("*.py") if p.is_file())


def _collect_import_module_names(tree: ast.AST) -> set[str]:
    """Return fully-qualified module strings from top-level import nodes."""
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.level != 0 or not node.module:
                continue
            names.add(node.module)
            # `from PIL import ImageTk` -> PIL.ImageTk (not just `PIL`).
            if node.module == "PIL":
                for alias in node.names:
                    if alias.name == "*":
                        continue
                    names.add(f"PIL.{alias.name}")
    return names


def _import_conflicts_excludes(imported: str, excludes: tuple[str, ...]) -> list[str]:
    """Return exclude entries that ban this imported module name."""
    hits: list[str] = []
    for exc in excludes:
        if imported == exc or imported.startswith(exc + "."):
            hits.append(exc)
    return hits


@pytest.mark.parametrize("root_name", ["src", "tests"])
def test_matplotlib_excluded_backends_not_imported(root_name: str) -> None:
    root = _ROOT / root_name
    assert root.is_dir(), f"missing {root}"
    offenders: list[str] = []
    for path in _python_files_under(root):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for mod in _collect_import_module_names(tree):
            if not mod.startswith("matplotlib.backends."):
                continue
            bad = _import_conflicts_excludes(mod, MATPLOTLIB_BACKEND_AND_WRITER_EXCLUDES)
            for exc in bad:
                offenders.append(f"{path.relative_to(_ROOT)}: imports {mod!r} (excluded {exc!r})")
    assert not offenders, "Excluded matplotlib backends imported:\n" + "\n".join(offenders)


@pytest.mark.parametrize("root_name", ["src", "tests"])
def test_pil_tk_helpers_not_imported(root_name: str) -> None:
    """Frozen app excludes PIL.ImageTk / PIL._tkinter_finder; fail if src/tests import them."""
    root = _ROOT / root_name
    assert root.is_dir(), f"missing {root}"
    offenders: list[str] = []
    for path in _python_files_under(root):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for mod in _collect_import_module_names(tree):
            bad = _import_conflicts_excludes(mod, PIL_TK_RELATED_EXCLUDES)
            for exc in bad:
                offenders.append(f"{path.relative_to(_ROOT)}: imports {mod!r} (excluded {exc!r})")
    assert not offenders, "Excluded PIL Tk helper modules imported:\n" + "\n".join(offenders)


@pytest.mark.parametrize("root_name", ["src", "tests"])
def test_macos_excluded_pyside6_not_imported(root_name: str) -> None:
    root = _ROOT / root_name
    assert root.is_dir(), f"missing {root}"
    offenders: list[str] = []
    for path in _python_files_under(root):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for mod in _collect_import_module_names(tree):
            if not mod.startswith("PySide6."):
                continue
            bad = _import_conflicts_excludes(mod, MACOS_PYSIDE6_MODULE_EXCLUDES)
            for exc in bad:
                offenders.append(f"{path.relative_to(_ROOT)}: imports {mod!r} (excluded on macOS {exc!r})")
    assert not offenders, "Excluded PySide6 modules imported:\n" + "\n".join(offenders)


def test_histogram_uses_qtagg_backend_only() -> None:
    """Regression: histogram must keep using backend_qtagg (matches hiddenimports)."""
    hw = _ROOT / "src" / "tools" / "histogram_widget.py"
    text = hw.read_text(encoding="utf-8")
    assert "backend_qtagg" in text
    assert "backend_qt5agg" not in text
    assert "backend_qt4agg" not in text
