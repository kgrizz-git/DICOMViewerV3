"""
Annotation paste handler for DICOM Viewer V3.

Purpose: handle copy/paste of ROI, measurement, crosshair, text, and arrow
annotations. Inputs are getters for current subwindow, managers, and scene
(via an app reference). Outputs are copy/paste behavior.
"""

from typing import Dict, Optional

from PySide6.QtCore import QPointF, Qt
from gui.sub_window_container import SubWindowContainer


class AnnotationPasteHandler:
    """Handles copy/paste of annotations (ROIs, measurements, crosshairs, text, arrows)."""

    def __init__(self, app):
        self._app = app

    def get_selected_rois(self, subwindow: SubWindowContainer) -> list:
        """
        Get selected ROI items from the scene.

        Args:
            subwindow: SubWindowContainer to get ROIs from

        Returns:
            List of selected ROIItem objects
        """
        selected_rois = []
        if subwindow and subwindow.image_viewer and subwindow.image_viewer.scene:
            try:
                selected_items = subwindow.image_viewer.scene.selectedItems()
                from tools.roi_manager import ROIItem

                subwindows = self._app.multi_window_layout.get_all_subwindows()
                if subwindow in subwindows:
                    idx = subwindows.index(subwindow)
                    if idx in self._app.subwindow_managers:
                        roi_manager = self._app.subwindow_managers[idx]['roi_manager']
                        for item in selected_items:
                            key = (roi_manager.current_study_uid,
                                   roi_manager.current_series_uid,
                                   roi_manager.current_instance_identifier)
                            if key in roi_manager.rois:
                                for roi in roi_manager.rois[key]:
                                    if roi.item == item:
                                        selected_rois.append(roi)
                                        break
            except RuntimeError:
                pass
        return selected_rois

    def get_selected_measurements(self, subwindow: SubWindowContainer) -> list:
        """
        Get selected measurement items from the scene.

        Args:
            subwindow: SubWindowContainer to get measurements from

        Returns:
            List of selected MeasurementItem objects
        """
        selected_measurements = []
        if subwindow and subwindow.image_viewer and subwindow.image_viewer.scene:
            try:
                selected_items = subwindow.image_viewer.scene.selectedItems()
                from tools.measurement_tool import MeasurementItem

                for item in selected_items:
                    if isinstance(item, MeasurementItem):
                        selected_measurements.append(item)
            except RuntimeError:
                pass
        return selected_measurements

    def get_selected_crosshairs(self, subwindow: SubWindowContainer) -> list:
        """
        Get selected crosshair items from the scene.

        Args:
            subwindow: SubWindowContainer to get crosshairs from

        Returns:
            List of selected CrosshairItem objects
        """
        selected_crosshairs = []
        if subwindow and subwindow.image_viewer and subwindow.image_viewer.scene:
            try:
                selected_items = subwindow.image_viewer.scene.selectedItems()
                from tools.crosshair_manager import CrosshairItem

                for item in selected_items:
                    if isinstance(item, CrosshairItem):
                        selected_crosshairs.append(item)
            except RuntimeError:
                pass
        return selected_crosshairs

    def get_selected_text_annotations(self, subwindow: SubWindowContainer) -> list:
        """
        Get selected text annotation items from the scene.

        Args:
            subwindow: SubWindowContainer to get text annotations from

        Returns:
            List of selected TextAnnotationItem objects
        """
        selected_text_annotations = []
        if subwindow and subwindow.image_viewer and subwindow.image_viewer.scene:
            try:
                selected_items = subwindow.image_viewer.scene.selectedItems()
                from tools.text_annotation_tool import TextAnnotationItem

                for item in selected_items:
                    if isinstance(item, TextAnnotationItem):
                        selected_text_annotations.append(item)
            except RuntimeError:
                pass
        return selected_text_annotations

    def get_selected_arrow_annotations(self, subwindow: SubWindowContainer) -> list:
        """
        Get selected arrow annotation items from the scene.

        Args:
            subwindow: SubWindowContainer to get arrow annotations from

        Returns:
            List of selected ArrowAnnotationItem objects
        """
        selected_arrow_annotations = []
        if subwindow and subwindow.image_viewer and subwindow.image_viewer.scene:
            try:
                selected_items = subwindow.image_viewer.scene.selectedItems()
                from tools.arrow_annotation_tool import ArrowAnnotationItem

                for item in selected_items:
                    if isinstance(item, ArrowAnnotationItem):
                        selected_arrow_annotations.append(item)
            except RuntimeError:
                pass
        return selected_arrow_annotations

    def copy_annotations(self) -> None:
        """
        Copy selected annotations (ROIs, measurements, crosshairs, text, arrows) to clipboard.
        Only copies selected annotations. If nothing is selected, shows a status message.
        """
        subwindow = self._app._get_focused_subwindow()
        if not subwindow:
            return

        selected_rois = self.get_selected_rois(subwindow)
        selected_measurements = self.get_selected_measurements(subwindow)
        selected_crosshairs = self.get_selected_crosshairs(subwindow)
        selected_text_annotations = self.get_selected_text_annotations(subwindow)
        selected_arrow_annotations = self.get_selected_arrow_annotations(subwindow)

        total_count = (len(selected_rois) + len(selected_measurements) + len(selected_crosshairs) +
                      len(selected_text_annotations) + len(selected_arrow_annotations))
        if total_count == 0:
            self._app.main_window.update_status("No annotations selected")
            return

        subwindows = self._app.multi_window_layout.get_all_subwindows()
        if subwindow in subwindows:
            idx = subwindows.index(subwindow)
            if idx in self._app.subwindow_managers:
                roi_manager = self._app.subwindow_managers[idx]['roi_manager']
                self._app.annotation_clipboard.copy_annotations(
                    selected_rois,
                    selected_measurements,
                    selected_crosshairs,
                    roi_manager.current_study_uid,
                    roi_manager.current_series_uid,
                    roi_manager.current_instance_identifier,
                    text_annotations=selected_text_annotations,
                    arrow_annotations=selected_arrow_annotations
                )
                self._app.main_window.update_status(f"Copied {total_count} annotation(s)")

    def paste_annotations(self) -> None:
        """
        Paste annotations from clipboard to current slice.
        Applies smart offset: 10px offset if pasting to same slice, otherwise no offset.
        """
        if not self._app.annotation_clipboard.has_data():
            return

        data = self._app.annotation_clipboard.paste_annotations()
        if not data or data.get('type') != 'dicom_viewer_annotations':
            return

        subwindow = self._app._get_focused_subwindow()
        if not subwindow:
            return

        subwindows = self._app.multi_window_layout.get_all_subwindows()
        if subwindow not in subwindows:
            return

        idx = subwindows.index(subwindow)
        if idx not in self._app.subwindow_managers:
            return

        managers = self._app.subwindow_managers[idx]
        roi_manager = managers['roi_manager']
        text_annotation_tool = managers.get('text_annotation_tool')
        arrow_annotation_tool = managers.get('arrow_annotation_tool')

        current_key = (roi_manager.current_study_uid,
                      roi_manager.current_series_uid,
                      roi_manager.current_instance_identifier)
        source_key = self._app.annotation_clipboard.get_source_slice_key()
        offset = QPointF(10, 10) if current_key == source_key else QPointF(0, 0)

        newly_created = []

        for roi_data in data.get('rois', []):
            new_roi = self.paste_roi(subwindow, managers, roi_data, offset)
            if new_roi:
                newly_created.append(new_roi.item)

        for meas_data in data.get('measurements', []):
            new_measurement = self.paste_measurement(subwindow, managers, meas_data, offset)
            if new_measurement:
                newly_created.append(new_measurement)

        for cross_data in data.get('crosshairs', []):
            new_crosshair = self.paste_crosshair(subwindow, managers, cross_data, offset)
            if new_crosshair:
                newly_created.append(new_crosshair)

        if text_annotation_tool:
            for text_data in data.get('text_annotations', []):
                new_text = self.paste_text_annotation(subwindow, managers, text_data, offset)
                if new_text:
                    newly_created.append(new_text)

        if arrow_annotation_tool:
            for arrow_data in data.get('arrow_annotations', []):
                new_arrow = self.paste_arrow_annotation(subwindow, managers, arrow_data, offset)
                if new_arrow:
                    newly_created.append(new_arrow)

        if subwindow.image_viewer and subwindow.image_viewer.scene:
            subwindow.image_viewer.scene.clearSelection()

        for item in newly_created:
            try:
                item.setSelected(True)
            except RuntimeError:
                pass

        if hasattr(subwindow, 'update_roi_list'):
            subwindow.update_roi_list()
        if subwindow.image_viewer and subwindow.image_viewer.scene:
            subwindow.image_viewer.scene.update()

        total_count = (len(data.get('rois', [])) + len(data.get('measurements', [])) +
                      len(data.get('crosshairs', [])) + len(data.get('text_annotations', [])) +
                      len(data.get('arrow_annotations', [])))
        self._app.main_window.update_status(f"Pasted {total_count} annotation(s)")

    def paste_roi(self, subwindow: SubWindowContainer, managers: Dict, roi_data: Dict, offset: QPointF):
        """
        Recreate an ROI from clipboard data.

        Args:
            subwindow: SubWindowContainer to paste into
            managers: Dictionary of managers for this subwindow
            roi_data: Serialized ROI data
            offset: QPointF offset to apply

        Returns:
            Created ROIItem or None
        """
        from PySide6.QtCore import QRectF
        from PySide6.QtGui import QPen, QColor
        from tools.roi_manager import ROIItem, ROIGraphicsEllipseItem, ROIGraphicsRectItem
        from utils.undo_redo import ROICommand

        if not subwindow.image_viewer or not subwindow.image_viewer.scene:
            return None

        roi_coordinator = managers['roi_coordinator']
        roi_manager = managers['roi_manager']

        shape_type = roi_data['shape_type']
        rect_data = roi_data['rect']
        pos_data = roi_data['position']
        pen_width = roi_data['pen_width']
        pen_color = roi_data['pen_color']

        new_pos = QPointF(pos_data['x'] + offset.x(), pos_data['y'] + offset.y())
        rect = QRectF(rect_data['x'], rect_data['y'], rect_data['width'], rect_data['height'])
        pen = QPen(QColor(*pen_color), pen_width)
        pen.setCosmetic(True)

        if shape_type == "ellipse":
            item = ROIGraphicsEllipseItem(rect)
        else:
            item = ROIGraphicsRectItem(rect)

        item.setPen(pen)
        item.setPos(new_pos)

        default_stats = None
        if 'visible_statistics' in roi_data:
            default_stats = set(roi_data['visible_statistics'])

        roi_item = ROIItem(shape_type, item, pen_width=pen_width, pen_color=pen_color,
                          default_visible_statistics=default_stats)

        item.setFlag(item.GraphicsItemFlag.ItemIsSelectable, True)
        item.setFlag(item.GraphicsItemFlag.ItemIsMovable, True)

        subwindow.image_viewer.scene.addItem(item)

        key = (roi_manager.current_study_uid,
               roi_manager.current_series_uid,
               roi_manager.current_instance_identifier)

        if key not in roi_manager.rois:
            roi_manager.rois[key] = []
        roi_manager.rois[key].append(roi_item)

        roi_item.on_moved_callback = lambda r=roi_item: roi_coordinator._on_roi_moved(r)

        command = ROICommand(
            roi_manager,
            "add",
            roi_item,
            subwindow.image_viewer.scene,
            roi_manager.current_study_uid,
            roi_manager.current_series_uid,
            roi_manager.current_instance_identifier,
            update_statistics_callback=roi_coordinator.update_roi_statistics_overlays
        )
        self._app.undo_redo_manager.execute_command(command)

        roi_coordinator.update_roi_statistics_overlays()

        return roi_item

    def paste_measurement(self, subwindow: SubWindowContainer, managers: Dict, meas_data: Dict, offset: QPointF):
        """
        Recreate a measurement from clipboard data.

        Args:
            subwindow: SubWindowContainer to paste into
            managers: Dictionary of managers for this subwindow
            meas_data: Serialized measurement data
            offset: QPointF offset to apply

        Returns:
            Created MeasurementItem or None
        """
        from PySide6.QtWidgets import QGraphicsLineItem
        from PySide6.QtGui import QPen, QColor, QFont
        from tools.measurement_tool import MeasurementItem, DraggableMeasurementText
        from utils.undo_redo import MeasurementCommand

        if not subwindow.image_viewer or not subwindow.image_viewer.scene:
            return None

        measurement_tool = managers['measurement_tool']

        start = QPointF(meas_data['start_point']['x'] + offset.x(),
                       meas_data['start_point']['y'] + offset.y())
        end = QPointF(meas_data['end_point']['x'] + offset.x(),
                     meas_data['end_point']['y'] + offset.y())
        pixel_spacing = meas_data['pixel_spacing']

        if self._app.config_manager:
            line_thickness = self._app.config_manager.get_measurement_line_thickness()
            line_color = self._app.config_manager.get_measurement_line_color()
            font_size = self._app.config_manager.get_measurement_font_size()
            font_color = self._app.config_manager.get_measurement_font_color()
        else:
            line_thickness = 2
            line_color = (0, 255, 0)
            font_size = 14
            font_color = (255, 255, 0)

        line_pen = QPen(QColor(*line_color), line_thickness)
        line_pen.setCosmetic(True)
        line_item = QGraphicsLineItem(start.x(), start.y(), end.x(), end.y())
        line_item.setPen(line_pen)

        text_item = DraggableMeasurementText(None, lambda offset: None)
        text_item.setDefaultTextColor(QColor(*font_color))
        font = QFont("Arial", font_size)
        font.setBold(True)
        text_item.setFont(font)
        text_item.setFlag(text_item.GraphicsItemFlag.ItemIgnoresTransformations, True)
        text_item.setFlag(text_item.GraphicsItemFlag.ItemIsMovable, True)
        text_item.setFlag(text_item.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        text_item.setFlag(text_item.GraphicsItemFlag.ItemIsSelectable, True)

        measurement = MeasurementItem(start, end, line_item, text_item, pixel_spacing=pixel_spacing)
        text_item.measurement = measurement

        subwindow.image_viewer.scene.addItem(measurement)
        measurement.setZValue(150)
        text_item.setZValue(151)
        subwindow.image_viewer.scene.addItem(text_item)

        measurement.update_distance()

        key = (measurement_tool.current_study_uid,
               measurement_tool.current_series_uid,
               measurement_tool.current_instance_identifier)

        if key not in measurement_tool.measurements:
            measurement_tool.measurements[key] = []
        measurement_tool.measurements[key].append(measurement)

        command = MeasurementCommand(
            measurement_tool,
            "add",
            measurement,
            subwindow.image_viewer.scene,
            measurement_tool.current_study_uid,
            measurement_tool.current_series_uid,
            measurement_tool.current_instance_identifier
        )
        self._app.undo_redo_manager.execute_command(command)

        return measurement

    def paste_crosshair(self, subwindow: SubWindowContainer, managers: Dict, cross_data: Dict, offset: QPointF):
        """
        Recreate a crosshair from clipboard data.

        Args:
            subwindow: SubWindowContainer to paste into
            managers: Dictionary of managers for this subwindow
            cross_data: Serialized crosshair data
            offset: QPointF offset to apply

        Returns:
            Created CrosshairItem or None
        """
        from tools.crosshair_manager import CrosshairItem
        from utils.undo_redo import CrosshairCommand

        if not subwindow.image_viewer or not subwindow.image_viewer.scene:
            return None

        crosshair_manager = managers['crosshair_manager']

        pos = QPointF(cross_data['position']['x'] + offset.x(),
                     cross_data['position']['y'] + offset.y())
        pixel_value_str = cross_data['pixel_value_str']
        x_coord = cross_data['x_coord']
        y_coord = cross_data['y_coord']
        z_coord = cross_data['z_coord']
        text_offset_viewport = cross_data.get('text_offset_viewport', (5.0, 5.0))

        crosshair = CrosshairItem(
            pos,
            pixel_value_str,
            x_coord,
            y_coord,
            z_coord,
            self._app.config_manager,
            crosshair_manager.privacy_mode
        )

        crosshair.text_offset_viewport = text_offset_viewport

        subwindow.image_viewer.scene.addItem(crosshair)
        if crosshair.text_item:
            subwindow.image_viewer.scene.addItem(crosshair.text_item)
            if subwindow.image_viewer:
                crosshair.update_text_position(subwindow.image_viewer)

        key = (crosshair_manager.current_study_uid,
               crosshair_manager.current_series_uid,
               crosshair_manager.current_instance_identifier)

        if key not in crosshair_manager.crosshairs:
            crosshair_manager.crosshairs[key] = []
        crosshair_manager.crosshairs[key].append(crosshair)

        command = CrosshairCommand(
            crosshair_manager,
            "add",
            crosshair,
            subwindow.image_viewer.scene,
            crosshair_manager.current_study_uid,
            crosshair_manager.current_series_uid,
            crosshair_manager.current_instance_identifier
        )
        self._app.undo_redo_manager.execute_command(command)

        return crosshair

    def paste_text_annotation(self, subwindow: SubWindowContainer, managers: Dict, text_data: Dict, offset: QPointF):
        """
        Recreate a text annotation from clipboard data.

        Args:
            subwindow: SubWindowContainer to paste into
            managers: Dictionary of managers for this subwindow
            text_data: Serialized text annotation data
            offset: QPointF offset to apply

        Returns:
            Created TextAnnotationItem or None
        """
        from tools.text_annotation_tool import TextAnnotationItem
        from utils.undo_redo import TextAnnotationCommand
        from PySide6.QtGui import QColor, QFont

        if not subwindow.image_viewer or not subwindow.image_viewer.scene:
            return None

        text_annotation_tool = managers.get('text_annotation_tool')
        if not text_annotation_tool:
            return None

        text = text_data.get('text', '')
        pos = QPointF(text_data['position']['x'] + offset.x(),
                     text_data['position']['y'] + offset.y())
        font_size = text_data.get('font_size', 12)
        color_data = text_data.get('color', {'r': 255, 'g': 255, 'b': 0})
        color = QColor(color_data['r'], color_data['g'], color_data['b'])

        text_item = TextAnnotationItem(text, self._app.config_manager, on_editing_finished=None)
        text_item.setPos(pos)
        text_item.setDefaultTextColor(color)
        font = QFont("Arial", font_size)
        font.setBold(True)
        text_item.setFont(font)

        subwindow.image_viewer.scene.addItem(text_item)
        text_item.setZValue(160)

        key = (text_annotation_tool.current_study_uid,
               text_annotation_tool.current_series_uid,
               text_annotation_tool.current_instance_identifier)

        if key not in text_annotation_tool.annotations:
            text_annotation_tool.annotations[key] = []
        text_annotation_tool.annotations[key].append(text_item)

        command = TextAnnotationCommand(
            text_annotation_tool,
            "add",
            text_item,
            subwindow.image_viewer.scene,
            text_annotation_tool.current_study_uid,
            text_annotation_tool.current_series_uid,
            text_annotation_tool.current_instance_identifier
        )
        self._app.undo_redo_manager.execute_command(command)

        return text_item

    def paste_arrow_annotation(self, subwindow: SubWindowContainer, managers: Dict, arrow_data: Dict, offset: QPointF):
        """
        Recreate an arrow annotation from clipboard data.

        Args:
            subwindow: SubWindowContainer to paste into
            managers: Dictionary of managers for this subwindow
            arrow_data: Serialized arrow annotation data
            offset: QPointF offset to apply

        Returns:
            Created ArrowAnnotationItem or None
        """
        from tools.arrow_annotation_tool import ArrowAnnotationItem
        from utils.undo_redo import ArrowAnnotationCommand
        from PySide6.QtGui import QColor, QPen
        from PySide6.QtCore import QLineF, QPointF
        from PySide6.QtWidgets import QGraphicsLineItem

        if not subwindow.image_viewer or not subwindow.image_viewer.scene:
            return None

        arrow_annotation_tool = managers.get('arrow_annotation_tool')
        if not arrow_annotation_tool:
            return None

        start = QPointF(arrow_data['start_point']['x'] + offset.x(),
                       arrow_data['start_point']['y'] + offset.y())
        end = QPointF(arrow_data['end_point']['x'] + offset.x(),
                     arrow_data['end_point']['y'] + offset.y())
        color_data = arrow_data.get('color', {'r': 255, 'g': 255, 'b': 0})
        color = QColor(color_data['r'], color_data['g'], color_data['b'])

        arrow_size = self._app.config_manager.get_arrow_annotation_size() if self._app.config_manager else 6
        from tools.arrow_annotation_tool import ARROWHEAD_SIZE_MULTIPLIER, ArrowHeadItem, _line_end_shortened
        arrowhead_size = arrow_size * ARROWHEAD_SIZE_MULTIPLIER

        relative_end = end - start
        line_end = _line_end_shortened(relative_end)
        line = QLineF(QPointF(0, 0), line_end)
        line_item = QGraphicsLineItem(line)
        pen = QPen(color, arrow_size)
        pen.setCosmetic(True)
        pen.setCapStyle(Qt.PenCapStyle.FlatCap)
        line_item.setPen(pen)
        line_item.setZValue(160)

        arrowhead = ArrowHeadItem(QPointF(0, 0), relative_end, color, arrowhead_size)
        arrow_item = ArrowAnnotationItem(start, end, line_item, arrowhead, color)
        arrow_item.setPos(start)

        subwindow.image_viewer.scene.addItem(arrow_item)

        view = subwindow.image_viewer
        arrow_item.update_line_end_for_view_scale(view)

        key = (arrow_annotation_tool.current_study_uid,
               arrow_annotation_tool.current_series_uid,
               arrow_annotation_tool.current_instance_identifier)

        if key not in arrow_annotation_tool.arrows:
            arrow_annotation_tool.arrows[key] = []
        arrow_annotation_tool.arrows[key].append(arrow_item)

        arrow_coordinator = managers.get('arrow_annotation_coordinator')
        if arrow_coordinator and hasattr(arrow_coordinator, '_on_arrow_moved'):
            arrow_item.on_moved_callback = arrow_coordinator._on_arrow_moved

        command = ArrowAnnotationCommand(
            arrow_annotation_tool,
            "add",
            arrow_item,
            subwindow.image_viewer.scene,
            arrow_annotation_tool.current_study_uid,
            arrow_annotation_tool.current_series_uid,
            arrow_annotation_tool.current_instance_identifier
        )
        self._app.undo_redo_manager.execute_command(command)

        return arrow_item
