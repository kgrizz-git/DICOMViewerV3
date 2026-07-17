"""Regression coverage for the executable privacy-boundary lifecycle."""

from __future__ import annotations

import importlib
import io
import logging
import os
import subprocess
import sys
from pathlib import Path
from types import ModuleType

from utils.privacy.logging_filter import PrivacyLogFilter
from utils.privacy.streams import PrivacyTextStream


def test_import_main_does_not_mutate_logging_or_process_streams() -> None:
    root_logger = logging.getLogger()
    handlers_before = tuple(root_logger.handlers)
    root_filters_before = tuple(root_logger.filters)
    handler_filters_before = {
        id(handler): tuple(handler.filters) for handler in handlers_before
    }
    stdout_before = sys.stdout
    stderr_before = sys.stderr
    excepthook_before = sys.excepthook
    sys_path_before = tuple(sys.path)
    previous_main = sys.modules.pop("main", None)
    previous_main_window = sys.modules.pop("gui.main_window", None)

    try:
        imported = importlib.import_module("main")

        assert isinstance(imported, ModuleType)
        assert tuple(root_logger.handlers) == handlers_before
        assert tuple(root_logger.filters) == root_filters_before
        assert {
            id(handler): tuple(handler.filters) for handler in root_logger.handlers
        } == handler_filters_before
        assert sys.stdout is stdout_before
        assert sys.stderr is stderr_before
        assert sys.excepthook is excepthook_before
        assert tuple(sys.path) == sys_path_before
    finally:
        sys.modules.pop("main", None)
        sys.modules.pop("gui.main_window", None)
        if previous_main is not None:
            sys.modules["main"] = previous_main
        if previous_main_window is not None:
            sys.modules["gui.main_window"] = previous_main_window


def test_fresh_process_import_main_preserves_sys_path() -> None:
    root = Path(__file__).resolve().parents[1]
    code = """
import sys
before = tuple(sys.path)
import main
raise SystemExit(0 if tuple(sys.path) == before else 7)
"""
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(root / "src")
    environment.setdefault("QT_QPA_PLATFORM", "offscreen")

    completed = subprocess.run(
        [sys.executable, "-c", code],
        cwd=root,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )

    assert completed.returncode == 0, "fresh main import mutated sys.path"


def test_explicit_startup_installs_once_and_protects_logs_and_streams(
    monkeypatch,
) -> None:
    main_module = importlib.import_module("main")
    root_logger = logging.getLogger()
    original_handlers = list(root_logger.handlers)
    original_filters = list(root_logger.filters)
    original_level = root_logger.level
    log_output = io.StringIO()
    stdout_output = io.StringIO()
    stderr_output = io.StringIO()
    handler = logging.StreamHandler(log_output)
    marker = "PatientID=LIFECYCLE-991 /Users/private/patient-file.dcm"

    root_logger.handlers = [handler]
    root_logger.filters = []
    root_logger.setLevel(logging.INFO)
    monkeypatch.setattr(sys, "stdout", stdout_output)
    monkeypatch.setattr(sys, "stderr", stderr_output)

    try:
        main_module.install_application_privacy_boundaries()
        first_stdout = sys.stdout
        first_stderr = sys.stderr
        first_root_filters = tuple(root_logger.filters)
        first_handler_filters = tuple(handler.filters)

        main_module.install_application_privacy_boundaries()

        assert sys.stdout is first_stdout
        assert sys.stderr is first_stderr
        assert isinstance(sys.stdout, PrivacyTextStream)
        assert isinstance(sys.stderr, PrivacyTextStream)
        assert tuple(root_logger.filters) == first_root_filters
        assert tuple(handler.filters) == first_handler_filters
        assert sum(isinstance(item, PrivacyLogFilter) for item in root_logger.filters) == 1
        assert sum(isinstance(item, PrivacyLogFilter) for item in handler.filters) == 1

        logging.getLogger("privacy.lifecycle").error(marker)
        sys.stdout.write(marker)
        sys.stderr.write(marker)
        sys.stdout.flush()
        sys.stderr.flush()

        assert marker not in log_output.getvalue()
        assert marker not in stdout_output.getvalue()
        assert marker not in stderr_output.getvalue()
    finally:
        root_logger.handlers = original_handlers
        root_logger.filters = original_filters
        root_logger.setLevel(original_level)


def test_main_installs_privacy_boundary_before_application_construction(monkeypatch) -> None:
    main_module = importlib.import_module("main")
    events: list[str] = []

    class _Application:
        def __init__(self) -> None:
            events.append("construct")

        def run(self) -> int:
            events.append("run")
            return 0

    monkeypatch.setattr(
        main_module,
        "install_application_privacy_boundaries",
        lambda: events.append("privacy"),
    )
    monkeypatch.setattr(main_module, "DICOMViewerApp", _Application)

    assert main_module.main() == 0
    assert events == ["privacy", "construct", "run"]
