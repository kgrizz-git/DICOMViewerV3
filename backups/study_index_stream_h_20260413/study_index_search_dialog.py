"""
Study index search dialog (local SQLCipher MVP).

Filter by patient, modality, dates, accession, study description; open a file
from the result list. Privacy mode masks patient-related columns.
"""

from __future__ import annotations

import os
from typing import Callable, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from core.study_index.index_service import LocalStudyIndexService
from utils.config_manager import ConfigManager


class StudyIndexSearchDialog(QDialog):
    """Modal search over the encrypted local study index."""

    def __init__(
        self,
        service: LocalStudyIndexService,
        config_manager: ConfigManager,
        open_paths_callback: Callable[[list[str]], None],
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._service = service
        self._config = config_manager
        self._open_paths = open_paths_callback
        self.setWindowTitle("Study index search")
        self.resize(960, 520)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        hint = QLabel(
            "Search the local encrypted index. Patient-related columns respect "
            "<b>Privacy mode</b> when it is enabled in View."
        )
        hint.setTextFormat(Qt.TextFormat.RichText)
        hint.setWordWrap(True)
        layout.addWidget(hint)

        filt = QGroupBox("Filters")
        form = QFormLayout(filt)
        self._patient_name = QLineEdit()
        self._patient_id = QLineEdit()
        self._modality = QLineEdit()
        self._accession = QLineEdit()
        self._study_desc = QLineEdit()
        self._date_from = QLineEdit()
        self._date_to = QLineEdit()
        self._date_from.setPlaceholderText("YYYYMMDD")
        self._date_to.setPlaceholderText("YYYYMMDD")
        form.addRow("Patient name contains:", self._patient_name)
        form.addRow("Patient ID contains:", self._patient_id)
        form.addRow("Modality contains:", self._modality)
        form.addRow("Accession contains:", self._accession)
        form.addRow("Study description contains:", self._study_desc)
        form.addRow("Study date from:", self._date_from)
        form.addRow("Study date to:", self._date_to)
        layout.addWidget(filt)

        btn_row = QHBoxLayout()
        search_btn = QPushButton("Search")
        search_btn.clicked.connect(self._run_search)
        index_btn = QPushButton("Index folder…")
        index_btn.clicked.connect(self._index_folder)
        btn_row.addWidget(search_btn)
        btn_row.addWidget(index_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        self._table = QTableWidget(0, 8)
        self._table.setHorizontalHeaderLabels(
            [
                "Patient name",
                "Patient ID",
                "Modality",
                "Study date",
                "Accession",
                "Study description",
                "File",
                "Study root",
            ]
        )
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.doubleClicked.connect(self._open_selected_file)
        layout.addWidget(self._table)

        bottom = QHBoxLayout()
        open_btn = QPushButton("Open selected file")
        open_btn.clicked.connect(self._open_selected_file)
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.reject)
        bottom.addWidget(open_btn)
        bottom.addStretch()
        bottom.addWidget(close_btn)
        layout.addLayout(bottom)

    def _privacy(self) -> bool:
        return bool(self._config.get_privacy_view())

    def _run_search(self) -> None:
        if not self._service.is_backend_available():
            QMessageBox.warning(
                self,
                "Study index",
                "sqlcipher3 or keyring is not available. Install dependencies from requirements.txt.",
            )
            return
        try:
            rows = self._service.search(
                patient_name_contains=self._patient_name.text(),
                patient_id_contains=self._patient_id.text(),
                modality=self._modality.text(),
                accession_contains=self._accession.text(),
                study_description_contains=self._study_desc.text(),
                study_date_from=self._date_from.text(),
                study_date_to=self._date_to.text(),
                limit=500,
                privacy_mode=self._privacy(),
            )
        except Exception as e:
            QMessageBox.critical(self, "Study index", f"Search failed:\n{e}")
            return
        self._table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            vals = [
                row.get("patient_name") or "",
                row.get("patient_id") or "",
                row.get("modality") or "",
                row.get("study_date") or "",
                row.get("accession_number") or "",
                row.get("study_description") or "",
                row.get("file_path") or "",
                row.get("study_root_path") or "",
            ]
            for c, v in enumerate(vals):
                self._table.setItem(r, c, QTableWidgetItem(str(v)))
        self._table.resizeColumnsToContents()

    def _current_file_path(self) -> Optional[str]:
        sel = self._table.selectedIndexes()
        if not sel:
            return None
        row = sel[0].row()
        item = self._table.item(row, 6)
        if not item:
            return None
        p = (item.text() or "").strip()
        return p if p else None

    def _open_selected_file(self) -> None:
        path = self._current_file_path()
        if not path:
            QMessageBox.information(self, "Study index", "Select a row with a file path.")
            return
        if not os.path.isfile(path):
            QMessageBox.warning(self, "Study index", f"File not found:\n{path}")
            return
        self._open_paths([path])
        self.accept()

    def _index_folder(self) -> None:
        if not self._service.is_backend_available():
            QMessageBox.warning(
                self,
                "Study index",
                "sqlcipher3 or keyring is not available.",
            )
            return
        start = self._config.get_last_path() or os.path.expanduser("~")
        folder = QFileDialog.getExistingDirectory(self, "Index DICOM folder", start)
        if not folder:
            return

        def on_fail(msg: str) -> None:
            if msg != "Cancelled":
                QMessageBox.warning(self, "Study index", f"Indexing failed:\n{msg}")

        def on_ok(n: int) -> None:
            QMessageBox.information(
                self, "Study index", f"Indexed {n} DICOM file(s) into the local database."
            )
            self._run_search()

        self._service.start_index_folder(
            folder,
            on_finished=lambda n: on_ok(n),
            on_failed=on_fail,
        )
