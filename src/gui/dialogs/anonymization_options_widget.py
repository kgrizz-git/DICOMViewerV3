"""
Shared de-identification options UI.

Provides a reusable widget (preset dropdown + detailed PS3.15 toggles) and a thin
options-only dialog wrapping it. Used both by the inline Export dialog's
"Options..." button and by the full de-identification export dialog, so a single
conformant ``DeepAnonymizerOptions`` shape drives every anonymized export path.

Inputs:
    Optional initial DeepAnonymizerOptions.

Outputs:
    DeepAnonymizerOptions via ``get_options()``.

Requirements:
    PySide6, utils.deep_anonymizer
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QGroupBox,
    QLabel,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from utils.deep_anonymizer import ANONYMIZER_PRESETS, DeepAnonymizerOptions

_CUSTOM_LABEL = "Custom…"

BURNED_IN_PHI_WARNING = (
    "<b>Warning:</b> De-identification removes identifying metadata only. "
    "<b>Burned-in text</b> (patient names or other PHI embedded in pixel data) "
    "is <b>not</b> removed or detected."
)


class AnonymizationOptionsWidget(QWidget):
    """Preset dropdown + detailed PS3.15 de-identification toggles.

    Selecting a preset fills the toggles; editing any toggle switches the preset
    selector to "Custom…". ``get_options`` always reflects the live toggle state.
    """

    def __init__(
        self,
        options: DeepAnonymizerOptions | None = None,
        show_warning: bool = True,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._syncing = False
        self._build_ui(show_warning)
        self.set_options(options or DeepAnonymizerOptions.standard_share())

    def _build_ui(self, show_warning: bool) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        if show_warning:
            warning = QLabel(BURNED_IN_PHI_WARNING)
            warning.setWordWrap(True)
            warning.setStyleSheet(
                "QLabel { color: #b45309; padding: 6px; background: #fffbeb; }"
            )
            layout.addWidget(warning)

        preset_label = QLabel("Preset:")
        layout.addWidget(preset_label)
        self.preset_combo = QComboBox()
        for _key, label, _factory in ANONYMIZER_PRESETS:
            self.preset_combo.addItem(label)
        self.preset_combo.addItem(_CUSTOM_LABEL)
        self.preset_combo.currentIndexChanged.connect(self._on_preset_changed)
        layout.addWidget(self.preset_combo)

        options_group = QGroupBox("De-identification options (PS3.15 Basic Profile)")
        options_layout = QVBoxLayout()

        self.retain_institution_cb = QCheckBox(
            "Retain institution identity (declares 113112)"
        )
        options_layout.addWidget(self.retain_institution_cb)

        self.retain_device_cb = QCheckBox(
            "Retain device identity — station / serial / manufacturer (declares 113109)"
        )
        options_layout.addWidget(self.retain_device_cb)

        self.strip_operators_cb = QCheckBox("Strip operator and physician names")
        options_layout.addWidget(self.strip_operators_cb)

        self.uid_remap_cb = QCheckBox(
            "Re-mint UIDs (consistent within this export; off declares 113110)"
        )
        options_layout.addWidget(self.uid_remap_cb)

        options_layout.addWidget(QLabel("Dates:"))
        self.date_button_group = QButtonGroup(self)
        self.date_keep_rb = QRadioButton("Keep dates (declares 113106)")
        self.date_shift_rb = QRadioButton(
            "Shift dates to ~1900 — preserves relative timing (declares 113107)"
        )
        self.date_remove_rb = QRadioButton("Remove dates (blank, keeps file valid)")
        for rb in (self.date_keep_rb, self.date_shift_rb, self.date_remove_rb):
            self.date_button_group.addButton(rb)
            rb.setStyleSheet("QRadioButton { margin-left: 16px; }")
            options_layout.addWidget(rb)

        self.strip_private_cb = QCheckBox("Remove private tags")
        options_layout.addWidget(self.strip_private_cb)

        self.strip_free_text_cb = QCheckBox(
            "Remove free-text comments and descriptions"
        )
        options_layout.addWidget(self.strip_free_text_cb)

        options_group.setLayout(options_layout)
        layout.addWidget(options_group)

        # Any manual edit drops the selector to "Custom…".
        for cb in (
            self.retain_institution_cb,
            self.retain_device_cb,
            self.strip_operators_cb,
            self.uid_remap_cb,
            self.strip_private_cb,
            self.strip_free_text_cb,
        ):
            cb.toggled.connect(self._on_toggle_edited)
        for rb in (self.date_keep_rb, self.date_shift_rb, self.date_remove_rb):
            rb.toggled.connect(self._on_toggle_edited)

    def _on_preset_changed(self, index: int) -> None:
        if self._syncing:
            return
        if index < 0 or index >= len(ANONYMIZER_PRESETS):
            return  # "Custom…" selected — leave toggles as-is
        _key, _label, factory = ANONYMIZER_PRESETS[index]
        self._apply_options_to_toggles(factory())

    def _on_toggle_edited(self, _checked: bool) -> None:
        if self._syncing:
            return
        self._sync_preset_selector()

    def _apply_options_to_toggles(self, options: DeepAnonymizerOptions) -> None:
        self._syncing = True
        try:
            self.retain_institution_cb.setChecked(options.retain_institution_identity)
            self.retain_device_cb.setChecked(options.retain_device_identity)
            self.strip_operators_cb.setChecked(options.strip_operators)
            self.uid_remap_cb.setChecked(options.uid_remap and not options.retain_uids)
            if options.date_remove:
                self.date_remove_rb.setChecked(True)
            elif options.date_shift:
                self.date_shift_rb.setChecked(True)
            else:
                self.date_keep_rb.setChecked(True)
            self.strip_private_cb.setChecked(options.strip_private)
            self.strip_free_text_cb.setChecked(options.strip_free_text)
        finally:
            self._syncing = False

    def _sync_preset_selector(self) -> None:
        """Point the combo at the matching preset, else "Custom…"."""
        current = self.get_options()
        self._syncing = True
        try:
            for i, (_key, _label, factory) in enumerate(ANONYMIZER_PRESETS):
                if _options_equal(current, factory()):
                    self.preset_combo.setCurrentIndex(i)
                    return
            self.preset_combo.setCurrentIndex(len(ANONYMIZER_PRESETS))  # Custom…
        finally:
            self._syncing = False

    def set_options(self, options: DeepAnonymizerOptions) -> None:
        self._apply_options_to_toggles(options)
        self._sync_preset_selector()

    def get_options(self) -> DeepAnonymizerOptions:
        return DeepAnonymizerOptions(
            retain_institution_identity=self.retain_institution_cb.isChecked(),
            retain_device_identity=self.retain_device_cb.isChecked(),
            retain_uids=not self.uid_remap_cb.isChecked(),
            strip_operators=self.strip_operators_cb.isChecked(),
            uid_remap=self.uid_remap_cb.isChecked(),
            date_shift=self.date_shift_rb.isChecked(),
            date_remove=self.date_remove_rb.isChecked(),
            strip_private=self.strip_private_cb.isChecked(),
            strip_free_text=self.strip_free_text_cb.isChecked(),
        )


def _options_equal(a: DeepAnonymizerOptions, b: DeepAnonymizerOptions) -> bool:
    """Compare on the fields the widget exposes (ignores derived/unused state)."""
    return (
        a.retain_institution_identity == b.retain_institution_identity
        and a.retain_device_identity == b.retain_device_identity
        and a.remint_uids == b.remint_uids
        and a.strip_operators == b.strip_operators
        and bool(a.date_shift) == bool(b.date_shift)
        and a.date_remove == b.date_remove
        and a.strip_private == b.strip_private
        and a.strip_free_text == b.strip_free_text
    )


class AnonymizationOptionsDialog(QDialog):
    """Options-only dialog (no file selection/export) returning de-id options."""

    def __init__(
        self,
        options: DeepAnonymizerOptions | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("De-identification Options (PS3.15)")
        self.setModal(True)
        layout = QVBoxLayout(self)
        self.options_widget = AnonymizationOptionsWidget(options, parent=self)
        layout.addWidget(self.options_widget)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_options(self) -> DeepAnonymizerOptions:
        return self.options_widget.get_options()
