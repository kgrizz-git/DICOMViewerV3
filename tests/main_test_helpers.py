"""
Shared helpers for DICOMViewerApp regression tests (main.py refactor Phase 0).

Provides a temp ConfigManager path so tests do not mutate the user's real config.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from qt_widget_scope import widget_scope

import main as main_module
import main_app_initialization
from utils.config_manager import ConfigManager as RealConfigManager


def make_test_config_manager(tmp_path: Path) -> RealConfigManager:
    """ConfigManager that writes under ``tmp_path`` instead of the user config dir."""
    return RealConfigManager(
        config_dir=tmp_path,
        config_filename="dicom_viewer_config_test_main.json",
    )


def with_test_config_manager(tmp_path: Path) -> tuple[Callable[[], RealConfigManager], Any]:
    """
    Patch ``main_app_initialization.ConfigManager`` to use a temp config file for the duration of a test.

    Returns:
        (restore_callback, original_ConfigManager) — call restore in ``finally``.
    """
    original_cm = main_app_initialization.ConfigManager
    main_app_initialization.ConfigManager = lambda: make_test_config_manager(tmp_path)
    return (
        lambda: setattr(main_app_initialization, "ConfigManager", original_cm),
        original_cm,
    )


def instantiate_app(tmp_path: Path) -> main_module.DICOMViewerApp:
    """Build ``DICOMViewerApp`` with an isolated config path."""
    restore, _ = with_test_config_manager(tmp_path)
    try:
        return main_module.DICOMViewerApp()
    finally:
        restore()


@contextmanager
def viewer_app(tmp_path: Path) -> Iterator[main_module.DICOMViewerApp]:
    """
    Build ``DICOMViewerApp`` with an isolated config and destroy it on exit.

    Each construction creates ~30 top-level widgets; see
    ``qt_widget_scope`` for why leaving them alive matters.
    """
    with widget_scope():
        restore, _ = with_test_config_manager(tmp_path)
        try:
            yield main_module.DICOMViewerApp()
        finally:
            restore()
