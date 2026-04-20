"""
Series Navigator Widget

This module provides a horizontal series navigator bar that displays thumbnails
of the first slice of each series with series numbers overlaid.

View widgets live in gui.series_navigator_view; study/instance helpers in
gui.series_navigator_model.

Inputs:
    - Studies dictionary with series data
    - Current study and series UIDs
    - DICOMProcessor for thumbnail generation

Outputs:
    - Visual series navigator with clickable thumbnails
    - Series selection signal

Requirements:
    - PySide6 for GUI components
    - PIL/Pillow for image handling
    - DICOMProcessor for image conversion
    - Thumbnail W/L uses the same preset / series-range / rescale rules as slice display
      (see `_resolve_thumbnail_window_level` and `core.slice_display_lut`).
"""

from PySide6.QtWidgets import (
    QWidget,
    QHBoxLayout,
    QScrollArea,
    QVBoxLayout,
    QFrame,
)
from PySide6.QtCore import Qt, Signal, QPoint
from PySide6.QtGui import QKeyEvent, QMouseEvent
from typing import Any, Optional, Dict, List, Tuple
from pydicom.dataset import Dataset
from core.dicom_processor import DICOMProcessor
from core.dicom_organizer import MultiFrameSeriesInfo
from PIL import Image
import time
import numpy as np

from utils.debug_flags import DEBUG_NAV
from gui.series_navigator_view import StudyDivider, StudyLabel, SeriesThumbnail
from gui.series_navigator_model import (
    build_instance_entries_for_navigator,
    study_label_from_dataset,
    build_study_navigator_tooltip,
    build_series_navigator_tooltip,
    build_instance_navigator_tooltip,
)
from gui.mpr_thumbnail_widget import MprThumbnailWidget
from core.slice_display_lut import apply_window_level_rescale_conversion


class SeriesNavigator(QWidget):
    """
    Horizontal series navigator bar with thumbnails.
    
    Displays thumbnails of the first slice of each series with series numbers
    overlaid. Clicking a thumbnail navigates to that series.
    """
    
    series_selected = Signal(str)  # Emitted with series_uid when thumbnail is clicked
    instance_selected = Signal(str, str, int)  # Emitted with (study_uid, series_uid, target_slice_index)
    show_instances_separately_toggled = Signal(bool)  # Emitted when navigator context menus toggle instance expansion
    series_navigation_requested = Signal(int)  # Emitted when arrow keys are pressed (-1 for prev, 1 for next)
    show_file_requested = Signal(str, str)  # Emitted with (study_uid, series_uid) when "Show file" is requested
    about_this_file_requested = Signal(str, str)  # Emitted with (study_uid, series_uid) when "About This File" is requested
    close_series_requested = Signal(str, str)  # (study_uid, series_key) — forwarded from thumbnail
    close_study_requested = Signal(str)         # (study_uid) — forwarded from thumbnail
    mpr_thumbnail_clicked = Signal(int)         # Emitted with subwindow_index when an MPR thumbnail is clicked
    mpr_thumbnail_clear_requested = Signal(int)  # Right-click → Clear MPR (index -1 = detached)

    def __init__(self, dicom_processor: DICOMProcessor, parent=None):
        """
        Initialize series navigator.
        
        Args:
            dicom_processor: DICOMProcessor instance for thumbnail generation
            parent: Parent widget
        """
        super().__init__(parent)
        self.setObjectName("series_navigator")
        self.dicom_processor = dicom_processor
        self.current_study_uid = ""
        self.current_series_uid = ""
        self.current_slice_index = 0
        self.thumbnails: Dict[str, SeriesThumbnail] = {}
        self.instance_thumbnails: Dict[str, SeriesThumbnail] = {}

        # Store study labels and dividers for cleanup
        self.study_labels: List[StudyLabel] = []
        self.study_dividers: List[StudyDivider] = []

        # Thumbnail cache: (study_uid, series_uid) -> PIL Image
        self.thumbnail_cache: Dict[Tuple[str, str], Image.Image] = {}
        self.instance_thumbnail_cache: Dict[Tuple[str, str, int], Image.Image] = {}
        self._last_studies: Dict[str, Any] = {}
        self._instance_start_indices: Dict[Tuple[str, str], List[int]] = {}
        self._multiframe_info_map: Dict[Tuple[str, str], MultiFrameSeriesInfo] = {}
        self._show_instances_separately = False
        self._privacy_mode_enabled = False
        # Compact slice/frame count on main series thumbnails (config-driven from main.py).
        self._show_slice_frame_count_badge: bool = True

        # Current subwindow slot → (study_uid, series_key) assignments for dot indicators
        self._subwindow_assignments: Dict[int, tuple[Any, ...]] = {}

        # Active MPR thumbnail render state keyed by subwindow index.
        # Widgets are rebuilt with the navigator so MPR entries can live inside
        # the correct study section, immediately after the source series.
        self._mpr_thumbnail_specs: Dict[int, Dict[str, Any]] = {}
        self._mpr_thumbnails: Dict[int, MprThumbnailWidget] = {}
        # Optional container for MPR row in ``main_layout`` (``clear`` skips deleting it).
        self._mpr_section_container: Optional[QWidget] = None

        # Enable keyboard focus so we can receive key events
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        
        self._create_ui()

    # ------------------------------------------------------------------
    # MPR thumbnail data + widgets
    # ------------------------------------------------------------------

    def _create_mpr_thumbnail_widget(
        self,
        subwindow_index: int,
        parent: QWidget,
    ) -> MprThumbnailWidget:
        """
        Create a navigator widget for one active MPR entry.

        The widget is ephemeral and tied to the current navigator layout build.
        Persistent MPR state lives in ``_mpr_thumbnail_specs`` instead.
        """
        widget = MprThumbnailWidget(subwindow_index, parent=parent)
        widget.clicked.connect(self.mpr_thumbnail_clicked.emit)
        widget.clear_mpr_requested.connect(self.mpr_thumbnail_clear_requested.emit)
        self._mpr_thumbnails[subwindow_index] = widget
        return widget

    def set_mpr_thumbnail(
        self,
        subwindow_index: int,
        pixel_array: Optional[np.ndarray],
        study_uid: str,
        source_series_uid: str,
        window_center: Optional[float] = None,
        window_width: Optional[float] = None,
        n_slices: Optional[int] = None,
    ) -> None:
        """
        Show or update an MPR thumbnail for *subwindow_index*.

        Passing ``pixel_array=None`` is equivalent to calling
        ``clear_mpr_thumbnail(subwindow_index)``.

        Args:
            subwindow_index: Subwindow slot (0–3), or -1 for detached MPR (same
                placement as attached: after the source series in that study).
            pixel_array:     2-D float MPR slice array, or None to remove.
            study_uid:       Study the source series belongs to.
            source_series_uid: Series key the MPR was built from.
            window_center:   W/L centre for rendering (optional).
            window_width:    W/L width for rendering (optional, must be > 0).
            n_slices:        Number of planes in the MPR stack for the navigator
                             slice-count badge (optional).
        """
        if pixel_array is None:
            self.clear_mpr_thumbnail(subwindow_index)
            return

        self._mpr_thumbnail_specs[subwindow_index] = {
            "study_uid": study_uid,
            "source_series_uid": source_series_uid,
            "pixel_array": pixel_array.copy(),
            "window_center": window_center,
            "window_width": window_width,
            "n_slices": n_slices,
        }
        self._rebuild_from_cached_studies()

    def clear_mpr_thumbnail(self, subwindow_index: int) -> None:
        """
        Remove the MPR thumbnail for *subwindow_index* from the navigator.

        Args:
            subwindow_index: Zero-based subwindow slot.
        """
        self._mpr_thumbnail_specs.pop(subwindow_index, None)
        self._rebuild_from_cached_studies()

    def set_show_slice_frame_count_badge(self, show: bool) -> None:
        """Toggle slice/frame count badge on series thumbnails (persists via config)."""
        self._show_slice_frame_count_badge = bool(show)
        for thumb in self.thumbnails.values():
            thumb.set_show_slice_frame_count_badge(self._show_slice_frame_count_badge)
        for thumb in self.instance_thumbnails.values():
            thumb.set_show_slice_frame_count_badge(False)
        for mpr_w in self._mpr_thumbnails.values():
            mpr_w.set_show_slice_frame_count_badge(self._show_slice_frame_count_badge)

    def set_multiframe_info_map(self, info_map: Dict[Tuple[str, str], MultiFrameSeriesInfo]) -> None:
        """Set per-series multiframe metadata used when painting thumbnails."""
        new_map = dict(info_map)
        changed = new_map != self._multiframe_info_map
        self._multiframe_info_map = new_map
        if changed:
            self._rebuild_from_cached_studies()

    def set_show_instances_separately(self, enabled: bool) -> None:
        """Store Phase 4 expansion preference and rebuild thumbnails if needed."""
        enabled = bool(enabled)
        changed = enabled != self._show_instances_separately
        self._show_instances_separately = enabled
        if changed:
            self._rebuild_from_cached_studies()

    def set_privacy_mode(self, enabled: bool) -> None:
        """
        Align navigator hover tooltips with View → Privacy mode.

        Rebuilds from cached studies when any are loaded so ``Patient name``
        lines match metadata / parser masking (``PRIVACY MODE``).
        """
        self._privacy_mode_enabled = bool(enabled)
        self._rebuild_from_cached_studies()

    def get_show_instances_separately(self) -> bool:
        """Return the current navigator expansion preference."""
        return self._show_instances_separately

    def can_expand_series(self, study_uid: str, series_uid: str) -> bool:
        """Return whether the given series supports per-instance expansion."""
        multiframe_info = self._multiframe_info_map.get((study_uid, series_uid))
        return bool(
            multiframe_info is not None
            and multiframe_info.max_frame_count > 1
            and multiframe_info.instance_count > 1
        )

    def _rebuild_from_cached_studies(self) -> None:
        """Rebuild thumbnails using the most recent studies/current selection."""
        if not self._last_studies:
            return
        self.update_series_list(
            self._last_studies,
            self.current_study_uid,
            self.current_series_uid,
        )
        self._refresh_dot_indicators()

    def _add_show_instances_action(self, menu, study_uid: str = "", series_uid: str = "") -> None:
        """Add the shared Show Instances Separately toggle action to a context menu."""
        action = menu.addAction("Show Instances Separately")
        action.setCheckable(True)
        action.setChecked(self._show_instances_separately)
        can_toggle = self._show_instances_separately or self.can_expand_series(study_uid, series_uid)
        action.setEnabled(can_toggle)
        # Do not connect triggered → Signal.emit directly: PySide6 may invoke the slot
        # with no arguments while show_instances_separately_toggled is Signal(bool).
        action.triggered.connect(
            lambda *args, act=action: self.show_instances_separately_toggled.emit(
                act.isChecked()
            )
        )

    def _show_navigator_context_menu(self, global_pos: QPoint) -> None:
        """Show a context menu for the navigator background/blank space."""
        from PySide6.QtWidgets import QMenu

        context_menu = QMenu(self)
        self._add_show_instances_action(
            context_menu,
            self.current_study_uid,
            self.current_series_uid,
        )
        context_menu.exec(global_pos)
    
    def _create_ui(self) -> None:
        """Create the UI layout with two-row structure (label row + thumbnail row)."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Create scroll area for horizontal scrolling
        scroll_area = QScrollArea(self)
        self.scroll_area = scroll_area
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        scroll_area.setObjectName("series_navigator_scroll_area")
        
        # Main container widget for study sections
        self.main_container = QWidget()
        self.main_container.setObjectName("series_navigator_container")
        self.main_container.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.main_container.customContextMenuRequested.connect(
            lambda pos: self._show_navigator_context_menu(self.main_container.mapToGlobal(pos))
        )
        self.main_layout = QHBoxLayout(self.main_container)
        # Reduce margins to ensure thumbnails aren't cut off
        # Top margin for spacing, left/right for padding, bottom minimal to prevent clipping
        self.main_layout.setContentsMargins(5, 5, 5, 1)
        self.main_layout.setSpacing(0)  # No spacing, dividers provide separation
        self.main_layout.addStretch()  # Add stretch at end
        
        scroll_area.setWidget(self.main_container)
        scroll_area.viewport().setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        scroll_area.viewport().customContextMenuRequested.connect(
            lambda pos: self._show_navigator_context_menu(scroll_area.viewport().mapToGlobal(pos))
        )
        layout.addWidget(scroll_area)
        
        # Set fixed height for navigator: 
        # Top margin (5px) + label row (18px) + thumbnail row (68px) + border (2px) + bottom margin (1px) = 94px
        # Round up to 95px for safety
        self.setFixedHeight(95)
    
    def update_series_list(self, studies: Dict[str, Any], current_study_uid: str, current_series_uid: str) -> None:
        """
        Update the series list with thumbnails from all studies.
        
        Displays all series from all studies in a two-row layout:
        - Top row: Study labels spanning full width of their thumbnails
        - Bottom row: Series thumbnails
        - Vertical dividers span both rows to separate studies.
        
        Args:
            studies: Dictionary of studies {study_uid: {series_uid: [datasets]}}
            current_study_uid: Current study UID
            current_series_uid: Current series UID
        """
        self.current_study_uid = current_study_uid
        self.current_series_uid = current_series_uid
        self._last_studies = studies
        
        # Clear existing widgets from main layout (keep stretch at the end).
        while self.main_layout.count() > 1:  # Keep the stretch at the end
            layout_item = self.main_layout.takeAt(0)
            if layout_item is None:
                break
            w = layout_item.widget()
            if w is None:
                continue
            w.deleteLater()
        
        # Clear tracking lists
        self.thumbnails.clear()
        self.instance_thumbnails.clear()
        self._mpr_thumbnails.clear()
        self.study_labels.clear()
        self.study_dividers.clear()
        self._instance_start_indices.clear()
        
        if not studies:
            return

        # Iterate through all studies and create study sections
        first_study = True
        for study_uid, study_series in studies.items():
            # Skip studies with no series
            if not study_series:
                continue
            
            # Add divider before study (except for first study)
            if not first_study:
                divider = StudyDivider(self.main_container)
                self.study_dividers.append(divider)
                self.main_layout.insertWidget(self.main_layout.count() - 1, divider)
            
            # Get study label from first dataset of first series
            study_label_text = "Unknown Study"
            first_dataset = None
            
            # Find first series with datasets
            for series_uid, datasets in study_series.items():
                if datasets:
                    first_dataset = datasets[0]
                    break
            
            if first_dataset:
                study_label_text = study_label_from_dataset(first_dataset)
            
            # Build list of (series_number, series_uid, first_dataset) for this study
            series_list = []
            for series_uid, datasets in study_series.items():
                if datasets:
                    first_dataset = datasets[0]
                    series_number = getattr(first_dataset, 'SeriesNumber', None)
                    try:
                        series_num = int(series_number) if series_number is not None else 0
                    except (ValueError, TypeError):
                        series_num = 0
                    series_list.append((series_num, series_uid, first_dataset))
            
            # Sort by series number
            series_list.sort(key=lambda x: x[0])
            
            # Calculate width for this study section based on visible thumbnail groups,
            # including any MPR thumbnails inserted after their source series.
            thumbnail_width = 68
            thumbnail_spacing = 5
            instance_thumbnail_width = 48
            instance_spacing = 4
            section_width = 0
            for _, series_uid, _ in series_list:
                group_width = thumbnail_width
                multiframe_info = self._multiframe_info_map.get((study_uid, series_uid))
                if (
                    self._show_instances_separately
                    and multiframe_info is not None
                    and multiframe_info.instance_count > 1
                    and multiframe_info.max_frame_count > 1
                ):
                    instance_count = multiframe_info.instance_count
                    group_width += instance_spacing + (instance_count * instance_thumbnail_width) + ((instance_count - 1) * instance_spacing)
                if section_width > 0:
                    section_width += thumbnail_spacing
                section_width += group_width
                mpr_count = sum(
                    1
                    for spec in self._mpr_thumbnail_specs.values()
                    if spec.get("study_uid") == study_uid
                    and spec.get("source_series_uid") == series_uid
                )
                if mpr_count > 0:
                    section_width += mpr_count * (thumbnail_spacing + thumbnail_width)
            if section_width <= 0:
                section_width = thumbnail_width
            
            # Create study section container
            # The global stylesheet has: QWidget[objectName="series_navigator_container"] > QWidget
            # This should apply to child widgets, but we need WA_StyledBackground for it to work
            study_section = QWidget(self.main_container)
            # Enable styled background so the global stylesheet rule applies
            study_section.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
            # Don't set local stylesheet - let the global one handle it
            # The global stylesheet rule should match: QWidget[objectName="series_navigator_container"] > QWidget
            
            section_layout = QVBoxLayout(study_section)
            section_layout.setContentsMargins(0, 0, 0, 0)
            section_layout.setSpacing(0)
            
            # Add study label at top (spans full width of section)
            study_label = StudyLabel(study_label_text, study_section)
            study_label.set_width(section_width)
            if first_dataset is not None:
                study_label.apply_navigator_tooltip(
                    build_study_navigator_tooltip(
                        first_dataset,
                        privacy_mode=self._privacy_mode_enabled,
                    )
                )
            else:
                study_label.apply_navigator_tooltip("")
            self.study_labels.append(study_label)
            section_layout.addWidget(study_label)
            
            # Create thumbnails container
            # The global stylesheet should apply here too via the child selector
            thumbnails_container = QWidget(study_section)
            # Enable styled background so the global stylesheet rule applies
            thumbnails_container.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
            # Don't set local stylesheet - let the global one handle it
            thumbnails_layout = QHBoxLayout(thumbnails_container)
            thumbnails_layout.setContentsMargins(0, 0, 0, 0)
            thumbnails_layout.setSpacing(thumbnail_spacing)
            
            # Create thumbnails for this study
            for series_num, series_uid, first_dataset in series_list:
                # Check cache first
                cache_key = (study_uid, series_uid)
                if cache_key in self.thumbnail_cache:
                    thumbnail_image = self.thumbnail_cache[cache_key]
                else:
                    # Generate thumbnail (WL aligned with slice display: presets / series range / rescale)
                    thumbnail_image = self._generate_thumbnail(
                        first_dataset,
                        study_series[series_uid],
                    )
                    if thumbnail_image:
                        self.thumbnail_cache[cache_key] = thumbnail_image
                
                series_group_widget = QWidget(thumbnails_container)
                series_group_layout = QHBoxLayout(series_group_widget)
                series_group_layout.setContentsMargins(0, 0, 0, 0)
                series_group_layout.setSpacing(4)

                # Create main series thumbnail widget
                thumbnail = SeriesThumbnail(series_uid, series_num, thumbnail_image, study_uid, series_group_widget)
                thumbnail.clicked.connect(self.series_selected.emit)
                thumbnail.show_file_requested.connect(self.show_file_requested.emit)
                thumbnail.about_this_file_requested.connect(self.about_this_file_requested.emit)
                thumbnail.close_series_signal.connect(self.close_series_requested.emit)
                thumbnail.close_study_signal.connect(self.close_study_requested.emit)

                thumbnail.setToolTip(
                    build_series_navigator_tooltip(
                        first_dataset,
                        privacy_mode=self._privacy_mode_enabled,
                    )
                )

                is_current = (series_uid == current_series_uid and study_uid == current_study_uid)
                thumbnail.set_current(is_current)
                multiframe_info = self._multiframe_info_map.get((study_uid, series_uid))
                if multiframe_info is not None:
                    thumbnail.set_multiframe_info(
                        multiframe_info.instance_count,
                        multiframe_info.max_frame_count,
                    )
                else:
                    thumbnail.set_multiframe_info(1, 1)
                thumbnail.set_show_slice_frame_count_badge(self._show_slice_frame_count_badge)

                composite_key = f"{study_uid}:{series_uid}"
                self.thumbnails[composite_key] = thumbnail
                series_group_layout.addWidget(thumbnail)

                if (
                    self._show_instances_separately
                    and multiframe_info is not None
                    and multiframe_info.instance_count > 1
                    and multiframe_info.max_frame_count > 1
                ):
                    instance_entries = build_instance_entries_for_navigator(study_series[series_uid])
                    self._instance_start_indices[(study_uid, series_uid)] = [
                        slice_index for slice_index, _, _ in instance_entries
                    ]
                    for slice_index, instance_dataset, instance_label in instance_entries:
                        cache_key = (study_uid, series_uid, slice_index)
                        if cache_key in self.instance_thumbnail_cache:
                            instance_thumbnail_image = self.instance_thumbnail_cache[cache_key]
                        else:
                            instance_thumbnail_image = self._generate_thumbnail(
                                instance_dataset,
                                study_series[series_uid],
                            )
                            if instance_thumbnail_image:
                                self.instance_thumbnail_cache[cache_key] = instance_thumbnail_image

                        instance_thumbnail = SeriesThumbnail(
                            series_uid,
                            series_num,
                            instance_thumbnail_image,
                            study_uid,
                            series_group_widget,
                            display_label=instance_label,
                            target_slice_index=slice_index,
                            thumbnail_size=48,
                        )
                        instance_thumbnail.instance_clicked.connect(self.instance_selected.emit)
                        instance_thumbnail.show_file_requested.connect(self.show_file_requested.emit)
                        instance_thumbnail.about_this_file_requested.connect(self.about_this_file_requested.emit)
                        instance_thumbnail.close_series_signal.connect(self.close_series_requested.emit)
                        instance_thumbnail.close_study_signal.connect(self.close_study_requested.emit)
                        instance_thumbnail.set_show_slice_frame_count_badge(False)
                        instance_thumbnail.setToolTip(
                            build_instance_navigator_tooltip(
                                first_dataset,
                                instance_label,
                                privacy_mode=self._privacy_mode_enabled,
                            )
                        )
                        instance_composite_key = f"{study_uid}:{series_uid}:{slice_index}"
                        self.instance_thumbnails[instance_composite_key] = instance_thumbnail
                        series_group_layout.addWidget(instance_thumbnail)

                thumbnails_layout.addWidget(series_group_widget)

                for mpr_idx, mpr_spec in self._mpr_thumbnail_specs.items():
                    if (
                        mpr_spec.get("study_uid") != study_uid
                        or mpr_spec.get("source_series_uid") != series_uid
                    ):
                        continue
                    mpr_widget = self._create_mpr_thumbnail_widget(
                        mpr_idx,
                        thumbnails_container,
                    )
                    mpr_widget.update_preview(
                        mpr_spec.get("pixel_array"),
                        mpr_spec.get("window_center"),
                        mpr_spec.get("window_width"),
                    )
                    mpr_widget.set_slice_count(mpr_spec.get("n_slices"))
                    mpr_widget.set_show_slice_frame_count_badge(
                        self._show_slice_frame_count_badge
                    )
                    thumbnails_layout.addWidget(mpr_widget)
            
            # Add thumbnails container to section
            section_layout.addWidget(thumbnails_container)
            
            # Add study section to main layout
            self.main_layout.insertWidget(self.main_layout.count() - 1, study_section)
            
            first_study = False

        self.set_current_position(current_series_uid, current_study_uid, self.current_slice_index)

    def set_subwindow_assignments(self, assignments: Dict[int, tuple[Any, ...]]) -> None:
        """
        Update which subwindow slots are currently displaying which series, then
        repaint the window-number indicators on all thumbnails.

        Must be called **after** update_series_list() so thumbnails exist.

        Args:
            assignments: Mapping of subwindow_idx → assignment tuple for every
                         occupied subwindow. Supported formats are
                         `(study_uid, series_key)` and `(study_uid, series_key, slice_index)`.
                         Pass an empty dict to clear all indicators.
        """
        self._subwindow_assignments = dict(assignments)
        self._refresh_dot_indicators()

    def _refresh_dot_indicators(self) -> None:
        """
        Rebuild the reverse map from (study_uid, series_key) → [slot_indices] and
        push the appropriate slot list to every thumbnail's ``set_subwindow_dots()``.
        """
        # Build reverse map: composite_key → list of slot indices
        reverse: Dict[str, List[int]] = {}
        instance_reverse: Dict[str, List[int]] = {}
        for slot_idx, assignment in self._subwindow_assignments.items():
            if not assignment or len(assignment) < 2:
                continue
            study_uid, series_key = assignment[0], assignment[1]
            slice_index = assignment[2] if len(assignment) > 2 else None
            composite_key = f"{study_uid}:{series_key}"
            reverse.setdefault(composite_key, []).append(slot_idx)
            if slice_index is not None:
                instance_key = self._get_instance_thumbnail_key(study_uid, series_key, slice_index)
                if instance_key is not None:
                    instance_reverse.setdefault(instance_key, []).append(slot_idx)

        # Apply to thumbnails — thumbnails not in the map get empty list (no numbers)
        for composite_key, thumbnail in self.thumbnails.items():
            thumbnail.set_subwindow_dots(reverse.get(composite_key, []))
        for composite_key, thumbnail in self.instance_thumbnails.items():
            thumbnail.set_subwindow_dots(instance_reverse.get(composite_key, []))

    def _get_instance_thumbnail_key(self, study_uid: str, series_uid: str, slice_index: int) -> Optional[str]:
        """Return the instance-thumbnail key that contains the provided slice index."""
        start_indices = self._instance_start_indices.get((study_uid, series_uid), [])
        if not start_indices:
            return None

        selected_start = start_indices[0]
        for start_index in start_indices:
            if slice_index < start_index:
                break
            selected_start = start_index
        return f"{study_uid}:{series_uid}:{selected_start}"

    def _resolve_thumbnail_window_level(
        self,
        dataset: Dataset,
        series_datasets: Optional[List[Dataset]],
    ) -> Tuple[Optional[float], Optional[float], bool]:
        """
        Match SliceDisplayManager new-series defaults: presets, tag WC/WW with rescale
        alignment, then series-wide or single-slice auto range. Returns (wc, ww, apply_rescale).
        """
        dp = self.dicom_processor
        rescale_slope, rescale_intercept, _ = dp.get_rescale_parameters(dataset)
        use_rescaled = rescale_slope is not None and rescale_intercept is not None

        series_pixel_min: Optional[float] = None
        series_pixel_max: Optional[float] = None
        if series_datasets:
            try:
                series_pixel_min, series_pixel_max = dp.get_series_pixel_value_range(
                    series_datasets, apply_rescale=use_rescaled
                )
            except Exception:
                series_pixel_min, series_pixel_max = None, None

        window_center: Optional[float] = None
        window_width: Optional[float] = None

        presets = dp.get_window_level_presets_from_dataset(
            dataset,
            rescale_slope=rescale_slope,
            rescale_intercept=rescale_intercept,
        )
        if presets:
            wc, ww, is_rescaled, _ = presets[0]
            wc, ww = apply_window_level_rescale_conversion(
                wc,
                ww,
                is_rescaled=is_rescaled,
                use_rescaled_values=use_rescaled,
                rescale_slope=rescale_slope,
                rescale_intercept=rescale_intercept,
                dicom_processor=dp,
            )
            window_center, window_width = wc, ww
        else:
            wc, ww, is_rescaled = dp.get_window_level_from_dataset(
                dataset,
                rescale_slope=rescale_slope,
                rescale_intercept=rescale_intercept,
            )
            if wc is not None and ww is not None:
                wc, ww = apply_window_level_rescale_conversion(
                    wc,
                    ww,
                    is_rescaled=is_rescaled,
                    use_rescaled_values=use_rescaled,
                    rescale_slope=rescale_slope,
                    rescale_intercept=rescale_intercept,
                    dicom_processor=dp,
                )
                window_center, window_width = wc, ww
            elif (
                series_pixel_min is not None
                and series_pixel_max is not None
                and series_datasets
            ):
                midpoint = (series_pixel_min + series_pixel_max) / 2.0
                median = dp.get_series_pixel_median(
                    series_datasets, apply_rescale=use_rescaled
                )
                if median is None:
                    window_center = midpoint
                else:
                    window_center = max(median, midpoint)
                window_width = series_pixel_max - series_pixel_min
                if window_width <= 0:
                    window_width = 1.0
            else:
                try:
                    pixel_min, pixel_max = dp.get_pixel_value_range(
                        dataset, apply_rescale=use_rescaled
                    )
                    if pixel_min is not None and pixel_max is not None:
                        pixel_array = dp.get_pixel_array(dataset)
                        if pixel_array is not None:
                            arr = pixel_array.astype(np.float32)
                            if use_rescaled and rescale_slope is not None and rescale_intercept is not None:
                                arr = arr * float(rescale_slope) + float(rescale_intercept)
                            midpoint = (pixel_min + pixel_max) / 2.0
                            non_zero = arr[arr != 0]
                            if len(non_zero) > 0:
                                window_center = max(float(np.median(non_zero)), midpoint)
                            else:
                                window_center = midpoint
                            window_width = pixel_max - pixel_min
                            if window_width <= 0:
                                window_width = 1.0
                except Exception:
                    pass

        return window_center, window_width, use_rescaled

    def _generate_thumbnail(
        self,
        dataset: Dataset,
        series_datasets: Optional[List[Dataset]] = None,
    ) -> Optional[Image.Image]:
        """
        Generate thumbnail image from a dataset (typically first slice of a series).

        Window/level and rescale match SliceDisplayManager so thumbnails are not black
        when tag-only WC/WW disagree with series statistics or HU rescale is used.

        Args:
            dataset: DICOM dataset to render (same slice the bar represents).
            series_datasets: Full series list for series-wide auto W/L; optional.

        Returns:
            PIL Image thumbnail (resized) or None if generation fails
        """
        try:
            # Check if this is a compressed file that can't be decoded
            if hasattr(dataset, 'file_meta') and hasattr(dataset.file_meta, 'TransferSyntaxUID'):
                transfer_syntax = str(dataset.file_meta.TransferSyntaxUID)
                # Check for JPEG compression transfer syntaxes that require pylibjpeg
                jpeg_transfer_syntaxes = [
                    '1.2.840.10008.1.2.4.50',  # JPEG Baseline (Process 1)
                    '1.2.840.10008.1.2.4.51',  # JPEG Extended (Process 2 & 4)
                    '1.2.840.10008.1.2.4.57',  # JPEG Lossless, Non-Hierarchical (Process 14)
                    '1.2.840.10008.1.2.4.70',  # JPEG Lossless, Non-Hierarchical (Process 14 [Selection Value 1])
                    '1.2.840.10008.1.2.4.80',  # JPEG-LS Lossless Image Compression
                    '1.2.840.10008.1.2.4.81',  # JPEG-LS Lossy (Near-Lossless) Image Compression
                    '1.2.840.10008.1.2.4.90',  # JPEG 2000 Image Compression (Lossless Only)
                    '1.2.840.10008.1.2.4.91',  # JPEG 2000 Image Compression
                ]
                if transfer_syntax in jpeg_transfer_syntaxes:
                    # Try to check if pixel array can be accessed (this will fail if pylibjpeg not installed)
                    try:
                        # Just check if we can access pixel_array property (don't actually load it)
                        _ = dataset.pixel_array
                    except Exception as e:
                        error_msg = str(e)
                        if ("pylibjpeg" in error_msg.lower() or
                            "missing required dependencies" in error_msg.lower() or
                            "unable to convert" in error_msg.lower()):
                            # This is a compressed file that can't be decoded
                            # Return a special marker image that will show compression error
                            return self._create_compression_error_thumbnail()

            wc, ww, use_rescaled = self._resolve_thumbnail_window_level(
                dataset, series_datasets
            )
            if wc is not None and ww is not None:
                image = self.dicom_processor.dataset_to_image(
                    dataset,
                    window_center=wc,
                    window_width=ww,
                    apply_rescale=use_rescaled,
                )
            else:
                image = self.dicom_processor.dataset_to_image(
                    dataset, apply_rescale=use_rescaled
                )
            if image is None:
                return None

            # Resize to thumbnail size (maintain aspect ratio)
            thumbnail_size = 57  # Target size for thumbnail (85% of 67px to fit smaller navigator height)
            image.thumbnail((thumbnail_size, thumbnail_size), Image.Resampling.LANCZOS)

            return image
        except Exception as e:
            error_msg = str(e)
            # Check if this is a compression error
            if ("pylibjpeg" in error_msg.lower() or
                "missing required dependencies" in error_msg.lower() or
                "unable to convert" in error_msg.lower()):
                return self._create_compression_error_thumbnail()
            print(f"Error generating thumbnail: {e}")
            return None
    
    def _create_compression_error_thumbnail(self) -> Image.Image:
        """
        Create a thumbnail placeholder indicating compression error.
        
        Returns:
            PIL Image with compression error indicator
        """
        from PIL import ImageDraw, ImageFont
        # Create a small image with error indicator
        size = 57
        img = Image.new('RGB', (size, size), color=(200, 150, 150))  # Light red background
        draw = ImageDraw.Draw(img)
        
        # Try to use a font, fallback to default if not available
        try:
            font = ImageFont.truetype("arial.ttf", 8)
        except:
            font = ImageFont.load_default()
        
        # Draw "COMP" text to indicate compression error
        text = "COMP"
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        x = (size - text_width) // 2
        y = (size - text_height) // 2
        draw.text((x, y), text, fill=(255, 255, 255), font=font)
        
        return img
    
    def set_current_series(self, series_uid: str, study_uid: Optional[str] = None) -> None:
        """
        Update current series highlighting.
        
        Args:
            series_uid: Series UID to highlight
            study_uid: Optional study UID. If provided, only highlights if both match.
                      If None, uses current_study_uid.
        """
        self.set_current_position(series_uid, study_uid, self.current_slice_index)

    def set_current_position(
        self,
        series_uid: str,
        study_uid: Optional[str] = None,
        slice_index: Optional[int] = None,
    ) -> None:
        """Update current highlighting for both the series thumbnail and instance thumbnail."""
        self.current_series_uid = series_uid
        if study_uid is not None:
            self.current_study_uid = study_uid
        if slice_index is not None:
            self.current_slice_index = max(0, int(slice_index))

        # Update highlighting for all series thumbnails.
        for composite_key, thumbnail in self.thumbnails.items():
            if ":" in composite_key:
                stored_study_uid, stored_series_uid = composite_key.split(":", 1)
                is_current = (
                    stored_series_uid == self.current_series_uid
                    and stored_study_uid == self.current_study_uid
                )
            else:
                is_current = (composite_key == self.current_series_uid)
            thumbnail.set_current(is_current)

        current_instance_key = None
        if self.current_series_uid and self.current_study_uid:
            current_instance_key = self._get_instance_thumbnail_key(
                self.current_study_uid,
                self.current_series_uid,
                self.current_slice_index,
            )

        for composite_key, thumbnail in self.instance_thumbnails.items():
            thumbnail.set_current(composite_key == current_instance_key)
    
    def regenerate_series_thumbnail(self, study_uid: str, series_uid: str, 
                                    dataset: Dataset, window_center: float, 
                                    window_width: float, apply_rescale: bool) -> None:
        """
        Regenerate thumbnail for a specific series with explicit window/level values.
        
        This is used to update thumbnails when window/level values are corrected
        after initial generation.
        
        Args:
            study_uid: Study instance UID
            series_uid: Series instance UID
            dataset: DICOM dataset (first slice of series)
            window_center: Window center value
            window_width: Window width value
            apply_rescale: Whether to apply rescale to the thumbnail
        """
        # Invalidate cached thumbnail for this series
        cache_key = (study_uid, series_uid)
        if cache_key in self.thumbnail_cache:
            del self.thumbnail_cache[cache_key]
        
        # Generate new thumbnail with explicit window/level
        try:
            # Convert dataset to image with explicit window/level
            image = self.dicom_processor.dataset_to_image(
                dataset, 
                window_center=window_center,
                window_width=window_width,
                apply_rescale=apply_rescale
            )
            if image is None:
                return
            
            # Resize to thumbnail size (maintain aspect ratio)
            thumbnail_size = 57  # Target size for thumbnail
            image.thumbnail((thumbnail_size, thumbnail_size), Image.Resampling.LANCZOS)
            
            # Cache the new thumbnail
            self.thumbnail_cache[cache_key] = image
            
            # Update the thumbnail widget if it exists (use composite key)
            composite_key = f"{study_uid}:{series_uid}"
            if composite_key in self.thumbnails:
                thumbnail_widget = self.thumbnails[composite_key]
                thumbnail_widget.thumbnail_image = image
                thumbnail_widget.update()  # Trigger repaint
                # print(f"[DEBUG-WL] Regenerated series navigator thumbnail for series {series_uid[:20]}...")
        except Exception as e:
            print(f"Error regenerating thumbnail: {e}")
    
    def clear(self) -> None:
        """Clear all thumbnails, labels, dividers, and study sections."""
        # Clear all widgets from main layout (except stretch and MPR section).
        while self.main_layout.count() > 1:  # Keep the stretch at the end
            layout_item = self.main_layout.takeAt(0)
            if layout_item is None:
                break
            w = layout_item.widget()
            if w is None:
                continue
            if w is self._mpr_section_container:
                w.setParent(None)
                continue
            w.deleteLater()

        # Clear tracking lists
        self.thumbnails.clear()
        self.study_labels.clear()
        self.study_dividers.clear()

        # Clear cache
        self.thumbnail_cache.clear()
    
    def keyPressEvent(self, event: QKeyEvent) -> None:
        """
        Handle key press events for series navigation.
        
        Args:
            event: Key event
        """
        # Ignore key repeat events to prevent rapid navigation
        if event.isAutoRepeat():
            event.accept()
            return
        
        # Check if any text annotation is being edited - if so, don't process arrow keys for navigation
        if event.key() == Qt.Key.Key_Left or event.key() == Qt.Key.Key_Right:
            # Check if the focused widget is a TextAnnotationItem or if any text annotation is being edited
            from PySide6.QtWidgets import QApplication
            from tools.text_annotation_tool import TextAnnotationItem, is_any_text_annotation_editing
            
            focused_widget = QApplication.focusWidget()
            # Check if focused widget is a TextAnnotationItem that's being edited
            if isinstance(focused_widget, TextAnnotationItem) and getattr(focused_widget, '_editing', False):
                # Let the text editor handle arrow keys for cursor movement
                super().keyPressEvent(event)
                return
            
            # Also check the scene if we can find it
            scene = None
            parent = self.parent()
            while parent is not None:
                sc = getattr(parent, "scene", None)
                if sc is not None:
                    scene = sc
                    break
                image_viewer = getattr(parent, "image_viewer", None)
                if image_viewer is not None:
                    sc2 = getattr(image_viewer, "scene", None)
                    if sc2 is not None:
                        scene = sc2
                        break
                parent = parent.parent()
            
            if scene is not None and is_any_text_annotation_editing(scene):
                # Let the text editor handle arrow keys for cursor movement
                super().keyPressEvent(event)
                return
        
        if event.key() == Qt.Key.Key_Left:
            # Left arrow: previous series
            if DEBUG_NAV:
                timestamp = time.time()
                print(f"[DEBUG-NAV] [{timestamp:.6f}] SeriesNavigator.keyPressEvent: LEFT arrow pressed, hasFocus={self.hasFocus()}")
                print(f"[DEBUG-NAV] [{timestamp:.6f}] SeriesNavigator: Emitting series_navigation_requested(-1)")
            self.series_navigation_requested.emit(-1)
            event.accept()
        elif event.key() == Qt.Key.Key_Right:
            # Right arrow: next series
            if DEBUG_NAV:
                timestamp = time.time()
                print(f"[DEBUG-NAV] [{timestamp:.6f}] SeriesNavigator.keyPressEvent: RIGHT arrow pressed, hasFocus={self.hasFocus()}")
                print(f"[DEBUG-NAV] [{timestamp:.6f}] SeriesNavigator: Emitting series_navigation_requested(1)")
            self.series_navigation_requested.emit(1)
            event.accept()
        else:
            super().keyPressEvent(event)
    
    
    def mousePressEvent(self, event: QMouseEvent) -> None:
        """
        Handle mouse press to set focus so keyboard events work.
        
        Args:
            event: Mouse event
        """
        # Set focus when clicked so keyboard events are received
        self.setFocus()
        super().mousePressEvent(event)

