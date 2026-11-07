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
from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QModelIndex, Qt, QTimer
from PySide6.QtGui import QAction, QShowEvent
from PySide6.QtWidgets import QDialog, QMenu, QMessageBox

from core.study_index.index_integrity_thread import StudyIndexIntegrityThread
from core.study_index.index_service import LocalStudyIndexService
from core.study_index.metadata_extract import repair_str_bytes_repr_artifact
from core.study_index.study_date_format import parse_study_date_filter_field
from gui.dialogs.study_index_about_dialog import _AboutStudyIndexDialog  # noqa: F401  # re-exported for tests
from gui.dialogs.study_index_dialog_common import _TITLE_STUDY_INDEX
from gui.dialogs.study_index_missing_studies_dialog import _MissingStudiesDialog  # noqa: F401  # re-exported for tests
from gui.dialogs.study_index_search_model import (
    _format_indexed_at_display,  # noqa: F401  # re-exported for tests
    _StudyIndexGroupedModel,
)
from gui.dialogs.study_index_search_panels import StudyIndexSearchPanelsMixin
from utils.config_manager import ConfigManager
from utils.log_sanitizer import sanitize_message

_PAGE_SIZE = 100


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


class StudyIndexSearchDialog(StudyIndexSearchPanelsMixin, QDialog):
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
        """Load one page of grouped studies into the table.

        ``reset`` replaces the rows and starts at offset 0; otherwise the page
        is appended. Invalid dates abort with a warning only when
        ``strict_dates`` is set. Load more stays enabled when the page is full.
        """
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

    def _selected_rows(self) -> list[int]:
        """Sorted, distinct row indices currently selected in the table."""
        sel_model = self._table.selectionModel()
        rows = {ix.row() for ix in sel_model.selectedRows()}
        if not rows:
            rows = {ix.row() for ix in sel_model.selectedIndexes()}
        return sorted(rows)

    def _open_selected_file(self) -> None:
        row = self._selected_row()
        if row < 0:
            QMessageBox.information(self, _TITLE_STUDY_INDEX, "Select a row first.")
            return
        self._open_row(row)

    def _open_row(self, row: int) -> None:
        """Open the study for this grouped row.

        When the indexed folder still exists, open that folder the same way as
        Open Folder so the loader rescans it instead of a partial path list
        from the index. When the folder is gone and no indexed file remains,
        offer relocate or, if a sample file still exists, load that file only.
        A partial miss warns and opens the files that are still on disk.
        """
        snap = self._model.group_row_snapshot(row)
        study_uid = (snap.get("study_uid") or "").strip()
        study_root = (snap.get("study_root_path") or "").strip()
        fallback = (snap.get("open_file_path") or "").strip()

        if not study_uid or not study_root:
            QMessageBox.warning(self, _TITLE_STUDY_INDEX, "Row is missing study UID or folder path.")
            return

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

    def _on_table_context_menu(self, pos) -> None:
        ix = self._table.indexAt(pos)
        if not ix.isValid():
            return
        if ix.row() not in self._selected_rows():
            self._table.selectRow(ix.row())
        rows = self._selected_rows()
        menu = QMenu(self)
        label = (
            f"Remove {len(rows)} studies from index…"
            if len(rows) > 1
            else "Remove from index…"
        )
        remove_act = QAction(label, self)
        menu.addAction(remove_act)
        chosen = menu.exec(self._table.viewport().mapToGlobal(pos))
        if chosen == remove_act:
            self._remove_studies_at_rows(self._selected_rows())

    def _on_remove_from_index_clicked(self) -> None:
        rows = self._selected_rows()
        if not rows:
            QMessageBox.information(self, _TITLE_STUDY_INDEX, "Select a study row first.")
            return
        self._remove_studies_at_rows(rows)

    def _remove_study_at_row(self, row: int) -> None:
        self._remove_studies_at_rows([row])

    def _remove_studies_at_rows(self, rows: list[int]) -> None:
        """Delete the selected grouped studies from the encrypted index only.

        Duplicate (study UID, folder) pairs are removed once. DICOM files on
        disk are left in place. One study's failure is reported and the rest
        continue. The browse list is refreshed afterward, including when
        nothing was removed.
        """
        if not self._backend_ok_or_warn():
            return

        studies: list[tuple[str, str, str, int]] = []
        seen: set[tuple[str, str]] = set()
        for row in rows:
            snap = self._model.group_row_snapshot(row)
            study_uid = (snap.get("study_uid") or "").strip()
            study_root = (snap.get("study_root_path") or "").strip()
            if not study_uid or not study_root:
                continue
            key = (study_uid, study_root)
            if key in seen:
                continue
            seen.add(key)
            pn_raw = str(snap.get("patient_name") or "")
            if self._privacy():
                patient_label = "***"
            else:
                patient_label = repair_str_bytes_repr_artifact(pn_raw) or "(unknown patient)"
            n_inst = int(snap.get("instance_count") or 0)
            studies.append((study_uid, study_root, patient_label, n_inst))

        if not studies:
            QMessageBox.warning(
                self,
                _TITLE_STUDY_INDEX,
                "The selected row(s) are missing a study UID or study folder path.",
            )
            return

        if len(studies) == 1:
            _uid, _root, patient_label, n_inst = studies[0]
            msg = (
                "Remove this study from the local encrypted index only?\n\n"
                f"Patient: {patient_label}\n"
                f"Indexed instances in this row: {n_inst}\n\n"
                "DICOM files on disk are not deleted. You can re-add the study by opening "
                "or indexing the folder again (if auto-add on open is enabled)."
            )
        else:
            labels = [s[2] for s in studies]
            shown = labels[:5]
            lines = "\n".join(f"  {label}" for label in shown)
            more = len(labels) - len(shown)
            if more > 0:
                lines += f"\n  …and {more} more"
            msg = (
                f"Remove {len(studies)} studies from the local encrypted index only?\n\n"
                f"{lines}\n\n"
                "DICOM files on disk are not deleted. You can re-add studies by opening "
                "or indexing the folder(s) again (if auto-add on open is enabled)."
            )

        if (
            QMessageBox.question(self, _TITLE_STUDY_INDEX, msg)
            != QMessageBox.StandardButton.Yes
        ):
            return

        total_deleted = 0
        studies_removed = 0
        for study_uid, study_root, _patient_label, _n_inst in studies:
            try:
                deleted = self._service.delete_grouped_study(study_uid, study_root)
            except Exception as e:
                safe_details = sanitize_message(str(e), redact_paths=True)
                QMessageBox.critical(
                    self, _TITLE_STUDY_INDEX, f"Remove failed:\n{safe_details}"
                )
                continue
            if deleted > 0:
                total_deleted += deleted
                studies_removed += 1

        if studies_removed <= 0:
            QMessageBox.warning(
                self,
                _TITLE_STUDY_INDEX,
                "No rows were removed (the entry may have changed or already been removed).",
            )
        else:
            QMessageBox.information(
                self,
                _TITLE_STUDY_INDEX,
                f"Removed {studies_removed} study(ies) ({total_deleted} indexed "
                "instance(s)) from the index.",
            )
        self._run_browse(reset=True, strict_dates=False)
