"""Save the current 3D volume render as a PNG or JPG file.

Pure filename/format helpers live at the top so they can be unit-tested
without a display.  The dialog helper at the bottom is the only Qt UI code.

Privacy: the default filename uses the preset name only, never patient or
study fields.  Failures are logged through the redacting helpers and the
message box never shows the destination path.
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QColor, QFont, QImage, QPainter
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from gui.volume.dicom_sc_save import save_dicom_sc
from utils.log_sanitizer import sanitized_format_exc

_log = logging.getLogger(__name__)

PNG_FILTER = "PNG image (*.png)"
JPG_FILTER = "JPEG image (*.jpg *.jpeg)"
FORMAT_PNG = "PNG"
FORMAT_JPG = "JPG"
FORMAT_DICOM = "DICOM"
DICOM_FILTER = "DICOM Secondary Capture (*.dcm)"
FORMAT_FILTERS = {
    FORMAT_PNG: PNG_FILTER,
    FORMAT_JPG: JPG_FILTER,
    FORMAT_DICOM: DICOM_FILTER,
}
JPG_QUALITY = 95
OPTIONS_CONFIG_KEY = "volume_3d_save_image_options"

# Capture is 1x only (the cached frame).  A high-resolution re-render at 2x/4x
# is a deliberate follow-up, see the derived-image export plan (A2).

LEGACY_TOOLTIP = (
    "Save Image is unavailable on the legacy 3D interactor, which has no "
    "cached frame to save."
)
READY_TOOLTIP = "Save the current 3D view as PNG, JPG, or DICOM (Ctrl+S)."
WAITING_TOOLTIP = "Available once the first 3D frame has been drawn."

# User-saved preset names are free text and may carry identifying words, so
# only built-in preset names are ever used outside the app.
CUSTOM_PRESET_LABEL = "Custom preset"
_CUSTOM_FILENAME_TOKEN = "Custom"

_UNSAFE_CHARS = re.compile(r"[^A-Za-z0-9._-]+")


def sanitize_preset_for_filename(preset_name: str) -> str:
    """Return a path-safe token from a preset name (never empty)."""
    token = _UNSAFE_CHARS.sub("_", preset_name or "").strip("._")
    token = re.sub(r"_+", "_", token)
    return token[:60] or "render"


def default_image_filename(preset_name: str, now: datetime | None = None) -> str:
    """Return ``3D_<preset>_<YYYYMMDD-HHMMSS>.png``."""
    stamp = (now or datetime.now()).strftime("%Y%m%d-%H%M%S")
    token = (
        _CUSTOM_FILENAME_TOKEN
        if preset_name == CUSTOM_PRESET_LABEL
        else sanitize_preset_for_filename(preset_name)
    )
    return f"3D_{token}_{stamp}.png"


def public_preset_name(widget: Any) -> str:
    """Return the preset name that may leave the app (built-ins only)."""
    logical_of = getattr(widget, "_current_logical_index", None)
    is_user = getattr(widget, "_is_user_preset_logical", None)
    if callable(logical_of) and callable(is_user):
        logical = logical_of()
        if isinstance(logical, int) and logical >= 0 and is_user(logical):
            return CUSTOM_PRESET_LABEL
    namer = getattr(widget, "_current_base_preset_name", None)
    return str(namer()) if callable(namer) else ""


def redact_custom_preset_line(widget: Any, text: str) -> str:
    """Replace a user preset's name in the overlay's first line."""
    if public_preset_name(widget) != CUSTOM_PRESET_LABEL:
        return text
    names = {
        str(p.get("name", ""))
        for p in getattr(widget, "_user_presets", [])
        if isinstance(p, dict)
    }
    lines = text.split("\n")
    if lines and lines[0] in names:
        lines[0] = CUSTOM_PRESET_LABEL
    return "\n".join(lines)


def resolve_output_path(path: str, fmt: str) -> str:
    """Return *path* with an extension matching the chosen format.

    The chosen format always wins: a typed extension that disagrees with it is
    replaced.  ``.jpeg`` is kept when the format is JPG.
    """
    root, ext = os.path.splitext(path)
    ext = ext.lower()
    if fmt == FORMAT_DICOM:
        return path if ext == ".dcm" else _swap_ext(path, root, ext, ".dcm")
    if fmt == FORMAT_JPG:
        return path if ext in (".jpg", ".jpeg") else _swap_ext(path, root, ext, ".jpg")
    return path if ext == ".png" else _swap_ext(path, root, ext, ".png")


def _swap_ext(path: str, root: str, ext: str, new_ext: str) -> str:
    """Replace a known image extension, otherwise append *new_ext*."""
    if ext in (".png", ".jpg", ".jpeg", ".dcm"):
        return root + new_ext
    return path + new_ext


def write_image(image: QImage, path: str, fmt: str) -> bool:
    """Write *image*; the extension picks the codec, JPG at quality 95.

    Returns ``True`` on success.
    """
    if image is None or image.isNull():
        return False
    if fmt == "JPG":
        return bool(image.save(path, None, JPG_QUALITY))
    return bool(image.save(path))


def save_enabled_state(surface: Any, *, first_paint_complete: bool) -> tuple[bool, str]:
    """Return ``(enabled, tooltip)`` for the Save Image button."""
    if surface is None:
        return False, WAITING_TOOLTIP
    if not getattr(surface, "supports_image_capture", True):
        return False, LEGACY_TOOLTIP
    has_image = getattr(surface, "has_image", None)
    if not first_paint_complete or not callable(has_image) or not has_image():
        return False, WAITING_TOOLTIP
    return True, READY_TOOLTIP


def _config_get_path(config: Any) -> str:
    getter = getattr(config, "get_last_export_path", None)
    if not callable(getter):
        return ""
    try:
        return str(getter() or "")
    except Exception:
        return ""


def _config_set_path(config: Any, folder: str) -> None:
    setter = getattr(config, "set_last_export_path", None)
    if callable(setter):
        try:
            setter(folder)
        except Exception:
            _log.debug("%s", sanitized_format_exc())


@dataclass(frozen=True)
class SaveOptions:
    """User choices from the Save 3D Image options dialog."""

    fmt: str = FORMAT_PNG
    burn_in: bool = False
    deidentify: bool = True


def load_save_options(config: Any) -> SaveOptions:
    """Read the remembered options; missing or malformed values use defaults."""
    getter = getattr(config, "get", None)
    stored = getter(OPTIONS_CONFIG_KEY) if callable(getter) else None
    if not isinstance(stored, dict):
        return SaveOptions()
    fmt = stored.get("format")
    return SaveOptions(
        fmt=fmt if fmt in FORMAT_FILTERS else FORMAT_PNG,
        burn_in=stored.get("burn_in") is True,
        deidentify=stored.get("deidentify") is not False,
    )


def store_save_options(config: Any, options: SaveOptions) -> None:
    """Persist the options through the config manager when it is available."""
    setter = getattr(config, "set", None)
    if not callable(setter):
        return
    setter(
        OPTIONS_CONFIG_KEY,
        {
            "format": options.fmt,
            "burn_in": options.burn_in,
            "deidentify": options.deidentify,
        },
    )
    saver = getattr(config, "save_config", None)
    if callable(saver):
        saver()


class SaveImageOptionsDialog(QDialog):
    """Small modal dialog shown before the file dialog."""

    def __init__(self, initial: SaveOptions, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Save 3D Image")
        self._format_combo = QComboBox(self)
        self._format_combo.addItem("PNG", FORMAT_PNG)
        self._format_combo.addItem("JPG", FORMAT_JPG)
        self._format_combo.addItem("DICOM (Secondary Capture)", FORMAT_DICOM)
        self._format_combo.setCurrentIndex(
            max(0, self._format_combo.findData(initial.fmt))
        )
        self._burn_in_check = QCheckBox("Burn in overlay text", self)
        self._burn_in_check.setToolTip(
            "Draw the viewport overlay text (preset, opacity, detail, blend "
            "mode) onto the saved image.  No patient or study text is added."
        )
        self._burn_in_check.setChecked(initial.burn_in)
        self._deid_check = QCheckBox("De-identify", self)
        self._deid_check.setToolTip(
            "Remove patient identity and re-mint UIDs in the saved DICOM file."
        )
        self._deid_check.setChecked(initial.deidentify)
        self._format_combo.currentIndexChanged.connect(self._sync_enabled)
        self._sync_enabled()
        form = QFormLayout()
        form.addRow("Format:", self._format_combo)
        form.addRow("", self._burn_in_check)
        form.addRow("", self._deid_check)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

    def _sync_enabled(self, _index: int = 0) -> None:
        """Burn-in is raster-only; de-identify applies to DICOM only."""
        is_dicom = self._format_combo.currentData() == FORMAT_DICOM
        self._burn_in_check.setEnabled(not is_dicom)
        self._deid_check.setEnabled(is_dicom)

    def options(self) -> SaveOptions:
        """Return the choices currently shown (burn-in is never set for DICOM)."""
        is_dicom = self._format_combo.currentData() == FORMAT_DICOM
        return SaveOptions(
            fmt=str(self._format_combo.currentData()),
            burn_in=self._burn_in_check.isChecked() and not is_dicom,
            deidentify=self._deid_check.isChecked(),
        )


def ask_save_options(parent: QWidget | None, config: Any) -> SaveOptions | None:
    """Show the options dialog; persist and return the choices, or ``None``."""
    dialog = SaveImageOptionsDialog(load_save_options(config), parent)
    if dialog.exec() != QDialog.DialogCode.Accepted:
        return None
    options = dialog.options()
    try:
        store_save_options(config, options)
    except Exception:
        _log.debug("%s", sanitized_format_exc())
    return options


def burn_in_overlay(image: QImage, text: str) -> QImage:
    """Return a copy of *image* with *text* drawn top-left; no-op if empty.

    The caller passes the exact string the viewer already shows, so nothing
    but preset/render settings can appear.  Style follows the on-screen
    overlay: light text on a translucent dark backing, monospace.
    """
    out = image.copy()
    if not text.strip() or out.isNull():
        return out
    ratio = out.devicePixelRatio() or 1.0
    out.setDevicePixelRatio(1.0)  # draw in raw pixels
    px = max(11.0 * ratio, min(out.width(), out.height()) * 0.025)
    margin = max(6, round(px * 0.6))
    pad = max(4, round(px * 0.4))
    font = QFont("Courier New")
    font.setStyleHint(QFont.StyleHint.Monospace)
    font.setPixelSize(max(1, round(px)))
    painter = QPainter(out)
    try:
        painter.setFont(font)
        bounds = painter.boundingRect(
            QRect(0, 0, out.width(), out.height()), Qt.AlignmentFlag.AlignLeft, text
        )
        backing = QRect(
            margin, margin, bounds.width() + 2 * pad, bounds.height() + 2 * pad
        )
        painter.fillRect(backing, QColor(0, 0, 0, 180))
        painter.setPen(QColor(220, 220, 220))
        painter.drawText(
            backing.adjusted(pad, pad, -pad, -pad),
            int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop),
            text,
        )
    finally:
        painter.end()
    out.setDevicePixelRatio(ratio)
    return out


def _confirm_overwrite(parent: QWidget | None) -> bool:
    """Ask before overwriting a file the dialog did not already confirm."""
    answer = QMessageBox.question(
        parent,
        "Save Image",
        "A file with that name already exists once the extension is applied. "
        "Replace it?",
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        QMessageBox.StandardButton.No,
    )
    return answer == QMessageBox.StandardButton.Yes


def prompt_and_save_image(
    parent: QWidget | None,
    surface: Any,
    preset_name: str,
    config_manager: Any = None,
    overlay_text: str = "",
    *,
    dicom_template: Any = None,
    blend_mode: str = "",
    source_refs: list[tuple[str, str]] | None = None,
) -> bool:
    """Ask for a destination and save the surface's current frame.

    Returns ``True`` only when a file was written.
    """
    image = surface.current_image() if surface is not None else None
    if image is None or image.isNull():
        return False
    options = ask_save_options(parent, config_manager)
    if options is None:
        return False
    start_dir = _config_get_path(config_manager)
    suggested = os.path.join(start_dir, default_image_filename(preset_name))
    if options.fmt != FORMAT_PNG:
        ext = ".dcm" if options.fmt == FORMAT_DICOM else ".jpg"
        suggested = os.path.splitext(suggested)[0] + ext
    path, _selected = QFileDialog.getSaveFileName(
        parent, "Save 3D Image", suggested, FORMAT_FILTERS[options.fmt]
    )
    if not path:
        return False
    fmt = options.fmt
    chosen = path
    path = resolve_output_path(chosen, fmt)
    if path != chosen and os.path.exists(path) and not _confirm_overwrite(parent):
        return False
    if options.burn_in:
        image = burn_in_overlay(image, overlay_text)
    try:
        if fmt == FORMAT_DICOM:
            ok = save_dicom_sc(
                image,
                path,
                dicom_template,
                preset_name=preset_name,
                blend_mode=blend_mode,
                deidentify=options.deidentify,
                source_refs=source_refs,
            )
        else:
            ok = write_image(image, path, fmt)
    except Exception:
        _log.error("3D image save failed; details withheld")
        _log.debug("%s", sanitized_format_exc())
        ok = False
    if not ok:
        _log.error("3D image save failed; details withheld")
        QMessageBox.warning(
            parent,
            "Save Image",
            "The image could not be saved. Check that the folder is writable "
            "and try again.",
        )
        return False
    _config_set_path(config_manager, os.path.dirname(path))
    return True


def refresh_save_button(widget: Any) -> None:
    """Sync the viewer's Save Image button with the current frame state."""
    button = getattr(widget, "_save_image_btn", None)
    if button is None:
        return
    enabled, tip = save_enabled_state(
        getattr(widget, "_surface", None),
        first_paint_complete=bool(getattr(widget, "_first_paint_complete", False))
        and not getattr(widget, "_cleaned_up", False),
    )
    button.setEnabled(enabled)
    button.setToolTip(tip)


def add_save_button(widget: Any, panel: QWidget, row: Any) -> QPushButton:
    """Create the **Save Image…** button on *row* and wire it to *widget*."""
    button = QPushButton("Save Image…", panel)
    button.clicked.connect(lambda _checked=False: save_from_viewer(widget))
    row.addWidget(button)
    widget._save_image_btn = button
    refresh_save_button(widget)
    return button


def _current_blend_mode(widget: Any) -> str:
    """Return the viewer's blend mode name (empty when unavailable)."""
    combo = getattr(widget, "_blend_mode_combo", None)
    return str(combo.currentText()) if combo is not None else ""


def save_from_viewer(widget: Any, preset_name: str | None = None) -> bool:
    """Save the viewer's current frame if the action is currently allowed."""
    if preset_name is None:
        preset_name = public_preset_name(widget)
    button = getattr(widget, "_save_image_btn", None)
    if button is None or not button.isEnabled():
        return False
    return prompt_and_save_image(
        widget,
        getattr(widget, "_surface", None),
        preset_name,
        getattr(widget, "_config_manager", None),
        redact_custom_preset_line(
            widget, str(getattr(widget, "_overlay_text_prev", "") or "")
        ),
        dicom_template=getattr(widget, "_source_template", None),
        blend_mode=_current_blend_mode(widget),
        source_refs=getattr(widget, "_source_refs", None),
    )
