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
from datetime import datetime
from typing import Any

from PySide6.QtGui import QImage
from PySide6.QtWidgets import QFileDialog, QMessageBox, QPushButton, QWidget

from utils.log_sanitizer import sanitized_format_exc

_log = logging.getLogger(__name__)

PNG_FILTER = "PNG image (*.png)"
JPG_FILTER = "JPEG image (*.jpg *.jpeg)"
SAVE_FILTERS = f"{PNG_FILTER};;{JPG_FILTER}"
JPG_QUALITY = 95

LEGACY_TOOLTIP = (
    "Save Image is unavailable on the legacy 3D interactor, which has no "
    "cached frame to save."
)
READY_TOOLTIP = "Save the current 3D view as a PNG or JPG image (Ctrl+S)."
WAITING_TOOLTIP = "Available once the first 3D frame has been drawn."

_UNSAFE_CHARS = re.compile(r"[^A-Za-z0-9._-]+")


def sanitize_preset_for_filename(preset_name: str) -> str:
    """Return a path-safe token from a preset name (never empty)."""
    token = _UNSAFE_CHARS.sub("_", preset_name or "").strip("._")
    token = re.sub(r"_+", "_", token)
    return token[:60] or "render"


def default_image_filename(preset_name: str, now: datetime | None = None) -> str:
    """Return ``3D_<preset>_<YYYYMMDD-HHMMSS>.png``."""
    stamp = (now or datetime.now()).strftime("%Y%m%d-%H%M%S")
    return f"3D_{sanitize_preset_for_filename(preset_name)}_{stamp}.png"


def resolve_output_path(path: str, selected_filter: str) -> tuple[str, str]:
    """Return ``(path, format)`` with an extension matching the choice.

    A recognised typed extension wins over the filter.  Otherwise the filter
    decides and its extension is appended.
    """
    ext = os.path.splitext(path)[1].lower()
    if ext == ".png":
        return path, "PNG"
    if ext in (".jpg", ".jpeg"):
        return path, "JPG"
    if selected_filter == JPG_FILTER:
        return path + ".jpg", "JPG"
    return path + ".png", "PNG"


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
    if not first_paint_complete:
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


def prompt_and_save_image(
    parent: QWidget | None,
    surface: Any,
    preset_name: str,
    config_manager: Any = None,
) -> bool:
    """Ask for a destination and save the surface's current frame.

    Returns ``True`` only when a file was written.
    """
    image = surface.current_image() if surface is not None else None
    if image is None or image.isNull():
        return False
    start_dir = _config_get_path(config_manager)
    suggested = os.path.join(start_dir, default_image_filename(preset_name))
    path, selected = QFileDialog.getSaveFileName(
        parent, "Save 3D Image", suggested, SAVE_FILTERS
    )
    if not path:
        return False
    path, fmt = resolve_output_path(path, selected)
    try:
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
        first_paint_complete=bool(getattr(widget, "_first_paint_complete", False)),
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


def save_from_viewer(widget: Any, preset_name: str | None = None) -> bool:
    """Save the viewer's current frame if the action is currently allowed."""
    if preset_name is None:
        namer = getattr(widget, "_current_base_preset_name", None)
        preset_name = str(namer()) if callable(namer) else ""
    button = getattr(widget, "_save_image_btn", None)
    if button is None or not button.isEnabled():
        return False
    return prompt_and_save_image(
        widget,
        getattr(widget, "_surface", None),
        preset_name,
        getattr(widget, "_config_manager", None),
    )
