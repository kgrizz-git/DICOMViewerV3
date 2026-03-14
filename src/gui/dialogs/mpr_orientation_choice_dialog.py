"""
MPR Orientation Choice Dialog

Shown when the user builds MPR from a series that contains slices in more than
one orientation. Lets the user pick which orientation group to use and shows
how many images are in each group.

Inputs:
    groups: List of (orientation_label, list_of_datasets) from
            mpr_volume.get_orientation_groups(datasets).
    parent: Optional QWidget parent.

Outputs:
    After exec(): get_selected_datasets() returns the selected group's datasets
    if the user clicked OK, or None if cancelled.

Requirements:
    PySide6
"""

from __future__ import annotations

from typing import List, Optional, Tuple

from pydicom.dataset import Dataset
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QLabel,
    QVBoxLayout,
    QWidget,
)


class MprOrientationChoiceDialog(QDialog):
    """
    Dialog to choose one orientation group when a series has mixed orientations.

    Displays each group as "&lt;label&gt; — &lt;N&gt; images" in a combo box.
    """

    def __init__(
        self,
        groups: List[Tuple[str, List[Dataset]]],
        parent: Optional[QWidget] = None,
    ) -> None:
        """
        Args:
            groups: List of (orientation_label, list_of_datasets). Must have
                    at least two entries (caller should only open dialog when
                    there are multiple orientations).
            parent: Parent widget.
        """
        super().__init__(parent)
        self.setWindowTitle("Choose Orientation for MPR")
        self.setWindowFlags(
            self.windowFlags() | Qt.WindowType.WindowStaysOnTopHint
        )
        self._groups = list(groups)
        self._combo: Optional[QComboBox] = None
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(12, 12, 12, 12)

        label = QLabel(
            "This series has slices in multiple orientations. "
            "Choose which orientation to use for MPR:"
        )
        label.setWordWrap(True)
        layout.addWidget(label)

        self._combo = QComboBox()
        for orient_label, ds_list in self._groups:
            n = len(ds_list)
            self._combo.addItem(f"{orient_label} — {n} image{'s' if n != 1 else ''}", ds_list)
        self._combo.setCurrentIndex(0)
        layout.addWidget(self._combo)

        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def get_selected_datasets(self) -> Optional[List[Dataset]]:
        """
        Return the list of datasets for the selected orientation group.

        Call after exec(). Returns None if the dialog was rejected or if
        there is no selection (should not happen if groups are non-empty).
        """
        if self._combo is None or self.result() != QDialog.DialogCode.Accepted:
            return None
        data = self._combo.currentData()
        if data is None:
            idx = self._combo.currentIndex()
            if 0 <= idx < len(self._groups):
                return self._groups[idx][1]
            return None
        return data if isinstance(data, list) else None
