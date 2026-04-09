"""
Stage 1 dialog: ACR MRI Large (pylinac) advanced options.

Surfaces echo selection, MRI low-contrast single-run tuning, and an optional
compare mode that lets the user configure up to 3 low-contrast parameter sets
(method + threshold + sanity multiplier) to run side-by-side.

Compare mode:
    Enable the "Compare low-contrast settings" group to add up to 3 rows.
    Each row specifies a contrast method and multiplier-based values for the
    visibility threshold and sanity multiplier, centred on pylinac defaults.
    The multiplier combos use the set defined in
    ``LC_COMPARE_MULTIPLIERS`` (0.75 × … 1.25 ×).
    When compare mode is enabled, ``get_options()`` includes an
    ``Optional[MRICompareRequest]`` before the final ``vanilla_pylinac`` bool.

Does not import pylinac directly.

Returns (from get_options / prompt_acr_mri_options):
    (echo_number, check_uid, origin_slice, scan_extent_tolerance_mm,
     low_contrast_method, low_contrast_visibility_threshold,
     low_contrast_visibility_sanity_multiplier,
     compare_request_or_none, vanilla_pylinac)
"""

from __future__ import annotations

from typing import List, Optional, Tuple

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from qa.analysis_types import LcRunConfig, MRICompareRequest
from utils.config.qa_pylinac_config import (
    ACR_MRI_LOW_CONTRAST_METHODS,
    DEFAULT_ACR_MRI_LOW_CONTRAST_METHOD,
    DEFAULT_ACR_MRI_LOW_CONTRAST_VISIBILITY_SANITY_MULTIPLIER,
    DEFAULT_ACR_MRI_LOW_CONTRAST_VISIBILITY_THRESHOLD,
    LC_COMPARE_MULTIPLIERS,
    LC_COMPARE_ROW_DEFAULT_MULTIPLIER_INDICES,
)

_MAX_COMPARE_ROWS = 3


def _multiplier_label(multiplier: float, base: float) -> str:
    """Format a combo item label: '× 0.90 (= 0.000900)'."""
    computed = multiplier * base
    # Choose decimal places based on magnitude
    if base < 0.01:
        return f"\u00d7 {multiplier:.2f}  (= {computed:.6f})"
    return f"\u00d7 {multiplier:.2f}  (= {computed:.4f})"


class _CompareRow(QWidget):
    """
    One row in the compare table.

    Contains:
        enable_check  -- QCheckBox enabling/disabling this row
        method_combo  -- contrast method selector
        threshold_combo -- threshold multiplier selector
        sanity_combo  -- sanity multiplier selector
    """

    def __init__(
        self,
        row_index: int,
        parent: Optional[QWidget] = None,
    ) -> None:
        """
        Args:
            row_index: 0-based index (determines default multiplier selection).
            parent: Optional parent widget.
        """
        super().__init__(parent)
        self._row_index = row_index
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.enable_check = QCheckBox(f"Run {row_index + 1}")
        self.enable_check.setChecked(row_index == 0)  # only first row on by default
        self.enable_check.toggled.connect(self._on_enabled_toggled)

        self.method_combo = QComboBox()
        for method in ACR_MRI_LOW_CONTRAST_METHODS:
            self.method_combo.addItem(method, method)
        self.method_combo.setCurrentIndex(
            self.method_combo.findData(DEFAULT_ACR_MRI_LOW_CONTRAST_METHOD)
        )

        self.threshold_combo = QComboBox()
        self.sanity_combo = QComboBox()
        self._populate_multiplier_combo(
            self.threshold_combo,
            DEFAULT_ACR_MRI_LOW_CONTRAST_VISIBILITY_THRESHOLD,
        )
        self._populate_multiplier_combo(
            self.sanity_combo,
            DEFAULT_ACR_MRI_LOW_CONTRAST_VISIBILITY_SANITY_MULTIPLIER,
        )

        # Pre-select row-specific default multiplier
        default_idx = LC_COMPARE_ROW_DEFAULT_MULTIPLIER_INDICES[
            min(row_index, len(LC_COMPARE_ROW_DEFAULT_MULTIPLIER_INDICES) - 1)
        ]
        self.threshold_combo.setCurrentIndex(default_idx)
        self.sanity_combo.setCurrentIndex(default_idx)

        layout.addWidget(self.enable_check, 0)
        layout.addWidget(QLabel("Method:"), 0)
        layout.addWidget(self.method_combo, 1)
        layout.addWidget(QLabel("Threshold:"), 0)
        layout.addWidget(self.threshold_combo, 1)
        layout.addWidget(QLabel("Sanity ×:"), 0)
        layout.addWidget(self.sanity_combo, 1)

        self._on_enabled_toggled(self.enable_check.isChecked())

    def _populate_multiplier_combo(self, combo: QComboBox, base: float) -> None:
        for m in LC_COMPARE_MULTIPLIERS:
            computed = m * base
            combo.addItem(_multiplier_label(m, base), computed)

    def _on_enabled_toggled(self, checked: bool) -> None:
        self.method_combo.setEnabled(checked)
        self.threshold_combo.setEnabled(checked)
        self.sanity_combo.setEnabled(checked)

    def is_enabled(self) -> bool:
        return bool(self.enable_check.isChecked())

    def to_lc_run_config(self) -> LcRunConfig:
        """Build an LcRunConfig from the current widget state."""
        return LcRunConfig(
            label=f"Run {self._row_index + 1}",
            low_contrast_method=str(
                self.method_combo.currentData() or DEFAULT_ACR_MRI_LOW_CONTRAST_METHOD
            ),
            low_contrast_visibility_threshold=float(
                self.threshold_combo.currentData()
                or DEFAULT_ACR_MRI_LOW_CONTRAST_VISIBILITY_THRESHOLD
            ),
            low_contrast_visibility_sanity_multiplier=float(
                self.sanity_combo.currentData()
                or DEFAULT_ACR_MRI_LOW_CONTRAST_VISIBILITY_SANITY_MULTIPLIER
            ),
        )

    def reset_to_defaults(self) -> None:
        """Reset combos to row-specific default multipliers."""
        self.method_combo.setCurrentIndex(
            max(self.method_combo.findData(DEFAULT_ACR_MRI_LOW_CONTRAST_METHOD), 0)
        )
        default_idx = LC_COMPARE_ROW_DEFAULT_MULTIPLIER_INDICES[
            min(self._row_index, len(LC_COMPARE_ROW_DEFAULT_MULTIPLIER_INDICES) - 1)
        ]
        self.threshold_combo.setCurrentIndex(default_idx)
        self.sanity_combo.setCurrentIndex(default_idx)


class AcrMrIQaOptionsDialog(QDialog):
    """
    Collect MRI-specific pylinac options before running analysis.

    Provides:
    - Echo selection and check_uid
    - Optional origin slice override
    - Scan-extent tolerance
    - Single-run low-contrast detectability knobs
    - Compare mode: up to 3 low-contrast parameter sets with multiplier combos
      centred on pylinac defaults

    Returns (from get_options):
        (echo_number, check_uid, origin_slice, scan_extent_tolerance_mm,
         low_contrast_method, low_contrast_visibility_threshold,
         low_contrast_visibility_sanity_multiplier,
         compare_request_or_none, vanilla_pylinac)
        where compare_request_or_none is an MRICompareRequest when compare mode
        is enabled, else None.
    """

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        *,
        low_contrast_method: str = DEFAULT_ACR_MRI_LOW_CONTRAST_METHOD,
        low_contrast_visibility_threshold: float = (
            DEFAULT_ACR_MRI_LOW_CONTRAST_VISIBILITY_THRESHOLD
        ),
        low_contrast_visibility_sanity_multiplier: float = (
            DEFAULT_ACR_MRI_LOW_CONTRAST_VISIBILITY_SANITY_MULTIPLIER
        ),
        vanilla_pylinac_default: bool = False,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("ACR MRI (pylinac) — Options")
        self.setWindowFlags(
            self.windowFlags() | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setMinimumWidth(1000)

        # ----------------------------------------------------------------
        # Left column: intro + Advanced + Scan extent
        # ----------------------------------------------------------------
        left_col = QVBoxLayout()

        intro = QLabel(
            "Echo: pylinac uses the lowest echo by default if you leave "
            '"Use lowest echo number" checked. '
            "Match SeriesInstanceUID: enable for strict series matching when "
            "your pylinac version supports analyze(check_uid=...); otherwise "
            "the choice is recorded in JSON only."
        )
        intro.setWordWrap(True)
        left_col.addWidget(intro)

        self._vanilla = QCheckBox("Vanilla pylinac (stock ACRMRILarge)")
        self._vanilla.setChecked(bool(vanilla_pylinac_default))
        self._vanilla.toggled.connect(self._on_vanilla_pylinac_toggled)
        left_col.addWidget(self._vanilla)

        # --- Advanced group ---
        advanced = QGroupBox("Advanced")
        form = QFormLayout()

        self._use_lowest_echo = QCheckBox("Use lowest echo number (recommended)")
        self._use_lowest_echo.setChecked(True)
        self._use_lowest_echo.toggled.connect(self._on_use_lowest_toggled)

        self._echo_spin = QSpinBox()
        self._echo_spin.setRange(1, 32)
        self._echo_spin.setValue(1)
        self._echo_spin.setEnabled(False)

        self._check_uid = QCheckBox(
            "Strict Series Instance UID matching (check_uid)"
        )
        self._check_uid.setChecked(True)

        self._origin_spin = QSpinBox()
        self._origin_spin.setRange(-1, 10_000)
        self._origin_spin.setSpecialValueText("(auto)")
        self._origin_spin.setValue(-1)

        form.addRow(self._use_lowest_echo)
        form.addRow("Echo number:", self._echo_spin)
        form.addRow(self._check_uid)
        form.addRow("Origin slice index (-1 = auto):", self._origin_spin)
        advanced.setLayout(form)
        left_col.addWidget(advanced)

        # --- Scan extent group ---
        self._geom = QGroupBox("Scan extent (optional, viewer integration only)")
        gform = QFormLayout()
        self._extent_tol = QCheckBox(
            "Allow small scan-extent tolerance (DICOM z rounding)"
        )
        self._extent_tol.setChecked(False)
        self._tol_spin = QDoubleSpinBox()
        self._tol_spin.setRange(0.5, 2.0)
        self._tol_spin.setSingleStep(0.5)
        self._tol_spin.setDecimals(2)
        self._tol_spin.setValue(1.0)
        self._tol_spin.setEnabled(False)
        self._extent_tol.toggled.connect(self._tol_spin.setEnabled)
        gform.addRow(self._extent_tol)
        gform.addRow("Tolerance (mm):", self._tol_spin)
        self._geom.setLayout(gform)
        left_col.addWidget(self._geom)
        left_col.addStretch()

        self._on_vanilla_pylinac_toggled(self._vanilla.isChecked())

        # ----------------------------------------------------------------
        # Right column: Low-contrast (single run) + Compare mode
        # ----------------------------------------------------------------
        right_col = QVBoxLayout()

        # --- Single-run low-contrast group ---
        lc = QGroupBox("Low-contrast detectability — single run")
        lc_form = QFormLayout()
        self._lc_method_combo = QComboBox()
        for method in ACR_MRI_LOW_CONTRAST_METHODS:
            self._lc_method_combo.addItem(method, method)
        method_idx = self._lc_method_combo.findData(str(low_contrast_method))
        if method_idx < 0:
            method_idx = self._lc_method_combo.findData(
                DEFAULT_ACR_MRI_LOW_CONTRAST_METHOD
            )
        self._lc_method_combo.setCurrentIndex(max(method_idx, 0))

        self._lc_vis_spin = QDoubleSpinBox()
        self._lc_vis_spin.setRange(0.0, 100.0)
        self._lc_vis_spin.setDecimals(6)
        self._lc_vis_spin.setSingleStep(0.0001)
        self._lc_vis_spin.setValue(float(low_contrast_visibility_threshold))

        self._lc_sanity_spin = QDoubleSpinBox()
        self._lc_sanity_spin.setRange(0.01, 100.0)
        self._lc_sanity_spin.setDecimals(3)
        self._lc_sanity_spin.setSingleStep(0.5)
        self._lc_sanity_spin.setValue(float(low_contrast_visibility_sanity_multiplier))

        lc_hint = QLabel(
            "Method: how contrast is measured before pylinac computes visibility. "
            "Threshold: minimum visibility for a disk to count as seen (lower = more "
            "permissive). Sanity multiplier: suppresses unrealistically large values "
            "on tiny disks. Values are saved on OK and used for each new analysis."
        )
        lc_hint.setWordWrap(True)
        reset_button = QPushButton("Reset to pylinac defaults")
        reset_button.clicked.connect(self._reset_low_contrast_defaults)
        lc_form.addRow(lc_hint)
        lc_form.addRow("Contrast method:", self._lc_method_combo)
        lc_form.addRow("Visibility threshold:", self._lc_vis_spin)
        lc_form.addRow("Sanity multiplier:", self._lc_sanity_spin)
        lc_form.addRow(reset_button)
        lc.setLayout(lc_form)
        right_col.addWidget(lc)

        # --- Compare mode group ---
        compare_group = QGroupBox("Compare low-contrast settings (up to 3 runs)")
        compare_group.setCheckable(True)
        compare_group.setChecked(False)
        compare_group.toggled.connect(self._on_compare_toggled)
        self._compare_group = compare_group

        compare_layout = QVBoxLayout()

        compare_hint = QLabel(
            "Enable up to 3 parameter sets to run side-by-side. Each row uses "
            "a multiplier applied to the pylinac defaults "
            f"(threshold \u00d7\u00a0{DEFAULT_ACR_MRI_LOW_CONTRAST_VISIBILITY_THRESHOLD:.3f}, "
            f"sanity \u00d7\u00a0{DEFAULT_ACR_MRI_LOW_CONTRAST_VISIBILITY_SANITY_MULTIPLIER:.1f}). "
            "Run 1 also drives the standard single-run PDF. "
            "Results and a comparison table are exported in the JSON."
        )
        compare_hint.setWordWrap(True)
        compare_layout.addWidget(compare_hint)

        self._compare_rows: List[_CompareRow] = []
        for i in range(_MAX_COMPARE_ROWS):
            row = _CompareRow(i, self)
            self._compare_rows.append(row)
            compare_layout.addWidget(row)
            if i > 0:
                row.enable_check.setChecked(False)

        btn_row = QHBoxLayout()
        add_btn = QPushButton("Enable next run")
        add_btn.clicked.connect(self._add_compare_row)
        reset_compare_btn = QPushButton("Reset all rows to defaults")
        reset_compare_btn.clicked.connect(self._reset_compare_rows)
        btn_row.addWidget(add_btn)
        btn_row.addWidget(reset_compare_btn)
        btn_row.addStretch()
        compare_layout.addLayout(btn_row)
        compare_group.setLayout(compare_layout)
        right_col.addWidget(compare_group)
        right_col.addStretch()

        # ----------------------------------------------------------------
        # Assemble two-column layout + dialog buttons
        # ----------------------------------------------------------------
        columns = QHBoxLayout()
        columns.addLayout(left_col, 1)
        columns.addLayout(right_col, 3)

        # --- Dialog buttons ---
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(columns)
        layout.addWidget(buttons)

        self._on_use_lowest_toggled(self._use_lowest_echo.isChecked())
        self._on_compare_toggled(compare_group.isChecked())

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _on_use_lowest_toggled(self, checked: bool) -> None:
        self._echo_spin.setEnabled(not checked)

    def _on_vanilla_pylinac_toggled(self, checked: bool) -> None:
        self._geom.setEnabled(not checked)
        if checked:
            self._extent_tol.setChecked(False)

    def _on_compare_toggled(self, checked: bool) -> None:
        for row in self._compare_rows:
            row.setVisible(checked)

    def _reset_low_contrast_defaults(self) -> None:
        idx = self._lc_method_combo.findData(DEFAULT_ACR_MRI_LOW_CONTRAST_METHOD)
        self._lc_method_combo.setCurrentIndex(max(idx, 0))
        self._lc_vis_spin.setValue(DEFAULT_ACR_MRI_LOW_CONTRAST_VISIBILITY_THRESHOLD)
        self._lc_sanity_spin.setValue(
            DEFAULT_ACR_MRI_LOW_CONTRAST_VISIBILITY_SANITY_MULTIPLIER
        )

    def _add_compare_row(self) -> None:
        """Enable the first unchecked compare row, if any."""
        for row in self._compare_rows:
            if not row.is_enabled():
                row.enable_check.setChecked(True)
                return

    def _reset_compare_rows(self) -> None:
        for row in self._compare_rows:
            row.reset_to_defaults()
        # Keep only row 0 enabled
        for i, row in enumerate(self._compare_rows):
            row.enable_check.setChecked(i == 0)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_options(
        self,
    ) -> Tuple[
        Optional[int],
        bool,
        Optional[int],
        float,
        str,
        float,
        float,
        Optional[MRICompareRequest],
        bool,
    ]:
        """
        Return collected options.

        Returns:
            (echo_number, check_uid, origin_slice, scan_extent_tolerance_mm,
             low_contrast_method, low_contrast_visibility_threshold,
             low_contrast_visibility_sanity_multiplier,
             compare_request_or_none, vanilla_pylinac)
        """
        if self._use_lowest_echo.isChecked():
            echo: Optional[int] = None
        else:
            echo = int(self._echo_spin.value())
        check_uid = bool(self._check_uid.isChecked())
        origin = int(self._origin_spin.value())
        origin_out: Optional[int] = None if origin < 0 else origin
        vanilla = bool(self._vanilla.isChecked())
        scan_tol = 0.0
        if not vanilla and self._extent_tol.isChecked():
            scan_tol = float(self._tol_spin.value())
        method = str(
            self._lc_method_combo.currentData() or DEFAULT_ACR_MRI_LOW_CONTRAST_METHOD
        )
        lc_vis = float(self._lc_vis_spin.value())
        lc_sanity = float(self._lc_sanity_spin.value())

        compare_request: Optional[MRICompareRequest] = None
        if self._compare_group.isChecked():
            enabled_configs = [
                row.to_lc_run_config()
                for row in self._compare_rows
                if row.is_enabled()
            ]
            if enabled_configs:
                compare_request = MRICompareRequest(run_configs=enabled_configs)

        return (
            echo,
            check_uid,
            origin_out,
            scan_tol,
            method,
            lc_vis,
            lc_sanity,
            compare_request,
            vanilla,
        )


def prompt_acr_mri_options(
    parent: Optional[QWidget] = None,
    *,
    low_contrast_method: str = DEFAULT_ACR_MRI_LOW_CONTRAST_METHOD,
    low_contrast_visibility_threshold: float = (
        DEFAULT_ACR_MRI_LOW_CONTRAST_VISIBILITY_THRESHOLD
    ),
    low_contrast_visibility_sanity_multiplier: float = (
        DEFAULT_ACR_MRI_LOW_CONTRAST_VISIBILITY_SANITY_MULTIPLIER
    ),
    vanilla_pylinac_default: bool = False,
) -> Optional[
    Tuple[
        Optional[int],
        bool,
        Optional[int],
        float,
        str,
        float,
        float,
        Optional[MRICompareRequest],
        bool,
    ]
]:
    """
    Show modal ACR MRI options dialog.

    Args:
        parent: Parent widget for the dialog.
        low_contrast_method: Pre-selected contrast method.
        low_contrast_visibility_threshold: Pre-filled threshold value.
        low_contrast_visibility_sanity_multiplier: Pre-filled sanity multiplier.
        vanilla_pylinac_default: Initial state of Vanilla pylinac checkbox.

    Returns:
        Tuple ending with compare_request_or_none and vanilla_pylinac, or None
        if the user cancelled.
    """
    dlg = AcrMrIQaOptionsDialog(
        parent,
        low_contrast_method=low_contrast_method,
        low_contrast_visibility_threshold=low_contrast_visibility_threshold,
        low_contrast_visibility_sanity_multiplier=(
            low_contrast_visibility_sanity_multiplier
        ),
        vanilla_pylinac_default=vanilla_pylinac_default,
    )
    dlg.activateWindow()
    dlg.raise_()
    if dlg.exec() != int(QDialog.DialogCode.Accepted):
        return None
    return dlg.get_options()
