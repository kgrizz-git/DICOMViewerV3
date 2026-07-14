"""
Main-window status bar — construction and updates (refactor Stream C).

Extracted from ``gui/main_window.py`` so the window stays a layout + signal
surface, mirroring the existing ``main_window_menu_builder`` /
``main_window_toolbar_builder`` pattern.

The controller owns the three permanent status-bar labels (file/study, centered
zoom + W/L, right-aligned pixel info) and exposes small update methods. The
window keeps references to these labels for backward compatibility (e.g. the
external pixel-info update in ``core/view_state_handlers.py``).

:func:`format_zoom_preset_status` is the **Qt-free** text builder (unit-tested
without a Qt application).
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QStatusBar

from core.wl_preset_catalog import format_status_bar_wl


def format_zoom_preset_status(
    zoom: float,
    window_center: float | None = None,
    window_width: float | None = None,
    *,
    unit: str | None = None,
) -> str:
    """Build the centered status text: zoom plus optional numeric W/L.

    Qt-free; mirrors the prior ``main_window`` logic — numeric center/width only
    (never preset names). W/L is appended only when both center and width are given.
    """
    if window_center is not None and window_width is not None:
        wl_text = format_status_bar_wl(window_center, window_width, unit=unit)
        return f"Zoom = {zoom:.1f}, W/L {wl_text}"
    return f"Zoom = {zoom:.1f}"


class MainWindowStatusController:
    """Owns the three permanent status-bar labels and their updates."""

    def __init__(self, status_bar: QStatusBar) -> None:
        # Three permanent widgets with equal stretch (1:1:1) for fixed 1/3 widths.
        # Left: file/study information.
        self.file_study_label = QLabel("Open a DICOM file or folder to begin")
        self.file_study_label.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        status_bar.addPermanentWidget(self.file_study_label, stretch=1)

        # Center: zoom and window/level info.
        self.zoom_preset_label = QLabel("")
        self.zoom_preset_label.setAlignment(
            Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter
        )
        status_bar.addPermanentWidget(self.zoom_preset_label, stretch=1)

        # Right: pixel values and coordinates.
        self.pixel_info_label = QLabel("")
        self.pixel_info_label.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        status_bar.addPermanentWidget(self.pixel_info_label, stretch=1)

    def set_file_study(self, message: str) -> None:
        """Set the left file/study segment."""
        self.file_study_label.setText(message)

    def set_zoom_preset(
        self,
        zoom: float,
        window_center: float | None = None,
        window_width: float | None = None,
        *,
        unit: str | None = None,
    ) -> None:
        """Set the centered zoom + numeric W/L segment."""
        self.zoom_preset_label.setText(
            format_zoom_preset_status(zoom, window_center, window_width, unit=unit)
        )

    def set_pixel_info(self, text: str) -> None:
        """Set the right pixel-info segment."""
        self.pixel_info_label.setText(text)
