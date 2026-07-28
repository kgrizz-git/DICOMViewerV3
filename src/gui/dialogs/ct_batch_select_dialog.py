"""
Batch ACR CT (pylinac) series-selection dialog.

Checkbox list of loaded CT series plus an "Add folder..." affordance,
per PYLINAC_CT_CNR_BATCH_XLSX_PLAN.md Feature 2. Returns parallel
``(requests, labels)`` lists consumed by ``QAAppFacade.open_acr_ct_batch_analysis``
/ ``QACTBatchWorker``.

Inputs:
    - ``DICOMOrganizer`` (in-memory ``studies`` dict) for series discovery.
    - A ``get_file_path_for_dataset`` callable (bound to the app's
      ``FileSeriesLoadingCoordinator``) to resolve ordered on-disk paths.
    - An ``open_folder`` callable (typically ``app.file_dialog.open_folder``)
      for the "Add folder..." affordance.

Outputs:
    - ``(list[QARequest], list[str])`` parallel lists, or ``None`` if
      cancelled / nothing selected.

Requirements:
    - PySide6; ``qa.analysis_types.QARequest``; no pylinac import.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from typing import Any

from pydicom.dataset import Dataset
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from qa.analysis_types import QARequest

# Sentinel stored in Qt.ItemDataRole.UserRole to distinguish folder-picker rows
# (payload: folder path) from organizer-backed series rows (payload:
# (study_uid, series_key)).
_ROLE_FOLDER = "folder"
_ROLE_SERIES = "series"


def _series_label(ds: Dataset, series_key: str) -> str:
    """
    ``str(SeriesDescription) + " #" + str(SeriesNumber)``, guarded; falls back
    to the composite series key when both tags are empty (see plan Feature 2
    step 1).
    """
    desc = str(getattr(ds, "SeriesDescription", "") or "").strip()
    number = getattr(ds, "SeriesNumber", "")
    number_text = str(number).strip() if number not in (None, "") else ""
    if desc and number_text:
        return f"{desc} #{number_text}"
    if desc:
        return desc
    if number_text:
        return f"Series #{number_text}"
    return series_key


def build_ct_series_entries(organizer: Any) -> list[tuple[str, str, str]]:
    """
    Enumerate CT series from the organizer for the selection list.

    Filters ``organizer.get_series_list()`` to series whose first dataset has
    ``Modality == "CT"``. Reading ``Modality`` / ``SeriesDescription`` /
    ``SeriesNumber`` off the already-loaded in-memory pydicom dataset is
    attribute access only (no file I/O, no pixel load), so this is cheap even
    for many series (plan Feature 2, review r3 item 9).

    Returns:
        List of ``(study_uid, series_key, label)`` tuples, in organizer order.
    """
    entries: list[tuple[str, str, str]] = []
    for study_uid, series_key in organizer.get_series_list():
        datasets = organizer.studies.get(study_uid, {}).get(series_key, [])
        if not datasets:
            continue
        ds = datasets[0]
        modality = str(getattr(ds, "Modality", "") or "")
        if modality.upper() != "CT":
            continue
        entries.append((study_uid, series_key, _series_label(ds, series_key)))
    return entries


def prompt_batch_series_selection(
    parent: QWidget | None,
    organizer: Any,
    get_file_path_for_dataset: Callable[[Dataset, str, str, int], str | None],
    *,
    open_folder: Callable[[], str | None] | None = None,
) -> tuple[list[QARequest], list[str]] | None:
    """
    Show the batch series-selection dialog.

    Args:
        parent: Owning window.
        organizer: ``DICOMOrganizer`` (or compatible: ``get_series_list()`` +
            ``studies`` dict of dataset lists).
        get_file_path_for_dataset: Resolves an on-disk path for one dataset
            (mirrors ``resolve_focused_series_ordered_paths``); called once
            per slice of each checked series.
        open_folder: Invoked when "Add folder..." is clicked; returns a
            folder path or ``None``/empty if cancelled. When omitted, the
            "Add folder..." button is not shown.

    Returns:
        ``(requests, labels)`` parallel lists (one ``QARequest`` +
        display label per checked entry, series entries first in organizer
        order followed by added folders in click order), or ``None`` if the
        dialog was cancelled or nothing was checked.
    """
    entries = build_ct_series_entries(organizer)

    dialog = QDialog(parent)
    dialog.setWindowTitle("ACR CT Batch Analysis — Select Series")
    dialog.setWindowFlags(dialog.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
    dialog.setMinimumWidth(480)

    layout = QVBoxLayout(dialog)
    layout.addWidget(
        QLabel(
            "Check the CT series to include in this batch run. "
            "One ACR CT options set applies to every series."
        )
    )

    list_widget = QListWidget()
    list_widget.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
    layout.addWidget(list_widget)

    def _add_series_item(study_uid: str, series_key: str, label: str) -> None:
        item = QListWidgetItem(label)
        item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
        item.setCheckState(Qt.CheckState.Unchecked)
        item.setData(Qt.ItemDataRole.UserRole, (_ROLE_SERIES, study_uid, series_key))
        list_widget.addItem(item)

    def _add_folder_item(folder_path: str) -> None:
        label = f"[Folder] {os.path.basename(folder_path.rstrip(os.sep)) or folder_path}"
        item = QListWidgetItem(label)
        item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
        item.setCheckState(Qt.CheckState.Checked)
        item.setData(Qt.ItemDataRole.UserRole, (_ROLE_FOLDER, folder_path))
        list_widget.addItem(item)

    for study_uid, series_key, label in entries:
        _add_series_item(study_uid, series_key, label)

    if not entries:
        layout.addWidget(QLabel("No loaded CT series were found."))

    btn_row = QHBoxLayout()
    if open_folder is not None:
        add_folder_btn = QPushButton("Add folder…")

        def _on_add_folder() -> None:
            picked = open_folder()
            if picked:
                _add_folder_item(picked)

        add_folder_btn.clicked.connect(_on_add_folder)
        btn_row.addWidget(add_folder_btn)
    btn_row.addStretch()
    layout.addLayout(btn_row)

    buttons = QDialogButtonBox(
        QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
    )
    buttons.accepted.connect(dialog.accept)
    buttons.rejected.connect(dialog.reject)
    layout.addWidget(buttons)

    dialog.activateWindow()
    dialog.raise_()
    if dialog.exec() != int(QDialog.DialogCode.Accepted):
        return None

    requests: list[QARequest] = []
    labels: list[str] = []
    for row in range(list_widget.count()):
        item = list_widget.item(row)
        if item.checkState() != Qt.CheckState.Checked:
            continue
        payload = item.data(Qt.ItemDataRole.UserRole)
        if not payload:
            continue
        if payload[0] == _ROLE_FOLDER:
            _, folder_path = payload
            requests.append(
                QARequest(
                    analysis_type="acr_ct",
                    folder_path=folder_path,
                    modality="CT",
                )
            )
            labels.append(item.text())
            continue
        _, study_uid, series_key = payload
        datasets = organizer.studies.get(study_uid, {}).get(series_key, [])
        ordered_paths: list[str] = []
        for slice_index, ds in enumerate(datasets):
            path = get_file_path_for_dataset(ds, study_uid, series_key, slice_index)
            if path:
                ordered_paths.append(path)
        if not ordered_paths:
            continue
        requests.append(
            QARequest(
                analysis_type="acr_ct",
                dicom_paths=ordered_paths,
                study_uid=study_uid,
                series_uid=series_key,
                modality="CT",
            )
        )
        labels.append(item.text())

    if not requests:
        QMessageBox.information(
            parent,
            "ACR CT Batch Analysis",
            "No series were selected (or resolvable to files).",
        )
        return None

    return requests, labels
