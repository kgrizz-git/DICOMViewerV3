"""
Dialog: nuclear-medicine QC options (pylinac.nuclear).

Supports multiple tests; the parameter controls swap with the selected test via
a QStackedWidget. The dialog does not import pylinac.

Returns a ``NuclearOptions`` subclass (from qa.analysis_types) or None on cancel.
"""

from __future__ import annotations

# Per-test parameter widgets are built in helper methods (QStackedWidget builder
# pattern) rather than assigned in ``__init__`` — same convention as
# ``main.py`` / ``image_viewer_view.py``.
# pyright: reportUninitializedInstanceVariable=false
import os

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from qa.analysis_types import (
    CenterOfRotationOptions,
    FourBarResolutionOptions,
    MaxCountRateOptions,
    NuclearOptions,
    PlanarUniformityOptions,
    QuadrantResolutionOptions,
    SimpleSensitivityOptions,
    TomographicContrastOptions,
    TomographicResolutionOptions,
    TomographicUniformityOptions,
)
from utils.config.qa_nuclear_config import (
    CENTER_OF_ROTATION_CLASS,
    DEFAULT_ACTIVITY_MBQ,
    DEFAULT_BAR_WIDTHS_MM,
    DEFAULT_CENTER_RATIO,
    DEFAULT_CFOV_RATIO,
    DEFAULT_DISTANCE_FROM_CENTER_MM,
    DEFAULT_FRAME_DURATION_S,
    DEFAULT_NUCLIDE,
    DEFAULT_ROI_DIAMETER_MM,
    DEFAULT_ROI_WIDTH_MM,
    DEFAULT_SEARCH_SLICES,
    DEFAULT_SEARCH_WINDOW_PX,
    DEFAULT_SEPARATION_MM,
    DEFAULT_SPHERE_ANGLES,
    DEFAULT_SPHERE_DIAMETERS_MM,
    DEFAULT_TC_UFOV_RATIO,
    DEFAULT_THRESHOLD,
    DEFAULT_TU_CFOV_RATIO,
    DEFAULT_TU_FIRST_FRAME,
    DEFAULT_TU_LAST_FRAME,
    DEFAULT_TU_THRESHOLD,
    DEFAULT_TU_UFOV_RATIO,
    DEFAULT_TU_WINDOW_SIZE,
    DEFAULT_UFOV_RATIO,
    DEFAULT_WINDOW_SIZE,
    FOUR_BAR_RESOLUTION_CLASS,
    MAX_ACTIVITY_MBQ,
    MAX_BAR_WIDTH_MM,
    MAX_COUNT_RATE_CLASS,
    MAX_DISTANCE_FROM_CENTER_MM,
    MAX_FOV_RATIO,
    MAX_FRAME_DURATION_S,
    MAX_FRAME_INDEX,
    MAX_ROI_DIAMETER_MM,
    MAX_ROI_WIDTH_MM,
    MAX_SEARCH_SLICES,
    MAX_SEARCH_WINDOW_PX,
    MAX_SEPARATION_MM,
    MAX_SPHERE_ANGLE_DEG,
    MAX_SPHERE_DIAMETER_MM,
    MAX_THRESHOLD,
    MAX_WINDOW_SIZE,
    MIN_ACTIVITY_MBQ,
    MIN_BAR_WIDTH_MM,
    MIN_DISTANCE_FROM_CENTER_MM,
    MIN_FOV_RATIO,
    MIN_FRAME_DURATION_S,
    MIN_FRAME_INDEX,
    MIN_ROI_DIAMETER_MM,
    MIN_ROI_WIDTH_MM,
    MIN_SEARCH_SLICES,
    MIN_SEARCH_WINDOW_PX,
    MIN_SEPARATION_MM,
    MIN_SPHERE_ANGLE_DEG,
    MIN_SPHERE_DIAMETER_MM,
    MIN_THRESHOLD,
    MIN_WINDOW_SIZE,
    NUCLIDE_NAMES,
    PLANAR_UNIFORMITY_CLASS,
    QUADRANT_RESOLUTION_CLASS,
    SIMPLE_SENSITIVITY_CLASS,
    TOMOGRAPHIC_CONTRAST_CLASS,
    TOMOGRAPHIC_RESOLUTION_CLASS,
    TOMOGRAPHIC_UNIFORMITY_CLASS,
)

# (label, pylinac class name) for the supported-test dropdown. The dropdown and
# the parameter stack share this order.
_SUPPORTED_TESTS = (
    ("Planar Uniformity", PLANAR_UNIFORMITY_CLASS),
    ("Four Bar Resolution", FOUR_BAR_RESOLUTION_CLASS),
    ("Quadrant Resolution", QUADRANT_RESOLUTION_CLASS),
    ("Center of Rotation", CENTER_OF_ROTATION_CLASS),
    ("Tomographic Resolution", TOMOGRAPHIC_RESOLUTION_CLASS),
    ("Max Count Rate", MAX_COUNT_RATE_CLASS),
    ("Tomographic Uniformity", TOMOGRAPHIC_UNIFORMITY_CLASS),
    ("Tomographic Contrast", TOMOGRAPHIC_CONTRAST_CLASS),
    ("Simple Sensitivity", SIMPLE_SENSITIVITY_CLASS),
)


class NuclearQaOptionsDialog(QDialog):
    """Collect pylinac.nuclear options before analysis."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Nuclear Medicine QC (pylinac) — Options")
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)

        intro = QLabel(
            "Runs a pylinac.nuclear analysis on a single NM DICOM file. Output is "
            "raw pylinac metrics for review — it is not a clinically validated "
            "pass/fail result."
        )
        intro.setWordWrap(True)

        self._test = QComboBox()
        for label, cls_name in _SUPPORTED_TESTS:
            self._test.addItem(label, cls_name)
        test_box = QGroupBox("Test")
        test_form = QFormLayout()
        test_form.addRow("Analysis:", self._test)
        test_box.setLayout(test_form)

        # Parameter pages, one per test, swapped by the dropdown (same order as
        # _SUPPORTED_TESTS).
        self._stack = QStackedWidget()
        self._stack.addWidget(self._build_planar_page())
        self._stack.addWidget(self._build_four_bar_page())
        self._stack.addWidget(self._build_quadrant_page())
        self._stack.addWidget(self._build_no_params_page("Center of Rotation"))
        self._stack.addWidget(self._build_no_params_page("Tomographic Resolution"))
        self._stack.addWidget(self._build_max_count_rate_page())
        self._stack.addWidget(self._build_tomo_uniformity_page())
        self._stack.addWidget(self._build_tomo_contrast_page())
        self._stack.addWidget(self._build_simple_sensitivity_page())
        self._test.currentIndexChanged.connect(self._stack.setCurrentIndex)

        params = QGroupBox("Parameters")
        params_layout = QVBoxLayout()
        params_layout.addWidget(self._stack)
        params.setLayout(params_layout)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(intro)
        layout.addWidget(test_box)
        layout.addWidget(params)
        layout.addWidget(buttons)

    def _build_planar_page(self) -> QWidget:
        page = QWidget()
        form = QFormLayout(page)
        self._ufov = QDoubleSpinBox()
        self._ufov.setRange(MIN_FOV_RATIO, MAX_FOV_RATIO)
        self._ufov.setSingleStep(0.01)
        self._ufov.setDecimals(2)
        self._ufov.setValue(DEFAULT_UFOV_RATIO)
        self._cfov = QDoubleSpinBox()
        self._cfov.setRange(MIN_FOV_RATIO, MAX_FOV_RATIO)
        self._cfov.setSingleStep(0.01)
        self._cfov.setDecimals(2)
        self._cfov.setValue(DEFAULT_CFOV_RATIO)
        self._window = QSpinBox()
        self._window.setRange(MIN_WINDOW_SIZE, MAX_WINDOW_SIZE)
        self._window.setSingleStep(2)  # differential window is conventionally odd
        self._window.setValue(DEFAULT_WINDOW_SIZE)
        self._threshold = QDoubleSpinBox()
        self._threshold.setRange(MIN_THRESHOLD, MAX_THRESHOLD)
        self._threshold.setSingleStep(0.05)
        self._threshold.setDecimals(2)
        self._threshold.setValue(DEFAULT_THRESHOLD)
        form.addRow("UFOV ratio:", self._ufov)
        form.addRow("CFOV ratio:", self._cfov)
        form.addRow("Differential window (px):", self._window)
        form.addRow("Threshold (fraction of mean):", self._threshold)
        return page

    def _build_four_bar_page(self) -> QWidget:
        page = QWidget()
        form = QFormLayout(page)
        self._separation = QDoubleSpinBox()
        self._separation.setRange(MIN_SEPARATION_MM, MAX_SEPARATION_MM)
        self._separation.setSingleStep(1.0)
        self._separation.setDecimals(1)
        self._separation.setValue(DEFAULT_SEPARATION_MM)
        self._roi_width = QDoubleSpinBox()
        self._roi_width.setRange(MIN_ROI_WIDTH_MM, MAX_ROI_WIDTH_MM)
        self._roi_width.setSingleStep(1.0)
        self._roi_width.setDecimals(1)
        self._roi_width.setValue(DEFAULT_ROI_WIDTH_MM)
        note = QLabel("Uses the first frame only for multi-frame images.")
        note.setWordWrap(True)
        form.addRow("Bar separation (mm):", self._separation)
        form.addRow("ROI width (mm):", self._roi_width)
        form.addRow(note)
        return page

    def _build_quadrant_page(self) -> QWidget:
        page = QWidget()
        form = QFormLayout(page)
        # One bar-width spinbox per quadrant (pylinac requires exactly 4).
        self._bar_widths = []
        for i, default in enumerate(DEFAULT_BAR_WIDTHS_MM, start=1):
            spin = QDoubleSpinBox()
            spin.setRange(MIN_BAR_WIDTH_MM, MAX_BAR_WIDTH_MM)
            spin.setSingleStep(0.1)
            spin.setDecimals(2)
            spin.setValue(float(default))
            self._bar_widths.append(spin)
            form.addRow(f"Quadrant {i} bar width (mm):", spin)
        self._roi_diameter = QDoubleSpinBox()
        self._roi_diameter.setRange(MIN_ROI_DIAMETER_MM, MAX_ROI_DIAMETER_MM)
        self._roi_diameter.setSingleStep(1.0)
        self._roi_diameter.setDecimals(1)
        self._roi_diameter.setValue(DEFAULT_ROI_DIAMETER_MM)
        self._distance = QDoubleSpinBox()
        self._distance.setRange(MIN_DISTANCE_FROM_CENTER_MM, MAX_DISTANCE_FROM_CENTER_MM)
        self._distance.setSingleStep(1.0)
        self._distance.setDecimals(1)
        self._distance.setValue(DEFAULT_DISTANCE_FROM_CENTER_MM)
        form.addRow("ROI diameter (mm):", self._roi_diameter)
        form.addRow("Distance from center (mm):", self._distance)
        note = QLabel(
            "Set the four bar widths to match your phantom's quadrants. "
            "Uses the first frame only for multi-frame images."
        )
        note.setWordWrap(True)
        form.addRow(note)
        return page

    @staticmethod
    def _build_no_params_page(test_label: str) -> QWidget:
        page = QWidget()
        form = QFormLayout(page)
        note = QLabel(
            f"{test_label} takes no parameters — it runs directly on the "
            "selected NM acquisition."
        )
        note.setWordWrap(True)
        form.addRow(note)
        return page

    def _build_max_count_rate_page(self) -> QWidget:
        page = QWidget()
        form = QFormLayout(page)
        self._frame_duration = QDoubleSpinBox()
        self._frame_duration.setRange(MIN_FRAME_DURATION_S, MAX_FRAME_DURATION_S)
        self._frame_duration.setSingleStep(0.1)
        self._frame_duration.setDecimals(3)
        self._frame_duration.setValue(DEFAULT_FRAME_DURATION_S)
        form.addRow("Frame duration (s):", self._frame_duration)
        note = QLabel("Seconds per dynamic frame (used to compute count rate).")
        note.setWordWrap(True)
        form.addRow(note)
        return page

    def _build_tomo_uniformity_page(self) -> QWidget:
        page = QWidget()
        form = QFormLayout(page)
        self._tu_first = QSpinBox()
        self._tu_first.setRange(MIN_FRAME_INDEX, MAX_FRAME_INDEX)
        self._tu_first.setValue(DEFAULT_TU_FIRST_FRAME)
        self._tu_last = QSpinBox()
        self._tu_last.setRange(MIN_FRAME_INDEX, MAX_FRAME_INDEX)
        self._tu_last.setSpecialValueText("(last)")  # -1 shows as "(last)"
        self._tu_last.setValue(DEFAULT_TU_LAST_FRAME)
        self._tu_ufov = self._ratio_spin(DEFAULT_TU_UFOV_RATIO)
        self._tu_cfov = self._ratio_spin(DEFAULT_TU_CFOV_RATIO)
        self._tu_center = QDoubleSpinBox()
        self._tu_center.setRange(MIN_THRESHOLD, MAX_THRESHOLD)
        self._tu_center.setSingleStep(0.05)
        self._tu_center.setDecimals(2)
        self._tu_center.setValue(DEFAULT_CENTER_RATIO)
        self._tu_threshold = QDoubleSpinBox()
        self._tu_threshold.setRange(MIN_THRESHOLD, MAX_THRESHOLD)
        self._tu_threshold.setSingleStep(0.05)
        self._tu_threshold.setDecimals(2)
        self._tu_threshold.setValue(DEFAULT_TU_THRESHOLD)
        self._tu_window = QSpinBox()
        self._tu_window.setRange(MIN_WINDOW_SIZE, MAX_WINDOW_SIZE)
        self._tu_window.setSingleStep(2)
        self._tu_window.setValue(DEFAULT_TU_WINDOW_SIZE)
        form.addRow("First frame:", self._tu_first)
        form.addRow("Last frame (-1 = last):", self._tu_last)
        form.addRow("UFOV ratio:", self._tu_ufov)
        form.addRow("CFOV ratio:", self._tu_cfov)
        form.addRow("Center ratio:", self._tu_center)
        form.addRow("Threshold (fraction of mean):", self._tu_threshold)
        form.addRow("Differential window (px):", self._tu_window)
        return page

    def _ratio_spin(self, value: float) -> QDoubleSpinBox:
        spin = QDoubleSpinBox()
        spin.setRange(MIN_FOV_RATIO, MAX_FOV_RATIO)
        spin.setSingleStep(0.01)
        spin.setDecimals(2)
        spin.setValue(value)
        return spin

    def _build_tomo_contrast_page(self) -> QWidget:
        page = QWidget()
        form = QFormLayout(page)
        # One row per sphere: diameter (mm) and angle (deg).
        self._sphere_diameters = []
        self._sphere_angles = []
        for i, (diam, angle) in enumerate(
            zip(DEFAULT_SPHERE_DIAMETERS_MM, DEFAULT_SPHERE_ANGLES, strict=False), start=1
        ):
            d_spin = QDoubleSpinBox()
            d_spin.setRange(MIN_SPHERE_DIAMETER_MM, MAX_SPHERE_DIAMETER_MM)
            d_spin.setSingleStep(0.1)
            d_spin.setDecimals(1)
            d_spin.setValue(float(diam))
            a_spin = QDoubleSpinBox()
            a_spin.setRange(MIN_SPHERE_ANGLE_DEG, MAX_SPHERE_ANGLE_DEG)
            a_spin.setSingleStep(1.0)
            a_spin.setDecimals(1)
            a_spin.setValue(float(angle))
            self._sphere_diameters.append(d_spin)
            self._sphere_angles.append(a_spin)
            row = QHBoxLayout()
            row.addWidget(QLabel("Ø"))
            row.addWidget(d_spin)
            row.addWidget(QLabel("∠"))
            row.addWidget(a_spin)
            holder = QWidget()
            holder.setLayout(row)
            form.addRow(f"Sphere {i} (mm / deg):", holder)
        self._tc_ufov = self._ratio_spin(DEFAULT_TC_UFOV_RATIO)
        self._tc_search_window = QSpinBox()
        self._tc_search_window.setRange(MIN_SEARCH_WINDOW_PX, MAX_SEARCH_WINDOW_PX)
        self._tc_search_window.setValue(DEFAULT_SEARCH_WINDOW_PX)
        self._tc_search_slices = QSpinBox()
        self._tc_search_slices.setRange(MIN_SEARCH_SLICES, MAX_SEARCH_SLICES)
        self._tc_search_slices.setValue(DEFAULT_SEARCH_SLICES)
        form.addRow("UFOV ratio:", self._tc_ufov)
        form.addRow("Search window (px):", self._tc_search_window)
        form.addRow("Search slices:", self._tc_search_slices)
        return page

    def _build_simple_sensitivity_page(self) -> QWidget:
        page = QWidget()
        form = QFormLayout(page)
        self._activity = QDoubleSpinBox()
        self._activity.setRange(MIN_ACTIVITY_MBQ, MAX_ACTIVITY_MBQ)
        self._activity.setSingleStep(1.0)
        self._activity.setDecimals(3)
        self._activity.setValue(DEFAULT_ACTIVITY_MBQ)
        self._nuclide = QComboBox()
        for name in NUCLIDE_NAMES:
            self._nuclide.addItem(name, name)
        self._nuclide.setCurrentText(DEFAULT_NUCLIDE)
        # Optional background image picker.
        self._background_path: str | None = None
        self._background_label = QLabel("(none)")
        self._background_label.setWordWrap(True)
        choose = QPushButton("Choose…")
        choose.clicked.connect(self._choose_background)
        bg_row = QHBoxLayout()
        bg_row.addWidget(self._background_label, 1)
        bg_row.addWidget(choose)
        bg_holder = QWidget()
        bg_holder.setLayout(bg_row)
        form.addRow("Administered activity (MBq):", self._activity)
        form.addRow("Nuclide:", self._nuclide)
        form.addRow("Background image (optional):", bg_holder)
        note = QLabel("Activity must be greater than 0. Background is optional.")
        note.setWordWrap(True)
        form.addRow(note)
        return page

    def _choose_background(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Choose background DICOM", "", "DICOM Files (*.dcm);;All Files (*)"
        )
        if path:
            self._background_path = path
            self._background_label.setText(os.path.basename(path))

    def get_options(self) -> NuclearOptions:
        """Return the per-class options dataclass for the selected test."""
        cls = str(self._test.currentData())
        if cls == FOUR_BAR_RESOLUTION_CLASS:
            return FourBarResolutionOptions(
                separation_mm=float(self._separation.value()),
                roi_width_mm=float(self._roi_width.value()),
            )
        if cls == QUADRANT_RESOLUTION_CLASS:
            return QuadrantResolutionOptions(
                bar_widths_mm=tuple(float(s.value()) for s in self._bar_widths),
                roi_diameter_mm=float(self._roi_diameter.value()),
                distance_from_center_mm=float(self._distance.value()),
            )
        if cls == CENTER_OF_ROTATION_CLASS:
            return CenterOfRotationOptions()
        if cls == TOMOGRAPHIC_RESOLUTION_CLASS:
            return TomographicResolutionOptions()
        if cls == MAX_COUNT_RATE_CLASS:
            return MaxCountRateOptions(frame_duration=float(self._frame_duration.value()))
        if cls == TOMOGRAPHIC_UNIFORMITY_CLASS:
            return TomographicUniformityOptions(
                first_frame=int(self._tu_first.value()),
                last_frame=int(self._tu_last.value()),
                ufov_ratio=float(self._tu_ufov.value()),
                cfov_ratio=float(self._tu_cfov.value()),
                center_ratio=float(self._tu_center.value()),
                threshold=float(self._tu_threshold.value()),
                window_size=int(self._tu_window.value()),
            )
        if cls == TOMOGRAPHIC_CONTRAST_CLASS:
            return TomographicContrastOptions(
                sphere_diameters_mm=tuple(float(s.value()) for s in self._sphere_diameters),
                sphere_angles=tuple(float(s.value()) for s in self._sphere_angles),
                ufov_ratio=float(self._tc_ufov.value()),
                search_window_px=int(self._tc_search_window.value()),
                search_slices=int(self._tc_search_slices.value()),
            )
        if cls == SIMPLE_SENSITIVITY_CLASS:
            return SimpleSensitivityOptions(
                activity_mbq=float(self._activity.value()),
                nuclide=str(self._nuclide.currentData()),
                background_path=self._background_path,
            )
        return PlanarUniformityOptions(
            ufov_ratio=float(self._ufov.value()),
            cfov_ratio=float(self._cfov.value()),
            window_size=int(self._window.value()),
            threshold=float(self._threshold.value()),
        )


def prompt_nuclear_options(
    parent: QWidget | None = None,
) -> NuclearOptions | None:
    """
    Show the modal nuclear QC options dialog.

    Returns:
        A configured ``NuclearOptions`` subclass, or ``None`` if cancelled.
    """
    dlg = NuclearQaOptionsDialog(parent)
    dlg.activateWindow()
    dlg.raise_()
    if dlg.exec() != int(QDialog.DialogCode.Accepted):
        return None
    return dlg.get_options()
