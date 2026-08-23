"""
Characterization tests for MainWindow._show_about and disclaimer link handling.

Pins About dialog title, visibility, version/disclaimer content, and the
disclaimer:// callback path before _show_about is extracted.
"""

from __future__ import annotations

import os
import sys

import pytest

_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_src = os.path.join(_project_root, "src")
if _src not in sys.path:
    sys.path.insert(0, _src)

pytest.importorskip("PySide6")

from PySide6.QtCore import QTimer, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QApplication, QDialog, QTextBrowser
from qt_widget_scope import widget_scope

from gui.main_window import MainWindow
from utils.config_manager import ConfigManager
from version import __version__ as APP_VERSION


def _find_about_dialog() -> QDialog | None:
    for widget in QApplication.topLevelWidgets():
        if isinstance(widget, QDialog) and widget.windowTitle() == "About DICOM Viewer V3":
            return widget
    return None



@pytest.fixture(autouse=True)
def _destroy_leaked_windows():
    """Destroy windows this module's tests create (see ``qt_widget_scope``)."""
    with widget_scope():
        yield

@pytest.mark.qt
def test_show_about_dialog_title_visibility_and_body(qapp, tmp_path):
    """_show_about opens a modal About dialog with version and disclaimer link."""
    w = MainWindow(ConfigManager(config_dir=tmp_path / "config"))
    captured: dict[str, QDialog] = {}

    def inspect_and_accept() -> None:
        dialog = _find_about_dialog()
        assert dialog is not None, "About dialog not found among top-level widgets"
        captured["dialog"] = dialog
        assert dialog.isVisible()
        browser = dialog.findChild(QTextBrowser)
        assert browser is not None
        html = browser.toHtml()
        assert APP_VERSION in html
        assert "disclaimer://" in html
        dialog.accept()

    QTimer.singleShot(0, inspect_and_accept)
    w._show_about()

    assert "dialog" in captured
    w.close()


@pytest.mark.qt
def test_about_disclaimer_link_calls_show_disclaimer_with_force_show(qapp, tmp_path, monkeypatch):
    """Disclaimer anchor in About dialog routes through force_show=True."""
    w = MainWindow(ConfigManager(config_dir=tmp_path / "config"))
    calls: list[dict[str, object]] = []

    def spy_show_disclaimer(config_manager, parent=None, force_show: bool = False) -> bool:
        calls.append(
            {
                "config_manager": config_manager,
                "parent": parent,
                "force_show": force_show,
            }
        )
        return True

    monkeypatch.setattr(
        "gui.dialogs.disclaimer_dialog.DisclaimerDialog.show_disclaimer",
        spy_show_disclaimer,
    )

    def click_disclaimer_and_accept() -> None:
        dialog = _find_about_dialog()
        assert dialog is not None, "About dialog not found among top-level widgets"
        browser = dialog.findChild(QTextBrowser)
        assert browser is not None
        browser.anchorClicked.emit(QUrl("disclaimer://show"))
        dialog.accept()

    QTimer.singleShot(0, click_disclaimer_and_accept)
    w._show_about()

    assert len(calls) == 1
    assert calls[0]["force_show"] is True
    assert calls[0]["config_manager"] is w.config_manager
    assert calls[0]["parent"] is w
    w.close()


@pytest.mark.qt
def test_about_https_link_opens_external_url(qapp, tmp_path, monkeypatch):
    """GitHub repo anchor in About dialog opens via QDesktopServices."""
    w = MainWindow(ConfigManager(config_dir=tmp_path / "config"))
    opened: list[QUrl] = []

    def spy_open_url(url: QUrl) -> bool:
        opened.append(url)
        return True

    monkeypatch.setattr(QDesktopServices, "openUrl", staticmethod(spy_open_url))

    def click_github_and_accept() -> None:
        dialog = _find_about_dialog()
        assert dialog is not None, "About dialog not found among top-level widgets"
        browser = dialog.findChild(QTextBrowser)
        assert browser is not None
        browser.anchorClicked.emit(
            QUrl("https://github.com/kgrizz-git/DICOMViewerV3")
        )
        dialog.accept()

    QTimer.singleShot(0, click_github_and_accept)
    w._show_about()

    assert len(opened) == 1
    assert opened[0].toString() == "https://github.com/kgrizz-git/DICOMViewerV3"
    w.close()
