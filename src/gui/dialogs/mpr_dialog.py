"""
MPR Dialog

Lets the user select source series, output orientation, pixel spacing,
slice thickness, and interpolation method before starting an MPR build.

Inputs:
    - loaded_series: dict mapping series_key → {description, modality,
                     n_slices, study_uid, datasets} for all currently loaded
                     series.  The dialog populates the source-series dropdown
                     from this dict.
    - initial_series_key: optional key to pre-select in the dropdown.

Outputs:
    - MprRequest emitted via the ``mpr_requested`` signal on OK, containing
      all parameters needed by MprBuilder.

Requirements:
    - PySide6
    - numpy (for custom normal computation)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple, cast

import numpy as np
from pydicom.dataset import Dataset
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from core.mpr_volume import MprVolume
from core.slice_geometry import SlicePlane


# ---------------------------------------------------------------------------
# Request dataclass
# ---------------------------------------------------------------------------

@dataclass
class MprRequest:
    """
    All parameters required to launch an MPR build.

    Attributes:
        series_key:          Key used to look up the source series in
                             ``loaded_series``.
        datasets:            Source DICOM datasets.
        output_plane:        SlicePlane defining output orientation.
        output_spacing_mm:   In-plane pixel spacing (mm).
        output_thickness_mm: Inter-slice spacing (mm).
        interpolation:       "linear" | "nearest" | "cubic".
        combine_mode:        Slab combine mode: "none" | "mip" | "minip" | "aip".
        slab_thickness_mm:   Slab thickness in mm used by combine modes.
        orientation_label:   Human-readable label ("Axial", "Coronal", etc.)
    """
    series_key: str
    datasets: List[Dataset]
    output_plane: SlicePlane
    output_spacing_mm: float
    output_thickness_mm: float
    interpolation: str
    combine_mode: str
    slab_thickness_mm: float
    orientation_label: str


# ---------------------------------------------------------------------------
# Dialog
# ---------------------------------------------------------------------------

class MprDialog(QDialog):
    """
    Dialog for creating an MPR view in a subwindow.

    Signals:
        mpr_requested (MprRequest): Emitted on OK with the full build spec.
    """

    mpr_requested = Signal(object)  # MprRequest

    def __init__(
        self,
        loaded_series: Dict[str, Dict[str, Any]],
        initial_series_key: Optional[str] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        """
        Args:
            loaded_series:      Dict of all currently loaded series.
                                Each value should have keys: "description",
                                "modality", "n_slices", "datasets".
            initial_series_key: Key to pre-select (usually the focused subwindow's
                                series).
            parent:             Parent widget.
        """
        super().__init__(parent)
        self.setWindowTitle("Create MPR View")
        self.setMinimumWidth(460)
        self.setWindowFlags(
            self.windowFlags()
            | Qt.WindowType.WindowStaysOnTopHint
        )

        self._loaded_series = loaded_series
        self._initial_series_key = initial_series_key

        self._build_ui()
        self._populate_series_combo()
        self._update_defaults()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        """Build and lay out all widgets."""
        root = QVBoxLayout(self)
        root.setSpacing(10)
        root.setContentsMargins(12, 12, 12, 12)

        # --- Source series ---
        series_group = QGroupBox("Source Series")
        series_layout = QFormLayout(series_group)
        self._series_combo = QComboBox()
        self._series_combo.setToolTip(
            "Series to use as the source volume for MPR resampling."
        )
        self._series_combo.currentIndexChanged.connect(self._on_series_changed)
        series_layout.addRow("Series:", self._series_combo)

        self._series_info_label = QLabel("")
        self._series_info_label.setStyleSheet("color: gray; font-size: 10px;")
        series_layout.addRow("", self._series_info_label)

        self._geometry_warning = QLabel(
            "⚠ This series lacks complete spatial metadata (ImagePositionPatient / "
            "ImageOrientationPatient). MPR may not be possible."
        )
        self._geometry_warning.setStyleSheet("color: orange; font-size: 10px;")
        self._geometry_warning.setWordWrap(True)
        self._geometry_warning.setVisible(False)
        series_layout.addRow("", self._geometry_warning)

        root.addWidget(series_group)

        # --- Orientation ---
        orient_group = QGroupBox("Output Orientation")
        orient_layout = QVBoxLayout(orient_group)

        self._radio_axial = QRadioButton("Axial  (normal = Superior)")
        self._radio_coronal = QRadioButton("Coronal  (normal = Anterior)")
        self._radio_sagittal = QRadioButton("Sagittal  (normal = Left)")
        self._radio_custom = QRadioButton("Custom normal vector:")
        self._radio_axial.setChecked(True)

        for btn in (
            self._radio_axial,
            self._radio_coronal,
            self._radio_sagittal,
            self._radio_custom,
        ):
            orient_layout.addWidget(btn)
            btn.toggled.connect(self._on_orientation_changed)

        # Custom normal inputs (shown only when Custom is selected).
        self._custom_widget = QWidget()
        custom_h = QHBoxLayout(self._custom_widget)
        custom_h.setContentsMargins(24, 0, 0, 0)
        self._nx_edit = QLineEdit("0.0")
        self._ny_edit = QLineEdit("0.0")
        self._nz_edit = QLineEdit("1.0")
        for label, edit in (("Nx:", self._nx_edit), ("Ny:", self._ny_edit), ("Nz:", self._nz_edit)):
            custom_h.addWidget(QLabel(label))
            custom_h.addWidget(edit)
        self._custom_widget.setVisible(False)
        orient_layout.addWidget(self._custom_widget)

        root.addWidget(orient_group)

        # --- Output parameters ---
        params_group = QGroupBox("Output Parameters")
        params_layout = QFormLayout(params_group)

        self._spacing_spin = QDoubleSpinBox()
        self._spacing_spin.setRange(0.1, 50.0)
        self._spacing_spin.setDecimals(2)
        self._spacing_spin.setSuffix(" mm")
        self._spacing_spin.setToolTip(
            "In-plane pixel spacing of the output slices."
        )

        self._thickness_spin = QDoubleSpinBox()
        self._thickness_spin.setRange(0.1, 50.0)
        self._thickness_spin.setDecimals(2)
        self._thickness_spin.setSuffix(" mm")
        self._thickness_spin.setToolTip(
            "Distance between consecutive output slices."
        )

        self._interp_combo = QComboBox()
        for label, val in (
            ("Linear (default)", "linear"),
            ("Nearest Neighbor", "nearest"),
            ("Cubic B-Spline", "cubic"),
        ):
            self._interp_combo.addItem(label, val)

        params_layout.addRow("Pixel Spacing:", self._spacing_spin)
        params_layout.addRow("Slice Thickness:", self._thickness_spin)
        params_layout.addRow("Interpolation:", self._interp_combo)

        # --- Slab combine ---
        # These options modify the final displayed output slice by combining a
        # small slab of neighboring MPR planes at the current slice index.
        combine_group = QGroupBox("Slab Combine (for MIP/MinIP/AIP)")
        combine_layout = QFormLayout(combine_group)

        self._combine_mode_combo = QComboBox()
        for label, val in (
            ("None (single slice)", "none"),
            ("MIP (max intensity)", "mip"),
            ("MinIP (min intensity)", "minip"),
            ("AIP (average intensity)", "aip"),
        ):
            self._combine_mode_combo.addItem(label, val)

        self._slab_thickness_spin = QDoubleSpinBox()
        self._slab_thickness_spin.setRange(0.1, 200.0)
        self._slab_thickness_spin.setDecimals(2)
        self._slab_thickness_spin.setSuffix(" mm")
        self._slab_thickness_spin.setToolTip(
            "Slab thickness in mm used by MIP/MinIP/AIP. "
            "The MPR builder combines neighboring output planes around the current slice."
        )

        combine_layout.addRow("Mode:", self._combine_mode_combo)
        combine_layout.addRow("Slab Thickness:", self._slab_thickness_spin)

        # Keep this section visible; the combo mode itself disables effectiveness.
        params_layout.addRow(combine_group)

        # Estimated output size (read-only).
        self._estimate_label = QLabel("")
        self._estimate_label.setStyleSheet("color: gray; font-size: 10px;")
        params_layout.addRow("Est. output:", self._estimate_label)

        self._spacing_spin.valueChanged.connect(self._update_estimate)
        self._thickness_spin.valueChanged.connect(self._update_estimate)

        root.addWidget(params_group)

        # --- Buttons ---
        btn_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        btn_box.accepted.connect(self._on_ok)
        btn_box.rejected.connect(self.reject)
        root.addWidget(btn_box)

    # ------------------------------------------------------------------
    # Population helpers
    # ------------------------------------------------------------------

    def _populate_series_combo(self) -> None:
        """Fill the series combo with all loaded series."""
        self._series_combo.clear()
        for key, info in self._loaded_series.items():
            description = info.get("description", "") or "Unknown"
            modality = info.get("modality", "") or ""
            n_slices = info.get("n_slices", 0)
            label = f"{modality}  {description}  ({n_slices} slices)"
            self._series_combo.addItem(label.strip(), key)

        if self._initial_series_key:
            idx = self._series_combo.findData(self._initial_series_key)
            if idx >= 0:
                self._series_combo.setCurrentIndex(idx)

    def _update_defaults(self) -> None:
        """Set default spacing / thickness from the currently selected series."""
        key = self._current_series_key()
        if not key:
            return
        info = self._loaded_series.get(key, {})
        datasets = info.get("datasets", [])
        if not datasets:
            return

        ds0 = datasets[0]
        # Default pixel spacing.
        try:
            ps = ds0.PixelSpacing
            default_sp = float(ps[0]) if ps else 1.0
        except (AttributeError, TypeError):
            default_sp = 1.0

        # Default slice thickness.
        try:
            default_th = float(ds0.SliceThickness) if hasattr(ds0, "SliceThickness") else default_sp
        except (TypeError, ValueError):
            default_th = default_sp

        self._spacing_spin.setValue(round(default_sp, 2))
        self._thickness_spin.setValue(round(default_th, 2))

        # Default slab thickness: match the default output slice thickness
        # so "None vs. combine" produces a sane starting behavior.
        self._slab_thickness_spin.setValue(round(default_th, 2))
        self._update_estimate()

    def _update_estimate(self) -> None:
        """Update the estimated output size label."""
        key = self._current_series_key()
        if not key:
            self._estimate_label.setText("")
            return
        info = self._loaded_series.get(key, {})
        datasets = info.get("datasets", [])
        if not datasets:
            self._estimate_label.setText("")
            return
        ds0 = datasets[0]
        try:
            rows = int(ds0.Rows)
            cols = int(ds0.Columns)
            n = len(datasets)
        except (AttributeError, TypeError):
            self._estimate_label.setText("")
            return
        sp = self._spacing_spin.value()
        th = self._thickness_spin.value()
        est_px = int(max(rows, cols) * 1.0) if sp > 0 else rows
        est_sl = int(n * (th / max(sp, 0.01))) if sp > 0 else n
        self._estimate_label.setText(
            f"≈ {est_px}×{est_px} px/slice × {est_sl} slices "
            f"(exact size computed at build time)"
        )

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def _on_series_changed(self, _index: int) -> None:
        """Update info label, geometry warning, and defaults on series change."""
        key = self._current_series_key()
        if not key:
            self._series_info_label.setText("")
            self._geometry_warning.setVisible(False)
            return

        info = self._loaded_series.get(key, {})
        datasets = info.get("datasets", [])

        # Info summary.
        study = info.get("study_uid", "")[:16] + "..." if info.get("study_uid") else ""
        self._series_info_label.setText(
            f"Study: {study}  |  Slices: {len(datasets)}"
        )

        # Geometry check.
        ok = MprVolume.available(datasets) if datasets else False
        self._geometry_warning.setVisible(not ok)
        ok_btn = self._button_box_ok()
        if ok_btn is not None:
            ok_btn.setEnabled(ok)

        self._update_defaults()

    def _on_orientation_changed(self, _checked: bool) -> None:
        """Show / hide custom normal widget."""
        self._custom_widget.setVisible(self._radio_custom.isChecked())

    def _on_ok(self) -> None:
        """Validate inputs and emit mpr_requested."""
        key = self._current_series_key()
        if not key:
            QMessageBox.warning(self, "MPR", "No series selected.")
            return

        info = self._loaded_series.get(key, {})
        datasets = info.get("datasets", [])
        if not datasets:
            QMessageBox.warning(self, "MPR", "Selected series has no datasets.")
            return

        if not MprVolume.available(datasets):
            QMessageBox.warning(
                self,
                "MPR",
                "The selected series lacks required DICOM spatial metadata "
                "(ImagePositionPatient / ImageOrientationPatient). "
                "MPR is not available for this series.",
            )
            return

        output_plane, label = self._resolve_output_plane()
        if output_plane is None:
            return  # Error already shown.

        sp = self._spacing_spin.value()
        th = self._thickness_spin.value()
        interp = self._interp_combo.currentData() or "linear"
        combine_mode = self._combine_mode_combo.currentData() or "none"
        slab_thickness = float(self._slab_thickness_spin.value())

        req = MprRequest(
            series_key=key,
            datasets=datasets,
            output_plane=output_plane,
            output_spacing_mm=sp,
            output_thickness_mm=th,
            interpolation=interp,
            combine_mode=combine_mode,
            slab_thickness_mm=slab_thickness,
            orientation_label=label,
        )
        # Close the dialog first so the orientation-choice or error dialogs
        # opened by the handler are visible on top and the user is not stuck.
        self.accept()
        self.mpr_requested.emit(req)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _current_series_key(self) -> Optional[str]:
        """Return the data payload of the currently selected series combo item."""
        idx = self._series_combo.currentIndex()
        if idx < 0:
            return None
        return self._series_combo.itemData(idx)

    def _button_box_ok(self) -> Optional[QPushButton]:
        """Return the OK button from the dialog's button box."""
        # Walk children to find the button box.
        for child in self.findChildren(QDialogButtonBox):
            btn = child.button(QDialogButtonBox.StandardButton.Ok)
            if btn is not None:
                return cast(QPushButton, btn)
        return None

    def _resolve_output_plane(self) -> Tuple[Optional[SlicePlane], str]:
        """
        Build the output SlicePlane from the selected orientation radio button.

        Returns:
            (SlicePlane, label_str) on success.
            (None, "") on failure (error message shown to user).
        """
        standard = self._get_standard_planes()

        if self._radio_axial.isChecked():
            return standard["axial"], "Axial"
        if self._radio_coronal.isChecked():
            return standard["coronal"], "Coronal"
        if self._radio_sagittal.isChecked():
            return standard["sagittal"], "Sagittal"

        # Custom normal.
        try:
            nx = float(self._nx_edit.text())
            ny = float(self._ny_edit.text())
            nz = float(self._nz_edit.text())
        except ValueError:
            QMessageBox.warning(
                self, "MPR", "Custom normal vector must be three numeric values."
            )
            return None, ""

        normal = np.array([nx, ny, nz], dtype=float)
        mag = float(np.linalg.norm(normal))
        if mag < 1e-6:
            QMessageBox.warning(
                self, "MPR", "Custom normal vector must be non-zero."
            )
            return None, ""
        normal /= mag

        # Build an orthonormal frame from the custom normal.
        row_cosine, col_cosine = self._perpendicular_axes(normal)
        plane = SlicePlane(
            origin=np.zeros(3),
            row_cosine=row_cosine,
            col_cosine=col_cosine,
            row_spacing=self._spacing_spin.value(),
            col_spacing=self._spacing_spin.value(),
        )
        label = f"Custom ({nx:.2f},{ny:.2f},{nz:.2f})"
        return plane, label

    @staticmethod
    def _get_standard_planes() -> Dict[str, SlicePlane]:
        """Return standard anatomical SlicePlane definitions."""
        from core.mpr_builder import MprBuilder
        return MprBuilder.standard_planes()

    @staticmethod
    def _perpendicular_axes(normal: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """
        Build two perpendicular unit vectors for a given normal.

        Uses the Gram-Schmidt approach with a fallback reference vector.

        Args:
            normal: Unit normal vector.

        Returns:
            (row_cosine, col_cosine) — both orthogonal to normal and each other.
        """
        # Choose a reference vector not parallel to normal.
        ref = np.array([1.0, 0.0, 0.0])
        if abs(float(np.dot(normal, ref))) > 0.9:
            ref = np.array([0.0, 1.0, 0.0])
        row_cosine = np.cross(normal, ref)
        row_cosine /= np.linalg.norm(row_cosine)
        col_cosine = np.cross(normal, row_cosine)
        col_cosine /= np.linalg.norm(col_cosine)
        return row_cosine, col_cosine
