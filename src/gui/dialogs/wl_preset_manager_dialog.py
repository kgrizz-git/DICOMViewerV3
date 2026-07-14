"""
Manage user-defined window/level presets (built-in presets are read-only).

Persists to display config ``wl_user_presets``. Emits ``presets_saved`` when OK is used.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

WL_MODALITIES = [
    "ANY",
    "CT",
    "MR",
    "PT",
    "CR",
    "DX",
    "MG",
    "US",
    "RF",
    "NM",
    "XA",
    "RT",
]


class WLPresetManagerDialog(QDialog):
    """
    Add, edit, and delete custom W/L presets stored in application config.

    Signals:
        presets_saved: Emitted after successful OK with the new preset list.
    """

    presets_saved = Signal(list)

    def __init__(
        self,
        user_presets: list[dict[str, Any]],
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.setWindowTitle("Manage Window/Level Presets")
        self.setMinimumSize(640, 360)
        self._rows: list[dict[str, Any]] = [dict(p) for p in user_presets]
        self._build_ui()
        self._refresh_table()
        self.raise_()
        self.activateWindow()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setSpacing(10)
        root.setContentsMargins(12, 12, 12, 12)

        intro = QLabel(
            "Custom presets appear in the Window/Level menu for matching modalities. "
            "Built-in modality presets cannot be edited here.<br><br>"
            "Choose whether each preset is stored in <b>rescaled/calibrated</b> units "
            "(e.g. HU for CT) or <b>raw stored pixel</b> values. The viewer converts "
            "automatically when your Raw/Rescaled mode differs."
        )
        intro.setWordWrap(True)
        intro.setTextFormat(Qt.TextFormat.RichText)
        root.addWidget(intro)

        btn_row = QHBoxLayout()
        add_btn = QPushButton("Add…")
        add_btn.clicked.connect(self._on_add)
        edit_btn = QPushButton("Edit…")
        edit_btn.clicked.connect(self._on_edit)
        delete_btn = QPushButton("Delete")
        delete_btn.clicked.connect(self._on_delete)
        btn_row.addWidget(add_btn)
        btn_row.addWidget(edit_btn)
        btn_row.addWidget(delete_btn)
        btn_row.addStretch()
        root.addLayout(btn_row)

        self._table = QTableWidget(0, 5)
        self._table.setHorizontalHeaderLabels(
            ["Name", "Modality", "Center", "Width", "Rescaled (HU/calibrated)"]
        )
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.doubleClicked.connect(lambda _idx: self._on_edit())
        root.addWidget(self._table)

        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self._on_ok)
        button_box.rejected.connect(self.reject)
        root.addWidget(button_box)

    def _refresh_table(self) -> None:
        self._table.setRowCount(len(self._rows))
        for row_idx, entry in enumerate(self._rows):
            self._table.setItem(row_idx, 0, QTableWidgetItem(str(entry.get("name", ""))))
            self._table.setItem(
                row_idx, 1, QTableWidgetItem(str(entry.get("modality", "ANY")))
            )
            self._table.setItem(
                row_idx, 2, QTableWidgetItem(f"{float(entry.get('center', 0)):.1f}")
            )
            self._table.setItem(
                row_idx, 3, QTableWidgetItem(f"{float(entry.get('width', 0)):.1f}")
            )
            rescaled = bool(entry.get("is_rescaled", True))
            self._table.setItem(
                row_idx,
                4,
                QTableWidgetItem("Yes" if rescaled else "No (raw pixels)"),
            )

    def _selected_row(self) -> int:
        rows = self._table.selectionModel().selectedRows()
        if not rows:
            return -1
        return rows[0].row()

    def _on_add(self) -> None:
        entry = self._edit_entry_dialog(None)
        if entry is not None:
            self._rows.append(entry)
            self._refresh_table()
            self._table.selectRow(len(self._rows) - 1)

    def _on_edit(self) -> None:
        row = self._selected_row()
        if row < 0:
            QMessageBox.information(self, "Edit preset", "Select a preset row to edit.")
            return
        entry = self._edit_entry_dialog(self._rows[row])
        if entry is not None:
            self._rows[row] = entry
            self._refresh_table()
            self._table.selectRow(row)

    def _on_delete(self) -> None:
        row = self._selected_row()
        if row < 0:
            QMessageBox.information(self, "Delete preset", "Select a preset row to delete.")
            return
        name = self._rows[row].get("name", "preset")
        reply = QMessageBox.question(
            self,
            "Delete preset",
            f"Delete preset \"{name}\"?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            del self._rows[row]
            self._refresh_table()

    def _edit_entry_dialog(
        self, existing: dict[str, Any] | None
    ) -> dict[str, Any] | None:
        dlg = QDialog(self)
        dlg.setWindowTitle("Edit preset" if existing else "Add preset")
        layout = QVBoxLayout(dlg)

        name_edit = QLineEdit()
        name_edit.setPlaceholderText("e.g. My Chest")
        if existing:
            name_edit.setText(str(existing.get("name", "")))

        modality_combo = QComboBox()
        for mod in WL_MODALITIES:
            modality_combo.addItem(mod)
        if existing:
            mod = str(existing.get("modality", "ANY")).upper()
            idx = modality_combo.findText(mod)
            if idx >= 0:
                modality_combo.setCurrentIndex(idx)

        center_spin = QDoubleSpinBox()
        center_spin.setRange(-1e6, 1e6)
        center_spin.setDecimals(1)
        center_spin.setValue(float(existing.get("center", 0)) if existing else 0.0)

        width_spin = QDoubleSpinBox()
        width_spin.setRange(0.1, 1e6)
        width_spin.setDecimals(1)
        width_spin.setValue(float(existing.get("width", 400)) if existing else 400.0)

        rescaled_check = QCheckBox("Values in rescaled / calibrated units (e.g. HU)")
        rescaled_check.setChecked(bool(existing.get("is_rescaled", True)) if existing else True)

        form_rows = [
            ("Name:", name_edit),
            ("Modality:", modality_combo),
            ("Center:", center_spin),
            ("Width:", width_spin),
        ]
        for label_text, widget in form_rows:
            row = QHBoxLayout()
            row.addWidget(QLabel(label_text))
            row.addWidget(widget, stretch=1)
            layout.addLayout(row)
        layout.addWidget(rescaled_check)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        layout.addWidget(buttons)

        if dlg.exec() != QDialog.DialogCode.Accepted:
            return None

        name = name_edit.text().strip()
        if not name:
            QMessageBox.warning(dlg, "Validation", "Name is required.")
            return None
        width_val = width_spin.value()
        if width_val <= 0:
            QMessageBox.warning(dlg, "Validation", "Width must be greater than zero.")
            return None

        return {
            "name": name,
            "modality": modality_combo.currentText(),
            "center": float(center_spin.value()),
            "width": float(width_val),
            "is_rescaled": rescaled_check.isChecked(),
        }

    def _on_ok(self) -> None:
        for entry in self._rows:
            if not str(entry.get("name", "")).strip():
                QMessageBox.warning(self, "Validation", "Every preset must have a name.")
                return
            if float(entry.get("width", 0)) <= 0:
                QMessageBox.warning(
                    self,
                    "Validation",
                    f"Preset \"{entry.get('name')}\" must have width > 0.",
                )
                return
        self.presets_saved.emit(list(self._rows))
        self.accept()

    def get_presets(self) -> list[dict[str, Any]]:
        """Return the current row list (after OK)."""
        return list(self._rows)
