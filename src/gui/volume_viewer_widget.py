"""
Volume Viewer Widget

QWidget wrapping a ``QVTKRenderWindowInteractor`` for 3D volume rendering
with a control panel for preset selection, global opacity, window/level,
and camera reset.

Inputs:
    - ``VolumeRenderer`` instance (from ``core.volume_renderer``).

Outputs:
    - Interactive 3D viewport with controls.

Requirements:
    - PySide6
    - VTK >= 9.3.0 (``vtkmodules.qt.QVTKRenderWindowInteractor``)
"""

from __future__ import annotations

# Control widgets are built in ``_build_controls`` helpers called from
# ``__init__``/``_setup_ui`` (Qt builder pattern) rather than assigned directly in
# ``__init__`` — same convention as ``main.py`` / ``image_viewer_view.py``.
# pyright: reportUninitializedInstanceVariable=false
import logging
from typing import Any, ClassVar, cast

from PySide6.QtCore import Qt, QTimer, QUrl
from PySide6.QtGui import QDesktopServices, QStandardItemModel
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from core.volume_3d_user_presets import (
    KEY_BACKGROUND,
    KEY_BASE_PRESET,
    KEY_LEVEL,
    KEY_NAME,
    KEY_OPACITY,
    KEY_QUALITY,
    KEY_THRESHOLD,
    KEY_WINDOW,
    builtin_preset_by_name,
    builtin_preset_names,
    normalize_user_presets,
    snapshot_current_settings,
    upsert_user_preset,
)
from core.volume_opacity_model import (
    RESPONSE_NEUTRAL,
    SLIDER_MAX,
    opacity_to_percent,
    opacity_to_slider,
    percent_to_opacity,
    response_to_gamma,
    slider_to_opacity,
)
from core.volume_renderer import (
    BACKGROUND_COLORS,
    BLEND_MODES,
    BUILTIN_PRESETS,
    PRESET_GROUPS,
    QUALITY_MODES,
    RENDER_METHODS,
    TransferFunctionPreset,
    VolumeRenderer,
    get_default_preset_for_modality,
    is_steep_preset,
    scalar_domain_label,
    vtk_mod,
)
from gui.volume.overlay_text import build_overlay_text
from utils.debug_flags import DEBUG_VOLUME_3D
from utils.doc_urls import user_doc_url

_log = logging.getLogger(__name__)

# Opaque chip behind overlay text (sibling QLabel on viewport_container).
# Transparent QLabel-on-QVTK caused ghosting; VTK text caused volume glyph mask.
_OVERLAY_LABEL_STYLE = (
    "color: rgb(220, 220, 220); "
    "background-color: rgba(0, 0, 0, 180); "
    "border-radius: 4px; "
    "padding: 4px 6px; "
    "font-family: 'Courier New', monospace; "
    "font-size: 11px;"
)


class VolumeViewerWidget(QWidget):
    """
    3D volume rendering viewport with interactive controls.

    Embeds a ``QVTKRenderWindowInteractor`` for VTK rendering and provides
    a side panel with preset selection, opacity slider, W/L controls, and
    a camera reset button.
    """

    def __init__(
        self,
        renderer: VolumeRenderer,
        parent: QWidget | None = None,
        config_manager: Any = None,
    ) -> None:
        super().__init__(parent)
        self._renderer = renderer
        self._config_manager = config_manager
        self._user_presets: list[dict[str, Any]] = []
        self._interactor: Any = None
        self._vtk_render_window: Any = None
        self._viewport_container: QWidget | None = None
        self._overlay_label: QLabel | None = None
        self._overlay_text_prev: str = ""
        self._initialized = False
        self._render_timer = QTimer(self)
        self._render_timer.setSingleShot(True)
        self._render_timer.setInterval(80)
        self._render_timer.timeout.connect(self._render)
        self._setup_ui()

    # ------------------------------------------------------------------
    # UI setup
    # ------------------------------------------------------------------

    def _setup_ui(self) -> None:
        """Build the layout: VTK viewport on the left, controls on the right."""
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # VTK viewport.
        from vtkmodules.qt.QVTKRenderWindowInteractor import QVTKRenderWindowInteractor

        self._viewport_container = QWidget(self)
        self._viewport_container.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        container_layout = QVBoxLayout(self._viewport_container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(0)

        self._interactor = QVTKRenderWindowInteractor(self._viewport_container)
        self._vtk_render_window = self._interactor.GetRenderWindow()
        self._vtk_render_window.AddRenderer(self._renderer.get_renderer())

        container_layout.addWidget(self._interactor)

        # Viewport text overlay — Qt QLabel sibling of QVTK (parent =
        # viewport_container), NOT a child of the native GL interactor.
        # VTK vtkCornerAnnotation / vtkTextActor (even on layer 1) reintroduced
        # glyph texture bleed into the GPU volume pass on Parallels/software GL.
        # Transparent QLabel-on-interactor caused ghosting when text shrank.
        self._overlay_label = QLabel(self._viewport_container)
        self._overlay_label.setStyleSheet(_OVERLAY_LABEL_STYLE)
        self._overlay_label.setAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents, True
        )
        self._overlay_label.move(8, 6)
        self._overlay_label.show()

        # Trackball camera interaction style.
        style = vtk_mod.vtkInteractorStyleTrackballCamera()
        self._interactor.SetInteractorStyle(style)

        main_layout.addWidget(self._viewport_container, stretch=1)

        # Control panel.
        controls = self._build_controls()
        main_layout.addWidget(controls, stretch=0)

    def _build_controls(self) -> QWidget:
        """Build the right-side control panel with progressive disclosure.

        Layout hierarchy (matching plan T2/S1 and the Slicer-style pattern):
          Quick:    Preset, Opacity, Window/Level, Threshold, View buttons
          Appearance: Contrast depth, Background
          Advanced: Render status readout (hidden by default)
        The whole panel is wrapped in a QScrollArea so it remains usable on
        short or narrow screens (T6).
        """
        # Outer wrapper — scrollable so nothing is clipped at 1280×720.
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setFixedWidth(240)

        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        # ── Interaction help strip (T4) ──────────────────────────────────
        help_strip = QLabel(
            "Rotate: left-drag  Zoom: right-drag/scroll  Pan: mid-drag\n"
            "Keys: R=reset  1-6=views  A=auto-rotate  +/-=opacity  [/]=preset",
            panel,
        )
        help_strip.setWordWrap(True)
        help_strip.setStyleSheet(
            "color: palette(mid); font-size: 10px; padding: 2px 4px;"
        )
        help_strip.setToolTip(
            "Mouse and keyboard shortcuts for the 3D viewport.\n\n"
            "Mouse: Left-drag=Rotate, Right-drag/Scroll=Zoom, Middle-drag=Pan\n"
            "Keys: R or Space=reset view, 1-6=standard views (A/P/L/R/S/I),\n"
            "A=auto-rotate toggle, +/-=opacity ±5%, [/]=step through presets,\n"
            "F=fit/zoom to volume"
        )
        layout.addWidget(help_strip)

        # ── QUICK CONTROLS ──────────────────────────────────────────────

        # Preset selector.
        preset_group = QGroupBox("Preset", panel)
        preset_layout = QVBoxLayout(preset_group)

        self._preset_combo = QComboBox(preset_group)
        self._preset_combo.setToolTip(
            "Transfer-function preset: defines the opacity and colour mapping "
            "from scalar values to the rendered appearance. Built-in presets "
            "are grouped by modality; saved user presets appear below."
        )
        self._preset_combo.currentIndexChanged.connect(self._on_preset_changed)
        preset_layout.addWidget(self._preset_combo)

        self._save_preset_btn = QPushButton("Save Preset…", preset_group)
        self._save_preset_btn.setToolTip(
            "Save the current preset, opacity, window/level, and threshold as "
            "a named user preset for later recall."
        )
        self._save_preset_btn.clicked.connect(self._on_save_preset)
        preset_layout.addWidget(self._save_preset_btn)

        # Honest scalar-domain readout (T0 / T3).
        self._scalar_domain_label = QLabel("", preset_group)
        self._scalar_domain_label.setWordWrap(True)
        self._scalar_domain_label.setStyleSheet("color: palette(mid); font-size: 11px;")
        self._scalar_domain_label.setToolTip(
            "The scalar domain the renderer is operating on.  CT presets use "
            "HU-like thresholds, but the 3D path currently renders raw stored "
            "pixel values (rescale slope/intercept is not applied), so values "
            "are not true calibrated HU.  Non-CT modalities show their own "
            "domain label."
        )
        preset_layout.addWidget(self._scalar_domain_label)
        layout.addWidget(preset_group)

        # Opacity (T8 perceptual slider + spinbox).
        opacity_group = QGroupBox("Opacity", panel)
        opacity_group.setToolTip(
            "Overall transparency of the rendered volume.\n\n"
            "The slider uses a perceptual response: most of its travel covers "
            "low opacity where small changes are visible (the 0–10% band "
            "occupies roughly 30–40% of slider travel).  The spinbox shows "
            "the resolved percent and allows direct sub-percent entry.\n\n"
            "This is different from the transfer-function opacity (which maps "
            "scalar values to per-voxel opacity) and from contrast depth (which "
            "reshapes that curve)."
        )
        opacity_layout = QVBoxLayout(opacity_group)

        self._opacity_slider = QSlider(Qt.Orientation.Horizontal, opacity_group)
        self._opacity_slider.setRange(0, SLIDER_MAX)
        self._opacity_slider.setValue(SLIDER_MAX)
        self._opacity_slider.valueChanged.connect(self._on_opacity_slider_changed)
        opacity_layout.addWidget(self._opacity_slider)

        spin_row = QHBoxLayout()
        spin_row.addWidget(QLabel("Opacity %:", opacity_group))
        self._opacity_spin = QDoubleSpinBox(opacity_group)
        self._opacity_spin.setRange(0.0, 100.0)
        self._opacity_spin.setDecimals(1)
        self._opacity_spin.setSingleStep(0.5)
        self._opacity_spin.setValue(100.0)
        self._opacity_spin.setToolTip(
            "Resolved opacity percent (0–100).  Sub-percent steps are "
            "available for fine control at low opacity."
        )
        self._opacity_spin.valueChanged.connect(self._on_opacity_spin_changed)
        spin_row.addWidget(self._opacity_spin)
        opacity_layout.addLayout(spin_row)
        layout.addWidget(opacity_group)

        # Window / Level (T1A true scaling) — sliders + spinboxes.
        wl_group = QGroupBox("Window / Level", panel)
        wl_group.setToolTip(
            "Window scales the transfer-function width: narrower = sharper "
            "contrast over a smaller value range; wider spreads it out.  Level "
            "recenters the transfer function along the scalar axis.\n\n"
            "Values are in the scalar units shown under the preset (raw pixel "
            "values for CT, not calibrated HU).\n\n"
            "When you select a new built-in preset, Window and Level reset to "
            "that preset’s natural range."
        )
        wl_layout = QVBoxLayout(wl_group)

        # Window row: label + slider + spinbox.
        wl_layout.addWidget(QLabel("Window:", wl_group))
        self._window_slider = QSlider(Qt.Orientation.Horizontal, wl_group)
        self._window_slider.setRange(1, 10000)
        self._window_slider.setValue(2000)
        self._window_slider.setSingleStep(10)
        self._window_slider.setPageStep(100)
        self._window_slider.setToolTip(
            "Transfer-function width in scalar units. Narrower = sharper "
            "contrast.  Setting it back to the preset’s natural width "
            "reproduces the original preset."
        )
        wl_layout.addWidget(self._window_slider)
        self._window_spin = QDoubleSpinBox(wl_group)
        self._window_spin.setRange(1.0, 10000.0)
        self._window_spin.setValue(2000.0)
        self._window_spin.setSingleStep(50.0)
        wl_layout.addWidget(self._window_spin)

        # Level row: label + slider + spinbox.
        wl_layout.addWidget(QLabel("Level:", wl_group))
        self._level_slider = QSlider(Qt.Orientation.Horizontal, wl_group)
        self._level_slider.setRange(-5000, 5000)
        self._level_slider.setValue(0)
        self._level_slider.setSingleStep(10)
        self._level_slider.setPageStep(100)
        self._level_slider.setToolTip(
            "Transfer-function center.  Shifts which scalar values appear "
            "brightest / most opaque."
        )
        wl_layout.addWidget(self._level_slider)
        self._level_spin = QDoubleSpinBox(wl_group)
        self._level_spin.setRange(-10000.0, 10000.0)
        self._level_spin.setValue(0.0)
        self._level_spin.setSingleStep(50.0)
        wl_layout.addWidget(self._level_spin)

        self._reset_wl_btn = QPushButton("Reset W/L", wl_group)
        self._reset_wl_btn.setToolTip(
            "Restore Window and Level to the current preset's natural range "
            "without changing opacity, threshold, background, or quality."
        )
        self._reset_wl_btn.clicked.connect(self._on_reset_window_level)
        wl_layout.addWidget(self._reset_wl_btn)

        # Connect sliders and spinboxes — bidirectional sync.
        self._window_slider.valueChanged.connect(self._on_window_slider_changed)
        self._window_spin.valueChanged.connect(self._on_window_spin_changed)
        self._level_slider.valueChanged.connect(self._on_level_slider_changed)
        self._level_spin.valueChanged.connect(self._on_level_spin_changed)
        layout.addWidget(wl_group)

        # Threshold.
        threshold_group = QGroupBox("Threshold", panel)
        threshold_group.setToolTip(
            "Shifts opacity onset along the scalar axis (−500 to +500).\n\n"
            "Positive values hide more low-density material; negative values "
            "reveal more.  This acts as an additive offset on top of the "
            "Window/Level position.  Resets to 0 when you pick a new built-in "
            "preset."
        )
        threshold_layout = QVBoxLayout(threshold_group)

        self._threshold_slider = QSlider(Qt.Orientation.Horizontal, threshold_group)
        self._threshold_slider.setRange(-500, 500)
        self._threshold_slider.setValue(0)
        self._threshold_slider.setSingleStep(10)
        self._threshold_slider.setPageStep(50)
        self._threshold_slider.setTickInterval(100)
        self._threshold_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self._threshold_slider.valueChanged.connect(self._on_threshold_changed)

        self._threshold_label = QLabel("0", threshold_group)
        self._threshold_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        threshold_layout.addWidget(self._threshold_slider)
        threshold_layout.addWidget(self._threshold_label)
        layout.addWidget(threshold_group)

        # Blend mode — fundamental rendering mode (Composite vs MIP vs MinIP).
        blend_row = QHBoxLayout()
        blend_row.addWidget(QLabel("Render mode:", panel))
        self._blend_mode_combo = QComboBox(panel)
        for name, _suffix in BLEND_MODES:
            self._blend_mode_combo.addItem(name)
        self._blend_mode_combo.setToolTip(
            "Composite: standard semi-transparent volume rendering (default).\n"
            "Max Intensity (MIP): the brightest voxel along each ray wins — "
            "useful for CT angiography and lung nodule review.\n"
            "Min Intensity (MinIP): the darkest voxel wins — useful for "
            "airways and low-attenuation structures."
        )
        self._blend_mode_combo.currentIndexChanged.connect(self._on_blend_mode_changed)
        blend_row.addWidget(self._blend_mode_combo)
        layout.addLayout(blend_row)

        # ── VIEW ─────────────────────────────────────────────────────────

        view_row = QHBoxLayout()
        self._reset_camera_btn = QPushButton("Reset View", panel)
        self._reset_camera_btn.setToolTip(
            "Return to the default anterior view with the patient’s head "
            "toward the top of the screen.  The camera is re-framed to fit "
            "the full volume."
        )
        self._reset_camera_btn.clicked.connect(self._on_reset_camera)
        view_row.addWidget(self._reset_camera_btn)

        self._help_btn = QPushButton("Help…", panel)
        self._help_btn.setToolTip(
            "Open the 3D volume rendering user guide (controls and how it works)."
        )
        self._help_btn.clicked.connect(self._on_open_documentation)
        view_row.addWidget(self._help_btn)
        layout.addLayout(view_row)

        view_grid = QGridLayout()
        view_grid.setSpacing(4)
        view_buttons = [
            ("A", "Anterior", "View from the patient's anterior side."),
            ("P", "Posterior", "View from the patient's posterior side."),
            ("L", "Left", "View from the patient's left side."),
            ("R", "Right", "View from the patient's right side."),
            ("S", "Superior", "View from above the patient's head."),
            ("I", "Inferior", "View from below the patient's feet."),
        ]
        for index, (label, view_name, tooltip) in enumerate(view_buttons):
            btn = QPushButton(label, panel)
            btn.setFixedSize(32, 28)
            btn.setToolTip(tooltip)
            btn.clicked.connect(
                lambda _checked=False, name=view_name: self._on_set_view(name)
            )
            view_grid.addWidget(btn, index // 3, index % 3)
        layout.addLayout(view_grid)

        # Auto-rotate toggle (S2).
        self._auto_rotate_btn = QPushButton("Auto-Rotate", panel)
        self._auto_rotate_btn.setCheckable(True)
        self._auto_rotate_btn.setToolTip(
            "Slowly rotate the volume around the vertical axis.  "
            "Stops when you interact with the viewport or click again."
        )
        self._auto_rotate_btn.toggled.connect(self._on_auto_rotate_toggled)
        layout.addWidget(self._auto_rotate_btn)

        self._auto_rotate_timer = QTimer(self)
        self._auto_rotate_timer.setInterval(33)  # ~30 fps
        self._auto_rotate_timer.timeout.connect(self._auto_rotate_step)

        # ── APPEARANCE ───────────────────────────────────────────────────

        appearance_group = QGroupBox("Appearance", panel)
        appearance_layout = QVBoxLayout(appearance_group)

        appearance_layout.addWidget(QLabel("Contrast depth:", appearance_group))
        self._response_slider = QSlider(Qt.Orientation.Horizontal, appearance_group)
        self._response_slider.setRange(0, 100)
        self._response_slider.setValue(RESPONSE_NEUTRAL)
        self._response_slider.setTickInterval(25)
        self._response_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self._response_slider.setToolTip(
            "Reshapes the transfer-function opacity curve independently of the "
            "global opacity multiplier.\n\n"
            "• Center (50): preset curve unchanged.\n"
            "• Lower: reveals faint material (exponent < 1 lifts low "
            "opacity values).\n"
            "• Higher: deepens contrast (exponent > 1 suppresses low "
            "opacity, making dense/internal structures stand out).\n\n"
            "This is different from global opacity (which multiplies all "
            "values equally) and from Window/Level (which repositions the "
            "curve along the scalar axis)."
        )
        self._response_slider.valueChanged.connect(self._on_response_changed)
        appearance_layout.addWidget(self._response_slider)

        # Display-only Gaussian smoothing (T21).
        smooth_row = QHBoxLayout()
        smooth_row.addWidget(QLabel("Smoothing:", appearance_group))
        self._smoothing_spin = QDoubleSpinBox(appearance_group)
        self._smoothing_spin.setRange(0.0, 3.0)
        self._smoothing_spin.setDecimals(1)
        self._smoothing_spin.setSingleStep(0.1)
        self._smoothing_spin.setValue(0.0)
        self._smoothing_spin.setToolTip(
            "Display-only Gaussian smoothing (sigma in voxels).  Reduces "
            "salt-and-pepper graininess on thin-slice or noisy CT.  "
            "0 = off; 0.5–1.0 = mild; 1.5–2.0 = heavy.\n\n"
            "Applied as a VTK filter to the render copy only — does not "
            "modify source DICOM data."
        )
        self._smoothing_spin.valueChanged.connect(self._on_smoothing_changed)
        smooth_row.addWidget(self._smoothing_spin)
        appearance_layout.addLayout(smooth_row)

        # Detail / oversampling (T7B) — single control for ray sample distance.
        # Merges the former Quality combo, an oversampling control, and the
        # per-preset auto-fineness into one slider + Auto checkbox.
        detail_header = QHBoxLayout()
        self._detail_caption = QLabel("Detail:", appearance_group)
        detail_header.addWidget(self._detail_caption)
        self._detail_auto_cb = QCheckBox("Auto", appearance_group)
        self._detail_auto_cb.setChecked(True)
        self._detail_auto_cb.setToolTip(
            "When on, the Detail level is chosen automatically from the "
            "preset: steep, narrow-band presets (e.g. CT Fat) use finer "
            "sampling to suppress wood-grain / Moiré rings; gentle presets "
            "use normal sampling for speed.  Moving the slider switches to "
            "manual."
        )
        self._detail_auto_cb.stateChanged.connect(self._on_detail_auto_changed)
        detail_header.addStretch()
        detail_header.addWidget(self._detail_auto_cb)
        appearance_layout.addLayout(detail_header)

        self._detail_slider = QSlider(Qt.Orientation.Horizontal, appearance_group)
        self._detail_slider.setRange(0, len(QUALITY_MODES) - 1)
        self._detail_slider.setValue(1)  # Normal
        self._detail_slider.setSingleStep(1)
        self._detail_slider.setPageStep(1)
        self._detail_slider.setTickInterval(1)
        self._detail_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self._detail_slider.setToolTip(
            "Rendering detail = ray sample distance, the main control for "
            "wood-grain / Moiré rings.\n\n"
            "Left (Fast) = coarse sampling, quickest; Right (Ultra) = finest "
            "sampling, cleanest but slowest.  Finer detail reduces ring "
            "artifacts, especially with steep presets.  This is different from "
            "Smoothing (which pre-blurs the data) and Contrast depth."
        )
        self._detail_slider.valueChanged.connect(self._on_detail_changed)
        appearance_layout.addWidget(self._detail_slider)

        bg_row = QHBoxLayout()
        bg_row.addWidget(QLabel("Background:", appearance_group))
        self._background_combo = QComboBox(appearance_group)
        for name, _rgb in BACKGROUND_COLORS:
            self._background_combo.addItem(name)
        self._background_combo.setToolTip("Viewport background colour.")
        self._background_combo.currentIndexChanged.connect(self._on_background_changed)
        bg_row.addWidget(self._background_combo)
        appearance_layout.addLayout(bg_row)

        # Lighting presets (T4).
        light_row = QHBoxLayout()
        light_row.addWidget(QLabel("Lighting:", appearance_group))
        self._lighting_combo = QComboBox(appearance_group)
        self._lighting_combo.addItems(["Default", "Flat", "Cinematic"])
        self._lighting_combo.setToolTip(
            "Default: balanced shading (ambient 0.3, diffuse 0.7, specular 0.2).\n"
            "Flat: uniform brightness, no specular highlights (good for seeing "
            "all regions equally).\n"
            "Cinematic: dramatic depth with strong specular highlights."
        )
        self._lighting_combo.currentIndexChanged.connect(self._on_lighting_changed)
        light_row.addWidget(self._lighting_combo)
        appearance_layout.addLayout(light_row)

        # Overlay toggle (T5).
        self._overlay_cb = QCheckBox("Show overlay", appearance_group)
        self._overlay_cb.setChecked(True)
        self._overlay_cb.setToolTip(
            "Show preset name, opacity, and quality mode in the viewport corner."
        )
        self._overlay_cb.stateChanged.connect(self._on_overlay_toggled)
        appearance_layout.addWidget(self._overlay_cb)

        layout.addWidget(appearance_group)

        # ── ADVANCED (collapsed by default) ──────────────────────────────

        self._advanced_toggle_btn = QPushButton("Advanced ▶", panel)
        self._advanced_toggle_btn.setFlat(True)
        self._advanced_toggle_btn.setToolTip("Show or hide advanced render status.")
        self._advanced_toggle_btn.clicked.connect(self._on_toggle_advanced)
        layout.addWidget(self._advanced_toggle_btn)

        self._advanced_group = QGroupBox(panel)
        self._advanced_group.setFlat(True)
        self._advanced_group.setVisible(False)
        advanced_layout = QVBoxLayout(self._advanced_group)
        advanced_layout.setContentsMargins(4, 4, 4, 4)

        # Render method (T22).
        rm_row = QHBoxLayout()
        rm_row.addWidget(QLabel("Render:", self._advanced_group))
        self._render_method_combo = QComboBox(self._advanced_group)
        for method in RENDER_METHODS:
            self._render_method_combo.addItem(method)
        self._render_method_combo.setToolTip(
            "Rendering backend.  Auto lets VTK decide (recommended); GPU "
            "forces GPU acceleration; CPU forces software ray casting."
        )
        self._render_method_combo.currentIndexChanged.connect(
            self._on_render_method_changed
        )
        rm_row.addWidget(self._render_method_combo)
        advanced_layout.addLayout(rm_row)

        # 1D transfer-function editor (T13).
        from gui.transfer_function_editor_widget import TransferFunctionEditorWidget
        advanced_layout.addWidget(QLabel("Opacity curve:", self._advanced_group))
        self._tf_editor = TransferFunctionEditorWidget(self._advanced_group)
        self._tf_editor.setToolTip(
            "Drag control points to reshape the opacity ramp.  Horizontal = "
            "scalar value, vertical = opacity (0 at bottom, 1 at top).  "
            "Endpoint scalar positions are locked; inner points can be moved "
            "freely.  Changes apply to the current preset."
        )
        self._tf_editor.points_changed.connect(self._on_tf_points_changed)
        advanced_layout.addWidget(self._tf_editor)

        # Gradient opacity toggle (T14).
        self._gradient_opacity_cb = QCheckBox(
            "Gradient opacity", self._advanced_group
        )
        self._gradient_opacity_cb.setToolTip(
            "Suppresses regions with low gradient magnitude (smooth/uniform "
            "tissue) so only voxels at tissue boundaries remain visible.  "
            "Adjust the strength slider below to avoid the volume going black "
            "on smooth data."
        )
        self._gradient_opacity_cb.stateChanged.connect(
            self._on_gradient_opacity_changed
        )
        advanced_layout.addWidget(self._gradient_opacity_cb)

        # Gradient opacity strength slider — shown always so user can pre-set
        # it before enabling the checkbox on unknown data.
        go_strength_row = QHBoxLayout()
        go_strength_row.addWidget(QLabel("  Strength:", self._advanced_group))
        self._go_strength_slider = QSlider(
            Qt.Orientation.Horizontal, self._advanced_group
        )
        self._go_strength_slider.setRange(0, 100)
        self._go_strength_slider.setValue(50)  # 50% blend — safe default
        self._go_strength_slider.setToolTip(
            "Blends the gradient opacity curve with a flat 1.0:\n"
            "  0%: no surface enhancement (gradient opacity has no effect)\n"
            " 50%: moderate — uniform regions keep 50 % of their opacity\n"
            "100%: full curve — uniform regions can approach opacity 0 on "
            "smooth volumes.\n\n"
            "If enabling gradient opacity turns the volume black, reduce "
            "strength first."
        )
        self._go_strength_slider.valueChanged.connect(self._on_go_strength_changed)
        go_strength_row.addWidget(self._go_strength_slider)
        advanced_layout.addLayout(go_strength_row)

        # Nearest-neighbour interpolation toggle.
        self._nearest_interp_cb = QCheckBox(
            "Nearest-neighbour", self._advanced_group
        )
        self._nearest_interp_cb.setToolTip(
            "Use nearest-neighbour voxel interpolation instead of linear.  "
            "Faster but produces blockier, less smooth renders."
        )
        self._nearest_interp_cb.stateChanged.connect(
            self._on_interpolation_changed
        )
        advanced_layout.addWidget(self._nearest_interp_cb)

        # SSAO toggle (S1/T3).
        self._ssao_cb = QCheckBox("Ambient occlusion", self._advanced_group)
        self._ssao_cb.setToolTip(
            "Screen-Space Ambient Occlusion (experimental).  Darkens "
            "crevices and concave regions to add depth perception.  "
            "Requires OpenGL 3.3+; effect on volume rendering may vary by GPU."
        )
        self._ssao_cb.setEnabled(self._renderer.is_ssao_available())
        self._ssao_cb.stateChanged.connect(self._on_ssao_changed)
        advanced_layout.addWidget(self._ssao_cb)

        # Crop box toggle (T26).
        crop_row = QHBoxLayout()
        self._crop_cb = QCheckBox("Crop box", self._advanced_group)
        self._crop_cb.setToolTip(
            "Show an interactive crop box to hide regions outside the box.  "
            "Drag the faces of the box in the 3D viewport to resize.  "
            "This is visualization-only and does not modify the source DICOM data."
        )
        self._crop_cb.stateChanged.connect(self._on_crop_toggled)
        crop_row.addWidget(self._crop_cb)
        self._reset_crop_btn = QPushButton("Reset", self._advanced_group)
        self._reset_crop_btn.setToolTip("Remove the crop box and show the full volume.")
        self._reset_crop_btn.clicked.connect(self._on_reset_crop)
        self._reset_crop_btn.setEnabled(False)
        crop_row.addWidget(self._reset_crop_btn)
        advanced_layout.addLayout(crop_row)

        # Render status readout (T7).
        self._render_status_label = QLabel("", self._advanced_group)
        self._render_status_label.setWordWrap(True)
        self._render_status_label.setStyleSheet(
            "color: palette(mid); font-size: 11px;"
        )
        self._render_status_label.setToolTip(
            "Technical readout: render method, mapper mode, and volume "
            "dimensions.  Useful for diagnosing performance or GPU fallback "
            "issues."
        )
        advanced_layout.addWidget(self._render_status_label)
        layout.addWidget(self._advanced_group)

        layout.addStretch()
        scroll.setWidget(panel)
        return scroll

    # ------------------------------------------------------------------
    # Initialisation after volume is set
    # ------------------------------------------------------------------

    def initialize(self, modality: str = "", *, rescale_applied: bool = False) -> None:
        """
        Schedule VTK initialisation for after the widget is shown.

        The ``QVTKRenderWindowInteractor`` requires a valid native window
        handle before ``Initialize()`` can create its OpenGL context.
        We apply the appropriate preset (chosen from *modality*) immediately
        but defer the actual VTK init to ``showEvent`` / a single-shot timer
        so the OS has allocated the native window.

        Args:
            modality: DICOM Modality string (e.g. ``'CT'``, ``'MR'``).
                If ``'MR'`` or related, the MR Default preset is selected
                automatically.  Defaults to CT Bone for unknown/CT modalities.
            rescale_applied: ``True`` when VTK is receiving calibrated scalar
                values instead of raw stored pixel values.
        """
        self._scalar_domain_label.setText(
            scalar_domain_label(modality, rescale_applied=rescale_applied)
        )
        # Apply the default background (first entry) to the renderer.
        if BACKGROUND_COLORS:
            _name, (r, g, b) = BACKGROUND_COLORS[0]
            self._renderer.set_background(r, g, b)
        self._current_modality = (modality or "").upper().strip() or "GENERIC"
        if BUILTIN_PRESETS:
            # T6: try to restore the last-used preset for this modality.
            preset_index = self._load_last_preset_index()
            if preset_index is None:
                preset = get_default_preset_for_modality(modality)
                preset_index = next(
                    (i for i, p in enumerate(BUILTIN_PRESETS) if p is preset), 0
                )
            self._reload_user_presets()
            self._refresh_preset_combo(select_index=preset_index)
            self._apply_builtin_preset(BUILTIN_PRESETS[preset_index], sync_wl=True)
        self._update_overlay_text()
        if DEBUG_VOLUME_3D:
            print(
                f"[DEBUG-VOLUME-3D] initialize() called — modality={modality!r}  "
                f"rescale_applied={rescale_applied!r}  "
                f"deferring VTK init to showEvent."
            )

    def showEvent(self, event: Any) -> None:
        """Perform the real VTK initialisation once the widget is visible."""
        super().showEvent(event)
        if not self._initialized:
            # Defer one more event-loop tick so the native window handle
            # is fully realised (important on Windows).
            QTimer.singleShot(0, self._deferred_vtk_init)

    def _deferred_vtk_init(self) -> None:
        """Actually initialise the VTK interactor now that the window exists."""
        if self._initialized or self._interactor is None:
            return
        self._initialized = True
        if DEBUG_VOLUME_3D:
            rw = self._vtk_render_window
            print(f"[DEBUG-VOLUME-3D] _deferred_vtk_init — render window size: {rw.GetSize()}")
            print(f"[DEBUG-VOLUME-3D] interactor widget size: {self._interactor.width()}x{self._interactor.height()}")
        self._interactor.Initialize()
        # Progressive refinement: coarser sampling during interaction.
        # StartInteractionEvent / EndInteractionEvent are fired by the
        # interactor *style* (vtkInteractorStyleTrackballCamera), not by the
        # raw vtkRenderWindowInteractor.  Observing the raw interactor means
        # EndInteractionEvent is never reliably delivered, leaving the coarse
        # sample distance permanently set after the first drag.
        iren = self._interactor.GetRenderWindow().GetInteractor()
        if iren is not None:
            style = iren.GetInteractorStyle()
            if style is not None:
                style.AddObserver("StartInteractionEvent", self._on_interaction_start)
                style.AddObserver("EndInteractionEvent", self._on_interaction_end)
                if DEBUG_VOLUME_3D:
                    print(f"[DEBUG-VOLUME-3D] interaction observers on style: {style.GetClassName()}")
            else:
                # Fallback for non-trackball styles that forward events from iren.
                iren.AddObserver("StartInteractionEvent", self._on_interaction_start)
                iren.AddObserver("EndInteractionEvent", self._on_interaction_end)
                if DEBUG_VOLUME_3D:
                    print("[DEBUG-VOLUME-3D] interaction observers on raw interactor (no style)")

        # Keyboard shortcuts (S2).
        if iren is not None:
            iren.AddObserver("KeyPressEvent", self._on_key_press)

        self._renderer.reset_camera()
        self._vtk_render_window.Render()
        # Check if GPU rendering produced a blank frame and fall back to CPU.
        self._renderer.check_gpu_fallback(self._vtk_render_window)
        # Populate the render status readout now that we have live mapper info.
        self._update_render_status()
        if DEBUG_VOLUME_3D:
            ren = self._renderer.get_renderer()
            cam = ren.GetActiveCamera()
            print(f"[DEBUG-VOLUME-3D] camera position: {cam.GetPosition()}")
            print(f"[DEBUG-VOLUME-3D] camera focal point: {cam.GetFocalPoint()}")
            print(f"[DEBUG-VOLUME-3D] camera clipping range: {cam.GetClippingRange()}")
            print(f"[DEBUG-VOLUME-3D] renderer has {ren.GetVolumes().GetNumberOfItems()} volume(s)")
            print(f"[DEBUG-VOLUME-3D] render window size after render: {self._vtk_render_window.GetSize()}")
            # Check mapper render mode after first render.
            vols = ren.GetVolumes()
            vols.InitTraversal()
            vol = vols.GetNextVolume()
            if vol is not None:
                mapper = vol.GetMapper()
                print(f"[DEBUG-VOLUME-3D] mapper class: {mapper.GetClassName()}")
                if hasattr(mapper, 'GetLastUsedRenderMode'):
                    mode = mapper.GetLastUsedRenderMode()
                    print(f"[DEBUG-VOLUME-3D] mapper last used render mode: {mode}")
                bounds = vol.GetBounds()
                print(f"[DEBUG-VOLUME-3D] volume actor bounds: {bounds}")
                print(f"[DEBUG-VOLUME-3D] volume visibility: {vol.GetVisibility()}")
                prop = vol.GetProperty()
                print(f"[DEBUG-VOLUME-3D] shade: {prop.GetShade()}")
                print(f"[DEBUG-VOLUME-3D] ambient={prop.GetAmbient()} diffuse={prop.GetDiffuse()} specular={prop.GetSpecular()}")
            print("[DEBUG-VOLUME-3D] _deferred_vtk_init complete.")

        # First-paint guarantee: set the overlay text now so it is present
        # immediately on open (not only after the first control change).
        self._update_overlay_text()
        self._render_timer.start()

    # ------------------------------------------------------------------
    # Preset catalog (built-in + user-saved)
    # ------------------------------------------------------------------

    def _reload_user_presets(self) -> None:
        """Load user presets from config (no-op when config is unavailable)."""
        if self._config_manager is None or not hasattr(
            self._config_manager, "get_volume_3d_user_presets"
        ):
            self._user_presets = []
            return
        raw = self._config_manager.get_volume_3d_user_presets()
        self._user_presets = normalize_user_presets(raw)

    def _refresh_preset_combo(self, select_index: int = 0) -> None:
        """Rebuild the preset combo from built-ins (grouped by modality) plus
        saved user presets.

        Group headers are inserted as disabled separator items so the combo
        stays a flat index that maps 1:1 onto ``BUILTIN_PRESETS`` plus user
        presets; the mapping helpers (``_builtin_index_for_combo``,
        ``_combo_index_for_builtin``) account for the extra separator rows.
        """
        self._preset_combo.blockSignals(True)
        self._preset_combo.clear()
        self._combo_separator_rows: list[int] = []
        row = 0
        for group_name, group_presets in PRESET_GROUPS:
            # Separator / header row (disabled, non-selectable).
            self._preset_combo.addItem(f"— {group_name} —")
            model = cast(QStandardItemModel, self._preset_combo.model())
            item = model.item(row)
            if item is not None:
                item.setEnabled(False)
            self._combo_separator_rows.append(row)
            row += 1
            for preset in group_presets:
                self._preset_combo.addItem(f"  {preset.name}")
                row += 1
        # User presets section.
        if self._user_presets:
            self._preset_combo.addItem("— Saved —")
            model = cast(QStandardItemModel, self._preset_combo.model())
            item = model.item(row)
            if item is not None:
                item.setEnabled(False)
            self._combo_separator_rows.append(row)
            row += 1
            for user_preset in self._user_presets:
                self._preset_combo.addItem(f"  {user_preset[KEY_NAME]}")
                row += 1
        if self._preset_combo.count() > 0:
            combo_idx = self._combo_index_for_builtin(select_index)
            combo_idx = max(0, min(combo_idx, self._preset_combo.count() - 1))
            self._preset_combo.setCurrentIndex(combo_idx)
        self._preset_combo.blockSignals(False)

    def _builtin_index_for_combo(self, combo_index: int) -> int:
        """Map a combo-box row to a BUILTIN_PRESETS index (-1 if separator or user)."""
        offset = 0
        for sep in self._combo_separator_rows:
            if combo_index <= sep:
                break
            offset += 1
        logical = combo_index - offset
        if combo_index in self._combo_separator_rows:
            return -1
        if logical < 0 or logical >= len(BUILTIN_PRESETS) + len(self._user_presets):
            return -1
        return logical

    def _combo_index_for_builtin(self, builtin_index: int) -> int:
        """Map a BUILTIN_PRESETS index to the corresponding combo-box row."""
        target = builtin_index
        for sep in self._combo_separator_rows:
            if sep <= target:
                target += 1
            else:
                break
        return target

    def _current_logical_index(self) -> int:
        """Return the logical preset index (into BUILTIN_PRESETS + user list)
        for the current combo selection, or -1 for separators."""
        return self._builtin_index_for_combo(self._preset_combo.currentIndex())

    def _is_user_preset_logical(self, logical: int) -> bool:
        return logical >= len(BUILTIN_PRESETS)

    def _current_base_preset_name(self) -> str:
        logical = self._current_logical_index()
        if logical < 0:
            return BUILTIN_PRESETS[0].name if BUILTIN_PRESETS else ""
        if self._is_user_preset_logical(logical):
            user_idx = logical - len(BUILTIN_PRESETS)
            if 0 <= user_idx < len(self._user_presets):
                return self._user_presets[user_idx][KEY_BASE_PRESET]
        if 0 <= logical < len(BUILTIN_PRESETS):
            return BUILTIN_PRESETS[logical].name
        return BUILTIN_PRESETS[0].name if BUILTIN_PRESETS else ""

    _LAST_PRESET_CONFIG_KEY = "volume_3d_last_preset_by_modality"

    def _save_last_preset(self, preset_name: str) -> None:
        """Persist the last-used preset name for the current modality."""
        if self._config_manager is None or not hasattr(self._config_manager, "get"):
            return
        mod = getattr(self, "_current_modality", "GENERIC")
        stored = self._config_manager.get(self._LAST_PRESET_CONFIG_KEY) or {}
        if not isinstance(stored, dict):
            stored = {}
        stored[mod] = preset_name
        self._config_manager.set(self._LAST_PRESET_CONFIG_KEY, stored)
        if hasattr(self._config_manager, "save_config"):
            self._config_manager.save_config()

    def _load_last_preset_index(self) -> int | None:
        """Return the BUILTIN_PRESETS index for the remembered preset, or None."""
        if self._config_manager is None or not hasattr(self._config_manager, "get"):
            return None
        mod = getattr(self, "_current_modality", "GENERIC")
        stored = self._config_manager.get(self._LAST_PRESET_CONFIG_KEY)
        if not isinstance(stored, dict):
            return None
        name = stored.get(mod)
        if not name:
            return None
        for i, p in enumerate(BUILTIN_PRESETS):
            if p.name == name:
                return i
        return None

    def _apply_builtin_preset(
        self, preset: TransferFunctionPreset, *, sync_wl: bool
    ) -> None:
        """Apply a built-in transfer function and optionally sync W/L spinboxes."""
        self._renderer.set_preset(preset)
        if sync_wl:
            self._sync_wl_to_preset(preset)
        # Populate the TF editor if it exists.
        if hasattr(self, "_tf_editor"):
            self._tf_editor.set_points(list(preset.scalar_opacity))
        # Auto-select Detail (sample distance) from preset steepness when Auto
        # is on.  No-op when the user has taken manual control.  For saved user
        # presets the caller overrides this with the stored detail afterward.
        if hasattr(self, "_detail_auto_cb"):
            self._apply_auto_detail(preset)

    def _set_opacity_controls(self, resolved: float) -> None:
        """Sync the opacity slider + spinbox to a resolved opacity (no render)."""
        self._opacity_slider.blockSignals(True)
        self._opacity_spin.blockSignals(True)
        self._opacity_slider.setValue(opacity_to_slider(resolved))
        self._opacity_spin.setValue(round(opacity_to_percent(resolved), 1))
        self._opacity_spin.blockSignals(False)
        self._opacity_slider.blockSignals(False)

    def _apply_control_values(
        self,
        *,
        opacity: float,
        window: float,
        level: float,
        threshold: int,
    ) -> None:
        """Push opacity, W/L, and threshold controls into the renderer."""
        opacity = max(0.0, min(100.0, float(opacity)))
        threshold = max(-500, min(500, threshold))

        resolved = percent_to_opacity(opacity)
        self._set_opacity_controls(resolved)
        self._renderer.set_global_opacity(resolved)

        self._set_wl_controls(window, level)
        self._renderer.set_window_level(window, level)

        label = f"+{threshold}" if threshold > 0 else str(threshold)
        self._threshold_slider.blockSignals(True)
        self._threshold_slider.setValue(threshold)
        self._threshold_slider.blockSignals(False)
        self._threshold_label.setText(label)
        self._renderer.set_threshold(float(threshold))

    def _apply_user_preset(self, user_preset: dict[str, Any]) -> None:
        """Apply a saved user preset (base TF + control overrides)."""
        base = builtin_preset_by_name(user_preset[KEY_BASE_PRESET])
        if base is None:
            return
        self._apply_builtin_preset(base, sync_wl=False)
        self._apply_control_values(
            opacity=float(user_preset[KEY_OPACITY]),
            window=float(user_preset[KEY_WINDOW]),
            level=float(user_preset[KEY_LEVEL]),
            threshold=int(user_preset[KEY_THRESHOLD]),
        )
        # Restore V2 fields (background, quality) if present.
        bg_name = user_preset.get(KEY_BACKGROUND, "Black")
        for i, (name, (r, g, b)) in enumerate(BACKGROUND_COLORS):
            if name == bg_name:
                self._background_combo.blockSignals(True)
                self._background_combo.setCurrentIndex(i)
                self._background_combo.blockSignals(False)
                self._renderer.set_background(r, g, b)
                break
        # A saved preset carries an explicit detail level — restore it and
        # switch Detail to manual so Auto doesn't override the user's choice.
        q_name = user_preset.get(KEY_QUALITY, "Normal")
        for i, (name, _dist) in enumerate(QUALITY_MODES):
            if name == q_name:
                self._detail_auto_cb.blockSignals(True)
                self._detail_auto_cb.setChecked(False)
                self._detail_auto_cb.blockSignals(False)
                self._detail_slider.blockSignals(True)
                self._detail_slider.setValue(i)
                self._detail_slider.blockSignals(False)
                self._apply_detail_index(i)
                break

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _set_wl_controls(self, window: float, level: float) -> None:
        """Sync both W/L sliders and spinboxes without emitting signals."""
        for w in (self._window_slider, self._window_spin,
                  self._level_slider, self._level_spin):
            w.blockSignals(True)
        self._window_spin.setValue(window)
        self._window_slider.setValue(int(round(window)))
        self._level_spin.setValue(level)
        self._level_slider.setValue(int(round(level)))
        for w in (self._window_slider, self._window_spin,
                  self._level_slider, self._level_spin):
            w.blockSignals(False)

    def _sync_wl_to_preset(self, preset: TransferFunctionPreset) -> None:
        """
        Update the Window / Level controls to reflect a preset's natural range.

        After ``VolumeRenderer.set_preset()`` the internal W/L is reset.  The
        controls must be synced so that "unchanged == zero shift" holds.
        """
        if not preset.scalar_opacity:
            return
        lo = preset.scalar_opacity[0][0]
        hi = preset.scalar_opacity[-1][0]
        center = (lo + hi) / 2.0
        window = max(1.0, hi - lo)
        self._set_wl_controls(window, center)

    def _on_preset_changed(self, combo_index: int) -> None:
        if combo_index < 0:
            return
        logical = self._builtin_index_for_combo(combo_index)
        if logical < 0:
            return  # separator row
        if self._is_user_preset_logical(logical):
            user_idx = logical - len(BUILTIN_PRESETS)
            if 0 <= user_idx < len(self._user_presets):
                self._apply_user_preset(self._user_presets[user_idx])
                self._render()
            return
        if 0 <= logical < len(BUILTIN_PRESETS):
            preset = BUILTIN_PRESETS[logical]
            self._apply_builtin_preset(preset, sync_wl=True)
            self._threshold_slider.blockSignals(True)
            self._threshold_slider.setValue(0)
            self._threshold_label.setText("0")
            self._threshold_slider.blockSignals(False)
            self._renderer.set_threshold(0.0)
            self._update_overlay_text()
            self._save_last_preset(preset.name)
            self._render()

    def _on_save_preset(self) -> None:
        if self._config_manager is None or not hasattr(
            self._config_manager, "set_volume_3d_user_presets"
        ):
            QMessageBox.warning(
                self,
                "Save Preset",
                "Preset saving is not available (configuration is unavailable).",
            )
            return

        base_name = self._current_base_preset_name()
        if builtin_preset_by_name(base_name) is None:
            QMessageBox.warning(
                self,
                "Save Preset",
                "Could not determine the base transfer function for the current settings.",
            )
            return

        preset_name, ok = QInputDialog.getText(
            self,
            "Save 3D Preset",
            "Preset name:",
            text="",
        )
        if not ok:
            return
        preset_name = preset_name.strip()
        if not preset_name:
            return

        if preset_name in builtin_preset_names():
            QMessageBox.warning(
                self,
                "Save Preset",
                f"The name {preset_name!r} is reserved for a built-in preset.\n"
                "Choose a different name.",
            )
            return

        existing = next(
            (
                p
                for p in self._user_presets
                if p[KEY_NAME].casefold() == preset_name.casefold()
            ),
            None,
        )
        if existing is not None:
            answer = QMessageBox.question(
                self,
                "Overwrite Preset",
                f"A saved preset named {preset_name!r} already exists.\nOverwrite it?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return

        try:
            bg_idx = self._background_combo.currentIndex()
            bg_name = BACKGROUND_COLORS[bg_idx][0] if 0 <= bg_idx < len(BACKGROUND_COLORS) else "Black"
            q_idx = self._detail_slider.value()
            q_name = QUALITY_MODES[q_idx][0] if 0 <= q_idx < len(QUALITY_MODES) else "Normal"
            record = snapshot_current_settings(
                name=preset_name,
                base_preset=base_name,
                opacity=self._opacity_spin.value(),
                window=self._window_spin.value(),
                level=self._level_spin.value(),
                threshold=self._threshold_slider.value(),
                background=bg_name,
                quality=q_name,
            )
        except ValueError:
            QMessageBox.warning(
                self,
                "Save Preset",
                "The preset could not be saved. Details were withheld to protect private data.",
            )
            return

        self._user_presets = upsert_user_preset(self._user_presets, record)
        self._config_manager.set_volume_3d_user_presets(self._user_presets)

        logical_index = len(BUILTIN_PRESETS) + len(self._user_presets) - 1
        for i, preset in enumerate(self._user_presets):
            if preset[KEY_NAME].casefold() == preset_name.casefold():
                logical_index = len(BUILTIN_PRESETS) + i
                break
        self._refresh_preset_combo(select_index=logical_index)

        if DEBUG_VOLUME_3D:
            print(f"[DEBUG-VOLUME-3D] Saved user preset: {record}")

        QMessageBox.information(
            self,
            "Preset Saved",
            f"Preset {preset_name!r} saved successfully.",
        )

    def _on_opacity_slider_changed(self, value: int) -> None:
        resolved = slider_to_opacity(value)
        self._opacity_spin.blockSignals(True)
        self._opacity_spin.setValue(round(opacity_to_percent(resolved), 1))
        self._opacity_spin.blockSignals(False)
        self._renderer.set_global_opacity(resolved)
        self._update_overlay_text()
        self._render_timer.start()

    def _on_opacity_spin_changed(self, percent: float) -> None:
        resolved = percent_to_opacity(percent)
        self._opacity_slider.blockSignals(True)
        self._opacity_slider.setValue(opacity_to_slider(resolved))
        self._opacity_slider.blockSignals(False)
        self._renderer.set_global_opacity(resolved)
        self._update_overlay_text()
        self._render_timer.start()

    def _on_response_changed(self, value: int) -> None:
        self._renderer.set_opacity_response(response_to_gamma(value))
        self._render_timer.start()

    def _on_background_changed(self, index: int) -> None:
        if 0 <= index < len(BACKGROUND_COLORS):
            _name, (r, g, b) = BACKGROUND_COLORS[index]
            self._renderer.set_background(r, g, b)
            self._render_timer.start()

    def _on_window_slider_changed(self, value: int) -> None:
        self._window_spin.blockSignals(True)
        self._window_spin.setValue(float(value))
        self._window_spin.blockSignals(False)
        self._renderer.set_window_level(float(value), self._level_spin.value())
        self._render_timer.start()

    def _on_window_spin_changed(self, value: float) -> None:
        self._window_slider.blockSignals(True)
        self._window_slider.setValue(int(round(value)))
        self._window_slider.blockSignals(False)
        self._renderer.set_window_level(value, self._level_spin.value())
        self._render_timer.start()

    def _on_level_slider_changed(self, value: int) -> None:
        self._level_spin.blockSignals(True)
        self._level_spin.setValue(float(value))
        self._level_spin.blockSignals(False)
        self._renderer.set_window_level(self._window_spin.value(), float(value))
        self._render_timer.start()

    def _on_level_spin_changed(self, value: float) -> None:
        self._level_slider.blockSignals(True)
        self._level_slider.setValue(int(round(value)))
        self._level_slider.blockSignals(False)
        self._renderer.set_window_level(self._window_spin.value(), value)
        self._render_timer.start()

    def _on_reset_window_level(self) -> None:
        window, level = self._renderer.reset_window_level()
        self._set_wl_controls(window, level)
        self._render_timer.start()

    def _on_threshold_changed(self, value: int) -> None:
        label = f"+{value}" if value > 0 else str(value)
        self._threshold_label.setText(label)
        self._renderer.set_threshold(float(value))
        self._render_timer.start()

    def _on_reset_camera(self) -> None:
        self._renderer.reset_camera()
        self._render()

    def _on_set_view(self, view_name: str) -> None:
        self._renderer.set_view(view_name)
        self._render()

    def _on_auto_rotate_toggled(self, checked: bool) -> None:
        if checked:
            self._auto_rotate_timer.start()
        else:
            self._auto_rotate_timer.stop()

    def _auto_rotate_step(self) -> None:
        if not self._initialized or self._vtk_render_window is None:
            return
        cam = self._renderer.get_renderer().GetActiveCamera()
        cam.Azimuth(1.0)
        self._renderer.get_renderer().ResetCameraClippingRange()
        self._vtk_render_window.Render()

    def _on_open_documentation(self) -> None:
        """Open the 3D volume rendering user guide in the default web browser."""
        url = QUrl(user_doc_url("USER_GUIDE_3D.md"))
        if not QDesktopServices.openUrl(url):
            QMessageBox.warning(
                self,
                "Open Documentation",
                "Could not open the documentation link in your web browser.\n\n"
                f"URL:\n{url.toString()}",
            )

    def _on_tf_points_changed(self, points: list[Any]) -> None:
        tuples = [(float(s), float(o)) for s, o in points]
        self._renderer.set_custom_opacity_points(tuples)
        self._render_timer.start()

    _LIGHTING_PRESETS: ClassVar[dict[int, tuple[float, float, float, float]]] = {
        0: (0.3, 0.7, 0.2, 10.0),   # Default
        1: (0.8, 0.5, 0.0, 1.0),    # Flat
        2: (0.1, 0.6, 0.8, 40.0),   # Cinematic
    }

    def _on_lighting_changed(self, index: int) -> None:
        params = self._LIGHTING_PRESETS.get(index)
        if params:
            self._renderer.set_lighting(*params)
            self._update_overlay_text()
            self._render_timer.start()

    def _on_overlay_toggled(self, state: int) -> None:
        visible = state == Qt.CheckState.Checked.value
        if self._overlay_label is not None:
            self._overlay_label.setVisible(visible)
            self._render_timer.start()
            if self._viewport_container is not None:
                self._viewport_container.update()

    def _update_overlay_text(self) -> None:
        """Rebuild the Qt viewport overlay text from current state."""
        if self._overlay_label is None:
            return
        logical = self._current_logical_index()
        if logical < 0:
            preset_name = ""
        elif logical < len(BUILTIN_PRESETS):
            preset_name = BUILTIN_PRESETS[logical].name
        else:
            user_idx = logical - len(BUILTIN_PRESETS)
            if 0 <= user_idx < len(self._user_presets):
                preset_name = self._user_presets[user_idx].get("name", "")
            else:
                preset_name = ""
        opacity_pct = self._opacity_spin.value()
        q_idx = self._detail_slider.value()
        quality = QUALITY_MODES[q_idx][0] if 0 <= q_idx < len(QUALITY_MODES) else ""
        blend_idx = self._blend_mode_combo.currentIndex()
        blend = BLEND_MODES[blend_idx][0] if 0 <= blend_idx < len(BLEND_MODES) else ""
        text = build_overlay_text(
            preset_name=preset_name,
            opacity_pct=opacity_pct,
            detail=quality,
            blend=blend,
        )
        prev = self._overlay_text_prev
        self._overlay_text_prev = text
        self._overlay_label.setText(text)
        self._overlay_label.adjustSize()
        hint = self._overlay_label.sizeHint()
        self._overlay_label.setMinimumSize(hint)
        self._overlay_label.setMaximumSize(hint)
        self._overlay_label.raise_()
        shrunk = len(text) < len(prev) or (
            prev
            and text != prev
            and len(text.splitlines()) < len(prev.splitlines())
        )
        self._render_timer.start()
        if shrunk and self._viewport_container is not None:
            self._viewport_container.update()

    def _on_blend_mode_changed(self, index: int) -> None:
        if 0 <= index < len(BLEND_MODES):
            self._renderer.set_blend_mode(BLEND_MODES[index][0])
            self._update_overlay_text()
            self._render_timer.start()

    def _on_smoothing_changed(self, value: float) -> None:
        # Smoothing is slow — debounce via the render timer so dragging the
        # spinbox doesn't stall the UI on every tick.
        self._renderer.set_display_smoothing(value)
        self._render_timer.start()

    def _on_ssao_changed(self, state: int) -> None:
        self._renderer.set_ssao_enabled(state == Qt.CheckState.Checked.value)
        self._render_timer.start()

    def _on_gradient_opacity_changed(self, state: int) -> None:
        self._renderer.set_gradient_opacity_enabled(state == Qt.CheckState.Checked.value)
        self._render_timer.start()

    def _on_go_strength_changed(self, value: int) -> None:
        self._renderer.set_gradient_opacity_strength(value / 100.0)
        self._render_timer.start()

    def _on_interpolation_changed(self, state: int) -> None:
        self._renderer.set_interpolation(state != Qt.CheckState.Checked.value)
        self._render_timer.start()

    def _on_crop_toggled(self, state: int) -> None:
        enabled = state == Qt.CheckState.Checked.value
        self._reset_crop_btn.setEnabled(enabled)
        if enabled:
            self._enable_crop_box()
        else:
            self._disable_crop_box()

    def _on_reset_crop(self) -> None:
        self._crop_cb.setChecked(False)

    def _enable_crop_box(self) -> None:
        """Create and enable a vtkBoxWidget2 for interactive cropping."""
        if not self._initialized or self._interactor is None:
            return
        if hasattr(self, "_box_widget") and self._box_widget is not None:
            self._box_widget.On()
            return
        try:
            box_widget = vtk_mod.vtkBoxWidget2()
            rep = vtk_mod.vtkBoxRepresentation()
            rep.SetPlaceFactor(1.0)
            ren = self._renderer.get_renderer()
            bounds = list(ren.ComputeVisiblePropBounds())
            # VTK ComputeVisiblePropBounds all-zero is empty-scene sentinel
            if all(v == 0.0 for v in bounds):  # NOSONAR(S1244)
                return
            rep.PlaceWidget(bounds)
            box_widget.SetRepresentation(rep)
            iren = self._interactor.GetRenderWindow().GetInteractor()
            box_widget.SetInteractor(iren)
            box_widget.AddObserver("InteractionEvent", self._on_crop_box_changed)
            box_widget.On()
            self._box_widget = box_widget
            self._crop_planes = vtk_mod.vtkPlanes()
        except Exception:
            _log.warning("Could not create crop box widget; details withheld")

    def _disable_crop_box(self) -> None:
        """Hide the box widget and remove clipping planes."""
        if hasattr(self, "_box_widget") and self._box_widget is not None:
            self._box_widget.Off()
        self._renderer.clear_cropping()
        self._render()

    def _on_crop_box_changed(self, obj=None, event=None) -> None:
        """Update clipping planes from the current box widget position."""
        if not hasattr(self, "_box_widget") or self._box_widget is None:
            return
        try:
            rep = self._box_widget.GetRepresentation()
            planes = vtk_mod.vtkPlanes()
            rep.GetPlanes(planes)
            plane_list = []
            for i in range(planes.GetNumberOfPlanes()):
                plane_list.append(planes.GetPlane(i))
            self._renderer.set_cropping(plane_list)
        except Exception:
            pass

    def _detail_caption_text(self, index: int, *, auto: bool) -> str:
        name = QUALITY_MODES[index][0] if 0 <= index < len(QUALITY_MODES) else ""
        return f"Detail: {name} (auto)" if auto else f"Detail: {name}"

    def _apply_detail_index(self, index: int) -> None:
        """Push a detail level to the renderer and update the caption + overlay."""
        index = max(0, min(len(QUALITY_MODES) - 1, index))
        name = QUALITY_MODES[index][0]
        self._renderer.set_quality_mode(name)
        self._detail_caption.setText(
            self._detail_caption_text(index, auto=self._detail_auto_cb.isChecked())
        )
        self._update_overlay_text()

    def _apply_auto_detail(
        self, preset: TransferFunctionPreset | None = None
    ) -> None:
        """Choose the detail level automatically from a preset's steepness."""
        if not self._detail_auto_cb.isChecked():
            return
        if preset is None:
            preset = self._current_preset_object()
        # High (finer) for steep presets, Normal otherwise.
        target = 2 if (preset is not None and is_steep_preset(preset)) else 1
        self._detail_slider.blockSignals(True)
        self._detail_slider.setValue(target)
        self._detail_slider.blockSignals(False)
        self._apply_detail_index(target)

    def _current_preset_object(self) -> TransferFunctionPreset | None:
        """Return the built-in preset backing the current selection, or None."""
        logical = self._current_logical_index()
        if 0 <= logical < len(BUILTIN_PRESETS):
            return BUILTIN_PRESETS[logical]
        if logical >= len(BUILTIN_PRESETS):
            user_idx = logical - len(BUILTIN_PRESETS)
            if 0 <= user_idx < len(self._user_presets):
                base = builtin_preset_by_name(
                    self._user_presets[user_idx][KEY_BASE_PRESET]
                )
                return base
        return None

    def _on_detail_changed(self, index: int) -> None:
        # Manual slider use switches off Auto.
        if self._detail_auto_cb.isChecked():
            self._detail_auto_cb.blockSignals(True)
            self._detail_auto_cb.setChecked(False)
            self._detail_auto_cb.blockSignals(False)
        self._apply_detail_index(index)
        self._render_timer.start()

    def _on_detail_auto_changed(self, state: int) -> None:
        if state == Qt.CheckState.Checked.value:
            self._apply_auto_detail()
            self._render_timer.start()
        else:
            # Re-stamp the caption without the "(auto)" suffix.
            self._apply_detail_index(self._detail_slider.value())

    def _on_render_method_changed(self, index: int) -> None:
        if 0 <= index < len(RENDER_METHODS):
            self._renderer.set_render_method(RENDER_METHODS[index])
            self._render_timer.start()

    def _on_toggle_advanced(self) -> None:
        """Show or hide the advanced render-status panel."""
        visible = not self._advanced_group.isVisible()
        self._advanced_group.setVisible(visible)
        self._advanced_toggle_btn.setText(
            "Advanced ▼" if visible else "Advanced ▶"
        )
        if visible:
            self._update_render_status()

    def _update_render_status(self) -> None:
        """Populate the advanced render-status readout from live VTK state."""
        parts: list[str] = []
        try:
            ren = self._renderer.get_renderer()
            vols = ren.GetVolumes()
            vols.InitTraversal()
            vol = vols.GetNextVolume()
            if vol is not None:
                mapper = vol.GetMapper()
                mapper_class = mapper.GetClassName()
                mode_str = mapper_class
                if hasattr(mapper, "GetLastUsedRenderMode"):
                    mode_id = mapper.GetLastUsedRenderMode()
                    mode_names = {0: "Default", 1: "CPU Ray Cast",
                                  2: "GPU", 3: "GPU OpenGL2"}
                    mode_str += f" ({mode_names.get(mode_id, str(mode_id))})"
                parts.append(f"Mapper: {mode_str}")
                inp = mapper.GetInput()
                if inp is not None:
                    dims = inp.GetDimensions()
                    parts.append(f"Volume: {dims[0]}×{dims[1]}×{dims[2]}")
                    # T23: memory estimate for the float32 volume.
                    voxels = dims[0] * dims[1] * dims[2]
                    mb = (voxels * 4) / (1024 * 1024)
                    parts.append(f"Memory: ~{mb:.0f} MB ({voxels:,} voxels)")
                    if mb > 512:
                        parts.append("⚠ Large volume — consider Fast quality")
            sd = getattr(self._renderer, "_mapper", None)
            if sd is not None and hasattr(sd, "GetSampleDistance"):
                parts.append(f"Sample dist: {sd.GetSampleDistance():.2f}")
        except Exception:
            parts.append("(status unavailable)")
        self._render_status_label.setText("\n".join(parts))

    # ------------------------------------------------------------------
    # Progressive refinement
    # ------------------------------------------------------------------

    _KEY_VIEW_MAP: ClassVar[dict[str, str]] = {"1": "Anterior", "2": "Posterior", "3": "Left",
                      "4": "Right", "5": "Superior", "6": "Inferior"}

    def _on_key_press(self, obj: Any = None, event: str = "") -> None:
        """Handle keyboard shortcuts in the 3D viewport."""
        iren = self._interactor.GetRenderWindow().GetInteractor() if self._interactor else None
        if iren is None:
            return
        key = iren.GetKeySym()
        if not key:
            return
        kl = key.lower()
        if kl in ("r", "space"):
            self._renderer.set_view("Anterior")
            self._render()
        elif kl == "f":
            self._renderer.get_renderer().ResetCamera()
            self._render()
        elif kl == "a":
            self._auto_rotate_btn.toggle()
        elif kl in self._KEY_VIEW_MAP:
            self._renderer.set_view(self._KEY_VIEW_MAP[kl])
            self._render()
        elif kl in ("plus", "equal"):
            new_val = min(self._opacity_spin.value() + 5.0, 100.0)
            self._opacity_spin.setValue(new_val)
        elif kl in ("minus",):
            new_val = max(self._opacity_spin.value() - 5.0, 0.0)
            self._opacity_spin.setValue(new_val)
        elif kl == "bracketright":
            idx = self._preset_combo.currentIndex() + 1
            if idx < self._preset_combo.count():
                self._preset_combo.setCurrentIndex(idx)
        elif kl == "bracketleft":
            idx = self._preset_combo.currentIndex() - 1
            if idx >= 0:
                self._preset_combo.setCurrentIndex(idx)

    def _on_interaction_start(self, obj: Any = None, event: str = "") -> None:
        """Switch to coarse sampling during mouse interaction for responsiveness."""
        self._renderer.set_interactive_quality(True)
        if self._auto_rotate_btn.isChecked():
            self._auto_rotate_btn.setChecked(False)

    def _on_interaction_end(self, obj: Any = None, event: str = "") -> None:
        """Restore fine sampling after interaction and re-render."""
        self._renderer.set_interactive_quality(False)
        self._render()

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def _render(self) -> None:
        """Trigger a VTK render update."""
        if self._initialized and self._vtk_render_window is not None:
            self._vtk_render_window.Render()

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def cleanup(self) -> None:
        """Release VTK interactor and renderer resources."""
        if DEBUG_VOLUME_3D:
            print("[DEBUG-VOLUME-3D] VolumeViewerWidget.cleanup() called from:")
        if hasattr(self, "_box_widget") and self._box_widget is not None:
            self._box_widget.Off()
            self._box_widget = None
        self._overlay_label = None
        self._viewport_container = None
        if self._interactor is not None:
            self._interactor.Finalize()
            self._interactor = None
        self._renderer.cleanup()
        self._vtk_render_window = None
        if DEBUG_VOLUME_3D:
            print("[DEBUG-VOLUME-3D] VolumeViewerWidget cleanup complete.")

    def closeEvent(self, event: Any) -> None:
        """Ensure cleanup on widget close."""
        if DEBUG_VOLUME_3D:
            print("[DEBUG-VOLUME-3D] VolumeViewerWidget.closeEvent() fired!")
        self.cleanup()
        super().closeEvent(event)
