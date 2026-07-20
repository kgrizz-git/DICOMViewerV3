"""First-open prompt for automatic encrypted study-index persistence.

The prompt offers four choices — two that record a persistent preference
(**Always add** / **Never add**) and two one-time actions (**Add this one
time** / **Skip this one time**) that leave the preference unrecorded so the
prompt appears again on a later load. It also surfaces where the index is
stored and what it contains.
"""

from __future__ import annotations

from enum import Enum

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from gui.study_index_info import open_study_index_location, study_index_about_lines
from utils.config_manager import ConfigManager


class StudyIndexOpenChoice(Enum):
    """Outcome of the first-open study-index prompt."""

    ALWAYS = "always"
    NEVER = "never"
    ADD_ONCE = "add_once"
    SKIP_ONCE = "skip_once"


class StudyIndexFirstOpenDialog(QDialog):
    """Four-option prompt with inline "where is this saved" disclosure."""

    def __init__(self, config: ConfigManager, parent: QWidget | None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Local Study Index")
        self.choice: StudyIndexOpenChoice = StudyIndexOpenChoice.SKIP_ONCE
        self._config = config

        outer = QVBoxLayout(self)

        heading = QLabel("Add opened studies to the local index?")
        heading.setStyleSheet("font-weight: bold;")
        outer.addWidget(heading)

        prefix = (
            "This version now requires an explicit privacy choice for automatic indexing.\n\n"
            if config.is_study_index_auto_add_consent_migration()
            else ""
        )
        body = QLabel(
            prefix
            + "The local study index lets you search and re-open studies you have viewed. "
            "Automatic indexing is off unless you choose to enable it."
        )
        body.setWordWrap(True)
        outer.addWidget(body)

        outer.addWidget(self._build_info_panel(config))

        outer.addLayout(self._build_button_row())

    def _build_info_panel(self, config: ConfigManager) -> QFrame:
        panel = QFrame()
        panel.setFrameShape(QFrame.Shape.StyledPanel)
        info = QVBoxLayout(panel)
        for line in study_index_about_lines(config):
            label = QLabel(line)
            label.setWordWrap(True)
            label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            info.addWidget(label)
        open_row = QHBoxLayout()
        open_btn = QPushButton("Open location")
        open_btn.clicked.connect(self._on_open_location)
        open_row.addWidget(open_btn)
        open_row.addStretch()
        info.addLayout(open_row)
        return panel

    def _build_button_row(self) -> QHBoxLayout:
        row = QHBoxLayout()
        # "Add" choices on the left, "don't add" choices on the right.
        always = QPushButton("Always add")
        always.setDefault(True)
        always.clicked.connect(lambda: self._choose(StudyIndexOpenChoice.ALWAYS))
        add_once = QPushButton("Add this one time")
        add_once.clicked.connect(lambda: self._choose(StudyIndexOpenChoice.ADD_ONCE))
        skip_once = QPushButton("Skip this one time")
        skip_once.clicked.connect(lambda: self._choose(StudyIndexOpenChoice.SKIP_ONCE))
        never = QPushButton("Never add")
        never.clicked.connect(lambda: self._choose(StudyIndexOpenChoice.NEVER))
        row.addWidget(always)
        row.addWidget(add_once)
        row.addStretch()
        row.addWidget(skip_once)
        row.addWidget(never)
        return row

    def _choose(self, choice: StudyIndexOpenChoice) -> None:
        self.choice = choice
        self.accept()

    def _on_open_location(self) -> None:
        if not open_study_index_location(self._config):
            QMessageBox.information(
                self,
                "Local Study Index",
                "Could not open the index location.",
            )


def apply_first_open_choice(config: ConfigManager, choice: StudyIndexOpenChoice) -> None:
    """Persist the preference for ALWAYS/NEVER; leave one-time choices unrecorded."""
    if choice is StudyIndexOpenChoice.ALWAYS:
        config.set_study_index_auto_add_on_open(True)
    elif choice is StudyIndexOpenChoice.NEVER:
        config.set_study_index_auto_add_on_open(False)
    # ADD_ONCE / SKIP_ONCE deliberately do not record consent.


def prompt_study_index_first_open(
    config: ConfigManager,
    parent: QWidget | None,
) -> StudyIndexOpenChoice:
    """Show the first-open prompt, persist the choice, and return it."""
    dialog = StudyIndexFirstOpenDialog(config, parent)
    dialog.exec()
    apply_first_open_choice(config, dialog.choice)
    return dialog.choice
