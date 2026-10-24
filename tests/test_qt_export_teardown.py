"""Regression for export widgets surviving into PySide interpreter cleanup."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest


def test_export_capture_releases_widgets_before_interpreter_shutdown(tmp_path):
    """Run the formerly leaking test in isolation, including interpreter exit."""
    probe = tmp_path / "qt_teardown_probe.py"
    probe.write_text(
        "from PySide6.QtWidgets import QApplication\n"
        "def pytest_sessionfinish(session):\n"
        "    widgets = QApplication.topLevelWidgets()\n"
        "    names = [type(widget).__name__ for widget in widgets]\n"
        "    print('QT_EXPORT_SURVIVORS:', names)\n"
        "    if widgets:\n"
        "        session.exitstatus = 1\n",
        encoding="utf-8",
    )
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join(
        filter(None, [str(tmp_path), env.get("PYTHONPATH", "")])
    )
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-o", "addopts=", "-n", "0",
         "-p", "no:cacheprovider", "-p", "qt_teardown_probe", "-q",
         "tests/test_volume_image_export.py::test_button_recovers_after_failed_first_capture"],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "QT_EXPORT_SURVIVORS: []" in result.stdout


@pytest.mark.parametrize("existing_qapp", [False, True], ids=["new-app", "existing-app"])
def test_session_finish_deletes_retained_widgets_before_interpreter_shutdown(tmp_path, existing_qapp):
    """Exercise session cleanup with widgets retained past fixture teardown."""
    probe = tmp_path / "qt_session_cleanup_probe.py"
    early_application = (
        "early_app = None\n"
        "@pytest.hookimpl(tryfirst=True)\n"
        "def pytest_configure(config):\n"
        "    global early_app\n"
        "    from PySide6.QtWidgets import QApplication\n"
        "    early_app = QApplication.instance() or QApplication([])\n"
    ) if existing_qapp else ""
    probe.write_text(
        "import pytest\n"
        + early_application
        + "retained = []\n"
        "@pytest.hookimpl(trylast=True)\n"
        "def pytest_runtest_teardown(item):\n"
        "    from PySide6.QtWidgets import QPushButton, QWidget\n"
        "    parent = QWidget()\n"
        "    child = QPushButton('Session teardown probe', parent)\n"
        "    orphan = QPushButton('Parentless teardown probe')\n"
        "    child.clicked.connect(lambda: parent.hide())\n"
        "    retained.extend([parent, child, orphan])\n"
        "@pytest.hookimpl(hookwrapper=True)\n"
        "def pytest_sessionfinish(session):\n"
        "    yield\n"
        "    import shiboken6\n"
        "    valid = [type(w).__name__ for w in retained if shiboken6.isValid(w)]\n"
        "    print('QT_SESSION_SURVIVORS:', valid)\n"
        "    if valid:\n"
        "        session.exitstatus = 1\n",
        encoding="utf-8",
    )
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join(
        filter(None, [str(tmp_path), env.get("PYTHONPATH", "")])
    )
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-o", "addopts=", "-n", "0",
         "-p", "no:cacheprovider", "-p", "qt_session_cleanup_probe", "-q",
         "tests/test_volume_image_export.py::test_button_recovers_after_failed_first_capture"],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "QT_SESSION_SURVIVORS: []" in result.stdout
