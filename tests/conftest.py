"""
Pytest and unittest configuration for DICOM Viewer V3 tests.

Adds project src/ to sys.path so tests can import from core, utils, gui, tools, etc.
Run tests from project root with:
  - pytest
  - python -m unittest discover -s tests -p "test_*.py"
  - python tests/run_tests.py
"""

import os
import sys

import pytest

# Match the CI configuration and permit QWidget visibility tests on headless
# developer/agent hosts. Set this before any test module creates QApplication.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

# Add src to path so that "from core.xxx" and "from utils.xxx" work
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_src_dir = os.path.join(_project_root, "src")
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)


# Holds the process-wide QApplication so it can never be garbage collected.
_QAPP = None


def pytest_configure(config):
    """Register markers and create the process-wide QApplication.

    The QApplication must exist before *any* test runs. A test that creates a
    bare ``QCoreApplication`` first would otherwise win the race and poison the
    process: ``QCoreApplication`` is non-GUI, so every later widget
    construction aborts with "QWidget: Cannot create a QWidget without
    QApplication". Serial ordering usually hides this; pytest-xdist shards
    tests across workers in a different order and exposes it.
    """
    config.addinivalue_line("markers", "qt: mark test as requiring QApplication (PySide6)")

    global _QAPP
    try:
        from PySide6.QtWidgets import QApplication
    except ImportError:
        return  # PySide6 absent; qapp-dependent tests skip themselves.
    if QApplication.instance() is None:
        _QAPP = QApplication(sys.argv[:1])


@pytest.fixture(scope="session")
def qapp():
    """Provide QApplication for tests that need Qt (e.g. measurement_items). One per test session."""
    try:
        from PySide6.QtWidgets import QApplication
    except ImportError:
        pytest.skip("PySide6 not installed")
    # Check the *type*, not merely existence: a stray QCoreApplication is
    # non-None but cannot host widgets, and must not satisfy this guard.
    app = QApplication.instance()
    if not isinstance(app, QApplication):
        if app is not None:
            raise RuntimeError(
                f"A non-GUI {type(app).__name__} owns this process; widgets cannot be "
                "created. Depend on the qapp fixture instead of constructing a "
                "QCoreApplication in a test."
            )
        app = QApplication(sys.argv[:1])
    return app
