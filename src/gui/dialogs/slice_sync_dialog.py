"""
Slice Sync Groups Dialog

Lets the user manage linked groups for anatomic slice synchronisation.

A linked group is a set of subwindow indices (0–3) that are synced together.
When one window in a group advances to a new slice, every other window in the
group is updated to the anatomically nearest slice.

Inputs:
    - Current group assignments (from ConfigManager / SliceSyncCoordinator).
    - Number of subwindow slots available (typically 4 for a 2x2 layout).

Outputs:
    - Updated group assignments emitted via ``groups_changed`` signal.

Requirements:
    - PySide6
    - No DICOM or coordinator imports; pure UI.
"""

from typing import List

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


# Labels shown for each subwindow slot in the UI.
_WINDOW_LABELS = ["Window 1 (top-left)", "Window 2 (top-right)",
                  "Window 3 (bottom-left)", "Window 4 (bottom-right)"]


class SliceSyncDialog(QDialog):
    """
    Dialog for managing slice-sync linked groups.

    Signals:
        groups_changed (List[List[int]]): Emitted on Apply / OK with the
            new group assignments.
    """

    groups_changed = Signal(list)  # List[List[int]]

    def __init__(self, current_groups: List[List[int]], parent=None, n_windows: int = 4):
        """
        Args:
            current_groups: Existing linked groups, e.g. [[0, 1], [2, 3]].
            parent:         Parent widget.
            n_windows:      Number of subwindow slots (default 4).
        """
        super().__init__(parent)
        self.setWindowTitle("Slice Sync — Manage Linked Groups")
        self.setMinimumWidth(420)
        self._n_windows = n_windows
        self._groups: List[List[int]] = [list(g) for g in current_groups]

        self._build_ui()
        self._refresh_group_list()

        # Bring to front.
        self.raise_()
        self.activateWindow()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setSpacing(10)
        root.setContentsMargins(12, 12, 12, 12)

        # Description label.
        desc = QLabel(
            "Windows in the same group will scroll to the anatomically "
            "nearest slice when any window in the group is navigated.\n"
            "A window can belong to at most one group."
        )
        desc.setWordWrap(True)
        root.addWidget(desc)

        # Existing groups list.
        groups_box = QGroupBox("Current groups")
        groups_layout = QVBoxLayout(groups_box)

        self._group_list = QListWidget()
        self._group_list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self._group_list.currentRowChanged.connect(self._on_group_selected)
        groups_layout.addWidget(self._group_list)

        btn_row = QHBoxLayout()
        self._dissolve_btn = QPushButton("Dissolve selected group")
        self._dissolve_btn.setEnabled(False)
        self._dissolve_btn.clicked.connect(self._dissolve_group)
        btn_row.addWidget(self._dissolve_btn)
        btn_row.addStretch()
        groups_layout.addLayout(btn_row)
        root.addWidget(groups_box)

        # Create new group.
        new_box = QGroupBox("Create new group")
        new_layout = QVBoxLayout(new_box)
        new_layout.addWidget(QLabel("Select two or more windows to link:"))

        self._checkboxes: List[QCheckBox] = []
        for i in range(self._n_windows):
            label = _WINDOW_LABELS[i] if i < len(_WINDOW_LABELS) else f"Window {i + 1}"
            cb = QCheckBox(label)
            new_layout.addWidget(cb)
            self._checkboxes.append(cb)

        create_btn = QPushButton("Create group from selection")
        create_btn.clicked.connect(self._create_group)
        new_layout.addWidget(create_btn)
        root.addWidget(new_box)

        # Dialog buttons.
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Apply |
            QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_ok)
        buttons.rejected.connect(self.reject)
        buttons.button(QDialogButtonBox.StandardButton.Apply).clicked.connect(self._on_apply)
        root.addWidget(buttons)

    # ------------------------------------------------------------------
    # Group list management
    # ------------------------------------------------------------------

    def _refresh_group_list(self) -> None:
        """Repopulate the group list widget from ``self._groups``."""
        self._group_list.clear()
        for i, group in enumerate(self._groups):
            labels = [
                (_WINDOW_LABELS[idx] if idx < len(_WINDOW_LABELS) else f"Window {idx + 1}")
                for idx in group
            ]
            text = f"Group {i + 1}: {', '.join(labels)}"
            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, i)
            self._group_list.addItem(item)

        has_groups = len(self._groups) > 0
        self._dissolve_btn.setEnabled(has_groups and self._group_list.currentRow() >= 0)

    def _on_group_selected(self, row: int) -> None:
        self._dissolve_btn.setEnabled(row >= 0)

    def _dissolve_group(self) -> None:
        row = self._group_list.currentRow()
        if 0 <= row < len(self._groups):
            self._groups.pop(row)
            self._refresh_group_list()

    def _create_group(self) -> None:
        """Collect checked windows, validate, and create a new group."""
        selected = [i for i, cb in enumerate(self._checkboxes) if cb.isChecked()]

        if len(selected) < 2:
            QMessageBox.warning(
                self,
                "Not enough windows",
                "Please select at least two windows to form a group.",
            )
            return

        # Check for conflicts with existing groups.
        all_grouped = {idx for group in self._groups for idx in group}
        conflicts = [idx for idx in selected if idx in all_grouped]
        if conflicts:
            labels = [
                _WINDOW_LABELS[idx] if idx < len(_WINDOW_LABELS) else f"Window {idx + 1}"
                for idx in conflicts
            ]
            reply = QMessageBox.question(
                self,
                "Conflict",
                f"{', '.join(labels)} {'is' if len(conflicts) == 1 else 'are'} already in a "
                f"group.\nRemove {'it' if len(conflicts) == 1 else 'them'} from the existing "
                f"group and create the new one?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
            # Remove conflicting indices from existing groups.
            self._groups = [
                [idx for idx in g if idx not in conflicts]
                for g in self._groups
            ]
            # Discard groups that now have fewer than 2 members.
            self._groups = [g for g in self._groups if len(g) >= 2]

        self._groups.append(selected)
        # Clear checkboxes.
        for cb in self._checkboxes:
            cb.setChecked(False)
        self._refresh_group_list()

    # ------------------------------------------------------------------
    # Dialog actions
    # ------------------------------------------------------------------

    def _on_apply(self) -> None:
        self.groups_changed.emit(list(self._groups))

    def _on_ok(self) -> None:
        self._on_apply()
        self.accept()

    # ------------------------------------------------------------------
    # Public accessors
    # ------------------------------------------------------------------

    def current_groups(self) -> List[List[int]]:
        """Return the groups as currently configured in this dialog."""
        return list(self._groups)
