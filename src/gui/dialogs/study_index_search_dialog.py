"""
Study index browser dialog (local SQLCipher).

Grouped rows per study and folder root with instance/series counts and modalities.
**Search all text** uses SQLite FTS5 across indexed fields (combined with per-field
filters with AND semantics). Filters, **Search** / **Clear** (reset filters and reload
full index), paginated browse (**Load more**), **Remove from index** (delete grouped
study from the encrypted DB only), optional folder indexing, and privacy masking for
patient-related fields. Column order is persisted (movable headers).
"""

from __future__ import annotations

import os
from typing import Any, Callable, Optional, Union

from PySide6.QtCore import (
    QAbstractTableModel,
    QModelIndex,
    QPersistentModelIndex,
    Qt,
    QTimer,
)
from PySide6.QtGui import QAction, QShowEvent
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QTableView,
    QVBoxLayout,
)

from core.study_index.index_service import LocalStudyIndexService
from core.study_index.metadata_extract import repair_str_bytes_repr_artifact
from core.study_index.study_date_format import (
    format_partial_mdy_digits,
    format_study_date_display_us,
    parse_study_date_filter_field,
)
from utils.config_manager import ConfigManager
from utils.log_sanitizer import sanitize_message

_PAGE_SIZE = 100


class _StudyIndexMdyLineEdit(QLineEdit):
    """
    Date filter field: keep only digits (max 8) and insert ``/`` after MM and DD.
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._formatting = False
        self.textChanged.connect(self._on_text_changed)

    def _on_text_changed(self, text: str) -> None:
        if self._formatting:
            return
        digits = "".join(c for c in (text or "") if c.isdigit())[:8]
        new_t = format_partial_mdy_digits(digits)
        if new_t != (text or ""):
            self._formatting = True
            self.setText(new_t)
            self.setCursorPosition(len(new_t))
            self._formatting = False


# Text columns that may contain legacy ``b'…'`` SQLite values from older builds.
_COLUMNS_SANITIZE_BYTES_REPR: frozenset[str] = frozenset(
    {
        "patient_name",
        "patient_id",
        "accession_number",
        "study_description",
    }
)

_COLUMN_LABELS: dict[str, str] = {
    "patient_name": "Patient name",
    "patient_id": "Patient ID",
    "study_date": "Study date",
    "accession_number": "Accession",
    "study_description": "Study description",
    "study_root_path": "Study folder",
    "instance_count": "# Instances",
    "series_count": "# Series",
    "modalities": "Modalities",
    "open_file_path": "Sample file",
    "study_uid": "Study UID",
}


class _StudyIndexGroupedModel(QAbstractTableModel):
    """Table model for grouped study rows (dicts from ``search_grouped_studies``)."""

    def __init__(self, column_ids: list[str], parent=None) -> None:
        super().__init__(parent)
        self._column_ids = list(column_ids)
        self._rows: list[dict[str, Any]] = []

    def column_id_at(self, logical_index: int) -> str:
        return self._column_ids[logical_index]

    def set_column_ids(self, column_ids: list[str]) -> None:
        self.beginResetModel()
        self._column_ids = list(column_ids)
        self.endResetModel()

    def rowCount(  # noqa: N802
        self, parent: Union[QModelIndex, QPersistentModelIndex] = QModelIndex()
    ) -> int:
        if parent.isValid():
            return 0
        return len(self._rows)

    def columnCount(  # noqa: N802
        self, parent: Union[QModelIndex, QPersistentModelIndex] = QModelIndex()
    ) -> int:
        if parent.isValid():
            return 0
        return len(self._column_ids)

    def data(  # noqa: N802
        self,
        index: Union[QModelIndex, QPersistentModelIndex],
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> Any:
        if not index.isValid():
            return None
        row = self._rows[index.row()]
        cid = self._column_ids[index.column()]
        val = row.get(cid)
        if role not in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.ToolTipRole):
            return None
        if val is None:
            return ""
        if cid in ("instance_count", "series_count"):
            return str(int(val))
        if cid == "study_date":
            return format_study_date_display_us(str(val))
        s = str(val)
        if cid in _COLUMNS_SANITIZE_BYTES_REPR:
            s = repair_str_bytes_repr_artifact(s)
        return s

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole):
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            cid = self._column_ids[section]
            return _COLUMN_LABELS.get(cid, cid)
        return super().headerData(section, orientation, role)

    def set_rows(self, rows: list[dict[str, Any]]) -> None:
        self.beginResetModel()
        self._rows = list(rows)
        self.endResetModel()

    def append_rows(self, rows: list[dict[str, Any]]) -> None:
        if not rows:
            return
        first = len(self._rows)
        self.beginInsertRows(QModelIndex(), first, first + len(rows) - 1)
        self._rows.extend(rows)
        self.endInsertRows()

    def open_path_for_row(self, row: int) -> str:
        if row < 0 or row >= len(self._rows):
            return ""
        p = (self._rows[row].get("open_file_path") or "").strip()
        return p

    def group_row_snapshot(self, row: int) -> dict[str, Any]:
        """Raw grouped row dict for the given row (study UID, folder path, counts, etc.)."""
        if row < 0 or row >= len(self._rows):
            return {}
        return dict(self._rows[row])


class StudyIndexSearchDialog(QDialog):
    """Browse and search the encrypted local study index (grouped by study + folder)."""

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
        self._offset = 0
        self._save_columns_timer = QTimer(self)
        self._save_columns_timer.setSingleShot(True)
        self._save_columns_timer.timeout.connect(self._persist_column_visual_order)
        self.setWindowTitle("Study Index")
        self.resize(1024, 672)
        col_ids = self._config.get_study_index_browser_column_order()
        self._model = _StudyIndexGroupedModel(col_ids, parent=self)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        hint = QLabel(
            "Browse or search the local encrypted index (one row per study per folder). "
            "<b>Search all text</b> finds words across patient, IDs, accession, study and series "
            "descriptions, modality, and UIDs (FTS5). The filter fields below narrow results; "
            "all active filters and quick search combine with <b>AND</b>. "
            "Patient-related columns respect <b>Privacy mode</b> when enabled in View. "
            "Study dates in the table use <b>MM/DD/YYYY</b>; date filters accept the same "
            "or <b>YYYYMMDD</b>. <b>Remove from index</b> deletes only database rows for that "
            "study and folder (not files on disk). Drag column headers to reorder; order is saved."
        )
        hint.setTextFormat(Qt.TextFormat.RichText)
        hint.setWordWrap(True)
        layout.addWidget(hint)

        quick = QGroupBox("Search all text")
        quick_row = QHBoxLayout(quick)
        quick_row.addWidget(QLabel("Quick search:"))
        self._global_fts = QLineEdit()
        self._global_fts.setPlaceholderText(
            "Words match across indexed fields (e.g. series keyword + patient name)"
        )
        self._global_fts.setToolTip(
            "Full-text search (FTS5) across patient name, IDs, accession, study and series "
            "description, modality, and instance UIDs. Leave empty to use only the filters below."
        )
        quick_row.addWidget(self._global_fts, stretch=1)
        layout.addWidget(quick)

        filt = QGroupBox("Filters")
        filt_columns = QHBoxLayout(filt)
        form_left = QFormLayout()
        form_right = QFormLayout()
        self._patient_name = QLineEdit()
        self._patient_id = QLineEdit()
        self._modality = QLineEdit()
        self._accession = QLineEdit()
        self._study_desc = QLineEdit()
        self._date_from = _StudyIndexMdyLineEdit()
        self._date_to = _StudyIndexMdyLineEdit()
        self._date_from.setPlaceholderText("MM/DD/YYYY")
        self._date_to.setPlaceholderText("MM/DD/YYYY")
        # Two columns to shorten vertical space (global quick search stays full-width above).
        form_left.addRow("Patient name contains:", self._patient_name)
        form_left.addRow("Patient ID contains:", self._patient_id)
        form_left.addRow("Modality contains:", self._modality)
        form_left.addRow("Accession contains:", self._accession)
        form_right.addRow("Study description contains:", self._study_desc)
        form_right.addRow("Study date from (MM/DD/YYYY):", self._date_from)
        form_right.addRow("Study date to (MM/DD/YYYY):", self._date_to)
        filt_columns.addLayout(form_left, stretch=1)
        filt_columns.addLayout(form_right, stretch=1)
        layout.addWidget(filt)

        btn_row = QHBoxLayout()
        search_btn = QPushButton("Search")
        search_btn.clicked.connect(self._on_search_clicked)
        clear_btn = QPushButton("Clear")
        clear_btn.setToolTip("Clear all filters and reload the full index")
        clear_btn.clicked.connect(self._on_clear_filters_clicked)
        self._load_more_btn = QPushButton("Load more")
        self._load_more_btn.clicked.connect(self._on_load_more)
        index_btn = QPushButton("Index folder…")
        index_btn.clicked.connect(self._index_folder)
        btn_row.addWidget(search_btn)
        btn_row.addWidget(clear_btn)
        btn_row.addWidget(self._load_more_btn)
        btn_row.addWidget(index_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        self._table = QTableView()
        self._table.setModel(self._model)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        hdr = self._table.horizontalHeader()
        hdr.setSectionsMovable(True)
        hdr.setFirstSectionMovable(True)
        hdr.setStretchLastSection(True)
        hdr.sectionMoved.connect(self._on_header_section_moved)
        self._table.doubleClicked.connect(self._on_double_click)
        self._table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._table.customContextMenuRequested.connect(self._on_table_context_menu)
        layout.addWidget(self._table)

        self._apply_hidden_columns()

        bottom = QHBoxLayout()
        open_btn = QPushButton("Open selected study")
        open_btn.setToolTip(
            "Load all indexed DICOM files for this study into the viewer"
        )
        open_btn.clicked.connect(self._open_selected_file)
        remove_btn = QPushButton("Remove from index…")
        remove_btn.setToolTip(
            "Delete this study’s index rows for the selected folder (does not delete DICOM files)"
        )
        remove_btn.clicked.connect(self._on_remove_from_index_clicked)
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.reject)
        bottom.addWidget(open_btn)
        bottom.addWidget(remove_btn)
        bottom.addStretch()
        bottom.addWidget(close_btn)
        layout.addLayout(bottom)

    def showEvent(self, event: QShowEvent) -> None:
        super().showEvent(event)
        # Do not block open on malformed date text; strict validation runs on Search.
        self._run_browse(reset=True, strict_dates=False)

    def _apply_hidden_columns(self) -> None:
        """Hide Study UID by default (still reorderable if shown via future UI)."""
        for i in range(self._model.columnCount()):
            self._table.setColumnHidden(i, self._model.column_id_at(i) == "study_uid")

    def _privacy(self) -> bool:
        return bool(self._config.get_privacy_view())

    def _effective_date_filters(self, *, strict: bool) -> tuple[str, str, Optional[str]]:
        """
        Resolve date filter fields to ``YYYYMMDD`` for SQL.

        If ``strict`` and a field is non-empty but invalid, returns ``("", "", error)``.
        If not ``strict``, invalid non-empty fields are treated as no bound (empty string).
        """
        raw_f = self._date_from.text().strip()
        raw_t = self._date_to.text().strip()
        yf, okf = parse_study_date_filter_field(self._date_from.text())
        yt, okt = parse_study_date_filter_field(self._date_to.text())
        msg = (
            "Use MM/DD/YYYY (e.g. 01/15/2020) or YYYYMMDD (e.g. 20200115)."
        )
        if strict and raw_f and not okf:
            return "", "", f"Study date from is not valid. {msg}"
        if strict and raw_t and not okt:
            return "", "", f"Study date to is not valid. {msg}"
        df = yf if okf else ""
        dt = yt if okt else ""
        return df, dt, None

    def _service_query_kwargs(
        self, study_date_from: str, study_date_to: str
    ) -> dict[str, Any]:
        return {
            "patient_name_contains": self._patient_name.text(),
            "patient_id_contains": self._patient_id.text(),
            "modality": self._modality.text(),
            "accession_contains": self._accession.text(),
            "study_description_contains": self._study_desc.text(),
            "study_date_from": study_date_from,
            "study_date_to": study_date_to,
            "global_fts_query": self._global_fts.text(),
        }

    def _backend_ok_or_warn(self) -> bool:
        if self._service.is_backend_available():
            return True
        QMessageBox.warning(
            self,
            "Study index",
            "sqlcipher3 or keyring is not available. Install dependencies from requirements.txt.",
        )
        return False

    def _run_browse(self, *, reset: bool, strict_dates: bool = False) -> None:
        if not self._backend_ok_or_warn():
            return
        df, dt, date_err = self._effective_date_filters(strict=strict_dates)
        if date_err:
            QMessageBox.warning(self, "Study index", date_err)
            return
        if reset:
            self._offset = 0
        try:
            batch = self._service.search_grouped_studies(
                **self._service_query_kwargs(df, dt),
                limit=_PAGE_SIZE,
                offset=self._offset,
                privacy_mode=self._privacy(),
            )
        except ValueError as e:
            safe_details = sanitize_message(str(e), redact_paths=True)
            QMessageBox.warning(
                self,
                "Study index",
                f"Search parameters are invalid. Please adjust filters.\n\nDetails: {safe_details}",
            )
            return
        except Exception as e:
            safe_details = sanitize_message(str(e), redact_paths=True)
            QMessageBox.critical(
                self,
                "Study index",
                f"Query failed. Please try again.\n\nDetails: {safe_details}",
            )
            return
        if reset:
            self._model.set_rows(batch)
        else:
            self._model.append_rows(batch)
        self._offset += len(batch)
        self._load_more_btn.setEnabled(len(batch) >= _PAGE_SIZE)

    def _on_search_clicked(self) -> None:
        self._run_browse(reset=True, strict_dates=True)

    def _on_clear_filters_clicked(self) -> None:
        """Reset filter fields and show the entire study index (first page)."""
        self._global_fts.clear()
        self._patient_name.clear()
        self._patient_id.clear()
        self._modality.clear()
        self._accession.clear()
        self._study_desc.clear()
        self._date_from.clear()
        self._date_to.clear()
        self._run_browse(reset=True, strict_dates=False)

    def _on_load_more(self) -> None:
        self._run_browse(reset=False)

    def _on_double_click(self, index: QModelIndex) -> None:
        if index.isValid():
            self._open_row(index.row())

    def _selected_row(self) -> int:
        idxs = self._table.selectionModel().selectedIndexes()
        if not idxs:
            return -1
        return idxs[0].row()

    def _open_selected_file(self) -> None:
        row = self._selected_row()
        if row < 0:
            QMessageBox.information(self, "Study index", "Select a row first.")
            return
        self._open_row(row)

    def _open_row(self, row: int) -> None:
        snap = self._model.group_row_snapshot(row)
        study_uid = (snap.get("study_uid") or "").strip()
        study_root = (snap.get("study_root_path") or "").strip()
        fallback = (snap.get("open_file_path") or "").strip()

        if not study_uid or not study_root:
            QMessageBox.warning(self, "Study index", "Row is missing study UID or folder path.")
            return

        try:
            paths = self._service.get_file_paths_for_study(study_uid, study_root)
        except Exception as e:
            safe_details = sanitize_message(str(e), redact_paths=True)
            QMessageBox.critical(
                self,
                "Study index",
                f"Failed to retrieve file list from index.\n\nDetails: {safe_details}",
            )
            return

        existing = [p for p in paths if os.path.isfile(p)]

        if not existing:
            # All indexed paths are gone — files may have been moved or deleted.
            if fallback and os.path.isfile(fallback):
                QMessageBox.information(
                    self,
                    "Study index",
                    (
                        "None of the indexed file paths were found at their recorded locations.\n"
                        "Loading only the sample file as a fallback.\n\n"
                        f"Study folder: {study_root}"
                    ),
                )
                self._open_paths([fallback])
                self.accept()
                return
            QMessageBox.warning(
                self,
                "Study index",
                (
                    "None of the indexed files were found on disk.\n"
                    "The study may have been moved or deleted.\n\n"
                    f"Study folder: {study_root}"
                ),
            )
            return

        missing_count = len(paths) - len(existing)
        if missing_count > 0:
            QMessageBox.warning(
                self,
                "Study index",
                (
                    f"{missing_count} of {len(paths)} indexed file(s) were not found "
                    "on disk and will be skipped.\n"
                    "The study may have been partially moved or modified.\n\n"
                    f"Study folder: {study_root}"
                ),
            )

        self._open_paths(existing)
        self.accept()

    def _on_table_context_menu(self, pos) -> None:
        ix = self._table.indexAt(pos)
        if not ix.isValid():
            return
        self._table.selectRow(ix.row())
        menu = QMenu(self)
        remove_act = QAction("Remove from index…", self)
        menu.addAction(remove_act)
        chosen = menu.exec(self._table.viewport().mapToGlobal(pos))
        if chosen == remove_act:
            self._remove_study_at_row(ix.row())

    def _on_remove_from_index_clicked(self) -> None:
        row = self._selected_row()
        if row < 0:
            QMessageBox.information(self, "Study index", "Select a study row first.")
            return
        self._remove_study_at_row(row)

    def _remove_study_at_row(self, row: int) -> None:
        if not self._backend_ok_or_warn():
            return
        snap = self._model.group_row_snapshot(row)
        study_uid = (snap.get("study_uid") or "").strip()
        study_root = (snap.get("study_root_path") or "").strip()
        if not study_uid or not study_root:
            QMessageBox.warning(
                self,
                "Study index",
                "The selected row is missing a study UID or study folder path.",
            )
            return
        n_inst = int(snap.get("instance_count") or 0)
        pn_raw = str(snap.get("patient_name") or "")
        patient_label = repair_str_bytes_repr_artifact(pn_raw) or "(unknown patient)"
        msg = (
            "Remove this study from the local encrypted index only?\n\n"
            f"Patient: {patient_label}\n"
            f"Indexed instances in this row: {n_inst}\n\n"
            "DICOM files on disk are not deleted. You can re-add the study by opening "
            "or indexing the folder again (if auto-add on open is enabled)."
        )
        if (
            QMessageBox.question(self, "Study index", msg)
            != QMessageBox.StandardButton.Yes
        ):
            return
        try:
            deleted = self._service.delete_grouped_study(study_uid, study_root)
        except Exception as e:
            QMessageBox.critical(self, "Study index", f"Remove failed:\n{e}")
            return
        if deleted <= 0:
            QMessageBox.warning(
                self,
                "Study index",
                "No rows were removed (the entry may have changed or already been removed).",
            )
        else:
            QMessageBox.information(
                self,
                "Study index",
                f"Removed {deleted} indexed instance(s) from the database.",
            )
        self._run_browse(reset=True, strict_dates=False)

    def _index_folder(self) -> None:
        if not self._backend_ok_or_warn():
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
            self._run_browse(reset=True)

        self._service.start_index_folder(
            folder,
            on_finished=lambda n: on_ok(n),
            on_failed=on_fail,
        )

    def _on_header_section_moved(self, _logical: int, _old_v: int, _new_v: int) -> None:
        self._save_columns_timer.start(150)

    def _persist_column_visual_order(self) -> None:
        hdr = self._table.horizontalHeader()
        n = self._model.columnCount()
        if n <= 0:
            return
        ordered: list[str] = []
        for visual in range(n):
            logical = hdr.logicalIndex(visual)
            ordered.append(self._model.column_id_at(logical))
        self._config.set_study_index_browser_column_order(ordered)
        normalized = self._config.get_study_index_browser_column_order()
        hdr.blockSignals(True)
        try:
            self._model.set_column_ids(normalized)
        finally:
            hdr.blockSignals(False)
        self._apply_hidden_columns()
