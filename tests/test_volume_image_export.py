"""Tests for saving the 3D render as PNG/JPG (surface accessor + helpers)."""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from typing import Any

import pytest
from PySide6.QtGui import QColor, QImage
from PySide6.QtWidgets import QFileDialog, QMessageBox, QPushButton

from gui.dialogs.volume_render_dialog import VolumeRenderDialog
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


def test_resolve_output_path_chosen_format_wins() -> None:
    assert ie.resolve_output_path("a.png", "PNG") == "a.png"
    assert ie.resolve_output_path("a.JPG", "JPG") == "a.JPG"
    assert ie.resolve_output_path("a.jpeg", "JPG") == "a.jpeg"
    assert ie.resolve_output_path("a", "JPG") == "a.jpg"
    assert ie.resolve_output_path("a", "PNG") == "a.png"
    assert ie.resolve_output_path("a.jpg", "PNG") == "a.png"
    assert ie.resolve_output_path("a.jpeg", "PNG") == "a.png"
    assert ie.resolve_output_path("a.png", "JPG") == "a.jpg"
    assert ie.resolve_output_path("a.v2", "PNG") == "a.v2.png"


def test_save_enabled_state() -> None:
    ready = SimpleNamespace(supports_image_capture=True, has_image=lambda: True)
    assert ie.save_enabled_state(ready, first_paint_complete=False)[0] is False
    assert ie.save_enabled_state(ready, first_paint_complete=True)[0] is True
    assert ie.save_enabled_state(None, first_paint_complete=True)[0] is False
    legacy = SimpleNamespace(supports_image_capture=False)
    enabled, tip = ie.save_enabled_state(legacy, first_paint_complete=True)
    assert enabled is False
    assert tip == ie.LEGACY_TOOLTIP


def _choose(monkeypatch: pytest.MonkeyPatch, options: Any) -> None:
    monkeypatch.setattr(ie, "ask_save_options", lambda _p, _c: options)


def _viewer(qapp: Any, surface: Any, config: Any = None) -> Any:
    return SimpleNamespace(
        _surface=surface,
        _first_paint_complete=False,
        _save_image_btn=QPushButton("Save Image…"),
        _config_manager=config,
    )


def test_button_disabled_until_frame_then_enabled(qapp: Any) -> None:
    surf = SimpleNamespace(supports_image_capture=True, has_image=lambda: True, current_image=_image)
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
    _choose(monkeypatch, ie.SaveOptions())
    surf = SimpleNamespace(supports_image_capture=True, has_image=lambda: True, current_image=_image)
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
    _choose(monkeypatch, ie.SaveOptions())
    shown: list[str] = []
    monkeypatch.setattr(
        QMessageBox, "warning", lambda _p, _t, text: shown.append(text)
    )
    surf = SimpleNamespace(supports_image_capture=True, has_image=lambda: True, current_image=_image)
    assert ie.prompt_and_save_image(None, surf, "CT Bone") is False
    assert len(shown) == 1
    assert "missing_dir" not in shown[0]


def test_save_blocked_when_button_disabled(qapp: Any) -> None:
    surf = SimpleNamespace(supports_image_capture=True, has_image=lambda: True, current_image=_image)
    widget = _viewer(qapp, surf)
    ie.refresh_save_button(widget)
    assert ie.save_from_viewer(widget, "CT Bone") is False


class _Config:
    def __init__(self, stored: Any = None) -> None:
        self.data: dict[str, Any] = {} if stored is None else {ie.OPTIONS_CONFIG_KEY: stored}
        self.saves = 0

    def get(self, key: str) -> Any:
        return self.data.get(key)

    def set(self, key: str, value: Any) -> None:
        self.data[key] = value

    def save_config(self) -> None:
        self.saves += 1


def test_options_defaults(qapp: Any) -> None:
    assert ie.load_save_options(None) == ie.SaveOptions("PNG", False)
    assert ie.load_save_options(_Config("junk")) == ie.SaveOptions("PNG", False)
    assert ie.load_save_options(_Config({"format": "BMP", "burn_in": "yes"})) == (
        ie.SaveOptions("PNG", False)
    )
    dialog = ie.SaveImageOptionsDialog(ie.load_save_options(None))
    assert dialog.options() == ie.SaveOptions("PNG", False)


def test_options_persist_and_preselect(
    qapp: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = _Config()
    monkeypatch.setattr(ie.SaveImageOptionsDialog, "exec", lambda self: self._burn_in_check.setChecked(True) or self._format_combo.setCurrentIndex(1) or 1)
    chosen = ie.ask_save_options(None, config)
    assert chosen == ie.SaveOptions("JPG", True)
    assert config.saves == 1
    assert ie.load_save_options(config) == chosen
    assert ie.SaveImageOptionsDialog(chosen).options() == chosen


def test_options_cancel_returns_none(
    qapp: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = _Config()
    monkeypatch.setattr(ie.SaveImageOptionsDialog, "exec", lambda _self: 0)
    assert ie.ask_save_options(None, config) is None
    assert config.data == {}


def test_burn_in_changes_top_left_only(qapp: Any) -> None:
    base = _image(400, 300)
    out = ie.burn_in_overlay(base, "CT Bone\nOpacity 50.0%")
    assert out.size() == base.size()
    assert base.pixelColor(5, 5) == QColor(10, 200, 30)  # source untouched
    assert out.pixelColor(10, 10) != QColor(10, 200, 30)
    assert out.pixelColor(390, 290) == QColor(10, 200, 30)


def test_burn_in_empty_text_is_unchanged(qapp: Any) -> None:
    base = _image(200, 100)
    assert ie.burn_in_overlay(base, "") == base
    out = ie.burn_in_overlay(base, "  \n")
    assert out == base


def test_burn_in_only_draws_given_text(
    qapp: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    drawn: list[str] = []
    real = ie.QPainter.drawText

    def spy(self: Any, *args: Any) -> Any:
        drawn.extend(a for a in args if isinstance(a, str))
        return real(self, *args)

    monkeypatch.setattr(ie.QPainter, "drawText", spy)
    ie.burn_in_overlay(_image(300, 200), "CT Bone")
    assert drawn == ["CT Bone"]


def test_save_burn_in_ignores_patient_fields(
    qapp: Any, tmp_path: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: list[str] = []
    monkeypatch.setattr(
        ie,
        "burn_in_overlay",
        lambda img, text: seen.append(text) or img,
    )
    _choose(monkeypatch, ie.SaveOptions("PNG", True))
    monkeypatch.setattr(
        QFileDialog,
        "getSaveFileName",
        lambda *_a, **_k: (str(tmp_path / "o"), ie.PNG_FILTER),
    )
    widget = _viewer(qapp, SimpleNamespace(supports_image_capture=True, has_image=lambda: True, current_image=_image))
    widget._datasets = [SimpleNamespace(PatientName="Doe^Jane", PatientID="123")]
    widget._overlay_text_prev = "CT Bone"
    widget._first_paint_complete = True
    ie.refresh_save_button(widget)
    assert ie.save_from_viewer(widget, "CT Bone") is True
    assert seen == ["CT Bone"]
    assert "Doe" not in "".join(seen)


def test_burn_in_off_does_not_call_overlay(
    qapp: Any, tmp_path: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        ie, "burn_in_overlay", lambda *_a: pytest.fail("burn-in must be off")
    )
    _choose(monkeypatch, ie.SaveOptions("PNG", False))
    monkeypatch.setattr(
        QFileDialog,
        "getSaveFileName",
        lambda *_a, **_k: (str(tmp_path / "o"), ie.PNG_FILTER),
    )
    surf = SimpleNamespace(supports_image_capture=True, has_image=lambda: True, current_image=_image)
    assert ie.prompt_and_save_image(None, surf, "CT", None, "CT Bone") is True


def test_jpg_save_is_readable_and_extension_replaced(
    qapp: Any, tmp_path: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    _choose(monkeypatch, ie.SaveOptions("JPG", False))
    seen_filters: list[str] = []

    def fake_dialog(_p: Any, _t: str, suggested: str, filters: str) -> tuple[str, str]:
        seen_filters.append(filters)
        assert suggested.endswith(".jpg")
        return str(tmp_path / "shot.png"), filters

    monkeypatch.setattr(QFileDialog, "getSaveFileName", fake_dialog)
    surf = SimpleNamespace(supports_image_capture=True, has_image=lambda: True, current_image=_image)
    assert ie.prompt_and_save_image(None, surf, "CT") is True
    assert seen_filters == [ie.JPG_FILTER]
    out = tmp_path / "shot.jpg"
    assert out.read_bytes()[:2] == b"\xff\xd8"
    loaded = QImage(str(out))
    assert (loaded.width(), loaded.height()) == (12, 7)
    assert not (tmp_path / "shot.png").exists()


def test_jpeg_extension_kept_for_jpg(
    qapp: Any, tmp_path: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    _choose(monkeypatch, ie.SaveOptions("JPG", False))
    monkeypatch.setattr(
        QFileDialog,
        "getSaveFileName",
        lambda *_a, **_k: (str(tmp_path / "x.jpeg"), ie.JPG_FILTER),
    )
    surf = SimpleNamespace(supports_image_capture=True, has_image=lambda: True, current_image=_image)
    assert ie.prompt_and_save_image(None, surf, "CT") is True
    assert (tmp_path / "x.jpeg").exists()


def test_ctrl_s_inert_without_viewer(
    qapp: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "gui.dialogs.volume_render_dialog.save_from_viewer",
        lambda *_a: pytest.fail("must not save while building"),
    )
    VolumeRenderDialog._on_save_image_shortcut(SimpleNamespace(_viewer_widget=None))  # type: ignore[arg-type]


def test_cancelled_options_dialog_skips_file_dialog(monkeypatch) -> None:
    monkeypatch.setattr(ie, "ask_save_options", lambda *_a, **_k: None)
    opened: list[bool] = []
    monkeypatch.setattr(
        QFileDialog, "getSaveFileName", lambda *_a, **_k: opened.append(True) or ("", "")
    )
    surf = SimpleNamespace(supports_image_capture=True, has_image=lambda: True, current_image=_image)
    assert ie.prompt_and_save_image(None, surf, "CT Bone") is False
    assert opened == []


def test_burn_in_on_null_image_returns_null_image(qapp) -> None:
    assert ie.burn_in_overlay(QImage(), "CT Bone").isNull()


def test_qimage_with_row_padding_converts_exactly(qapp: Any) -> None:
    from gui.volume.dicom_sc_save import qimage_to_rgb_array

    img = QImage(5, 3, QImage.Format.Format_RGB888)
    assert img.bytesPerLine() % 4 == 0 and img.bytesPerLine() > 15  # padded rows
    for y in range(3):
        for x in range(5):
            img.setPixelColor(x, y, QColor(x * 40, y * 80, 7))
    arr = qimage_to_rgb_array(img)
    assert arr.shape == (3, 5, 3)
    assert tuple(arr[2, 4]) == (160, 160, 7)
    assert tuple(arr[0, 1]) == (40, 0, 7)


def test_dialog_enables_options_per_format(qapp: Any) -> None:
    dialog = ie.SaveImageOptionsDialog(ie.SaveOptions())
    assert dialog._burn_in_check.isEnabled()
    assert not dialog._deid_check.isEnabled()
    assert dialog._deid_check.isChecked()  # default ON
    dialog._burn_in_check.setChecked(True)
    dialog._format_combo.setCurrentIndex(dialog._format_combo.findData("DICOM"))
    assert not dialog._burn_in_check.isEnabled()
    assert dialog._deid_check.isEnabled()
    assert dialog.options() == ie.SaveOptions("DICOM", False, True)
    dialog._deid_check.setChecked(False)
    assert dialog.options().deidentify is False


def test_dicom_options_persist(qapp: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    config = _Config()
    monkeypatch.setattr(
        ie.SaveImageOptionsDialog,
        "exec",
        lambda self: (
            self._format_combo.setCurrentIndex(self._format_combo.findData("DICOM")),
            self._deid_check.setChecked(False),
            1,
        )[-1],
    )
    chosen = ie.ask_save_options(None, config)
    assert chosen == ie.SaveOptions("DICOM", False, False)
    assert ie.load_save_options(config) == chosen
    assert ie.SaveImageOptionsDialog(chosen).options() == chosen


def test_resolve_output_path_dicom() -> None:
    assert ie.resolve_output_path("a", "DICOM") == "a.dcm"
    assert ie.resolve_output_path("a.png", "DICOM") == "a.dcm"
    assert ie.resolve_output_path("a.dcm", "PNG") == "a.png"


def test_save_dicom_end_to_end_deidentified(
    qapp: Any, tmp_path: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    import pydicom
    from pydicom.dataset import Dataset

    template = Dataset()
    template.PatientName = "Doe^Jane"
    template.PatientID = "PID-1"
    template.StudyInstanceUID = "1.2.9.1"
    template.SeriesInstanceUID = "1.2.9.2"
    template.Modality = "CT"
    _choose(monkeypatch, ie.SaveOptions("DICOM", False, True))
    seen: list[str] = []

    def fake_dialog(_p: Any, _t: str, suggested: str, filters: str) -> tuple[str, str]:
        seen.append(suggested)
        assert filters == ie.DICOM_FILTER
        return str(tmp_path / "shot"), filters

    monkeypatch.setattr(QFileDialog, "getSaveFileName", fake_dialog)
    surf = SimpleNamespace(supports_image_capture=True, has_image=lambda: True, current_image=_image)
    assert ie.prompt_and_save_image(
        None, surf, "CT Bone", None, "", dicom_template=template, blend_mode="Composite"
    ) is True
    assert seen[0].endswith(".dcm") and "Doe" not in seen[0]
    ds = pydicom.dcmread(str(tmp_path / "shot.dcm"))
    assert ds.pixel_array.shape == (7, 12, 3)
    assert "Doe" not in str(ds.PatientName)
    assert "CT Bone" in ds.DerivationDescription


def _custom_widget(qapp: Any, user_name: str = "Doe^Jane") -> Any:
    surf = SimpleNamespace(
        supports_image_capture=True, has_image=lambda: True, current_image=_image
    )
    widget = _viewer(qapp, surf)
    widget._first_paint_complete = True
    widget._current_logical_index = lambda: 99
    widget._is_user_preset_logical = lambda logical: logical >= 50
    widget._current_base_preset_name = lambda: "CT Bone"
    widget._user_presets = [{"name": user_name, "base_preset": "CT Bone"}]
    widget._overlay_text_prev = f"{user_name}\nOpacity 50.0%"
    widget._blend_mode_combo = SimpleNamespace(currentText=lambda: "Composite")
    ie.refresh_save_button(widget)
    return widget


def test_custom_preset_never_leaks(
    qapp: Any, tmp_path: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    import pydicom

    widget = _custom_widget(qapp)
    assert ie.public_preset_name(widget) == "Custom preset"
    assert "Doe" not in ie.redact_custom_preset_line(widget, widget._overlay_text_prev)
    assert ie.redact_custom_preset_line(widget, "Doe^Jane\nOpacity 50.0%") == (
        "Custom preset\nOpacity 50.0%"
    )
    assert ie.default_image_filename("Custom preset", datetime(2026, 1, 1)).startswith(
        "3D_Custom_2026"
    )
    suggested: list[str] = []
    drawn: list[str] = []
    real = ie.QPainter.drawText

    def spy(self: Any, *args: Any) -> Any:
        drawn.extend(a for a in args if isinstance(a, str))
        return real(self, *args)

    monkeypatch.setattr(ie.QPainter, "drawText", spy)
    for fmt, burn in (("PNG", True), ("DICOM", False)):
        _choose(monkeypatch, ie.SaveOptions(fmt, burn, False))

        def fake(_p: Any, _t: str, sug: str, filters: str, _f: str = fmt) -> tuple[str, str]:
            suggested.append(sug)
            return str(tmp_path / f"o_{_f}"), filters

        monkeypatch.setattr(QFileDialog, "getSaveFileName", fake)
        assert ie.save_from_viewer(widget) is True
    assert all("Doe" not in name for name in suggested)
    assert "Custom_" in suggested[0]
    assert drawn and all("Doe" not in text for text in drawn)
    assert "Custom preset" in "".join(drawn)
    ds = pydicom.dcmread(str(tmp_path / "o_DICOM.dcm"))
    assert "Doe" not in ds.DerivationDescription
    assert "Custom preset" in ds.DerivationDescription


def test_builtin_preset_name_is_kept(qapp: Any) -> None:
    widget = _custom_widget(qapp)
    widget._is_user_preset_logical = lambda _l: False
    assert ie.public_preset_name(widget) == "CT Bone"
    assert ie.redact_custom_preset_line(widget, "CT Bone\nX") == "CT Bone\nX"


def test_overwrite_confirmation_after_extension_change(
    qapp: Any, tmp_path: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "x.png").write_bytes(b"old")
    _choose(monkeypatch, ie.SaveOptions("PNG", False))
    monkeypatch.setattr(
        QFileDialog, "getSaveFileName", lambda *_a, **_k: (str(tmp_path / "x"), ie.PNG_FILTER)
    )
    surf = SimpleNamespace(supports_image_capture=True, has_image=lambda: True, current_image=_image)
    asked: list[bool] = []
    monkeypatch.setattr(
        QMessageBox,
        "question",
        lambda *_a, **_k: asked.append(True) or QMessageBox.StandardButton.No,
    )
    assert ie.prompt_and_save_image(None, surf, "CT") is False
    assert asked == [True]
    assert (tmp_path / "x.png").read_bytes() == b"old"
    monkeypatch.setattr(
        QMessageBox, "question", lambda *_a, **_k: QMessageBox.StandardButton.Yes
    )
    assert ie.prompt_and_save_image(None, surf, "CT") is True
    assert (tmp_path / "x.png").read_bytes() != b"old"


def test_no_confirmation_when_path_unchanged(
    qapp: Any, tmp_path: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "x.png").write_bytes(b"old")
    _choose(monkeypatch, ie.SaveOptions("PNG", False))
    monkeypatch.setattr(
        QFileDialog, "getSaveFileName", lambda *_a, **_k: (str(tmp_path / "x.png"), ie.PNG_FILTER)
    )
    monkeypatch.setattr(
        QMessageBox, "question", lambda *_a, **_k: pytest.fail("dialog already confirmed")
    )
    surf = SimpleNamespace(supports_image_capture=True, has_image=lambda: True, current_image=_image)
    assert ie.prompt_and_save_image(None, surf, "CT") is True


def test_painted_but_no_image_stays_disabled(qapp: Any) -> None:
    surf = SimpleNamespace(supports_image_capture=True, has_image=lambda: False)
    widget = _viewer(qapp, surf)
    widget._first_paint_complete = True
    ie.refresh_save_button(widget)
    assert not widget._save_image_btn.isEnabled()


def test_cleanup_disables_button(qapp: Any) -> None:
    surf = SimpleNamespace(supports_image_capture=True, has_image=lambda: True)
    widget = _viewer(qapp, surf)
    widget._first_paint_complete = True
    ie.refresh_save_button(widget)
    assert widget._save_image_btn.isEnabled()
    widget._cleaned_up = True
    ie.refresh_save_button(widget)
    assert not widget._save_image_btn.isEnabled()


def test_surface_has_image(surface: Any) -> None:
    assert surface.has_image() is False
    surface._image = _image()
    assert surface.has_image() is True
    surface.cleanup()
    assert surface.has_image() is False


def test_legacy_has_image_false() -> None:
    from gui.volume.legacy_surface import LegacyInteractorSurface

    assert LegacyInteractorSurface.has_image(None) is False  # type: ignore[arg-type]


def test_hidpi_odd_width_dimensions(qapp: Any) -> None:
    from gui.volume.dicom_sc_save import qimage_to_rgb_array

    img = QImage(7, 5, QImage.Format.Format_RGB888)
    img.fill(QColor(1, 2, 3))
    img.setDevicePixelRatio(2.0)
    arr = qimage_to_rgb_array(img)
    assert arr.shape == (5, 7, 3)
    out = ie.burn_in_overlay(
        _hidpi(120, 61), "CT Bone"
    )
    assert (out.width(), out.height()) == (120, 61)
    assert out.devicePixelRatio() == 2.0


def _hidpi(w: int, h: int) -> QImage:
    img = _image(w, h)
    img.setDevicePixelRatio(2.0)
    return img


def test_resolve_output_path_case_and_missing_extension() -> None:
    assert ie.resolve_output_path("a.PNG", "PNG") == "a.PNG"
    assert ie.resolve_output_path("a.DCM", "DICOM") == "a.DCM"
    assert ie.resolve_output_path("a.JPEG", "JPG") == "a.JPEG"
    assert ie.resolve_output_path("a.PNG", "JPG") == "a.jpg"
    assert ie.resolve_output_path("noext", "DICOM") == "noext.dcm"


def test_ctrl_s_inert_when_button_disabled(
    qapp: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        ie, "ask_save_options", lambda *_a: pytest.fail("must not prompt")
    )
    widget = _viewer(qapp, SimpleNamespace(supports_image_capture=True, has_image=lambda: True, current_image=_image))
    ie.refresh_save_button(widget)  # first paint not complete: disabled
    assert not widget._save_image_btn.isEnabled()
    dialog = SimpleNamespace(_viewer_widget=widget)
    VolumeRenderDialog._on_save_image_shortcut(dialog)  # type: ignore[arg-type]
