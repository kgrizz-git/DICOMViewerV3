"""
Screenshot Export Dialog

Saves the currently displayed image(s) from one or more subwindows exactly as shown.
Supports: one file per selected subwindow, a single composite image matching the
on-screen multi-pane grid, or a grab of the entire main window (toolbars and panes).

Inputs:
    - List of subwindow containers (with image_viewer)
    - Optional MultiWindowLayout for composite grid geometry
    - Output directory, filename prefix, format (PNG/JPG)
    - Which subwindows to include (checkboxes) for per-view and composite modes

Outputs:
    - PNG/JPG file(s) per chosen export mode

Requirements:
    - PySide6 for dialogs and widget grab
"""

from __future__ import annotations

import os
from typing import Any, List, Optional, Tuple

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPalette, QPixmap

from core.export_rendering import effective_scale_for_image
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
)


class ScreenshotExportDialog(QDialog):
    """
    Dialog to export screenshots from selected subwindows or the full main window.

    Export modes:
        - Separate file per selected view (viewport grab, WYSIWYG).
        - Single composite image laid out like the current 1x1 / 1x2 / 2x1 / 2x2 grid.
        - Entire main window (parent QMainWindow grab; export dialog is hidden first).
    """

    MODE_SEPARATE = "separate"
    MODE_COMPOSITE = "composite"
    MODE_FULL_WINDOW = "full_window"

    def __init__(
        self,
        subwindows: List[Any],  # SubWindowContainer-like objects with .image_viewer
        config_manager=None,
        multi_window_layout: Optional[Any] = None,
        parent=None,
    ):
        super().__init__(parent)
        self.setWindowTitle("Export Screenshots")
        self.setModal(True)
        self.resize(520, 460)
        self.subwindows = subwindows
        self.config_manager = config_manager
        self.multi_window_layout = multi_window_layout
        self.output_path = config_manager.get_last_export_path() if config_manager else ""
        self.prefix = "screenshot"
        self.format = "PNG"
        self.include_annotations = True
        self.export_mode = self.MODE_SEPARATE
        # Same magnification semantics as Export Images / Export Cine (8192 px cap).
        self.export_scale: float = 1.0
        self._checkboxes: List[QCheckBox] = []
        self._mode_button_group: Optional[QButtonGroup] = None
        self._create_ui()

    def showEvent(self, event) -> None:
        """Bring dialog to front when shown (user preference for dialogs)."""
        super().showEvent(event)
        self.activateWindow()
        self.raise_()

    def _create_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)

        # Export scope
        mode_group = QGroupBox("Export as")
        mode_layout = QVBoxLayout()
        self._mode_button_group = QButtonGroup(self)
        self._radio_separate = QRadioButton("Separate file per selected view")
        self._radio_composite = QRadioButton("Single composite image (grid as on screen)")
        self._radio_full = QRadioButton("Entire main window (toolbar, panes, and image area)")
        self._radio_separate.setChecked(True)
        for rb in (self._radio_separate, self._radio_composite, self._radio_full):
            self._mode_button_group.addButton(rb)
            mode_layout.addWidget(rb)
        self._radio_separate.toggled.connect(self._on_mode_changed)
        self._radio_composite.toggled.connect(self._on_mode_changed)
        self._radio_full.toggled.connect(self._on_mode_changed)
        mode_group.setLayout(mode_layout)
        layout.addWidget(mode_group)

        hint = QLabel(
            "Composite is a single grab of the image grid (same layout as on screen, no extra gutters). "
            "Separate files use each pane’s viewport. View checkboxes apply only to separate-file export. "
            "Full-window capture ignores view checkboxes."
        )
        hint.setWordWrap(True)
        layout.addWidget(hint)

        # Subwindow selection
        self._subwindow_group = QGroupBox("Subwindows to export (separate files only)")
        group_layout = QVBoxLayout()
        for i, subwindow in enumerate(self.subwindows):
            has_image = bool(
                getattr(subwindow, "image_viewer", None)
                and getattr(subwindow.image_viewer, "image_item", None) is not None
            )
            cb = QCheckBox(f"View {i + 1}")
            cb.setChecked(has_image)
            cb.setEnabled(has_image)
            if not has_image:
                cb.setToolTip("No image loaded in this view")
            self._checkboxes.append(cb)
            group_layout.addWidget(cb)
        self._subwindow_group.setLayout(group_layout)
        layout.addWidget(self._subwindow_group)

        self.include_annotations_cb = QCheckBox("Include overlays and annotations (capture shows current display)")
        self.include_annotations_cb.setChecked(True)
        self.include_annotations_cb.toggled.connect(lambda v: setattr(self, "include_annotations", v))
        layout.addWidget(self.include_annotations_cb)

        path_layout = QHBoxLayout()
        path_layout.addWidget(QLabel("Output directory:"))
        self.path_label = QLabel(self.output_path or "(Not selected)")
        self.path_label.setWordWrap(True)
        path_layout.addWidget(self.path_label, 1)
        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self._browse)
        path_layout.addWidget(browse_btn)
        layout.addLayout(path_layout)

        prefix_layout = QHBoxLayout()
        prefix_layout.addWidget(QLabel("Filename prefix:"))
        self.prefix_edit = QLineEdit()
        self.prefix_edit.setPlaceholderText("screenshot")
        self.prefix_edit.setText(self.prefix)
        self.prefix_edit.textChanged.connect(lambda t: setattr(self, "prefix", t or "screenshot"))
        prefix_layout.addWidget(self.prefix_edit)
        layout.addLayout(prefix_layout)

        format_layout = QHBoxLayout()
        format_layout.addWidget(QLabel("Format:"))
        self.format_combo = QComboBox()
        self.format_combo.addItem("PNG", "PNG")
        self.format_combo.addItem("JPG", "JPG")
        self.format_combo.currentIndexChanged.connect(
            lambda: setattr(self, "format", self.format_combo.currentData())
        )
        format_layout.addWidget(self.format_combo)
        format_layout.addStretch()
        layout.addLayout(format_layout)

        resolution_group = QGroupBox("Resolution (PNG / JPG)")
        resolution_layout = QVBoxLayout()
        self.resolution_combo = QComboBox()
        for label, scale in [("Native resolution", 1.0), ("1.5×", 1.5), ("2×", 2.0), ("4×", 4.0)]:
            self.resolution_combo.addItem(label, scale)
        self.resolution_combo.setCurrentIndex(0)
        self.resolution_combo.currentIndexChanged.connect(self._on_resolution_changed)
        resolution_layout.addWidget(self.resolution_combo)
        res_tip = QLabel(
            "Same rules as Export Images: if the scaled width or height would exceed 8192 px, "
            "a lower magnification is used automatically."
        )
        res_tip.setWordWrap(True)
        resolution_layout.addWidget(res_tip)
        resolution_group.setLayout(resolution_layout)
        layout.addWidget(resolution_group)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        export_btn = QPushButton("Export")
        export_btn.clicked.connect(self._on_export)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(export_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

        self._on_mode_changed()

    def _on_resolution_changed(self, _index: int) -> None:
        data = self.resolution_combo.currentData()
        self.export_scale = float(data) if data is not None else 1.0

    def _set_subwindow_focus_borders_suppressed(self, suppress: bool) -> None:
        """Use normal (gray) pane borders on all subwindows while True — no blue focus ring in grabs."""
        for sw in self.subwindows:
            fn = getattr(sw, "set_suppress_focus_border_for_export", None)
            if callable(fn):
                fn(suppress)

    def _on_mode_changed(self) -> None:
        """Enable subwindow checkboxes only for separate-file export."""
        full = self._radio_full.isChecked()
        composite = self._radio_composite.isChecked()
        self._subwindow_group.setEnabled(not full and not composite)
        if full:
            self._subwindow_group.setToolTip(
                "Full-window capture exports the entire application window."
            )
        elif composite:
            self._subwindow_group.setToolTip(
                "Composite always includes every cell in the current layout; use the checkboxes "
                "when exporting separate files per view."
            )
        else:
            self._subwindow_group.setToolTip("")

    def _current_export_mode(self) -> str:
        if self._radio_full.isChecked():
            return self.MODE_FULL_WINDOW
        if self._radio_composite.isChecked():
            return self.MODE_COMPOSITE
        return self.MODE_SEPARATE

    def _browse(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Select output directory", self.output_path or "")
        if path:
            self.output_path = path
            self.path_label.setText(path)

    def _selected_indices(self) -> List[int]:
        return [i for i, cb in enumerate(self._checkboxes) if cb.isChecked()]

    def _paths_for_overwrite_prompt(self, prefix: str, ext: str, mode: str) -> List[str]:
        paths: List[str] = []
        if mode == self.MODE_FULL_WINDOW:
            paths.append(os.path.join(self.output_path, f"{prefix}_fullwindow{ext}"))
            return paths
        selected = self._selected_indices()
        if mode == self.MODE_SEPARATE:
            for i in selected:
                paths.append(os.path.join(self.output_path, f"{prefix}_view{i + 1}{ext}"))
            return paths
        # composite
        paths.append(os.path.join(self.output_path, f"{prefix}_grid{ext}"))
        return paths

    def _grab_viewport(self, view_idx: int) -> Optional[QPixmap]:
        if view_idx < 0 or view_idx >= len(self.subwindows):
            return None
        subwindow = self.subwindows[view_idx]
        viewer = getattr(subwindow, "image_viewer", None)
        if not viewer or getattr(viewer, "image_item", None) is None:
            return None
        viewport = viewer.viewport()
        if not viewport:
            return None
        pm = viewport.grab()
        return None if pm.isNull() else pm

    def _viewport_for_view(self, view_idx: int) -> Optional[Any]:
        """Return the image viewer's viewport widget for *view_idx*, if any."""
        if view_idx < 0 or view_idx >= len(self.subwindows):
            return None
        viewer = getattr(self.subwindows[view_idx], "image_viewer", None)
        if not viewer:
            return None
        return viewer.viewport()

    def _scale_pixmap_for_export(self, pm: QPixmap) -> Tuple[QPixmap, Optional[str]]:
        """
        Apply the selected export magnification (1.5× / 2× / 4×) with the same 8192 px cap
        as slice export. Returns the (possibly unchanged) pixmap and an optional user note.
        """
        if pm.isNull():
            return pm, None
        w, h = pm.width(), pm.height()
        if w < 1 or h < 1:
            return pm, None
        req = float(self.export_scale)
        eff = effective_scale_for_image(w, h, req)
        warn: Optional[str] = None
        if req > 1.0 and eff < req:
            warn = (
                f"Requested {req}× magnification; largest side would exceed 8192 px at that size, "
                f"so this capture was exported at {eff}×."
            )
        if eff <= 1.0:
            return pm, warn
        nw = max(1, int(round(w * eff)))
        nh = max(1, int(round(h * eff)))
        scaled = pm.scaled(
            nw,
            nh,
            Qt.AspectRatioMode.IgnoreAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        return scaled, warn

    def _composite_canvas_color(self) -> QColor:
        """Theme-derived background for composite canvas and fallbacks."""
        parent = self.parent()
        if parent is not None:
            return parent.palette().color(QPalette.ColorRole.Window)
        return self.palette().color(QPalette.ColorRole.Window)

    def _grab_viewport_for_composite_cell(self, view_idx: int) -> Tuple[Optional[QPixmap], QColor]:
        """
        WYSIWYG grab for one grid cell: always use the viewport (even with no image).

        Returns:
            (pixmap or None if grab failed, per-cell fallback fill color from palette).
        """
        vp = self._viewport_for_view(view_idx)
        canvas = self._composite_canvas_color()
        if vp is None:
            return None, canvas
        fallback = vp.palette().color(QPalette.ColorRole.Window)
        pm = vp.grab()
        if pm.isNull():
            return None, fallback
        return pm, fallback

    def _export_separate(self, prefix: str, ext: str, selected: List[int]) -> Tuple[int, Optional[str], List[str]]:
        saved = 0
        notes: List[str] = []
        for i in selected:
            pm = self._grab_viewport(i)
            if pm is None:
                continue
            pm2, note = self._scale_pixmap_for_export(pm)
            if note:
                notes.append(note)
            img = pm2.toImage()
            path = os.path.join(self.output_path, f"{prefix}_view{i + 1}{ext}")
            if not img.save(path):
                return saved, f"Failed to save View {i + 1}", notes
            saved += 1
        return saved, None, notes

    def _export_composite_tiled_fallback(self, prefix: str, ext: str) -> Tuple[int, Optional[str], List[str]]:
        """
        Build composite from per-viewport grabs when a single layout grab is unavailable.

        Cell sizes use each grab's pixel size (not QWidget logical size) to avoid gutters
        from device-pixel-ratio mismatch.
        """
        mwl = self.multi_window_layout
        if mwl is None:
            return 0, "Composite export requires layout information (internal error).", []
        cells = mwl.get_screenshot_grid_cells()
        if not cells:
            return 0, "No grid cells for composite export.", []

        gap = 0
        rows = max(r for r, _, _ in cells) + 1
        cols = max(c for _, c, _ in cells) + 1

        col_w = [0] * cols
        row_h = [0] * rows
        cell_pix: dict[Tuple[int, int], Optional[QPixmap]] = {}
        cell_fill: dict[Tuple[int, int], QColor] = {}
        for r, c, vi in cells:
            pm, fb = self._grab_viewport_for_composite_cell(vi)
            cell_pix[(r, c)] = pm
            cell_fill[(r, c)] = fb
            if pm is not None:
                col_w[c] = max(col_w[c], max(1, pm.width()))
                row_h[r] = max(row_h[r], max(1, pm.height()))

        for c in range(cols):
            if col_w[c] < 1:
                col_w[c] = 1
        for r in range(rows):
            if row_h[r] < 1:
                row_h[r] = 1

        canvas_bg = self._composite_canvas_color()
        total_w = sum(col_w) + gap * max(0, cols - 1)
        total_h = sum(row_h) + gap * max(0, rows - 1)
        out_img = QImage(total_w, total_h, QImage.Format.Format_ARGB32)
        out_img.fill(canvas_bg)
        painter = QPainter(out_img)
        y_off = 0
        for r in range(rows):
            x_off = 0
            for c in range(cols):
                pm = cell_pix.get((r, c))
                cell_w, cell_h = col_w[c], row_h[r]
                fill = cell_fill.get((r, c), canvas_bg)
                painter.fillRect(x_off, y_off, cell_w, cell_h, fill)
                if pm is not None:
                    if pm.width() == cell_w and pm.height() == cell_h:
                        painter.drawPixmap(x_off, y_off, pm)
                    else:
                        scaled = pm.scaled(
                            cell_w,
                            cell_h,
                            Qt.AspectRatioMode.KeepAspectRatio,
                            Qt.TransformationMode.SmoothTransformation,
                        )
                        dx = x_off + (cell_w - scaled.width()) // 2
                        dy = y_off + (cell_h - scaled.height()) // 2
                        painter.drawPixmap(dx, dy, scaled)
                x_off += cell_w + gap
            y_off += row_h[r] + gap
        painter.end()

        path = os.path.join(self.output_path, f"{prefix}_grid{ext}")
        out_img2, note = self._scale_qimage_for_export(out_img)
        notes = [note] if note else []
        if ext.lower() == ".jpg" and out_img2.hasAlphaChannel():
            out_img2 = out_img2.convertToFormat(QImage.Format.Format_RGB32)
        if not out_img2.save(path):
            return 0, "Failed to save composite image.", notes
        return 1, None, notes

    def _scale_qimage_for_export(self, img: QImage) -> Tuple[QImage, Optional[str]]:
        """Apply export magnification to a QImage (used for tiled composite before save)."""
        if img.isNull():
            return img, None
        w, h = img.width(), img.height()
        req = float(self.export_scale)
        eff = effective_scale_for_image(w, h, req)
        warn: Optional[str] = None
        if req > 1.0 and eff < req:
            warn = (
                f"Requested {req}× magnification; largest side would exceed 8192 px at that size, "
                f"so this capture was exported at {eff}×."
            )
        if eff <= 1.0:
            return img, warn
        nw = max(1, int(round(w * eff)))
        nh = max(1, int(round(h * eff)))
        scaled = img.scaled(
            nw,
            nh,
            Qt.AspectRatioMode.IgnoreAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        return scaled, warn

    def _export_composite(self, prefix: str, ext: str) -> Tuple[int, Optional[str], List[str]]:
        if self.multi_window_layout is None:
            return 0, "Composite export requires layout information (internal error).", []

        QApplication.processEvents()
        mwl = self.multi_window_layout
        pm: Optional[QPixmap] = None
        grab_fn = getattr(mwl, "grab_layout_grid_pixmap", None)
        if callable(grab_fn):
            pm = grab_fn()

        if pm is not None and not pm.isNull():
            pm2, note = self._scale_pixmap_for_export(pm)
            notes = [note] if note else []
            img = pm2.toImage()
            path = os.path.join(self.output_path, f"{prefix}_grid{ext}")
            if ext.lower() == ".jpg" and img.hasAlphaChannel():
                img = img.convertToFormat(QImage.Format.Format_RGB32)
            if not img.save(path):
                return 0, "Failed to save composite image.", notes
            return 1, None, notes

        return self._export_composite_tiled_fallback(prefix, ext)

    def _export_full_window(self, prefix: str, ext: str) -> Tuple[int, Optional[str], List[str]]:
        mw = self.parent()
        if mw is None:
            return 0, "No parent window for full-window capture.", []
        self.hide()
        QApplication.processEvents()
        try:
            pix = mw.grab()
        finally:
            self.show()
            QApplication.processEvents()
        if pix.isNull():
            return 0, "Full-window grab failed.", []
        pix2, note = self._scale_pixmap_for_export(pix)
        notes = [note] if note else []
        img = pix2.toImage()
        path = os.path.join(self.output_path, f"{prefix}_fullwindow{ext}")
        if ext.lower() == ".jpg" and img.hasAlphaChannel():
            img = img.convertToFormat(QImage.Format.Format_RGB32)
        if not img.save(path):
            return 0, "Failed to save full-window image.", notes
        return 1, None, notes

    def _on_export(self) -> None:
        prefix = (self.prefix_edit.text() or "screenshot").strip() or "screenshot"
        self.prefix = prefix
        self.format = self.format_combo.currentData() or "PNG"
        scale_data = self.resolution_combo.currentData()
        self.export_scale = float(scale_data) if scale_data is not None else 1.0
        mode = self._current_export_mode()

        if not self.output_path:
            QMessageBox.warning(self, "No directory", "Please select an output directory.")
            return

        if mode == self.MODE_FULL_WINDOW:
            selected: List[int] = []
        elif mode == self.MODE_COMPOSITE:
            selected = []
        else:
            selected = self._selected_indices()
            if not selected:
                QMessageBox.warning(self, "No selection", "Please select at least one view to export.")
                return

        ext = ".png" if self.format == "PNG" else ".jpg"
        paths_to_write = self._paths_for_overwrite_prompt(prefix, ext, mode)
        existing = [p for p in paths_to_write if os.path.exists(p)]
        if existing:
            msg = (
                f"{len(existing)} file(s) already exist and will be overwritten:\n"
                + "\n".join(os.path.basename(p) for p in existing)
                + "\n\nContinue?"
            )
            reply = QMessageBox.question(
                self,
                "Overwrite existing files?",
                msg,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return

        err: Optional[str] = None
        saved = 0
        scale_notes: List[str] = []
        self._set_subwindow_focus_borders_suppressed(True)
        QApplication.processEvents()
        try:
            if mode == self.MODE_SEPARATE:
                saved, err, scale_notes = self._export_separate(prefix, ext, selected)
            elif mode == self.MODE_COMPOSITE:
                saved, err, scale_notes = self._export_composite(prefix, ext)
            else:
                saved, err, scale_notes = self._export_full_window(prefix, ext)
        except Exception as e:
            QMessageBox.critical(self, "Export failed", str(e))
            return
        finally:
            self._set_subwindow_focus_borders_suppressed(False)
            QApplication.processEvents()

        if err:
            QMessageBox.warning(self, "Export incomplete", err)
            if saved == 0:
                return

        if self.config_manager and self.output_path:
            self.config_manager.set_last_export_path(self.output_path)
        done_msg = f"Saved {saved} screenshot file(s) to:\n{self.output_path}"
        uniq = list(dict.fromkeys(scale_notes))
        if uniq:
            done_msg += "\n\n" + "\n".join(uniq)
        QMessageBox.information(self, "Export complete", done_msg)
        self.accept()
