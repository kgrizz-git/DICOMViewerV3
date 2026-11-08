"""Table model and date-entry widget for the study index search dialog."""

from __future__ import annotations

import math
from datetime import datetime
from typing import Any

from PySide6.QtCore import (
    QAbstractTableModel,
    QModelIndex,
    QPersistentModelIndex,
    Qt,
)
from PySide6.QtWidgets import QLineEdit

from core.study_index.metadata_extract import repair_str_bytes_repr_artifact
from core.study_index.study_date_format import (
    format_partial_mdy_digits,
    format_study_date_display_us,
)


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
