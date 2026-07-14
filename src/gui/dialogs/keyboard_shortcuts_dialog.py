"""
Keyboard Shortcuts Dialog

Displays a grouped, scrollable reference of all keyboard shortcuts available
in the DICOM viewer. Read-only; no editable fields.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

# ---------------------------------------------------------------------------
# Shortcut data
# ---------------------------------------------------------------------------

_SECTIONS: list[tuple[str, list[tuple[str, str]]]] = [
    (
        "File",
        [
            ("Open File(s)…", "Ctrl+O"),
            ("Open Folder…", "Ctrl+Shift+O"),
            ("Export…", "Ctrl+E"),
            ("Close All", "Ctrl+W"),
            ("Quit", "Ctrl+Q / Alt+F4"),
        ],
    ),
    (
        "Edit",
        [
            ("Undo", "Ctrl+Z"),
            ("Redo", "Ctrl+Y / Ctrl+Shift+Z"),
            ("Copy Annotation", "Ctrl+C"),
            ("Cut Annotation", "Ctrl+X"),
            ("Paste Annotation", "Ctrl+V"),
        ],
    ),
    (
        "Tools — Mouse Modes",
        [
            ("Pan / Scroll", "P"),
            ("Select", "S"),
            ("Ellipse ROI", "E"),
            ("Rectangle ROI", "R"),
            ("Measure Distance", "M"),
            ("Measure Angle", "Shift+M"),
            ("Text Annotation", "T"),
            ("Arrow Annotation", "A"),
            ("Crosshair", "H"),
            ("Zoom", "Z"),
            ("Magnifier", "G"),
            ("Window/Level from ROI", "W"),
            ("Quick Window/Level", "Q"),
        ],
    ),
    (
        "Annotations — Clear & Delete",
        [
            ("Clear Measurements", "C"),
            ("Delete All ROIs (current slice)", "D"),
            ("Delete Selected Item", "Delete"),
        ],
    ),
    (
        "View & Display",
        [
            ("Reset View (focused pane)", "V  or  Shift+V"),
            ("Reset All Views", "Shift+A"),
            ("Fullscreen", "F11  or  Ctrl+F"),
            ("Privacy View", "Ctrl+P"),
            ("Invert Image", "I"),
            ("Cycle Overlay Detail (all panes)", "Space"),
            ("Legacy Overlay Cycle (focused pane)", "Shift+Space"),
            ("Overlay Tags Config", "Ctrl+Shift+L"),
            ("DICOM File Info", "Ctrl+I"),
            ("Histogram", "Ctrl+Shift+H"),
            ("Flip Horizontal", "Alt+H"),
            ("Flip Vertical", "Alt+V"),
            ("Rotate 90° CW", "Alt+R"),
            ("Rotate 90° CCW", "Shift+Alt+R"),
            ("Reset Orientation", "Shift+Alt+O"),
            ("Toggle Series Navigator", "N"),
        ],
    ),
    (
        "Navigation & Layout",
        [
            ("Next / Previous Slice", "↑ / ↓  (or wheel)"),
            ("Cine Play / Pause", "Ctrl+Space"),
            ("Layout 1×1", "1"),
            ("Toggle 1×2 ↔ 2×1", "2"),
            ("Cycle 3-Pane (asymmetric)", "3"),
            ("Layout 2×2", "4"),
        ],
    ),
    (
        "DICOM Tags",
        [
            ("View/Edit Tags", "Ctrl+T"),
            ("Export Tags", "Ctrl+Shift+T"),
        ],
    ),
]


# ---------------------------------------------------------------------------
# Dialog
# ---------------------------------------------------------------------------

class KeyboardShortcutsDialog(QDialog):
    """
    Non-modal dialog showing all keyboard shortcuts grouped by category.

    Opens as a modal dialog (exec()) from the Help menu or via F1.
    Fixed size ~580×600 px; content scrollable.
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Keyboard Shortcuts")
        self.setFixedSize(580, 600)
        self.setWindowFlags(
            self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint
        )

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(8, 8, 8, 8)
        outer_layout.setSpacing(6)

        # Scrollable content area
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(4, 4, 4, 4)
        content_layout.setSpacing(8)

        for section_title, entries in _SECTIONS:
            group = QGroupBox(section_title)
            form = QFormLayout(group)
            form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
            form.setFormAlignment(
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop
            )
            form.setHorizontalSpacing(24)
            form.setVerticalSpacing(4)
            for action_name, shortcut in entries:
                action_label = QLabel(action_name)
                shortcut_label = QLabel(shortcut)
                shortcut_label.setTextInteractionFlags(
                    Qt.TextInteractionFlag.TextSelectableByMouse
                )
                form.addRow(action_label, shortcut_label)
            content_layout.addWidget(group)

        content_layout.addStretch()
        scroll.setWidget(content_widget)
        outer_layout.addWidget(scroll)

        # Close button
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        button_box.rejected.connect(self.accept)
        outer_layout.addWidget(button_box)
