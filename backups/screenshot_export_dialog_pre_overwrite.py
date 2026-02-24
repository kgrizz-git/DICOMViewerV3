"""
Screenshot Export Dialog

Saves the currently displayed image(s) from one or more subwindows exactly as shown.
One file per selected subwindow. Option to include overlays/annotations (capture is
always WYSIWYG from the viewport).

Inputs:
    - List of subwindow containers (with image_viewer)
    - Output directory, filename prefix, format (PNG/JPG)
    - Which subwindows to include (checkboxes)

Outputs:
    - One image file per selected subwindow (e.g. prefix_view1.png)

Requirements:
    - PySide6 for dialogs and widget grab
"""

from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                                QPushButton, QFileDialog, QMessageBox,
                                QGroupBox, QCheckBox, QComboBox, QLineEdit)
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage
from typing import Optional, List
import os


class ScreenshotExportDialog(QDialog):
    """
    Dialog to export screenshots from selected subwindows.
    One file per selected subwindow; capture is viewport grab (WYSIWYG).
    """

    def __init__(
        self,
        subwindows: List,  # List of SubWindowContainer-like objects with .image_viewer
        config_manager=None,
        parent=None
    ):
        super().__init__(parent)
        self.setWindowTitle("Export Screenshots")
        self.setModal(True)
        self.resize(480, 380)
        self.subwindows = subwindows
        self.config_manager = config_manager
        self.output_path = config_manager.get_last_export_path() if config_manager else ""
        self.prefix = "screenshot"
        self.format = "PNG"
        self.include_annotations = True  # Captured view is always WYSIWYG; option for UI consistency
        self._checkboxes: List[QCheckBox] = []
        self._create_ui()

    def showEvent(self, event) -> None:
        """Bring dialog to front when shown (user preference for dialogs)."""
        super().showEvent(event)
        self.activateWindow()
        self.raise_()

    def _create_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)

        # Subwindow selection
        group = QGroupBox("Subwindows to export (one file per selected view)")
        group_layout = QVBoxLayout()
        for i, subwindow in enumerate(self.subwindows):
            has_image = getattr(subwindow, 'image_viewer', None) and getattr(
                subwindow.image_viewer, 'image_item', None
            ) is not None
            cb = QCheckBox(f"View {i + 1}")
            cb.setChecked(has_image)
            cb.setEnabled(has_image)
            if not has_image:
                cb.setToolTip("No image loaded in this view")
            self._checkboxes.append(cb)
            group_layout.addWidget(cb)
        group.setLayout(group_layout)
        layout.addWidget(group)

        # Include annotations (informational; capture is always WYSIWYG)
        self.include_annotations_cb = QCheckBox("Include overlays and annotations (capture shows current display)")
        self.include_annotations_cb.setChecked(True)
        self.include_annotations_cb.toggled.connect(lambda v: setattr(self, 'include_annotations', v))
        layout.addWidget(self.include_annotations_cb)

        # Output directory
        path_layout = QHBoxLayout()
        path_layout.addWidget(QLabel("Output directory:"))
        self.path_label = QLabel(self.output_path or "(Not selected)")
        self.path_label.setWordWrap(True)
        path_layout.addWidget(self.path_label, 1)
        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self._browse)
        path_layout.addWidget(browse_btn)
        layout.addLayout(path_layout)

        # Filename prefix
        prefix_layout = QHBoxLayout()
        prefix_layout.addWidget(QLabel("Filename prefix:"))
        self.prefix_edit = QLineEdit()
        self.prefix_edit.setPlaceholderText("screenshot")
        self.prefix_edit.setText(self.prefix)
        self.prefix_edit.textChanged.connect(lambda t: setattr(self, 'prefix', t or "screenshot"))
        prefix_layout.addWidget(self.prefix_edit)
        layout.addLayout(prefix_layout)

        # Format
        format_layout = QHBoxLayout()
        format_layout.addWidget(QLabel("Format:"))
        self.format_combo = QComboBox()
        self.format_combo.addItem("PNG", "PNG")
        self.format_combo.addItem("JPG", "JPG")
        self.format_combo.currentIndexChanged.connect(
            lambda: setattr(self, 'format', self.format_combo.currentData())
        )
        format_layout.addWidget(self.format_combo)
        format_layout.addStretch()
        layout.addLayout(format_layout)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        export_btn = QPushButton("Export")
        export_btn.clicked.connect(self._on_export)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(export_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

    def _browse(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Select output directory", self.output_path or "")
        if path:
            self.output_path = path
            self.path_label.setText(path)

    def _on_export(self) -> None:
        prefix = (self.prefix_edit.text() or "screenshot").strip() or "screenshot"
        self.prefix = prefix
        self.format = self.format_combo.currentData() or "PNG"
        if not self.output_path:
            QMessageBox.warning(self, "No directory", "Please select an output directory.")
            return
        selected = [i for i, cb in enumerate(self._checkboxes) if cb.isChecked()]
        if not selected:
            QMessageBox.warning(self, "No selection", "Please select at least one view to export.")
            return
        ext = ".png" if self.format == "PNG" else ".jpg"
        saved = 0
        for i in selected:
            if i >= len(self.subwindows):
                continue
            subwindow = self.subwindows[i]
            viewer = getattr(subwindow, 'image_viewer', None)
            if not viewer or getattr(viewer, 'image_item', None) is None:
                continue
            viewport = viewer.viewport()
            if not viewport:
                continue
            try:
                pixmap = viewport.grab()
                if pixmap.isNull():
                    continue
                img = pixmap.toImage()
                path = os.path.join(self.output_path, f"{prefix}_view{i + 1}{ext}")
                if img.save(path):
                    saved += 1
            except Exception as e:
                QMessageBox.critical(
                    self,
                    "Export failed",
                    f"Failed to save View {i + 1}: {e}"
                )
                return
        if self.config_manager and self.output_path:
            self.config_manager.set_last_export_path(self.output_path)
        QMessageBox.information(
            self,
            "Export complete",
            f"Saved {saved} screenshot(s) to:\n{self.output_path}"
        )
        self.accept()
