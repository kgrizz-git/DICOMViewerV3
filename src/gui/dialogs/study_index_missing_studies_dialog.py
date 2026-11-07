"""Missing-files dialog for the study index search."""

from __future__ import annotations

import os
from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from core.study_index.index_service import (
    LocalStudyIndexService,
    MissingStudyRecord,
)
from core.study_index.metadata_extract import repair_str_bytes_repr_artifact
from core.study_index.study_date_format import format_study_date_display_us
from gui.dialogs.study_index_dialog_common import (
    _MSG_RELOCATE_UNCHANGED,
    _TITLE_STUDY_INDEX,
)
from utils.log_sanitizer import sanitize_message

_MISSING_COLUMNS = (
    "Patient name",
    "Study date",
    "Modalities",
    "Study folder",
    "Files missing",
)


class _MissingStudiesDialog(QDialog):
    """Results of an integrity scan: relocate or remove studies with missing files."""

    def __init__(
        self,
        records: list[MissingStudyRecord],
        service: LocalStudyIndexService,
        *,
        privacy: bool,
        on_changed: Callable[[], None],
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._records: list[MissingStudyRecord] = list(records)
        self._service = service
        self._privacy = privacy
        self._on_changed = on_changed
        self.setWindowTitle("Check indexed studies")
        self.resize(880, 480)
        self._build_ui()
        self._populate()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        hint = QLabel(
            "These indexed studies have files that were not found on disk. "
            "<b>Relocate…</b> points the index at a new folder (the files must exist "
            "there); <b>Remove from index</b> deletes only the database rows for that "
            "study (never files on disk)."
        )
        hint.setTextFormat(Qt.TextFormat.RichText)
        hint.setWordWrap(True)
        layout.addWidget(hint)

        self._table = QTableWidget()
        self._table.setColumnCount(len(_MISSING_COLUMNS))
        self._table.setHorizontalHeaderLabels(list(_MISSING_COLUMNS))
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.verticalHeader().setVisible(False)
        hdr = self._table.horizontalHeader()
        hdr.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self._table)

        btn_row = QHBoxLayout()
        self._relocate_btn = QPushButton("Relocate…")
        self._relocate_btn.setToolTip("Point the selected study at a new folder")
        self._relocate_btn.clicked.connect(self._relocate_selected)
        self._remove_btn = QPushButton("Remove from index")
        self._remove_btn.setToolTip(
            "Delete the selected study’s index rows (does not delete DICOM files)"
        )
        self._remove_btn.clicked.connect(self._remove_selected)
        remove_all_btn = QPushButton("Remove all missing")
        remove_all_btn.setToolTip(
            "Delete index rows for every study listed here (does not delete DICOM files)"
        )
        remove_all_btn.clicked.connect(self._remove_all)
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(self._relocate_btn)
        btn_row.addWidget(self._remove_btn)
        btn_row.addWidget(remove_all_btn)
        btn_row.addStretch()
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

    def _populate(self) -> None:
        self._table.setRowCount(len(self._records))
        for row, rec in enumerate(self._records):
            pn = "***" if self._privacy else (
                repair_str_bytes_repr_artifact(rec.patient_name) or ""
            )
            values = (
                pn,
                format_study_date_display_us(rec.study_date or ""),
                rec.modalities or "",
                rec.study_root_path or "",
                f"{rec.missing_count} of {rec.total_count} files missing",
            )
            for col, text in enumerate(values):
                item = QTableWidgetItem(text)
                item.setToolTip(text)
                self._table.setItem(row, col, item)
        self._table.resizeColumnsToContents()
        has_rows = bool(self._records)
        self._relocate_btn.setEnabled(has_rows)
        self._remove_btn.setEnabled(has_rows)

    def _selected_record(self) -> MissingStudyRecord | None:
        row = self._table.currentRow()
        if row < 0 or row >= len(self._records):
            return None
        return self._records[row]

    def _drop_record(self, rec: MissingStudyRecord) -> None:
        try:
            self._records.remove(rec)
        except ValueError:
            pass
        self._populate()

    def _relocate_selected(self) -> None:
        rec = self._selected_record()
        if rec is None:
            QMessageBox.information(self, _TITLE_STUDY_INDEX, "Select a study first.")
            return
        start = rec.study_root_path or os.path.expanduser("~")
        new_root = QFileDialog.getExistingDirectory(
            self, "Select the study’s new folder", start
        )
        if not new_root:
            return
        try:
            n = self._service.relocate_study(
                rec.study_uid, rec.study_root_path, new_root
            )
        except Exception as e:
            safe = sanitize_message(str(e), redact_paths=True)
            QMessageBox.critical(self, _TITLE_STUDY_INDEX, f"Relocate failed:\n{safe}")
            return
        if n <= 0:
            QMessageBox.warning(
                self,
                _TITLE_STUDY_INDEX,
                _MSG_RELOCATE_UNCHANGED,
            )
            return
        QMessageBox.information(
            self,
            _TITLE_STUDY_INDEX,
            f"Relocated {n} indexed file(s) to the new folder.",
        )
        self._drop_record(rec)
        self._on_changed()

    def _remove_selected(self) -> None:
        rec = self._selected_record()
        if rec is None:
            QMessageBox.information(self, _TITLE_STUDY_INDEX, "Select a study first.")
            return
        patient_label = (
            "***" if self._privacy
            else repair_str_bytes_repr_artifact(rec.patient_name) or "(unknown patient)"
        )
        msg = (
            "Remove this study from the local encrypted index only?\n\n"
            f"Patient: {patient_label}\n"
            f"Folder: {rec.study_root_path}\n\n"
            "DICOM files on disk are not deleted."
        )
        if (
            QMessageBox.question(self, _TITLE_STUDY_INDEX, msg)
            != QMessageBox.StandardButton.Yes
        ):
            return
        if self._delete_one(rec):
            self._drop_record(rec)
            self._on_changed()

    def _remove_all(self) -> None:
        if not self._records:
            return
        msg = (
            f"Remove all {len(self._records)} listed studies from the local encrypted "
            "index?\n\nDICOM files on disk are not deleted."
        )
        if (
            QMessageBox.question(self, _TITLE_STUDY_INDEX, msg)
            != QMessageBox.StandardButton.Yes
        ):
            return
        removed = 0
        for rec in list(self._records):
            if self._delete_one(rec):
                removed += 1
        self._records = []
        self._populate()
        QMessageBox.information(
            self,
            _TITLE_STUDY_INDEX,
            f"Removed {removed} study(ies) from the index.",
        )
        self._on_changed()

    def _delete_one(self, rec: MissingStudyRecord) -> bool:
        try:
            self._service.delete_grouped_study(rec.study_uid, rec.study_root_path)
        except Exception as e:
            safe = sanitize_message(str(e), redact_paths=True)
            QMessageBox.critical(self, _TITLE_STUDY_INDEX, f"Remove failed:\n{safe}")
            return False
        return True
