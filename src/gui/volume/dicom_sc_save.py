"""GUI-side glue for saving the 3D render as a Secondary Capture DICOM file."""

from __future__ import annotations

from typing import Any

from pydicom.dataset import Dataset
from PySide6.QtGui import QImage

from core.volume_sc_dicom_export import qimage_rgb_array, write_volume_sc


def qimage_to_rgb_array(image: QImage) -> Any:
    """Convert any ``QImage`` to an (H, W, 3) uint8 array, honouring row padding."""
    rgb = image.convertToFormat(QImage.Format.Format_RGB888)
    rgb.setDevicePixelRatio(1.0)  # width()/height() are physical pixels
    width, height = rgb.width(), rgb.height()
    return qimage_rgb_array(
        width, height, bytes(rgb.constBits()), rgb.bytesPerLine()
    )


def save_dicom_sc(
    image: QImage,
    path: str,
    template: Dataset | None,
    *,
    preset_name: str,
    blend_mode: str,
    deidentify: bool,
    source_refs: list[tuple[str, str]] | None = None,
) -> bool:
    """Write *image* as a single-frame RGB SC instance; return ``True`` on success."""
    if image is None or image.isNull():
        return False
    write_volume_sc(
        qimage_to_rgb_array(image),
        template if template is not None else Dataset(),
        path,
        preset_name=preset_name,
        blend_mode=blend_mode,
        deidentify=deidentify,
        source_refs=source_refs,
    )
    return True
