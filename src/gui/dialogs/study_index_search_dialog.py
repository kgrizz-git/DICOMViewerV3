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

import math
import os
from collections.abc import Callable
from datetime import datetime
from typing import Any

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
    QProgressDialog,
    QPushButton,
    QTableView,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from core.study_index.index_integrity_thread import StudyIndexIntegrityThread
from core.study_index.index_service import (
    LocalStudyIndexService,
    MissingStudyRecord,
)
from core.study_index.metadata_extract import repair_str_bytes_repr_artifact
from core.study_index.portability import (
    PIXEL_DATA_DISCLAIMER,
    read_entries_csv,
    write_entries_csv,
)
from core.study_index.study_date_format import (
    format_partial_mdy_digits,
    format_study_date_display_us,
    parse_study_date_filter_field,
)
from gui.study_index_info import (
    credential_store_note,
    format_last_modified,
    format_size_on_disk,
    open_study_index_location,
    study_index_db_path,
)
from utils.config_manager import ConfigManager
from utils.log_sanitizer import sanitize_message

_PAGE_SIZE = 100



_TITLE_STUDY_INDEX = "Study index"

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

# Column ids the browser can sort by (server-side). Mirrors the store's grouped-sort
# whitelist; columns absent here (folder, modalities, sample file, UID) ignore clicks.
_SORTABLE_COLUMN_IDS: frozenset[str] = frozenset(
    {
        "study_date",
        "patient_name",
        "patient_id",
        "accession_number",
        "study_description",
        "instance_count",
        "series_count",
        "indexed_at",
    }
)


def _format_indexed_at_display(value: Any) -> str:
    """Format an ``indexed_at`` epoch-seconds float as local ``YYYY-MM-DD HH:MM``.

    Returns an empty string when the value is missing or not a finite number.
    """
    if value is None or value == "":
        return ""
    try:
        epoch = float(value)
    except (TypeError, ValueError):
        return ""
    if not math.isfinite(epoch):
        return ""
    try:
        return datetime.fromtimestamp(epoch).strftime("%Y-%m-%d %H:%M")
    except (OverflowError, OSError, ValueError):
        return ""


_COLUMN_LABELS: dict[str, str] = {
    "patient_name": "Patient name",
    "patient_id": "Patient ID",
    "study_date": "Study date",
    "indexed_at": "Indexed",
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

    def rowCount(
        self, parent: QModelIndex | QPersistentModelIndex = QModelIndex()
    ) -> int:
        if parent.isValid():
            return 0
        return len(self._rows)

    def columnCount(
        self, parent: QModelIndex | QPersistentModelIndex = QModelIndex()
    ) -> int:
        if parent.isValid():
            return 0
        return len(self._column_ids)

    def data(
        self,
        index: QModelIndex | QPersistentModelIndex,
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
        if cid == "indexed_at":
            return _format_indexed_at_display(val)
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
        self._sort_column_id = "study_date"
        self._sort_descending = True
        self._integrity_thread: StudyIndexIntegrityThread | None = None
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
            "study and folder (not files on disk). Drag column headers to reorder; order is saved. "
            "<b>Recently indexed</b> clears filters and surfaces the most recently added studies first."
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
        check_btn = QPushButton("Check indexed studies…")
        check_btn.setToolTip(
            "Scan the index for studies whose DICOM files are missing on disk, "
            "then relocate or remove them"
        )
        check_btn.clicked.connect(self._check_indexed_studies)
        recent_btn = QPushButton("Recently indexed")
        recent_btn.setToolTip(
            "Clear filters and list studies newest-indexed first "
            "(most recent auto-adds at top)."
        )
        recent_btn.clicked.connect(self._on_recently_indexed_clicked)
        open_loc_btn = QPushButton("Open index location")
        open_loc_btn.setToolTip(
            f"Reveal the index database folder in your file manager\n{study_index_db_path(self._config)}"
        )
        open_loc_btn.clicked.connect(self._on_open_index_location)
        about_btn = QPushButton("About this index…")
        about_btn.setToolTip(
            "Show where the index lives, its size and encryption status, and "
            "move / export / import it"
        )
        about_btn.clicked.connect(self._show_about_index)
        btn_row.addWidget(search_btn)
        btn_row.addWidget(clear_btn)
        btn_row.addWidget(self._load_more_btn)
        btn_row.addWidget(index_btn)
        btn_row.addWidget(check_btn)
        btn_row.addWidget(recent_btn)
        btn_row.addWidget(open_loc_btn)
        btn_row.addWidget(about_btn)
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
        hdr.setSectionsClickable(True)
        hdr.setSortIndicatorShown(True)
        hdr.sectionMoved.connect(self._on_header_section_moved)
        hdr.sectionClicked.connect(self._on_header_section_clicked)
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

    def _effective_date_filters(self, *, strict: bool) -> tuple[str, str, str | None]:
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
            _TITLE_STUDY_INDEX,
            "sqlcipher3 or keyring is not available. Install dependencies from requirements.txt.",
        )
        return False

    def _run_browse(self, *, reset: bool, strict_dates: bool = False) -> None:
        if not self._backend_ok_or_warn():
            return
        df, dt, date_err = self._effective_date_filters(strict=strict_dates)
        if date_err:
            QMessageBox.warning(self, _TITLE_STUDY_INDEX, date_err)
            return
        if reset:
            self._offset = 0
        try:
            batch = self._service.search_grouped_studies(
                **self._service_query_kwargs(df, dt),
                limit=_PAGE_SIZE,
                offset=self._offset,
                order_by=self._sort_column_id,
                descending=self._sort_descending,
                privacy_mode=self._privacy(),
            )
        except ValueError as e:
            safe_details = sanitize_message(str(e), redact_paths=True)
            QMessageBox.warning(
                self,
                _TITLE_STUDY_INDEX,
                f"Search parameters are invalid. Please adjust filters.\n\nDetails: {safe_details}",
            )
            return
        except Exception as e:
            safe_details = sanitize_message(str(e), redact_paths=True)
            QMessageBox.critical(
                self,
                _TITLE_STUDY_INDEX,
                f"Query failed. Please try again.\n\nDetails: {safe_details}",
            )
            return
        if reset:
            self._model.set_rows(batch)
            self._update_sort_indicator()
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

    def _on_recently_indexed_clicked(self) -> None:
        """Clear filters and show the newest-indexed studies first."""
        self._global_fts.clear()
        self._patient_name.clear()
        self._patient_id.clear()
        self._modality.clear()
        self._accession.clear()
        self._study_desc.clear()
        self._date_from.clear()
        self._date_to.clear()
        self._sort_column_id = "indexed_at"
        self._sort_descending = True
        self._run_browse(reset=True, strict_dates=False)
        self._update_sort_indicator()
        if self._model.rowCount() > 0:
            self._table.selectRow(0)

    def _on_load_more(self) -> None:
        self._run_browse(reset=False)

    def _on_header_section_clicked(self, logical_index: int) -> None:
        """Set the sort column from the clicked header and re-query from the top.

        Clicking the active column toggles ascending/descending; a new column starts
        descending. Non-sortable columns (folder, modalities, sample file, UID) are
        ignored. Current filters are preserved and paging uses the same sort.
        """
        if logical_index < 0 or logical_index >= self._model.columnCount():
            return
        cid = self._model.column_id_at(logical_index)
        if cid not in _SORTABLE_COLUMN_IDS:
            return
        if cid == self._sort_column_id:
            self._sort_descending = not self._sort_descending
        else:
            self._sort_column_id = cid
            self._sort_descending = True
        self._run_browse(reset=True, strict_dates=False)

    def _update_sort_indicator(self) -> None:
        """Show the sort arrow on the active column's current visual position."""
        hdr = self._table.horizontalHeader()
        order = (
            Qt.SortOrder.DescendingOrder
            if self._sort_descending
            else Qt.SortOrder.AscendingOrder
        )
        for i in range(self._model.columnCount()):
            if self._model.column_id_at(i) == self._sort_column_id:
                hdr.setSortIndicator(i, order)
                return

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
            QMessageBox.information(self, _TITLE_STUDY_INDEX, "Select a row first.")
            return
        self._open_row(row)

    def _open_row(self, row: int) -> None:
        snap = self._model.group_row_snapshot(row)
        study_uid = (snap.get("study_uid") or "").strip()
        study_root = (snap.get("study_root_path") or "").strip()
        fallback = (snap.get("open_file_path") or "").strip()

        if not study_uid or not study_root:
            QMessageBox.warning(self, _TITLE_STUDY_INDEX, "Row is missing study UID or folder path.")
            return

        # Full folder rescan (same as Open Folder / recent folder) when the indexed
        # study root still exists — avoids opening only a partial path list from the DB.
        if os.path.isdir(study_root):
            self._open_paths([study_root])
            self.accept()
            return

        try:
            paths = self._service.get_file_paths_for_study(study_uid, study_root)
        except Exception as e:
            safe_details = sanitize_message(str(e), redact_paths=True)
            QMessageBox.critical(
                self,
                _TITLE_STUDY_INDEX,
                f"Failed to retrieve file list from index.\n\nDetails: {safe_details}",
            )
            return

        existing = [p for p in paths if os.path.isfile(p)]

        if not existing:
            # All indexed paths are gone — files may have been moved or deleted.
            has_fallback = bool(fallback) and os.path.isfile(fallback)
            box = QMessageBox(self)
            box.setIcon(QMessageBox.Icon.Warning)
            box.setWindowTitle(_TITLE_STUDY_INDEX)
            if has_fallback:
                box.setText(
                    "None of the indexed file paths were found at their recorded "
                    "locations.\n"
                    "If the study folder moved, you can point the index at its new "
                    "location, or load only the sample file.\n\n"
                    f"Study folder: {study_root}"
                )
                load_sample_btn = box.addButton(
                    "Load sample only", QMessageBox.ButtonRole.AcceptRole
                )
            else:
                box.setText(
                    "None of the indexed files were found on disk.\n"
                    "If the study folder moved, you can point the index at its new "
                    "location.\n\n"
                    f"Study folder: {study_root}"
                )
                load_sample_btn = None
            relocate_btn = box.addButton(
                "Relocate…", QMessageBox.ButtonRole.ActionRole
            )
            box.addButton(QMessageBox.StandardButton.Cancel)
            box.setDefaultButton(relocate_btn)
            box.exec()
            clicked = box.clickedButton()
            if clicked is relocate_btn:
                self._relocate_and_reopen(study_uid, study_root)
                return
            if load_sample_btn is not None and clicked is load_sample_btn:
                self._open_paths([fallback])
                self.accept()
            return

        missing_count = len(paths) - len(existing)
        if missing_count > 0:
            QMessageBox.warning(
                self,
                _TITLE_STUDY_INDEX,
                (
                    f"{missing_count} of {len(paths)} indexed file(s) were not found "
                    "on disk and will be skipped.\n"
                    "The study may have been partially moved or modified.\n\n"
                    f"Study folder: {study_root}"
                ),
            )

        self._open_paths(existing)
        self.accept()

    def _relocate_and_reopen(self, study_uid: str, study_root: str) -> bool:
        """Prompt for the study's new folder, relocate index paths, then retry opening.

        Returns True when relocation updated the index (open was retried), False when
        the user canceled or no relocated files were found.
        """
        if not self._backend_ok_or_warn():
            return False
        start = study_root or os.path.expanduser("~")
        new_root = QFileDialog.getExistingDirectory(
            self, "Select the study’s new folder", start
        )
        if not new_root:
            return False
        try:
            n = self._service.relocate_study(study_uid, study_root, new_root)
        except Exception as e:
            safe = sanitize_message(str(e), redact_paths=True)
            QMessageBox.critical(self, _TITLE_STUDY_INDEX, f"Relocate failed:\n{safe}")
            return False
        if n <= 0:
            QMessageBox.warning(
                self,
                _TITLE_STUDY_INDEX,
                "No relocated files were found in that folder. The index was not changed.",
            )
            return False
        # Index now points at the new location. Refresh so the list reflects the new
        # paths, then open the chosen folder directly (mirrors the fast-path rescan).
        self._run_browse(reset=True)
        self._open_paths([new_root])
        self.accept()
        return True

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
            QMessageBox.information(self, _TITLE_STUDY_INDEX, "Select a study row first.")
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
                _TITLE_STUDY_INDEX,
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
            QMessageBox.question(self, _TITLE_STUDY_INDEX, msg)
            != QMessageBox.StandardButton.Yes
        ):
            return
        try:
            deleted = self._service.delete_grouped_study(study_uid, study_root)
        except Exception as e:
            safe_details = sanitize_message(str(e), redact_paths=True)
            QMessageBox.critical(self, _TITLE_STUDY_INDEX, f"Remove failed:\n{safe_details}")
            return
        if deleted <= 0:
            QMessageBox.warning(
                self,
                _TITLE_STUDY_INDEX,
                "No rows were removed (the entry may have changed or already been removed).",
            )
        else:
            QMessageBox.information(
                self,
                _TITLE_STUDY_INDEX,
                f"Removed {deleted} indexed instance(s) from the database.",
            )
        self._run_browse(reset=True, strict_dates=False)

    def _on_open_index_location(self) -> None:
        """Reveal the index database folder in the OS file manager."""
        if not open_study_index_location(self._config):
            QMessageBox.information(
                self,
                _TITLE_STUDY_INDEX,
                f"Could not open the index location:\n{study_index_db_path(self._config)}",
            )

    def _show_about_index(self) -> None:
        """Open the About-this-index panel (metadata + move / export / import)."""
        if not self._backend_ok_or_warn():
            return

        def on_changed() -> None:
            self._run_browse(reset=True, strict_dates=False)

        dlg = _AboutStudyIndexDialog(
            self._service, self._config, on_changed=on_changed, parent=self
        )
        dlg.exec()

    def _index_folder(self) -> None:
        if not self._backend_ok_or_warn():
            return
        start = self._config.get_last_path() or os.path.expanduser("~")
        folder = QFileDialog.getExistingDirectory(self, "Index DICOM folder", start)
        if not folder:
            return

        def on_fail(msg: str) -> None:
            if msg != "Cancelled":
                QMessageBox.warning(self, _TITLE_STUDY_INDEX, f"Indexing failed:\n{msg}")

        def on_ok(n: int) -> None:
            QMessageBox.information(
                self, _TITLE_STUDY_INDEX, f"Indexed {n} DICOM file(s) into the local database."
            )
            self._run_browse(reset=True)

        self._service.start_index_folder(
            folder,
            on_finished=lambda n: on_ok(n),
            on_failed=on_fail,
        )

    def _check_indexed_studies(self) -> None:
        """Scan the index for missing files on a background thread, then show results."""
        if not self._backend_ok_or_warn():
            return

        progress = QProgressDialog(
            "Checking indexed studies…", "Cancel", 0, 0, self
        )
        progress.setWindowTitle(_TITLE_STUDY_INDEX)
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(0)
        progress.setAutoClose(False)
        progress.setAutoReset(False)

        thread = StudyIndexIntegrityThread(self._service, parent=self)
        self._integrity_thread = thread

        def on_progress(done: int, total: int) -> None:
            if total > 0:
                progress.setMaximum(total)
                progress.setValue(done)

        def cleanup() -> None:
            progress.close()
            self._integrity_thread = None

        def on_ok(records: object) -> None:
            cleanup()
            recs = list(records) if isinstance(records, list) else []
            self._show_missing_studies(recs)

        def on_fail(msg: str) -> None:
            cleanup()
            safe = sanitize_message(msg, redact_paths=True)
            QMessageBox.warning(
                self, _TITLE_STUDY_INDEX, f"Checking the index failed:\n{safe}"
            )

        thread.progress.connect(on_progress)
        thread.finished_ok.connect(on_ok)
        thread.failed.connect(on_fail)
        # Cancelling the progress dialog just detaches the UI; the scan is read-only.
        progress.canceled.connect(progress.close)
        thread.start()

    def _show_missing_studies(self, records: list[MissingStudyRecord]) -> None:
        if not records:
            QMessageBox.information(
                self,
                _TITLE_STUDY_INDEX,
                "All indexed studies were found on disk. Nothing to relocate or remove.",
            )
            return

        def on_changed() -> None:
            self._run_browse(reset=True, strict_dates=False)

        dlg = _MissingStudiesDialog(
            records,
            self._service,
            privacy=self._privacy(),
            on_changed=on_changed,
            parent=self,
        )
        dlg.exec()
        # A relocate/remove already refreshed the browse list via on_changed.

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
                "No relocated files were found in that folder. The index was not changed.",
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
