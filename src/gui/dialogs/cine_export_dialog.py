"""
Cine export options dialog — format, FPS, loop range, overlays.

Used before **File → Export cine as…** chooses an output path. Window uses
``WindowStaysOnTopHint`` only while opening so the dialog is visible; it does
not stay on top after defocus (same pattern as other export dialogs).

Inputs:
    - Default FPS, total frame count, optional cine loop bounds.

Outputs:
    - :class:`CineExportOptions` when the user accepts.

Requirements:
    - PySide6.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QSpinBox,
    QVBoxLayout,
)


@dataclass
class CineExportOptions:
    """User-selected options for cine video export."""

    video_format: str  # "GIF", "AVI", or "MPG"
    fps: float
    use_cine_loop_bounds: bool
    loop_start_frame: int
    loop_end_frame: int
    include_overlays: bool


class CineExportDialog(QDialog):
    """Modal dialog for cine export settings."""

    def __init__(
        self,
        parent,
        *,
        default_fps: float,
        total_frames: int,
        loop_start: Optional[int],
        loop_end: Optional[int],
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Export cine as…")
        self.setModal(True)
        self.setWindowFlags(
            self.windowFlags() | Qt.WindowType.WindowStaysOnTopHint
        )

        self._total = max(0, int(total_frames))
        last = max(0, self._total - 1)

        self._format_combo = QComboBox()
        self._format_combo.addItems(["GIF", "AVI", "MPG"])
        self._format_combo.setCurrentIndex(0)
        self._format_combo.setToolTip(
            "MPG uses MPEG-2 in an MPEG program stream (FFmpeg). "
            "Playback depends on installed codecs and players."
        )

        self._fps_spin = QDoubleSpinBox()
        self._fps_spin.setRange(0.1, 120.0)
        self._fps_spin.setDecimals(2)
        self._fps_spin.setSingleStep(0.5)
        self._fps_spin.setValue(float(max(0.1, default_fps)))

        self._use_loop_check = QCheckBox("Use cine loop range (A–B markers)")
        has_bounds = (
            loop_start is not None
            and loop_end is not None
            and self._total > 0
        )
        self._use_loop_check.setChecked(bool(has_bounds))
        self._use_loop_check.setEnabled(self._total > 1)

        self._loop_start = QSpinBox()
        self._loop_start.setRange(0, max(0, last))
        self._loop_end = QSpinBox()
        self._loop_end.setRange(0, max(0, last))
        if has_bounds:
            ls = int(max(0, min(loop_start or 0, last)))
            le = int(max(0, min(loop_end or last, last)))
            if le < ls:
                ls, le = le, ls
            self._loop_start.setValue(ls)
            self._loop_end.setValue(le)
        else:
            self._loop_start.setValue(0)
            self._loop_end.setValue(last)

        loop_row = QFormLayout()
        loop_row.addRow("Loop start frame:", self._loop_start)
        loop_row.addRow("Loop end frame:", self._loop_end)

        loop_group = QGroupBox("Frame range")
        lg = QVBoxLayout()
        lg.addWidget(self._use_loop_check)
        lg.addLayout(loop_row)
        loop_group.setLayout(lg)

        self._overlay_check = QCheckBox("Include overlays, ROIs, and measurements")
        self._overlay_check.setChecked(False)
        self._overlay_check.setToolTip(
            "When enabled, export runs on the UI thread so annotation managers "
            "stay thread-safe. Large series may take longer."
        )

        help_lbl = QLabel(
            "Frames are rendered with the same LUT and rescale settings as "
            "PNG export (not a viewport grab). Cancel removes a partial output file.\n"
            "Video encoding uses FFmpeg via the imageio-ffmpeg package (LGPL/GPL components)."
        )
        help_lbl.setWordWrap(True)

        form = QFormLayout()
        form.addRow("Format:", self._format_combo)
        form.addRow("Frames per second:", self._fps_spin)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        root = QVBoxLayout()
        root.addLayout(form)
        root.addWidget(loop_group)
        root.addWidget(self._overlay_check)
        root.addWidget(help_lbl)
        root.addWidget(buttons)
        self.setLayout(root)

    def build_options(self) -> CineExportOptions:
        return CineExportOptions(
            video_format=str(self._format_combo.currentText()).upper(),
            fps=float(self._fps_spin.value()),
            use_cine_loop_bounds=bool(self._use_loop_check.isChecked()),
            loop_start_frame=int(self._loop_start.value()),
            loop_end_frame=int(self._loop_end.value()),
            include_overlays=bool(self._overlay_check.isChecked()),
        )
