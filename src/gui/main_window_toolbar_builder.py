"""
Main Window Toolbar Builder

Builds the main application toolbar for MainWindow.  All buttons carry SVG
icons loaded from ``resources/icons/toolbar/`` and tinted to match the current
theme (light grey on dark, near-black on light) by replacing ``currentColor``
in the SVG bytes before rasterising with QSvgRenderer at 48×48 pixels
(marked as 2× so the icon is sharp on HiDPI displays).

Action texts are short labels (≤12 chars) suitable for the "text under icon"
display mode.  Tooltips always carry the full description and shortcut.

Commented-out items (font size controls, scroll-wheel mode) are intentionally
preserved for future customisable-toolbar support.

Inputs:
    - MainWindow instance with ``config_manager``, ``reset_view_action``,
      and all signals used by toolbar actions.
    - SVG files under ``resources/icons/toolbar/`` (missing files degrade
      gracefully to an empty QIcon).

Outputs:
    - QToolBar added to the window.
    - Action/widget references on main_window:
        main_toolbar, _open_split_btn,
        mouse_mode_* actions, series_navigator_action,
        prev/next_series_action, cine_play_pause_action.
    - Toggled-state icon references refreshed on theme change:
        _privacy_icon_off, _privacy_icon_on,
        _cine_icon_play, _cine_icon_pause.
    - ``refresh_toolbar_icon_theme(color)`` — called by ``_apply_theme()``.
    - ``apply_toolbar_label_style(style)`` — called by settings apply.

Requirements:
    - PySide6 (incl. QtSvg for QSvgRenderer)
    - reset_view_action must exist on main_window before calling.
"""

from pathlib import Path

from PySide6.QtCore import QByteArray, Qt
from PySide6.QtGui import QAction, QIcon, QKeySequence, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (
    QMenu,
    QToolBar,
    QToolButton,
)

# ---------------------------------------------------------------------------
# Icon helpers
# ---------------------------------------------------------------------------

_ICONS_DIR = Path(__file__).parent.parent.parent / "resources" / "icons" / "toolbar"

_LABEL_STYLE_MAP = {
    "icon_only":       Qt.ToolButtonStyle.ToolButtonIconOnly,
    "text_under_icon": Qt.ToolButtonStyle.ToolButtonTextUnderIcon,
    "text_only":       Qt.ToolButtonStyle.ToolButtonTextOnly,
}

# MenuButtonPopup: fixed width + reserved right strip for the arrow so icon/label
# center in the main area (not over the dropdown).
_SPLIT_TOOLBUTTON_OBJECT_NAME = "toolbar_menu_split_button"
_SPLIT_TOOLBUTTON_WIDTH_TEXT_UNDER = 52
# Narrow strip + tight padding-right (no extra gap before the arrow).
_SPLIT_MENU_BUTTON_STRIP_PX = 10
_SPLIT_CONTENT_SHIFT_LEFT_PX = 1


def _split_toolbutton_text_under_stylesheet() -> str:
    """QSS for Open / W/L split buttons when labels show under icons."""
    w = _SPLIT_TOOLBUTTON_WIDTH_TEXT_UNDER
    menu_w = _SPLIT_MENU_BUTTON_STRIP_PX
    shift = _SPLIT_CONTENT_SHIFT_LEFT_PX
    name = _SPLIT_TOOLBUTTON_OBJECT_NAME
    # padding-right matches menu strip width; margin-left centers icon in the main cell.
    return (
        "QToolBar QToolButton { font-size: 7pt; }"
        f"QToolBar QToolButton#{name} {{"
        f" min-width: {w}px;"
        f" max-width: {w}px;"
        f" padding-right: {menu_w}px;"
        " padding-left: 0px;"
        f" margin-left: -{shift}px;"
        " }"
        f"QToolBar QToolButton#{name}::menu-button {{"
        f" width: {menu_w}px;"
        " subcontrol-position: right center;"
        " subcontrol-origin: margin;"
        " border: none;"
        " background: transparent;"
        " }"
    )


def _apply_split_toolbutton_layout(btn: QToolButton, *, text_under_icon: bool) -> None:
    """Size menu split buttons and tag them for split-button QSS."""
    btn.setObjectName(_SPLIT_TOOLBUTTON_OBJECT_NAME)
    if text_under_icon:
        btn.setMinimumWidth(_SPLIT_TOOLBUTTON_WIDTH_TEXT_UNDER)
        btn.setMaximumWidth(_SPLIT_TOOLBUTTON_WIDTH_TEXT_UNDER)
    else:
        btn.setMinimumWidth(0)
        btn.setMaximumWidth(16777215)


def _icon_color(theme: str) -> str:
    """Return the SVG stroke colour for the given theme name."""
    return "#e0e0e0" if theme == "dark" else "#2c2c2c"


def _icon(name: str, color: str | None = None) -> QIcon:
    """
    Load ``name.svg`` from the toolbar icons directory, optionally replacing
    ``currentColor`` with *color* before rendering.

    Renders to a 48×48 QPixmap at DPR 2.0 for HiDPI sharpness.
    Returns an empty QIcon if the file is missing.
    """
    p = _ICONS_DIR / f"{name}.svg"
    if not p.exists():
        return QIcon()
    raw: bytes = p.read_bytes()
    if color is not None:
        raw = raw.replace(b"currentColor", color.encode())
    renderer = QSvgRenderer(QByteArray(raw))
    if not renderer.isValid():
        return QIcon()
    pm = QPixmap(48, 48)
    pm.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pm)
    renderer.render(painter)
    painter.end()
    pm.setDevicePixelRatio(2.0)
    return QIcon(pm)


# ---------------------------------------------------------------------------
# Builder
# ---------------------------------------------------------------------------

def build_main_toolbar(main_window) -> None:
    """
    Create and attach the main toolbar to the given main window.

    Args:
        main_window: MainWindow instance (same contract as build_menu_bar).
    """
    # ── Resolve initial colour from persisted theme preference ────────────
    theme = (
        main_window.config_manager.get_theme()
        if main_window.config_manager
        else "dark"
    )
    color = _icon_color(theme)

    # Registry: list of (QAction | QToolButton, icon_name) for theme refresh.
    main_window._toolbar_icon_registry = []

    def _ri(action, name: str) -> None:
        """Set icon on *action* and register it for theme refresh."""
        action.setIcon(_icon(name, color))
        main_window._toolbar_icon_registry.append((action, name))

    # ── Pre-load toggled-state icons ──────────────────────────────────────
    main_window._privacy_icon_off = _icon("privacy-off", color)   # eye
    main_window._privacy_icon_on  = _icon("privacy-on",  color)   # eye-off
    main_window._cine_icon_play   = _icon("cine-play",   color)
    main_window._cine_icon_pause  = _icon("cine-pause",  color)

    # ── Theme-refresh closure ─────────────────────────────────────────────
    def _refresh_icons(new_color: str) -> None:
        for target, name in main_window._toolbar_icon_registry:
            target.setIcon(_icon(name, new_color))
        main_window._privacy_icon_off = _icon("privacy-off", new_color)
        main_window._privacy_icon_on  = _icon("privacy-on",  new_color)
        main_window._cine_icon_play   = _icon("cine-play",   new_color)
        main_window._cine_icon_pause  = _icon("cine-pause",  new_color)
        main_window._update_privacy_action()
        # Cine: registry resets to play icon; on_cine_playback_state_changed
        # will swap back to pause on the next frame tick if playing.
        # Also refresh icons on keyed menu items.
        for action, name in getattr(main_window, '_menu_icon_registry', []):
            action.setIcon(_icon(name, new_color))

    main_window.refresh_toolbar_icon_theme = _refresh_icons

    # ── Label-style applicator (called at startup and from Settings) ──────
    def _apply_label_style(style: str) -> None:
        qt_style = _LABEL_STYLE_MAP.get(style, Qt.ToolButtonStyle.ToolButtonIconOnly)
        tb = getattr(main_window, "main_toolbar", None)
        if tb is None:
            return
        tb.setToolButtonStyle(qt_style)
        # QToolButton widgets added via addWidget() don't follow toolbar style.
        text_under = style == "text_under_icon"
        for _btn_attr in ("_open_split_btn", "_wl_toolbar_btn"):
            btn = getattr(main_window, _btn_attr, None)
            if btn is not None:
                btn.setToolButtonStyle(qt_style)
                _apply_split_toolbutton_layout(btn, text_under_icon=text_under)
        # Small condensed font when text is visible under icons.
        if text_under:
            tb.setStyleSheet(_split_toolbutton_text_under_stylesheet())
        else:
            tb.setStyleSheet("")

    main_window.apply_toolbar_label_style = _apply_label_style

    # ── Build toolbar ─────────────────────────────────────────────────────
    toolbar = QToolBar("Main Toolbar", main_window)
    toolbar.setMovable(False)
    toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)  # default; overridden below
    main_window.addToolBar(toolbar)

    # ── Open (split button: click = Open File, arrow = dropdown) ──────────
    open_btn = QToolButton(main_window)
    open_btn.setText("Open")
    open_btn.setToolTip("Open file(s)  (Ctrl+O)")
    open_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
    open_btn.setPopupMode(QToolButton.ToolButtonPopupMode.MenuButtonPopup)
    open_btn.clicked.connect(main_window.open_file_requested.emit)
    _ri(open_btn, "open-file")

    _open_menu = QMenu(open_btn)
    _open_file_act = QAction("Open File(s)…", open_btn)
    _open_file_act.triggered.connect(main_window.open_file_requested.emit)
    _open_folder_act = QAction("Open Folder…", open_btn)
    _open_folder_act.triggered.connect(main_window.open_folder_requested.emit)
    _open_menu.addAction(_open_file_act)
    _open_menu.addAction(_open_folder_act)
    open_btn.setMenu(_open_menu)
    _apply_split_toolbutton_layout(open_btn, text_under_icon=False)
    toolbar.addWidget(open_btn)
    main_window._open_split_btn = open_btn  # stored for style refresh

    export_action = QAction("Export", main_window)
    export_action.setToolTip("Export…  (Ctrl+E)")
    export_action.triggered.connect(main_window.export_requested.emit)
    _ri(export_action, "export")
    toolbar.addAction(export_action)

    study_index_action = QAction("Index", main_window)
    study_index_action.setToolTip("Browse local study index")
    study_index_action.triggered.connect(main_window.study_index_search_requested.emit)
    _ri(study_index_action, "study-index")
    toolbar.addAction(study_index_action)

    toolbar.addSeparator()

    # ── Mouse interaction mode buttons (exclusive) ────────────────────────
    main_window.mouse_mode_ellipse_roi_action = QAction("Ellipse", main_window)
    main_window.mouse_mode_ellipse_roi_action.setCheckable(True)
    main_window.mouse_mode_ellipse_roi_action.setShortcut(QKeySequence("E"))
    main_window.mouse_mode_ellipse_roi_action.setToolTip("Ellipse ROI  (E)")
    main_window.mouse_mode_ellipse_roi_action.triggered.connect(
        lambda: main_window._on_mouse_mode_changed("roi_ellipse")
    )
    _ri(main_window.mouse_mode_ellipse_roi_action, "roi-ellipse")
    toolbar.addAction(main_window.mouse_mode_ellipse_roi_action)

    main_window.mouse_mode_rectangle_roi_action = QAction("Rect", main_window)
    main_window.mouse_mode_rectangle_roi_action.setCheckable(True)
    main_window.mouse_mode_rectangle_roi_action.setShortcut(QKeySequence("R"))
    main_window.mouse_mode_rectangle_roi_action.setToolTip("Rectangle ROI  (R)")
    main_window.mouse_mode_rectangle_roi_action.triggered.connect(
        lambda: main_window._on_mouse_mode_changed("roi_rectangle")
    )
    _ri(main_window.mouse_mode_rectangle_roi_action, "roi-rectangle")
    toolbar.addAction(main_window.mouse_mode_rectangle_roi_action)

    main_window.mouse_mode_measure_action = QAction("Measure", main_window)
    main_window.mouse_mode_measure_action.setCheckable(True)
    main_window.mouse_mode_measure_action.setShortcut(QKeySequence("M"))
    main_window.mouse_mode_measure_action.setToolTip("Linear measurement  (M)")
    main_window.mouse_mode_measure_action.triggered.connect(
        lambda: main_window._on_mouse_mode_changed("measure")
    )
    _ri(main_window.mouse_mode_measure_action, "measure")
    toolbar.addAction(main_window.mouse_mode_measure_action)

    main_window.mouse_mode_measure_angle_action = QAction("Angle", main_window)
    main_window.mouse_mode_measure_angle_action.setCheckable(True)
    main_window.mouse_mode_measure_angle_action.setShortcut(QKeySequence("Shift+M"))
    main_window.mouse_mode_measure_angle_action.setToolTip("Angle measurement  (Shift+M)")
    main_window.mouse_mode_measure_angle_action.setStatusTip(
        "Three-click angle at middle vertex: first segment, then second  (Shift+M)"
    )
    main_window.mouse_mode_measure_angle_action.triggered.connect(
        lambda: main_window._on_mouse_mode_changed("measure_angle")
    )
    _ri(main_window.mouse_mode_measure_angle_action, "measure-angle")
    toolbar.addAction(main_window.mouse_mode_measure_angle_action)

    main_window.mouse_mode_text_annotation_action = QAction("Text", main_window)
    main_window.mouse_mode_text_annotation_action.setCheckable(True)
    main_window.mouse_mode_text_annotation_action.setShortcut(QKeySequence("T"))
    main_window.mouse_mode_text_annotation_action.setToolTip("Text annotation  (T)")
    main_window.mouse_mode_text_annotation_action.triggered.connect(
        lambda: main_window._on_mouse_mode_changed("text_annotation")
    )
    _ri(main_window.mouse_mode_text_annotation_action, "text-annotation")
    toolbar.addAction(main_window.mouse_mode_text_annotation_action)

    main_window.mouse_mode_arrow_annotation_action = QAction("Arrow", main_window)
    main_window.mouse_mode_arrow_annotation_action.setCheckable(True)
    main_window.mouse_mode_arrow_annotation_action.setShortcut(QKeySequence("A"))
    main_window.mouse_mode_arrow_annotation_action.setToolTip("Arrow annotation  (A)")
    main_window.mouse_mode_arrow_annotation_action.triggered.connect(
        lambda: main_window._on_mouse_mode_changed("arrow_annotation")
    )
    _ri(main_window.mouse_mode_arrow_annotation_action, "arrow-annotation")
    toolbar.addAction(main_window.mouse_mode_arrow_annotation_action)

    main_window.mouse_mode_crosshair_action = QAction("Crosshair", main_window)
    main_window.mouse_mode_crosshair_action.setCheckable(True)
    main_window.mouse_mode_crosshair_action.setShortcut(QKeySequence("H"))
    main_window.mouse_mode_crosshair_action.setToolTip("Crosshair  (H)")
    main_window.mouse_mode_crosshair_action.triggered.connect(
        lambda: main_window._on_mouse_mode_changed("crosshair")
    )
    _ri(main_window.mouse_mode_crosshair_action, "crosshair")
    toolbar.addAction(main_window.mouse_mode_crosshair_action)

    main_window.mouse_mode_zoom_action = QAction("Zoom", main_window)
    main_window.mouse_mode_zoom_action.setCheckable(True)
    main_window.mouse_mode_zoom_action.setShortcut(QKeySequence("Z"))
    main_window.mouse_mode_zoom_action.setToolTip("Zoom  (Z)")
    main_window.mouse_mode_zoom_action.triggered.connect(
        lambda: main_window._on_mouse_mode_changed("zoom")
    )
    _ri(main_window.mouse_mode_zoom_action, "zoom")
    toolbar.addAction(main_window.mouse_mode_zoom_action)

    main_window.mouse_mode_magnifier_action = QAction("Magnify", main_window)
    main_window.mouse_mode_magnifier_action.setCheckable(True)
    main_window.mouse_mode_magnifier_action.setShortcut(QKeySequence("G"))
    main_window.mouse_mode_magnifier_action.setToolTip("Magnifier glass  (G)")
    main_window.mouse_mode_magnifier_action.triggered.connect(
        lambda: main_window._on_mouse_mode_changed("magnifier")
    )
    _ri(main_window.mouse_mode_magnifier_action, "magnifier")
    toolbar.addAction(main_window.mouse_mode_magnifier_action)

    main_window.mouse_mode_pan_action = QAction("Pan", main_window)
    main_window.mouse_mode_pan_action.setCheckable(True)
    main_window.mouse_mode_pan_action.setChecked(True)  # Default mode
    main_window.mouse_mode_pan_action.setShortcut(QKeySequence("P"))
    main_window.mouse_mode_pan_action.setToolTip("Pan / scroll  (P)")
    main_window.mouse_mode_pan_action.triggered.connect(
        lambda: main_window._on_mouse_mode_changed("pan")
    )
    _ri(main_window.mouse_mode_pan_action, "pan")
    toolbar.addAction(main_window.mouse_mode_pan_action)

    main_window.mouse_mode_select_action = QAction("Select", main_window)
    main_window.mouse_mode_select_action.setCheckable(True)
    main_window.mouse_mode_select_action.setShortcut(QKeySequence("S"))
    main_window.mouse_mode_select_action.setToolTip("Select annotation / ROI  (S)")
    main_window.mouse_mode_select_action.triggered.connect(
        lambda: main_window._on_mouse_mode_changed("select")
    )
    _ri(main_window.mouse_mode_select_action, "select")
    toolbar.addAction(main_window.mouse_mode_select_action)

    main_window.mouse_mode_auto_window_level_action = QAction("W/L", main_window)
    main_window.mouse_mode_auto_window_level_action.setCheckable(True)
    main_window.mouse_mode_auto_window_level_action.setShortcut(QKeySequence("W"))
    main_window.mouse_mode_auto_window_level_action.setToolTip(
        "Window/level from drawn ROI  (W)"
    )
    main_window.mouse_mode_auto_window_level_action.triggered.connect(
        lambda: main_window._on_mouse_mode_changed("auto_window_level")
    )
    _ri(main_window.mouse_mode_auto_window_level_action, "window-level")

    # ── Mouse-mode exclusive action group ────────────────────────────────────
    from PySide6.QtGui import QActionGroup
    _mouse_mode_group = QActionGroup(main_window)
    _mouse_mode_group.setExclusive(True)
    for _act in [
        main_window.mouse_mode_ellipse_roi_action,
        main_window.mouse_mode_rectangle_roi_action,
        main_window.mouse_mode_measure_action,
        main_window.mouse_mode_measure_angle_action,
        main_window.mouse_mode_text_annotation_action,
        main_window.mouse_mode_arrow_annotation_action,
        main_window.mouse_mode_crosshair_action,
        main_window.mouse_mode_zoom_action,
        main_window.mouse_mode_magnifier_action,
        main_window.mouse_mode_pan_action,
        main_window.mouse_mode_select_action,
        main_window.mouse_mode_auto_window_level_action,
    ]:
        _mouse_mode_group.addAction(_act)
    main_window.mouse_mode_group = _mouse_mode_group

    # ── W/L split-button: click activates mode; arrow opens preset dropdown ─
    wl_btn = QToolButton(toolbar)
    wl_btn.setDefaultAction(main_window.mouse_mode_auto_window_level_action)
    wl_btn.setPopupMode(QToolButton.ToolButtonPopupMode.MenuButtonPopup)
    wl_wl_menu = QMenu(wl_btn)
    wl_btn.setMenu(wl_wl_menu)

    from gui.wl_preset_menu import wire_dynamic_wl_preset_menu

    wire_dynamic_wl_preset_menu(
        wl_wl_menu,
        get_context=getattr(main_window, "_get_wl_preset_menu_context", None),
        get_legacy_presets=getattr(main_window, "_get_active_wl_presets", None),
        on_select=lambda i: main_window._apply_wl_preset_requested.emit(i),
        on_manage=getattr(main_window, "_open_wl_preset_manager", None),
    )
    _apply_split_toolbutton_layout(wl_btn, text_under_icon=False)
    toolbar.addWidget(wl_btn)
    main_window._wl_toolbar_btn = wl_btn

    toolbar.addSeparator()

    # ── Privacy Mode ──────────────────────────────────────────────────────
    # Uses the shared privacy_action created in MainWindow.__init__.
    # Icon/tooltip/text managed by _update_privacy_action(); not registered
    # in _toolbar_icon_registry since _refresh_icons calls _update_privacy_action.
    toolbar.addAction(main_window.privacy_action)
    main_window.main_toolbar = toolbar
    main_window._update_privacy_action()

    toolbar.addSeparator()

    # ── Reset View / Reset All ────────────────────────────────────────────
    main_window.reset_view_action.setText("Reset")
    main_window.reset_view_action.setToolTip(
        main_window.reset_view_action.toolTip() or "Reset zoom, pan, window/level  (V)"
    )
    _ri(main_window.reset_view_action, "reset-view")
    toolbar.addAction(main_window.reset_view_action)

    reset_all_views_action = QAction("Reset All", main_window)
    reset_all_views_action.setShortcut(QKeySequence("Shift+A"))
    reset_all_views_action.setToolTip("Reset all subwindows  (Shift+A)")
    reset_all_views_action.triggered.connect(main_window.reset_all_views_requested.emit)
    _ri(reset_all_views_action, "reset-all-views")
    toolbar.addAction(reset_all_views_action)

    toolbar.addSeparator()

    # ── Overlay toggle ────────────────────────────────────────────────────
    overlay_toggle_action = QAction("Overlay", main_window)
    overlay_toggle_action.setToolTip("Toggle overlay detail  (Space)")
    overlay_toggle_action.triggered.connect(main_window.toggle_overlay_requested.emit)
    _ri(overlay_toggle_action, "overlay-toggle")
    toolbar.addAction(overlay_toggle_action)

    toolbar.addSeparator()

    # ── Cine play/pause ───────────────────────────────────────────────────
    main_window.cine_play_pause_action = QAction("Cine", main_window)
    main_window.cine_play_pause_action.setShortcut(QKeySequence("Ctrl+Space"))
    main_window.cine_play_pause_action.setToolTip("Play cine loop  (Ctrl+Space)")
    main_window.cine_play_pause_action.triggered.connect(
        main_window.cine_play_pause_requested.emit
    )
    _ri(main_window.cine_play_pause_action, "cine-play")
    toolbar.addAction(main_window.cine_play_pause_action)

    toolbar.addSeparator()

    # ── MPR ───────────────────────────────────────────────────────────────
    mpr_action = QAction("MPR", main_window)
    mpr_action.setToolTip("Create MPR view for focused window")
    mpr_action.triggered.connect(main_window.create_mpr_view_requested.emit)
    _ri(mpr_action, "mpr")
    toolbar.addAction(mpr_action)

    view_3d_action = QAction("3D View", main_window)
    view_3d_action.setToolTip("Open 3D Volume Render of current series")
    view_3d_action.triggered.connect(main_window.create_3d_view_requested.emit)
    view_3d_action.setEnabled(False)
    main_window.view_3d_action = view_3d_action
    _ri(view_3d_action, "3d-view")
    toolbar.addAction(view_3d_action)

    toolbar.addSeparator()

    # ── View chrome toggles ───────────────────────────────────────────────
    main_window.fullscreen_action.setIconText("Full")
    _ri(main_window.fullscreen_action, "fullscreen")
    toolbar.addAction(main_window.fullscreen_action)

    main_window.series_navigator_action = QAction("Navigator", main_window)
    main_window.series_navigator_action.setToolTip("Show/hide series navigator")
    main_window.series_navigator_action.triggered.connect(
        main_window.toggle_series_navigator
    )
    _ri(main_window.series_navigator_action, "series-navigator")
    toolbar.addAction(main_window.series_navigator_action)

    toolbar.addSeparator()

    # ── Series navigation ─────────────────────────────────────────────────
    main_window.prev_series_action = QAction("Prev", main_window)
    main_window.prev_series_action.setToolTip("Previous series  (←)")
    main_window.prev_series_action.triggered.connect(main_window._on_prev_series)
    _ri(main_window.prev_series_action, "prev-series")
    toolbar.addAction(main_window.prev_series_action)

    main_window.next_series_action = QAction("Next", main_window)
    main_window.next_series_action.setToolTip("Next series  (→)")
    main_window.next_series_action.triggered.connect(main_window._on_next_series)
    _ri(main_window.next_series_action, "next-series")
    toolbar.addAction(main_window.next_series_action)

    # ── Apply persisted label style ───────────────────────────────────────
    saved_style = (
        main_window.config_manager.get_toolbar_label_style()
        if main_window.config_manager
        else "icon_only"
    )
    _apply_label_style(saved_style)

    # ── Commented-out items — preserved for customisable-toolbar support ──
    #
    # toolbar.addSeparator()
    # toolbar.addWidget(QLabel("Font Size:"))
    # font_size_decrease_action = QAction("−", main_window)
    # font_size_decrease_action.setToolTip("Decrease overlay font size")
    # font_size_decrease_action.triggered.connect(main_window._on_font_size_decrease)
    # toolbar.addAction(font_size_decrease_action)
    # font_size_increase_action = QAction("+", main_window)
    # font_size_increase_action.setToolTip("Increase overlay font size")
    # font_size_increase_action.triggered.connect(main_window._on_font_size_increase)
    # toolbar.addAction(font_size_increase_action)
    #
    # toolbar.addSeparator()
    # spacer = QWidget()
    # spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
    # toolbar.addWidget(spacer)
    # toolbar.addWidget(QLabel("Scroll Wheel:"))
    # main_window.scroll_wheel_mode_combo = QComboBox()
    # main_window.scroll_wheel_mode_combo.setObjectName("scroll_wheel_mode_combo")
    # main_window.scroll_wheel_mode_combo.addItems(["Slice", "Zoom"])
    # current_mode = (
    #     main_window.config_manager.get_scroll_wheel_mode()
    #     if main_window.config_manager
    #     else "slice"
    # )
    # if current_mode == "zoom":
    #     main_window.scroll_wheel_mode_combo.setCurrentIndex(1)
    # else:
    #     main_window.scroll_wheel_mode_combo.setCurrentIndex(0)
    # main_window.scroll_wheel_mode_combo.currentTextChanged.connect(
    #     main_window._on_scroll_wheel_mode_combo_changed
    # )
    # toolbar.addWidget(main_window.scroll_wheel_mode_combo)
