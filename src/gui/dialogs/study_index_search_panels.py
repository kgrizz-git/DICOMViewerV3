"""Search dialog panels mixin for the study index browser.

This mixin builds the search dialog panels and owns folder indexing,
the integrity check, relocate-and-reopen, and column-order persistence.
Inputs are attributes the dialog assigns (``_service``, ``_config``,
``_model``, ``_table``, ``_open_paths``, ``_save_columns_timer``, and
the query helpers). Outputs are widgets and the relocated/opened study.
Requires PySide6 and the study-index service already constructed by
the dialog.
"""
# Pyright: methods run only on ``StudyIndexSearchDialog`` (combined Qt type); mixin bases
# cannot express cross-mixin ``self`` without a duplicate protocol surface.
# ``reportArgumentType`` is also off so ``self`` can be passed as a ``QWidget``
# parent to ``QMessageBox`` / ``QFileDialog`` without a Protocol cast surface.
# pyright: reportAttributeAccessIssue=false, reportUninitializedInstanceVariable=false, reportArgumentType=false
from __future__ import annotations

import os

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressDialog,
    QPushButton,
    QTableView,
    QVBoxLayout,
)

from core.study_index.index_integrity_thread import StudyIndexIntegrityThread
from core.study_index.index_service import MissingStudyRecord
from gui.dialogs.study_index_about_dialog import _AboutStudyIndexDialog
from gui.dialogs.study_index_dialog_common import (
    _MSG_RELOCATE_UNCHANGED,
    _TITLE_STUDY_INDEX,
)
from gui.dialogs.study_index_missing_studies_dialog import _MissingStudiesDialog
from gui.dialogs.study_index_search_model import _StudyIndexMdyLineEdit
from gui.study_index_info import (
    open_study_index_location,
    study_index_db_path,
)
from utils.log_sanitizer import sanitize_message


class StudyIndexSearchPanelsMixin:
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
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
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
            "Delete index rows for all selected studies (does not delete DICOM files)"
        )
        remove_btn.clicked.connect(self._on_remove_from_index_clicked)
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.reject)
        bottom.addWidget(open_btn)
        bottom.addWidget(remove_btn)
        bottom.addStretch()
        bottom.addWidget(close_btn)
        layout.addLayout(bottom)

    def _relocate_and_reopen(self, study_uid: str, study_root: str) -> bool:
        """Relocate the study folder and reopen it. True when the index changed."""
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
                _MSG_RELOCATE_UNCHANGED,
            )
            return False
        self._run_browse(reset=True)
        try:
            self._open_paths(self._service.get_file_paths_for_study(study_uid, new_root))
        except Exception as exc:
            safe = sanitize_message(str(exc), redact_paths=True)
            QMessageBox.warning(
                self,
                _TITLE_STUDY_INDEX,
                "The index was updated, but the study could not be opened.\n" + safe,
            )
            return True
        self.accept()
        return True

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
