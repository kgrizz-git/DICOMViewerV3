"""Tests for saving the 3D render as PNG/JPG (surface accessor + helpers)."""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from typing import Any

import pytest
from PySide6.QtGui import QColor, QImage
from PySide6.QtWidgets import QFileDialog, QMessageBox, QPushButton

from gui.volume import image_export as ie
from gui.volume import render_surface as rs


class _FakeRenderWindow:
    def SetOffScreenRendering(self, _v: int) -> None: ...
    def SetSize(self, _w: int, _h: int) -> None: ...
    def AddObserver(self, *_a: Any) -> None: ...
    def RemoveAllObservers(self) -> None: ...


def _image(w: int = 12, h: int = 7) -> QImage:
    img = QImage(w, h, QImage.Format.Format_RGB888)
    img.fill(QColor(10, 200, 30))
    return img


@pytest.fixture
def surface(qapp: Any, monkeypatch: pytest.MonkeyPatch) -> Any:
    fake_vtk = SimpleNamespace(vtkRenderWindow=_FakeRenderWindow)
    monkeypatch.setattr(rs, "_vtk", lambda: fake_vtk)
    monkeypatch.setattr(rs, "create_interactor", lambda _rw: object())
    surf = rs.VolumeRenderSurface()
    yield surf
    surf.cleanup()


def test_current_image_none_before_grab(surface: Any) -> None:
    assert surface.current_image() is None


def test_current_image_is_detached_copy(surface: Any) -> None:
    surface._image = _image()
    copy = surface.current_image()
    assert copy is not None
    assert copy.size() == surface._image.size()
    copy.fill(QColor(0, 0, 0))
    assert surface._image.pixelColor(0, 0) == QColor(10, 200, 30)


def test_current_image_none_after_cleanup(surface: Any) -> None:
    surface._image = _image()
    surface.cleanup()
    assert surface.current_image() is None


def test_filename_sanitizes_preset() -> None:
    name = ie.default_image_filename(
        'CT: Bone/Soft "x"?*<>|\\', datetime(2026, 1, 2, 3, 4, 5)
    )
    assert name == "3D_CT_Bone_Soft_x_20260102-030405.png"
    assert ie.sanitize_preset_for_filename("../..") == "render"
    assert ie.sanitize_preset_for_filename("") == "render"


def test_resolve_output_path() -> None:
    assert ie.resolve_output_path("a.JPG", ie.PNG_FILTER) == ("a.JPG", "JPG")
    assert ie.resolve_output_path("a", ie.JPG_FILTER) == ("a.jpg", "JPG")
    assert ie.resolve_output_path("a", ie.PNG_FILTER) == ("a.png", "PNG")


def test_save_enabled_state() -> None:
    ready = SimpleNamespace(supports_image_capture=True)
    assert ie.save_enabled_state(ready, first_paint_complete=False)[0] is False
    assert ie.save_enabled_state(ready, first_paint_complete=True)[0] is True
    assert ie.save_enabled_state(None, first_paint_complete=True)[0] is False
    legacy = SimpleNamespace(supports_image_capture=False)
    enabled, tip = ie.save_enabled_state(legacy, first_paint_complete=True)
    assert enabled is False
    assert tip == ie.LEGACY_TOOLTIP


def _viewer(qapp: Any, surface: Any, config: Any = None) -> Any:
    return SimpleNamespace(
        _surface=surface,
        _first_paint_complete=False,
        _save_image_btn=QPushButton("Save Image…"),
        _config_manager=config,
    )


def test_button_disabled_until_frame_then_enabled(qapp: Any) -> None:
    surf = SimpleNamespace(supports_image_capture=True, current_image=_image)
    widget = _viewer(qapp, surf)
    ie.refresh_save_button(widget)
    assert not widget._save_image_btn.isEnabled()
    widget._first_paint_complete = True
    ie.refresh_save_button(widget)
    assert widget._save_image_btn.isEnabled()


def test_legacy_surface_disables_button(qapp: Any) -> None:
    from gui.volume.legacy_surface import LegacyInteractorSurface

    assert LegacyInteractorSurface.supports_image_capture is False
    assert LegacyInteractorSurface.current_image(None) is None  # type: ignore[arg-type]
    widget = _viewer(qapp, SimpleNamespace(supports_image_capture=False))
    widget._first_paint_complete = True
    ie.refresh_save_button(widget)
    assert not widget._save_image_btn.isEnabled()
    assert widget._save_image_btn.toolTip() == ie.LEGACY_TOOLTIP


def test_save_writes_png_and_remembers_folder(
    qapp: Any, tmp_path: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    saved: dict[str, str] = {}
    config = SimpleNamespace(
        get_last_export_path=lambda: str(tmp_path),
        set_last_export_path=lambda p: saved.setdefault("folder", p),
    )
    target = tmp_path / "out"
    monkeypatch.setattr(
        QFileDialog,
        "getSaveFileName",
        lambda *_a, **_k: (str(target), ie.PNG_FILTER),
    )
    surf = SimpleNamespace(supports_image_capture=True, current_image=_image)
    widget = _viewer(qapp, surf, config)
    widget._first_paint_complete = True
    ie.refresh_save_button(widget)
    assert ie.save_from_viewer(widget, "CT Bone") is True
    written = QImage(str(tmp_path / "out.png"))
    assert (written.width(), written.height()) == (12, 7)
    assert saved["folder"] == str(tmp_path)


def test_save_failure_shows_message_without_path(
    qapp: Any, tmp_path: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    bad = tmp_path / "missing_dir" / "x.png"
    monkeypatch.setattr(
        QFileDialog, "getSaveFileName", lambda *_a, **_k: (str(bad), ie.PNG_FILTER)
    )
    shown: list[str] = []
    monkeypatch.setattr(
        QMessageBox, "warning", lambda _p, _t, text: shown.append(text)
    )
    surf = SimpleNamespace(supports_image_capture=True, current_image=_image)
    assert ie.prompt_and_save_image(None, surf, "CT Bone") is False
    assert len(shown) == 1
    assert "missing_dir" not in shown[0]


def test_save_blocked_when_button_disabled(qapp: Any) -> None:
    surf = SimpleNamespace(supports_image_capture=True, current_image=_image)
    widget = _viewer(qapp, surf)
    ie.refresh_save_button(widget)
    assert ie.save_from_viewer(widget, "CT Bone") is False
