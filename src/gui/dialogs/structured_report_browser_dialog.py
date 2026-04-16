"""
Structured Report browser — modeless SR document tree, dose event table, exports.

**Purpose:** Full-fidelity ``ContentSequence`` tree (lazy ``QAbstractItemModel``), optional
per-irradiation-event table for RDSR-style instances, legacy CT dose summary tab when parsing
succeeds, raw-tags shortcut, and JSON / CSV / XLSX export.

**Inputs:** ``pydicom.dataset.Dataset``, privacy flag, optional callbacks.

**Outputs:** User-visible modeless window.

**Requirements:** PySide6, pydicom, openpyxl (for ``.xlsx``).

See ``dev-docs/plans/supporting/SR_FULL_FIDELITY_BROWSER_PLAN.md``.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Callable, Optional

from PySide6.QtCore import QAbstractItemModel, QModelIndex, Qt, QPersistentModelIndex
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextBrowser,
    QTreeView,
    QVBoxLayout,
    QWidget,
)
from pydicom.dataset import Dataset

from core.rdsr_dose_sr import (
    CtRadiationDoseSummary,
    RadiationDoseSrParseError,
    apply_privacy_to_ct_radiation_dose_summary,
    is_radiation_dose_sr,
    parse_ct_radiation_dose_summary,
)
from core.rdsr_irradiation_events import IrradiationEventRow, attach_tree_node_ids, extract_irradiation_events
from core.sr_document_tree import SrContentNode, SrDocumentTree, build_sr_document_tree, path_to_node_id_map, sr_tree_to_json_dict
from core.sr_sop_classes import structured_report_storage_label


def _mask_uid(s: str) -> str:
    t = str(s).strip()
    if len(t) <= 20:
        return "***"
    return f"{t[:6]}…{t[-4:]}"


def _privacy_cell(text: str, value_type: str, privacy: bool) -> str:
    if not privacy:
        return text
    vt = (value_type or "").strip().upper()
    if vt in ("TEXT", "PNAME"):
        return "[Redacted]" if text else ""
    if vt in ("UIDREF", "IMAGE", "COMPOSITE", "WAVEFORM"):
        if "Study=" in text or "Series=" in text or "SOP=" in text or "UID" in text:
            parts = []
            for segment in text.split(";"):
                segment = segment.strip()
                if "=" in segment:
                    k, v = segment.split("=", 1)
                    parts.append(f"{k}={_mask_uid(v)}")
                else:
                    parts.append(_mask_uid(segment))
            return "; ".join(parts)
    return text


class SrTreeModel(QAbstractItemModel):
    """Lazy-friendly tree model over pre-built :class:`SrContentNode` roots."""

    COL_CONCEPT = 0
    COL_REL = 1
    COL_VT = 2
    COL_VAL = 3
    COL_REF = 4
    HEADERS = ("Concept", "Relationship", "Value type", "Value", "Reference")

    def __init__(self, tree: SrDocumentTree, *, privacy_mode: bool = False) -> None:
        super().__init__()
        self._tree = tree
        self._privacy = privacy_mode

    def set_privacy_mode(self, enabled: bool) -> None:
        self._privacy = enabled
        self.beginResetModel()
        self.endResetModel()

    def index_from_node(self, node: SrContentNode) -> QModelIndex:
        if node.parent is None:
            try:
                row = self._tree.roots.index(node)
            except ValueError:
                return QModelIndex()
            return self.index(row, 0, QModelIndex())
        prow = node.parent.children.index(node)
        return self.index(prow, 0, self.index_from_node(node.parent))

    def expand_path_to_node(self, tree_view: QTreeView, node: SrContentNode) -> None:
        idx = self.index_from_node(node)
        if not idx.isValid():
            return
        anc: list[QModelIndex] = []
        walk = idx
        while walk.isValid():
            anc.append(walk)
            walk = walk.parent()
        for a in reversed(anc):
            tree_view.setExpanded(a, True)
        tree_view.setCurrentIndex(idx)
        tree_view.scrollTo(idx, QAbstractItemView.ScrollHint.PositionAtCenter)

    def columnCount(self, parent: QModelIndex | QPersistentModelIndex = QModelIndex()) -> int:  # type: ignore[override]
        return 5

    def rowCount(self, parent: QModelIndex | QPersistentModelIndex = QModelIndex()) -> int:  # type: ignore[override]
        if not parent.isValid():
            return len(self._tree.roots)
        node = parent.internalPointer()
        if isinstance(node, SrContentNode):
            return len(node.children)
        return 0

    def index(self, row: int, column: int, parent: QModelIndex | QPersistentModelIndex = QModelIndex()) -> QModelIndex:  # type: ignore[override]
        if column < 0 or column >= 5:
            return QModelIndex()
        if not parent.isValid():
            if row < 0 or row >= len(self._tree.roots):
                return QModelIndex()
            node = self._tree.roots[row]
            return self.createIndex(row, column, node)
        pnode = parent.internalPointer()
        if not isinstance(pnode, SrContentNode):
            return QModelIndex()
        if row < 0 or row >= len(pnode.children):
            return QModelIndex()
        ch = pnode.children[row]
        return self.createIndex(row, column, ch)

    def parent(self, index: QModelIndex | QPersistentModelIndex) -> QModelIndex:  # type: ignore[override]
        if not index.isValid():
            return QModelIndex()
        node = index.internalPointer()
        if not isinstance(node, SrContentNode):
            return QModelIndex()
        par = node.parent
        if par is None:
            return QModelIndex()
        if par.parent is None:
            try:
                row = self._tree.roots.index(par)
            except ValueError:
                return QModelIndex()
            return self.createIndex(row, 0, par)
        try:
            row = par.parent.children.index(par)
        except ValueError:
            return QModelIndex()
        return self.createIndex(row, 0, par)

    def data(self, index: QModelIndex | QPersistentModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:  # type: ignore[override]
        if not index.isValid():
            return None
        node = index.internalPointer()
        if not isinstance(node, SrContentNode):
            return None
        col = index.column()
        if role == Qt.ItemDataRole.DisplayRole:
            if col == self.COL_CONCEPT:
                return node.concept_label
            if col == self.COL_REL:
                return node.relationship
            if col == self.COL_VT:
                return node.value_type
            if col == self.COL_VAL:
                return _privacy_cell(node.value_text, node.value_type, self._privacy)
            if col == self.COL_REF:
                return _privacy_cell(node.reference_text, node.value_type, self._privacy)
        return None

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole) -> Any:  # type: ignore[override]
        if role == Qt.ItemDataRole.DisplayRole and orientation == Qt.Orientation.Horizontal:
            if 0 <= section < len(self.HEADERS):
                return self.HEADERS[section]
        return None

    def flags(self, index: QModelIndex | QPersistentModelIndex) -> Qt.ItemFlag:  # type: ignore[override]
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags
        return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable


class StructuredReportBrowserDialog(QDialog):
    """Modeless SR browser: document tree, dose events, optional CT summary, exports."""

    def __init__(
        self,
        parent: QWidget | None,
        dataset: Dataset,
        *,
        get_privacy_enabled: Callable[[], bool],
        main_window: QWidget | None = None,
        open_tag_viewer_callback: Optional[Callable[[Dataset], None]] = None,
    ) -> None:
        super().__init__(parent)
        self._ds = dataset
        self._get_privacy_enabled = get_privacy_enabled
        self._open_tag_viewer_callback = open_tag_viewer_callback
        self._main_window = main_window

        sop = str(getattr(dataset, "SOPClassUID", "") or "")
        label = structured_report_storage_label(sop)
        sdesc = str(getattr(dataset, "SeriesDescription", "") or "").strip() or "SR"
        self.setWindowTitle(f"Structured Report — {label} — {sdesc[:80]}")
        self.setModal(False)
        self.resize(980, 640)

        self._tree_data: SrDocumentTree = build_sr_document_tree(dataset)
        self._model = SrTreeModel(self._tree_data, privacy_mode=self._effective_privacy())
        self._events = extract_irradiation_events(dataset)
        attach_tree_node_ids(self._events, path_to_node_id_map(self._tree_data))

        self._dose_summary: CtRadiationDoseSummary | None = None
        self._dose_summary_error: str | None = None
        if is_radiation_dose_sr(dataset):
            try:
                self._dose_summary = parse_ct_radiation_dose_summary(dataset)
            except RadiationDoseSrParseError as e:
                self._dose_summary_error = str(e)

        layout = QVBoxLayout(self)
        hint = QLabel(
            "Document tab: full SR ContentSequence tree. Dose events tab: rows interpreted per "
            "PS3.16 (113706 X-ray / 113819 CT irradiation event containers). Export respects the "
            "active tab where applicable."
        )
        hint.setWordWrap(True)
        layout.addWidget(hint)

        warn_parts = list(self._tree_data.warnings) + list(self._events.notes)
        if warn_parts:
            wlab = QLabel("\n".join(warn_parts))
            wlab.setWordWrap(True)
            wlab.setStyleSheet("color: #a60;")
            layout.addWidget(wlab)

        self._tabs = QTabWidget(self)
        layout.addWidget(self._tabs)

        doc = QWidget()
        dv = QVBoxLayout(doc)
        split = QSplitter(Qt.Orientation.Horizontal)
        self._tree_view = QTreeView()
        self._tree_view.setModel(self._model)
        self._tree_view.setAlternatingRowColors(True)
        self._tree_view.setUniformRowHeights(True)
        for c in range(5):
            self._tree_view.resizeColumnToContents(c)
        split.addWidget(self._tree_view)
        self._detail = QTextBrowser()
        self._detail.setPlaceholderText("Select a tree row for raw detail.")
        split.addWidget(self._detail)
        split.setStretchFactor(0, 3)
        split.setStretchFactor(1, 2)
        dv.addWidget(split)
        export_doc = QHBoxLayout()
        self._btn_json_tree = QPushButton("Export document tree JSON…")
        self._btn_json_tree.clicked.connect(self._export_tree_json)
        export_doc.addWidget(self._btn_json_tree)
        export_doc.addStretch()
        dv.addLayout(export_doc)
        self._tabs.addTab(doc, "Document")

        dose_w = QWidget()
        dl = QVBoxLayout(dose_w)
        dl.addWidget(
            QLabel(
                "Irradiation events (template-derived columns). Selecting a row highlights the "
                "matching CONTAINER in the Document tab."
            )
        )
        self._event_table = QTableWidget(0, 0)
        self._event_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._event_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._event_table.itemSelectionChanged.connect(self._on_event_row_selected)
        self._populate_event_table()
        dl.addWidget(self._event_table)
        export_ev = QHBoxLayout()
        self._btn_csv_events = QPushButton("Export dose events CSV…")
        self._btn_xlsx_events = QPushButton("Export dose events XLSX…")
        self._btn_csv_events.clicked.connect(lambda: self._export_events_csv_xlsx(xlsx=False))
        self._btn_xlsx_events.clicked.connect(lambda: self._export_events_csv_xlsx(xlsx=True))
        export_ev.addWidget(self._btn_csv_events)
        export_ev.addWidget(self._btn_xlsx_events)
        export_ev.addStretch()
        dl.addLayout(export_ev)
        self._tabs.addTab(dose_w, "Dose events")

        sum_w = QWidget()
        sl = QVBoxLayout(sum_w)
        if self._dose_summary is not None:
            self._summary_table = QTableWidget(0, 2)
            self._summary_table.setHorizontalHeaderLabels(["Field", "Value"])
            self._summary_table.horizontalHeader().setStretchLastSection(True)
            self._populate_summary_table()
            sl.addWidget(self._summary_table)
        else:
            msg = self._dose_summary_error or "Not a dose SR or summary unavailable."
            sl.addWidget(QLabel(msg))
        self._tabs.addTab(sum_w, "Dose summary")

        raw = QWidget()
        rl = QVBoxLayout(raw)
        rl.addWidget(
            QLabel("Open the full DICOM Tag Viewer for search, private tags, and optional editing.")
        )
        btn_tags = QPushButton("Open DICOM Tag Viewer…")
        btn_tags.clicked.connect(self._open_tag_viewer)
        rl.addWidget(btn_tags)
        rl.addStretch()
        self._tabs.addTab(raw, "Raw tags")

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.close)
        buttons.accepted.connect(self.close)
        layout.addWidget(buttons)

        self._tree_view.selectionModel().selectionChanged.connect(self._on_tree_selection)

        if main_window is not None and hasattr(main_window, "privacy_view_toggled"):
            main_window.privacy_view_toggled.connect(self._on_privacy_toggled)  # type: ignore[attr-defined]

    def _effective_privacy(self) -> bool:
        try:
            return bool(self._get_privacy_enabled())
        except Exception:
            return False

    def _on_privacy_toggled(self, _enabled: bool) -> None:
        self._model.set_privacy_mode(self._effective_privacy())
        self._populate_summary_table()

    def _populate_summary_table(self) -> None:
        if self._dose_summary is None or not hasattr(self, "_summary_table"):
            return
        s = self._dose_summary
        if self._effective_privacy():
            s = apply_privacy_to_ct_radiation_dose_summary(s)

        def fmt(v: Any) -> str:
            if v is None:
                return ""
            if isinstance(v, float):
                return f"{v:.6g}"
            if isinstance(v, bool):
                return "Yes" if v else "No"
            return str(v)

        rows = [
            ("Study Instance UID", fmt(s.study_instance_uid)),
            ("Series Instance UID", fmt(s.series_instance_uid)),
            ("SOP Instance UID", fmt(s.sop_instance_uid)),
            ("Manufacturer", fmt(s.manufacturer)),
            ("Manufacturer Model Name", fmt(s.manufacturer_model_name)),
            ("Device Serial Number", fmt(s.device_serial_number)),
            ("CTDIvol (mGy)", fmt(s.ctdi_vol_mgy)),
            ("DLP (mGy·cm)", fmt(s.dlp_mgy_cm)),
            ("SSDE (mGy)", fmt(s.ssde_mgy)),
            ("Irradiation events (113819)", fmt(s.irradiation_event_count)),
            ("Parse hit node cap", fmt(s.parse_node_cap_hit)),
        ]
        self._summary_table.setRowCount(len(rows))
        for r, (a, b) in enumerate(rows):
            self._summary_table.setItem(r, 0, QTableWidgetItem(a))
            it = QTableWidgetItem(b)
            it.setFlags(it.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self._summary_table.setItem(r, 1, it)

    def _populate_event_table(self) -> None:
        rows = self._events.rows
        headers: list[str] = []
        for r in rows:
            for k in r.columns:
                if k not in headers:
                    headers.append(k)
        self._event_table.setColumnCount(len(headers))
        self._event_table.setHorizontalHeaderLabels(headers)
        self._event_table.setRowCount(len(rows))
        for ri, er in enumerate(rows):
            for ci, h in enumerate(headers):
                val = er.columns.get(h, "")
                it = QTableWidgetItem(val)
                it.setFlags(it.flags() & ~Qt.ItemFlag.ItemIsEditable)
                it.setData(Qt.ItemDataRole.UserRole, er.node_id_placeholder)
                self._event_table.setItem(ri, ci, it)

    def _on_tree_selection(self, *_args: Any) -> None:
        idx = self._tree_view.currentIndex()
        if not idx.isValid():
            return
        node = idx.internalPointer()
        if not isinstance(node, SrContentNode):
            return
        lines = [
            f"<b>Concept</b>: {node.concept_label}",
            f"<b>Relationship</b>: {node.relationship}",
            f"<b>Value type</b>: {node.value_type}",
            f"<b>Value</b>: {_privacy_cell(node.value_text, node.value_type, self._effective_privacy())}",
            f"<b>Reference</b>: {_privacy_cell(node.reference_text, node.value_type, self._effective_privacy())}",
            f"<b>node_id</b>: {node.node_id} &nbsp; <b>path</b>: {node.path_indices}",
        ]
        self._detail.setHtml("<br/>".join(lines))

    def _on_event_row_selected(self) -> None:
        items = self._event_table.selectedItems()
        if not items:
            return
        nid = items[0].data(Qt.ItemDataRole.UserRole)
        if nid is None:
            return
        node = self._tree_data.node_by_id.get(int(nid))
        if node is None:
            return
        self._tabs.setCurrentIndex(0)
        self._model.expand_path_to_node(self._tree_view, node)

    def _export_tree_json(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export SR document tree as JSON",
            str(Path.home() / "sr_document_tree.json"),
            "JSON (*.json)",
        )
        if not path:
            return
        try:
            payload = sr_tree_to_json_dict(self._tree_data)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2)
        except OSError as e:
            QMessageBox.warning(self, "Export", f"Could not write file:\n{e}")
            return
        QMessageBox.information(self, "Export", f"Wrote:\n{path}")

    def _export_events_csv_xlsx(self, *, xlsx: bool) -> None:
        rows = self._events.rows
        if not rows:
            QMessageBox.information(self, "Export", "No dose event rows to export.")
            return
        headers: list[str] = []
        for r in rows:
            for k in r.columns:
                if k not in headers:
                    headers.append(k)
        ext = "xlsx" if xlsx else "csv"
        path, _ = QFileDialog.getSaveFileName(
            self,
            f"Export dose events as {ext.upper()}",
            str(Path.home() / f"sr_irradiation_events.{ext}"),
            f"{ext.upper()} (*.{ext})",
        )
        if not path:
            return
        try:
            if xlsx:
                self._write_events_xlsx(path, headers, rows)
            else:
                self._write_events_csv(path, headers, rows)
        except OSError as e:
            QMessageBox.warning(self, "Export", f"Could not write file:\n{e}")
            return
        QMessageBox.information(self, "Export", f"Wrote:\n{path}")

    def _write_events_csv(self, path: str, headers: list[str], rows: list[IrradiationEventRow]) -> None:
        with open(path, "w", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            w.writerow(headers)
            for er in rows:
                w.writerow([er.columns.get(h, "") for h in headers])

    def _write_events_xlsx(self, path: str, headers: list[str], rows: list[IrradiationEventRow]) -> None:
        from openpyxl import Workbook

        wb = Workbook()
        ws = wb.active
        assert ws is not None
        ws.title = "Irradiation events"
        ws.append(headers)
        for er in rows:
            ws.append([er.columns.get(h, "") for h in headers])
        wb.save(path)

    def _open_tag_viewer(self) -> None:
        if self._open_tag_viewer_callback is not None:
            self._open_tag_viewer_callback(self._ds)
