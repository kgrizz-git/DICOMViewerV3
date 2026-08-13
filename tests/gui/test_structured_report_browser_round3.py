"""Synthetic Qt coverage for the structured report browser's remaining seams."""

from __future__ import annotations

import csv
import json

import pytest
from pydicom.dataset import Dataset
from PySide6.QtCore import QModelIndex, Qt
from PySide6.QtWidgets import QMessageBox

from core.rdsr_irradiation_events import IrradiationEventExtraction, IrradiationEventRow
from core.sr_document_tree import SrContentNode, SrDocumentTree
from gui.dialogs.structured_report_browser_dialog import (
    SrTreeModel,
    StructuredReportBrowserDialog,
)


def _synthetic_tree() -> SrDocumentTree:
    root = SrContentNode(
        node_id=10,
        depth=0,
        concept_label="Study context (CONCEPT, DCM)",
        relationship="CONTAINS",
        value_type="CONTAINER",
        value_text="",
        reference_text="",
        path_indices=(0,),
    )
    child = SrContentNode(
        node_id=11,
        depth=1,
        concept_label="Patient name",
        relationship="CONTAINS",
        value_type="TEXT",
        value_text="Synthetic Person",
        reference_text="",
        path_indices=(0, 0),
        parent=root,
    )
    uid = SrContentNode(
        node_id=12,
        depth=1,
        concept_label="Referenced study",
        relationship="SELECTED FROM",
        value_type="UIDREF",
        value_text="",
        reference_text="Study=1.2.840.10008.1.2.3.456789012345; SOP=1.2.3.456789012345678901",
        path_indices=(0, 1),
        parent=root,
    )
    root.children = [child, uid]
    return SrDocumentTree(
        roots=[root],
        warnings=[],
        truncated=False,
        total_nodes=3,
        node_by_id={10: root, 11: child, 12: uid},
    )


def _synthetic_events() -> IrradiationEventExtraction:
    return IrradiationEventExtraction(
        rows=[
            IrradiationEventRow(
                node_id_placeholder=11,
                path_indices=(0, 0),
                event_concept="Synthetic event",
                columns={"Dose": "2.5", "Empty column": ""},
            ),
            IrradiationEventRow(
                node_id_placeholder=12,
                path_indices=(0, 1),
                event_concept="Synthetic event",
                columns={"Dose": "3.0", "Empty column": ""},
            ),
        ],
        notes=[],
    )


@pytest.fixture
def synthetic_browser(monkeypatch):
    tree = _synthetic_tree()
    events = _synthetic_events()
    monkeypatch.setattr(
        "gui.dialogs.structured_report_browser_dialog.build_sr_document_tree",
        lambda _dataset: tree,
    )
    monkeypatch.setattr(
        "gui.dialogs.structured_report_browser_dialog.extract_irradiation_events",
        lambda _dataset: events,
    )
    monkeypatch.setattr(
        "gui.dialogs.structured_report_browser_dialog.attach_tree_node_ids",
        lambda _events, _mapping: None,
    )
    dataset = Dataset()
    dataset.SOPClassUID = "1.2.3.4"
    dataset.SeriesDescription = "Synthetic SR"
    return dataset, tree, events


@pytest.mark.qt
def test_sr_tree_model_indices_privacy_data_parents_and_headers(qapp) -> None:
    tree = _synthetic_tree()
    model = SrTreeModel(tree)
    root = model.index(0, 0)
    child = model.index(0, model.COL_VAL, root)
    uid = model.index(1, model.COL_REF, root)

    assert model.columnCount() == 5
    assert model.rowCount() == 1
    assert model.rowCount(root) == 2
    assert model.data(child) == "Synthetic Person"
    assert model.data(uid) == "Study=1.2.840.10008.1.2.3.456789012345; SOP=1.2.3.456789012345678901"
    assert model.parent(child).internalPointer() is tree.roots[0]
    assert not model.index(-1, 0).isValid()
    assert not model.index(0, 5).isValid()
    assert [model.headerData(i, Qt.Orientation.Horizontal) for i in range(5)] == [
        "Concept",
        "Relationship",
        "Value type",
        "Value",
        "Reference",
    ]
    assert model.flags(child) & Qt.ItemFlag.ItemIsSelectable

    model.set_privacy_mode(True)
    assert model.data(child) == "[Redacted]"
    assert model.data(uid) == "Study=1.2.84…2345; SOP=1.2.3.…8901"
    assert model.data(QModelIndex()) is None


@pytest.mark.qt
def test_dialog_tabs_event_visibility_selection_privacy_and_tag_callback(
    qapp, synthetic_browser
) -> None:
    dataset, tree, _events = synthetic_browser
    privacy = {"enabled": False}
    opened: list[Dataset] = []
    dialog = StructuredReportBrowserDialog(
        None,
        dataset,
        get_privacy_enabled=lambda: privacy["enabled"],
        open_tag_viewer_callback=opened.append,
    )

    assert [dialog._tabs.tabText(i) for i in range(dialog._tabs.count())] == [
        "Document",
        "Dose events",
        "Dose summary",
        "Raw tags",
    ]
    assert dialog._event_table.rowCount() == 2
    assert dialog._event_table.columnCount() == 2
    assert dialog._event_table.isColumnHidden(1)
    dialog._hide_empty_event_columns.setChecked(False)
    assert not dialog._event_table.isColumnHidden(1)

    dialog._event_table.selectRow(0)
    assert dialog._tabs.currentIndex() == 0
    assert dialog._tree_view.currentIndex().internalPointer() is tree.node_by_id[11]
    dialog._tree_view.setCurrentIndex(dialog._model.index_from_node(tree.node_by_id[12]))
    assert "Referenced study" in dialog._detail.toHtml()

    privacy["enabled"] = True
    dialog._on_privacy_toggled(True)
    assert dialog._model._privacy is True
    child_index = dialog._model.index_from_node(tree.node_by_id[11])
    child_value = dialog._model.index(child_index.row(), dialog._model.COL_VAL, child_index.parent())
    assert dialog._model.data(child_value) == "[Redacted]"
    dialog._open_tag_viewer()
    assert opened == [dataset]
    dialog.close()


@pytest.mark.qt
def test_dialog_exports_json_csv_and_xlsx_to_selected_paths(
    qapp, synthetic_browser, monkeypatch, tmp_path
) -> None:
    dataset, _tree, _events = synthetic_browser
    dialog = StructuredReportBrowserDialog(None, dataset, get_privacy_enabled=lambda: False)
    messages: list[str] = []
    monkeypatch.setattr(
        QMessageBox,
        "information",
        lambda *_args: messages.append("ok") or QMessageBox.StandardButton.Ok,
    )

    json_path = tmp_path / "tree.json"
    monkeypatch.setattr(
        "gui.dialogs.structured_report_browser_dialog.QFileDialog.getSaveFileName",
        lambda *_args, **_kwargs: (str(json_path), "JSON (*.json)"),
    )
    dialog._export_tree_json()
    assert json.loads(json_path.read_text(encoding="utf-8"))["total_nodes"] == 3

    csv_path = tmp_path / "events.csv"
    monkeypatch.setattr(
        "gui.dialogs.structured_report_browser_dialog.QFileDialog.getSaveFileName",
        lambda *_args, **_kwargs: (str(csv_path), "CSV (*.csv)"),
    )
    dialog._export_events_csv_xlsx(xlsx=False)
    with csv_path.open(newline="", encoding="utf-8") as stream:
        rows = list(csv.reader(stream))
    assert rows == [["Dose", "Empty column"], ["2.5", ""], ["3.0", ""]]

    xlsx_path = tmp_path / "events.xlsx"
    monkeypatch.setattr(
        "gui.dialogs.structured_report_browser_dialog.QFileDialog.getSaveFileName",
        lambda *_args, **_kwargs: (str(xlsx_path), "XLSX (*.xlsx)"),
    )
    dialog._export_events_csv_xlsx(xlsx=True)
    from openpyxl import load_workbook

    sheet = load_workbook(xlsx_path, read_only=True).active
    assert sheet is not None
    assert list(sheet.values) == [("Dose", "Empty column"), ("2.5", None), ("3.0", None)]
    assert len(messages) == 3
    dialog.close()
