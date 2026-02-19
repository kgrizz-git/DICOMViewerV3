"""
Pytest and unittest configuration for DICOM Viewer V3 tests.

Adds project src/ to sys.path so tests can import from core, utils, gui, tools, etc.
Run tests from project root with:
  - pytest
  - python -m unittest discover -s tests -p "test_*.py"
  - python tests/run_tests.py
"""

import sys
import os

import pytest

# Add src to path so that "from core.xxx" and "from utils.xxx" work
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_src_dir = os.path.join(_project_root, "src")
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)


def pytest_configure(config):
    """Optional: mark tests that need Qt (Phase 1 measurement_items)."""
    config.addinivalue_line("markers", "qt: mark test as requiring QApplication (PySide6)")


@pytest.fixture(scope="session")
def qapp():
    """Provide QApplication for tests that need Qt (e.g. measurement_items). One per test session."""
    try:
        from PySide6.QtWidgets import QApplication
    except ImportError:
        pytest.skip("PySide6 not installed")
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app
