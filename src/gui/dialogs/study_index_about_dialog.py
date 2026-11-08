"""About-this-index dialog for the study index search."""

from __future__ import annotations

import os
from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from core.study_index.index_service import LocalStudyIndexService
from core.study_index.portability import (
    PIXEL_DATA_DISCLAIMER,
    read_entries_csv,
    write_entries_csv,
)
from gui.dialogs.study_index_dialog_common import _TITLE_STUDY_INDEX
from gui.study_index_info import (
    credential_store_note,
    format_last_modified,
    format_size_on_disk,
    open_study_index_location,
    study_index_db_path,
)
from utils.config_manager import ConfigManager
from utils.log_sanitizer import sanitize_message


class _AboutStudyIndexDialog(QDialog):
    """About-this-index panel: location, encryption, size, and move / export / import."""

    def __init__(
        self,
        service: LocalStudyIndexService,
        config: ConfigManager,
        *,
        on_changed: Callable[[], None],
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._service = service
        self._config = config
        self._on_changed = on_changed
        self.setWindowTitle("About this index")
        self.resize(640, 360)
        self._build_ui()
        self._refresh_info()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        info = QGroupBox("This index")
        form = QFormLayout(info)
        self._path_value = QLabel()
        self._path_value.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self._path_value.setWordWrap(True)
        self._encryption_value = QLabel()
        self._encryption_value.setWordWrap(True)
        self._rows_value = QLabel()
        self._size_value = QLabel()
        self._modified_value = QLabel()
        form.addRow("Location:", self._path_value)
        form.addRow("Encryption:", self._encryption_value)
        form.addRow("Indexed instances:", self._rows_value)
        form.addRow("Size on disk:", self._size_value)
        form.addRow("Last modified:", self._modified_value)
        layout.addWidget(info)

        open_row = QHBoxLayout()
        open_loc_btn = QPushButton("Open location")
        open_loc_btn.setToolTip("Reveal the index database folder in your file manager")
        open_loc_btn.clicked.connect(self._open_location)
        open_row.addWidget(open_loc_btn)
        open_row.addStretch()
        layout.addLayout(open_row)

        note = QLabel(PIXEL_DATA_DISCLAIMER)
        note.setWordWrap(True)
        layout.addWidget(note)

        actions = QHBoxLayout()
        move_btn = QPushButton("Move index…")
        move_btn.setToolTip("Copy the database to a new location and switch to it")
        move_btn.clicked.connect(self._move_index)
        export_btn = QPushButton("Export index…")
        export_btn.setToolTip("Write metadata and file paths to a CSV file")
        export_btn.clicked.connect(self._export_index)
        import_btn = QPushButton("Import index…")
        import_btn.setToolTip("Add rows from a prior CSV export (duplicates skipped)")
        import_btn.clicked.connect(self._import_index)
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        actions.addWidget(move_btn)
        actions.addWidget(export_btn)
        actions.addWidget(import_btn)
        actions.addStretch()
        actions.addWidget(close_btn)
        layout.addLayout(actions)

    def _refresh_info(self) -> None:
        db_path = study_index_db_path(self._config)
        self._path_value.setText(db_path)
        self._encryption_value.setText(
            "Encrypted at rest (SQLCipher). " + credential_store_note()
        )
        try:
            count = self._service.row_count()
            self._rows_value.setText(f"{count:,}")
        except Exception:
            self._rows_value.setText("Unavailable")
        self._size_value.setText(
            format_size_on_disk(self._service.db_file_size_bytes())
        )
        self._modified_value.setText(
            format_last_modified(self._service.db_last_modified())
        )

    def _open_location(self) -> None:
        if not open_study_index_location(self._config):
            QMessageBox.information(
                self,
                _TITLE_STUDY_INDEX,
                f"Could not open the index location:\n{study_index_db_path(self._config)}",
            )

    def _move_index(self) -> None:
        current = study_index_db_path(self._config)
        dest, _ = QFileDialog.getSaveFileName(
            self,
            "Move index database to…",
            current,
            "SQLite database (*.sqlite);;All files (*)",
        )
        if not dest:
            return
        confirm = (
            "Move the encrypted index database to:\n\n"
            f"{dest}\n\n"
            "The copy is verified before the old file is deleted. Continue?"
        )
        if (
            QMessageBox.question(self, _TITLE_STUDY_INDEX, confirm)
            != QMessageBox.StandardButton.Yes
        ):
            return
        try:
            new_path = self._service.move_database(dest)
        except Exception as e:
            safe = sanitize_message(str(e), redact_paths=True)
            QMessageBox.critical(
                self, _TITLE_STUDY_INDEX, f"Could not move the index:\n{safe}"
            )
            return
        QMessageBox.information(
            self, _TITLE_STUDY_INDEX, f"Index moved to:\n{new_path}"
        )
        self._refresh_info()
        self._on_changed()

    def _export_index(self) -> None:
        default_name = os.path.join(
            os.path.dirname(study_index_db_path(self._config)),
            "study_index_export.csv",
        )
        dest, _ = QFileDialog.getSaveFileName(
            self,
            "Export index (metadata + file paths only)",
            default_name,
            "CSV files (*.csv);;All files (*)",
        )
        if not dest:
            return
        try:
            rows = self._service.export_entries()
            n = write_entries_csv(dest, rows)
        except Exception as e:
            safe = sanitize_message(str(e), redact_paths=True)
            QMessageBox.critical(
                self, _TITLE_STUDY_INDEX, f"Export failed:\n{safe}"
            )
            return
        QMessageBox.information(
            self,
            _TITLE_STUDY_INDEX,
            f"Exported {n} indexed entr(ies) (metadata + file paths only).",
        )

    def _import_index(self) -> None:
        start = os.path.dirname(study_index_db_path(self._config))
        src, _ = QFileDialog.getOpenFileName(
            self, "Import index from CSV", start, "CSV files (*.csv);;All files (*)"
        )
        if not src:
            return
        try:
            rows = read_entries_csv(src)
            added, skipped = self._service.import_entries(rows)
        except Exception as e:
            safe = sanitize_message(str(e), redact_paths=True)
            QMessageBox.critical(
                self, _TITLE_STUDY_INDEX, f"Import failed:\n{safe}"
            )
            return
        QMessageBox.information(
            self,
            _TITLE_STUDY_INDEX,
            f"Imported {added} new entr(ies); skipped {skipped} duplicate(s).",
        )
        if added:
            self._refresh_info()
            self._on_changed()
