"""
Undo/Redo System

This module implements an undo/redo system using the command pattern
for ROI, measurement, crosshair changes, and DICOM tag edits.

Inputs:
    - Commands to execute
    - Undo/redo requests
    
Outputs:
    - Command execution
    - State restoration
    
Requirements:
    - Standard library only
    - PySide6.QtCore.QPointF for position tracking
    - pydicom for DICOM tag operations
"""

from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QPointF, QRectF

from utils.undo_redo_command import Command


class UndoRedoManager:
    """
    Manages undo/redo operations.
    
    Features:
    - Execute commands
    - Undo/redo operations
    - Command history management
    """

    def __init__(self, max_history: int = 100):
        """
        Initialize the undo/redo manager.
        
        Args:
            max_history: Maximum number of commands to keep in history
        """
        self.undo_stack: list[Command] = []
        self.redo_stack: list[Command] = []
        self.max_history = max_history

    def execute_command(self, command: Command) -> None:
        """
        Execute a command and add it to undo stack.
        
        Args:
            command: Command to execute
        """
        command.execute()
        self.undo_stack.append(command)

        # Clear redo stack when new command is executed
        self.redo_stack.clear()

        # Limit history size
        if len(self.undo_stack) > self.max_history:
            self.undo_stack.pop(0)

    def undo(self) -> bool:
        """
        Undo the last command.
        
        Returns:
            True if undo was successful, False if no commands to undo
        """
        if not self.undo_stack:
            return False

        command = self.undo_stack.pop()
        command.undo()
        self.redo_stack.append(command)
        return True

    def redo(self) -> bool:
        """
        Redo the last undone command.
        
        Returns:
            True if redo was successful, False if no commands to redo
        """
        if not self.redo_stack:
            return False

        command = self.redo_stack.pop()
        command.execute()
        self.undo_stack.append(command)
        return True

    def can_undo(self) -> bool:
        """
        Check if undo is possible.
        
        Returns:
            True if undo is possible
        """
        return len(self.undo_stack) > 0

    def can_redo(self) -> bool:
        """
        Check if redo is possible.
        
        Returns:
            True if redo is possible
        """
        return len(self.redo_stack) > 0

    def clear(self) -> None:
        """Clear all command history."""
        self.undo_stack.clear()
        self.redo_stack.clear()


class ROICommand(Command):
    """
    Command for ROI operations (add, remove).
    Uses composite key: (study_uid, series_uid, instance_identifier)
    """

    def __init__(self, roi_manager, action: str, roi_item, scene,
                 study_uid: str, series_uid: str, instance_identifier: int,
                 update_statistics_callback: Callable[[], None] | None = None):
        """
        Initialize ROI command.
        
        Args:
            roi_manager: ROIManager instance
            action: "add" or "remove"
            roi_item: ROI item
            scene: QGraphicsScene
            study_uid: StudyInstanceUID
            series_uid: SeriesInstanceUID
            instance_identifier: InstanceNumber or slice_index
            update_statistics_callback: Optional callback to trigger statistics overlay update
        """
        self.roi_manager = roi_manager
        self.action = action
        self.roi_item = roi_item
        self.scene = scene
        self.key = (study_uid, series_uid, instance_identifier)
        self.update_statistics_callback = update_statistics_callback
        # Capture overlay visibility before execute() or handle_roi_deleted() mutate it.
        # Required so undo("remove") can restore the flag to its pre-deletion state.
        self._saved_overlay_visible: bool = getattr(roi_item, 'statistics_overlay_visible', True)

    def _clear_roi_removal_ui_state(self) -> None:
        """Remove resize handles and manager pointers; safe before remove and on undo-add."""
        if self.scene is None:
            return
        try:
            self.roi_item.hide_resize_handles(self.scene)
        except RuntimeError:
            pass
        if self.roi_manager._editing_roi == self.roi_item:
            self.roi_manager._editing_roi = None
            self.roi_manager._geometry_edit_scene = None
        if self.roi_manager.selected_roi == self.roi_item:
            self.roi_manager.selected_roi = None

    def _add_roi_to_manager_and_scene(self) -> bool:
        """
        Add the ROI to the manager list and scene when not already present.

        Returns:
            True if the ROI was newly added; False if it was already registered.
        """
        if self.scene is None:
            return False
        if self.key not in self.roi_manager.rois:
            self.roi_manager.rois[self.key] = []
        if self.roi_item in self.roi_manager.rois[self.key]:
            return False
        self.roi_manager.rois[self.key].append(self.roi_item)
        if self.roi_item.item.scene() != self.scene:
            self.scene.addItem(self.roi_item.item)
        return True

    def _remove_roi_from_manager_and_scene(self) -> None:
        """Clear UI state, drop the ROI from the manager list, and remove scene items."""
        if self.scene is None:
            return
        if self.key not in self.roi_manager.rois:
            return
        if self.roi_item not in self.roi_manager.rois[self.key]:
            return
        self._clear_roi_removal_ui_state()
        self.roi_manager.rois[self.key].remove(self.roi_item)
        if self.roi_item.item.scene() != self.scene:
            return
        # Remove statistics overlay if present
        if (
            hasattr(self.roi_item, "statistics_overlay_item")
            and self.roi_item.statistics_overlay_item is not None
        ):
            self.roi_manager.remove_statistics_overlay(self.roi_item, self.scene)
        self.scene.removeItem(self.roi_item.item)

    def _restore_overlay_after_undo_remove(self) -> None:
        """
        Restore overlay-visible flag and reattach a surviving overlay item.

        Called only on undo of a remove action, before the statistics callback.
        """
        if self.scene is None:
            return
        # Restore the overlay visibility flag to its pre-deletion value so
        # that the subsequent overlay re-add and statistics callback work
        # correctly (handle_roi_deleted sets the flag to False during deletion).
        self.roi_item.statistics_overlay_visible = self._saved_overlay_visible
        # Re-add existing overlay item to scene if it survived deletion
        if (
            hasattr(self.roi_item, "statistics_overlay_item")
            and self.roi_item.statistics_overlay_item is not None
            and self.roi_item.statistics_overlay_visible
        ):
            overlay_item = self.roi_item.statistics_overlay_item
            if overlay_item.scene() != self.scene:
                self.scene.addItem(overlay_item)
            overlay_item.setVisible(True)

    def execute(self) -> None:
        """Execute the command."""
        if self.scene is None:
            return

        if self.action == "add":
            if self._add_roi_to_manager_and_scene() and self.update_statistics_callback:
                self.update_statistics_callback()
        elif self.action == "remove":
            self._remove_roi_from_manager_and_scene()

    def undo(self) -> None:
        """Undo the command."""
        if self.scene is None:
            return

        if self.action == "add":
            self._remove_roi_from_manager_and_scene()
        elif self.action == "remove":
            if not self._add_roi_to_manager_and_scene():
                return
            self._restore_overlay_after_undo_remove()
            # Trigger statistics overlay update to recalculate and refresh text;
            # update_roi_statistics_overlays checks statistics_overlay_visible, so
            # the flag must be restored (above) before this call.
            if self.update_statistics_callback:
                self.update_statistics_callback()


class ROIGeometryResizeCommand(Command):
    """
    Command for resizing a rectangle or ellipse ROI (scene bounding rect before / after).
    """

    def __init__(self, roi_item, old_rect: QRectF, new_rect: QRectF, scene, apply_fn: Callable[..., Any] | None = None) -> None:
        self.roi_item = roi_item
        self.old_rect = QRectF(old_rect)
        self.new_rect = QRectF(new_rect)
        self.scene = scene
        self._apply_fn = apply_fn

    def _apply(self, rect: QRectF) -> None:
        if self.roi_item is None or self.scene is None:
            return
        it = getattr(self.roi_item, "item", None)
        if it is None or it.scene() != self.scene:
            return
        if self._apply_fn is not None:
            self._apply_fn(self.roi_item, rect)

    def execute(self) -> None:
        self._apply(self.new_rect)

    def undo(self) -> None:
        self._apply(self.old_rect)

    def redo(self) -> None:
        self.execute()


class ROIMoveCommand(Command):
    """
    Command for ROI movement operations.
    """

    def __init__(self, roi_item, old_position: 'QPointF', new_position: 'QPointF', scene):
        """
        Initialize ROI move command.
        
        Args:
            roi_item: ROI item to move
            old_position: Original position (QPointF)
            new_position: New position (QPointF)
            scene: QGraphicsScene
        """
        self.roi_item = roi_item
        self.old_position = old_position
        self.new_position = new_position
        self.scene = scene

    def execute(self) -> None:
        """Execute the command - move to new position."""
        if self.roi_item is None or self.scene is None:
            return
        if self.roi_item.item.scene() == self.scene:
            self.roi_item.item.setPos(self.new_position)

    def undo(self) -> None:
        """Undo the command - move back to old position."""
        if self.roi_item is None or self.scene is None:
            return
        if self.roi_item.item.scene() == self.scene:
            self.roi_item.item.setPos(self.old_position)


class MeasurementCommand(Command):
    """
    Command for measurement operations (add, remove).
    Uses composite key: (study_uid, series_uid, instance_identifier)
    """

    def __init__(self, measurement_tool, action: str, measurement_item, scene,
                 study_uid: str, series_uid: str, instance_identifier: int):
        """
        Initialize measurement command.
        
        Args:
            measurement_tool: MeasurementTool instance
            action: "add" or "remove"
            measurement_item: MeasurementItem
            scene: QGraphicsScene
            study_uid: StudyInstanceUID
            series_uid: SeriesInstanceUID
            instance_identifier: InstanceNumber or slice_index
        """
        self.measurement_tool = measurement_tool
        self.action = action
        self.measurement_item = measurement_item
        self.scene = scene
        self.key = (study_uid, series_uid, instance_identifier)

    def _add_measurement_to_manager_and_scene(self, *, refresh_geometry: bool = False) -> bool:
        """
        Add the measurement to the tool list and scene when not already present.

        Returns:
            True if newly added; False if already registered.
        """
        if self.scene is None:
            return False
        if self.key not in self.measurement_tool.measurements:
            self.measurement_tool.measurements[self.key] = []
        if self.measurement_item in self.measurement_tool.measurements[self.key]:
            return False
        self.measurement_tool.measurements[self.key].append(self.measurement_item)
        if self.measurement_item.scene() != self.scene:
            self.scene.addItem(self.measurement_item)
        if hasattr(self.measurement_item, "text_item") and self.measurement_item.text_item is not None:
            if self.measurement_item.text_item.scene() != self.scene:
                self.scene.addItem(self.measurement_item.text_item)
            if refresh_geometry:
                # Ensure text is visible and positioned correctly after undo-remove.
                self.measurement_item.text_item.setVisible(True)
                if hasattr(self.measurement_item, "update_distance"):
                    self.measurement_item.update_distance()
                elif hasattr(self.measurement_item, "update_angle_geometry"):
                    self.measurement_item.update_angle_geometry()
        return True

    def _remove_measurement_from_manager_and_scene(self) -> None:
        """Drop the measurement from the tool list and remove scene items/handles."""
        if self.scene is None:
            return
        if self.key not in self.measurement_tool.measurements:
            return
        if self.measurement_item not in self.measurement_tool.measurements[self.key]:
            return
        self.measurement_tool.measurements[self.key].remove(self.measurement_item)
        if self.measurement_item.scene() != self.scene:
            return
        if hasattr(self.measurement_item, "text_item") and self.measurement_item.text_item is not None:
            if self.measurement_item.text_item.scene() == self.scene:
                self.scene.removeItem(self.measurement_item.text_item)
        if hasattr(self.measurement_item, "hide_handles"):
            self.measurement_item.hide_handles()
        self.scene.removeItem(self.measurement_item)

    def execute(self) -> None:
        """Execute the command."""
        if self.scene is None:
            return
        if self.action == "add":
            self._add_measurement_to_manager_and_scene()
        elif self.action == "remove":
            self._remove_measurement_from_manager_and_scene()

    def undo(self) -> None:
        """Undo the command."""
        if self.scene is None:
            return
        if self.action == "add":
            self._remove_measurement_from_manager_and_scene()
        elif self.action == "remove":
            self._add_measurement_to_manager_and_scene(refresh_geometry=True)


class TextAnnotationCommand(Command):
    """
    Command for text annotation operations (add, remove).
    Uses composite key: (study_uid, series_uid, instance_identifier)
    """

    def __init__(self, text_annotation_tool, action: str, annotation_item, scene,
                 study_uid: str, series_uid: str, instance_identifier: int):
        """
        Initialize text annotation command.
        
        Args:
            text_annotation_tool: TextAnnotationTool instance
            action: "add" or "remove"
            annotation_item: TextAnnotationItem
            scene: QGraphicsScene
            study_uid: StudyInstanceUID
            series_uid: SeriesInstanceUID
            instance_identifier: InstanceNumber or slice_index
        """
        self.text_annotation_tool = text_annotation_tool
        self.action = action
        self.annotation_item = annotation_item
        self.scene = scene
        self.key = (study_uid, series_uid, instance_identifier)

    def _add_annotation_to_manager_and_scene(self) -> bool:
        """
        Add the text annotation to the tool list and scene when not already present.

        Returns:
            True if newly added; False if already registered.
        """
        if self.scene is None:
            return False
        if self.key not in self.text_annotation_tool.annotations:
            self.text_annotation_tool.annotations[self.key] = []
        if self.annotation_item in self.text_annotation_tool.annotations[self.key]:
            return False
        self.text_annotation_tool.annotations[self.key].append(self.annotation_item)
        # Ensure item state is correct (no callback, not new annotation)
        self.annotation_item.on_editing_finished = None
        self.annotation_item._is_new_annotation = False
        if self.annotation_item.scene() != self.scene:
            self.scene.addItem(self.annotation_item)
        return True

    def _remove_annotation_from_manager_and_scene(self) -> None:
        """Drop the text annotation from the tool list and remove it from the scene."""
        if self.scene is None:
            return
        if self.key not in self.text_annotation_tool.annotations:
            return
        if self.annotation_item not in self.text_annotation_tool.annotations[self.key]:
            return
        self.text_annotation_tool.annotations[self.key].remove(self.annotation_item)
        if self.annotation_item.scene() == self.scene:
            self.scene.removeItem(self.annotation_item)

    def execute(self) -> None:
        """Execute the command."""
        if self.scene is None:
            return
        if self.action == "add":
            self._add_annotation_to_manager_and_scene()
        elif self.action == "remove":
            self._remove_annotation_from_manager_and_scene()

    def undo(self) -> None:
        """Undo the command."""
        if self.scene is None:
            return
        if self.action == "add":
            self._remove_annotation_from_manager_and_scene()
        elif self.action == "remove":
            self._add_annotation_to_manager_and_scene()


class ArrowAnnotationCommand(Command):
    """
    Command for arrow annotation operations (add, remove).
    Uses composite key: (study_uid, series_uid, instance_identifier)
    """

    def __init__(self, arrow_annotation_tool, action: str, arrow_item, scene,
                 study_uid: str, series_uid: str, instance_identifier: int):
        """
        Initialize arrow annotation command.
        
        Args:
            arrow_annotation_tool: ArrowAnnotationTool instance
            action: "add" or "remove"
            arrow_item: ArrowAnnotationItem
            scene: QGraphicsScene
            study_uid: StudyInstanceUID
            series_uid: SeriesInstanceUID
            instance_identifier: InstanceNumber or slice_index
        """
        self.arrow_annotation_tool = arrow_annotation_tool
        self.action = action
        self.arrow_item = arrow_item
        self.scene = scene
        self.key = (study_uid, series_uid, instance_identifier)

    def _add_arrow_to_manager_and_scene(self) -> bool:
        """
        Add the arrow to the tool list and scene when not already present.

        Returns:
            True if newly added; False if already registered.
        """
        if self.scene is None:
            return False
        if self.key not in self.arrow_annotation_tool.arrows:
            self.arrow_annotation_tool.arrows[self.key] = []
        if self.arrow_item in self.arrow_annotation_tool.arrows[self.key]:
            return False
        self.arrow_annotation_tool.arrows[self.key].append(self.arrow_item)
        if self.arrow_item.scene() != self.scene:
            self.scene.addItem(self.arrow_item)
        return True

    def _remove_arrow_from_manager_and_scene(self) -> None:
        """Drop the arrow from the tool list and remove it from the scene."""
        if self.scene is None:
            return
        if self.key not in self.arrow_annotation_tool.arrows:
            return
        if self.arrow_item not in self.arrow_annotation_tool.arrows[self.key]:
            return
        self.arrow_annotation_tool.arrows[self.key].remove(self.arrow_item)
        if self.arrow_item.scene() == self.scene:
            self.scene.removeItem(self.arrow_item)

    def execute(self) -> None:
        """Execute the command."""
        if self.scene is None:
            return
        if self.action == "add":
            self._add_arrow_to_manager_and_scene()
        elif self.action == "remove":
            self._remove_arrow_from_manager_and_scene()

    def undo(self) -> None:
        """Undo the command."""
        if self.scene is None:
            return
        if self.action == "add":
            self._remove_arrow_from_manager_and_scene()
        elif self.action == "remove":
            self._add_arrow_to_manager_and_scene()


class TextAnnotationEditCommand(Command):
    """
    Command for text annotation text content edits (not creation/deletion).
    """

    def __init__(self, text_annotation_item, old_text: str, new_text: str):
        """
        Initialize text annotation edit command.
        
        Args:
            text_annotation_item: TextAnnotationItem to edit
            old_text: Original text content
            new_text: New text content
        """
        self.text_annotation_item = text_annotation_item
        self.old_text = old_text
        self.new_text = new_text

    def execute(self) -> None:
        """Execute the command - set to new text."""
        if self.text_annotation_item is None:
            return
        self.text_annotation_item.setPlainText(self.new_text)

    def undo(self) -> None:
        """Undo the command - restore old text."""
        if self.text_annotation_item is None:
            return
        self.text_annotation_item.setPlainText(self.old_text)


class TextAnnotationMoveCommand(Command):
    """
    Command for text annotation movement operations.
    """

    def __init__(self, text_annotation_item, old_position: 'QPointF', new_position: 'QPointF', scene):
        """
        Initialize text annotation move command.
        
        Args:
            text_annotation_item: TextAnnotationItem to move
            old_position: Original position (QPointF)
            new_position: New position (QPointF)
            scene: QGraphicsScene
        """
        self.text_annotation_item = text_annotation_item
        self.old_position = old_position
        self.new_position = new_position
        self.scene = scene

    def execute(self) -> None:
        """Execute the command - move to new position."""
        if self.text_annotation_item is None or self.scene is None:
            return
        if self.text_annotation_item.scene() == self.scene:
            self.text_annotation_item.setPos(self.new_position)

    def undo(self) -> None:
        """Undo the command - restore old position."""
        if self.text_annotation_item is None or self.scene is None:
            return
        if self.text_annotation_item.scene() == self.scene:
            self.text_annotation_item.setPos(self.old_position)


class ArrowAnnotationMoveCommand(Command):
    """
    Command for arrow annotation movement operations.
    Tracks both start_point and end_point changes.
    """

    def __init__(self, arrow_item, old_start_point: 'QPointF', old_end_point: 'QPointF',
                 new_start_point: 'QPointF', new_end_point: 'QPointF', scene):
        """
        Initialize arrow annotation move command.
        
        Args:
            arrow_item: ArrowAnnotationItem to move
            old_start_point: Original start point (QPointF)
            old_end_point: Original end point (QPointF)
            new_start_point: New start point (QPointF)
            new_end_point: New end point (QPointF)
            scene: QGraphicsScene
        """
        self.arrow_item = arrow_item
        self.old_start_point = old_start_point
        self.old_end_point = old_end_point
        self.new_start_point = new_start_point
        self.new_end_point = new_end_point
        self.scene = scene

    def execute(self) -> None:
        """Execute the command - move to new positions."""
        if self.arrow_item is None or self.scene is None:
            return

        if self.arrow_item.scene() == self.scene:
            # Save and temporarily clear callback to prevent recursive updates
            saved_callback = self.arrow_item.on_moved_callback
            self.arrow_item.on_moved_callback = None

            # Set flag to prevent recursive updates BEFORE any position changes
            self.arrow_item._updating_position = True

            # Update arrow points and position
            # Use update_endpoints which handles both position and line/arrowhead correctly
            self.arrow_item.update_endpoints(self.new_start_point, self.new_end_point)

            # Clear flag AFTER all position changes
            self.arrow_item._updating_position = False

            # Restore callback AFTER flag is cleared
            self.arrow_item.on_moved_callback = saved_callback

    def undo(self) -> None:
        """Undo the command - restore old positions."""

        if self.arrow_item is None or self.scene is None:
            return

        if self.arrow_item.scene() == self.scene:
            # Save and temporarily clear callback to prevent recursive updates
            saved_callback = self.arrow_item.on_moved_callback
            self.arrow_item.on_moved_callback = None

            # Set flag to prevent recursive updates BEFORE any position changes
            self.arrow_item._updating_position = True

            # Restore arrow points and position using update_endpoints
            # This handles both position and line/arrowhead correctly
            self.arrow_item.update_endpoints(self.old_start_point, self.old_end_point)

            # Clear flag AFTER all position changes
            self.arrow_item._updating_position = False

            # Restore callback AFTER flag is cleared
            self.arrow_item.on_moved_callback = saved_callback
class MeasurementMoveCommand(Command):
    """
    Command for measurement movement operations.
    Tracks both start_point and end_point changes.
    """

    def __init__(self, measurement_item, old_start_point: 'QPointF', old_end_point: 'QPointF',
                 new_start_point: 'QPointF', new_end_point: 'QPointF', scene):
        """
        Initialize measurement move command.
        
        Args:
            measurement_item: MeasurementItem to move
            old_start_point: Original start point (QPointF)
            old_end_point: Original end point (QPointF)
            new_start_point: New start point (QPointF)
            new_end_point: New end point (QPointF)
            scene: QGraphicsScene
        """
        self.measurement_item = measurement_item
        self.old_start_point = old_start_point
        self.old_end_point = old_end_point
        self.new_start_point = new_start_point
        self.new_end_point = new_end_point
        self.scene = scene

    def execute(self) -> None:
        """Execute the command - move to new positions."""
        if self.measurement_item is None or self.scene is None:
            return
        if self.measurement_item.scene() == self.scene:
            # Update measurement points
            self.measurement_item.start_point = self.new_start_point
            self.measurement_item.end_point = self.new_end_point
            self.measurement_item.end_relative = self.new_end_point - self.new_start_point
            # Move group to new start point
            self.measurement_item.setPos(self.new_start_point)
            # Update line and text
            if hasattr(self.measurement_item, 'line_item'):
                self.measurement_item.line_item.prepareGeometryChange()
            # Update distance to recalculate line, text, and handle positions
            if hasattr(self.measurement_item, 'update_distance'):
                self.measurement_item.update_distance()

    def undo(self) -> None:
        """Undo the command - restore old positions."""
        if self.measurement_item is None or self.scene is None:
            return
        if self.measurement_item.scene() == self.scene:
            # Restore measurement points
            self.measurement_item.start_point = self.old_start_point
            self.measurement_item.end_point = self.old_end_point
            self.measurement_item.end_relative = self.old_end_point - self.old_start_point
            # Move group back to old start point
            self.measurement_item.setPos(self.old_start_point)
            # Update line and text
            if hasattr(self.measurement_item, 'line_item'):
                self.measurement_item.line_item.prepareGeometryChange()
            # Update distance to recalculate line, text, and handle positions
            if hasattr(self.measurement_item, 'update_distance'):
                self.measurement_item.update_distance()


class AngleMeasurementMoveCommand(Command):
    """Undo/redo for moving an angle measurement (all three vertices)."""

    def __init__(
        self,
        angle_item,
        old_p1: "QPointF",
        old_p2: "QPointF",
        old_p3: "QPointF",
        new_p1: "QPointF",
        new_p2: "QPointF",
        new_p3: "QPointF",
        scene,
    ):
        self.angle_item = angle_item
        self.old_p1 = old_p1
        self.old_p2 = old_p2
        self.old_p3 = old_p3
        self.new_p1 = new_p1
        self.new_p2 = new_p2
        self.new_p3 = new_p3
        self.scene = scene

    def execute(self) -> None:
        if self.angle_item is None or self.scene is None:
            return
        if self.angle_item.scene() == self.scene:
            self.angle_item.p1 = self.new_p1
            self.angle_item.p2 = self.new_p2
            self.angle_item.p3 = self.new_p3
            self.angle_item.setPos(self.new_p2)
            if hasattr(self.angle_item, "update_angle_geometry"):
                self.angle_item.update_angle_geometry()

    def undo(self) -> None:
        if self.angle_item is None or self.scene is None:
            return
        if self.angle_item.scene() == self.scene:
            self.angle_item.p1 = self.old_p1
            self.angle_item.p2 = self.old_p2
            self.angle_item.p3 = self.old_p3
            self.angle_item.setPos(self.old_p2)
            if hasattr(self.angle_item, "update_angle_geometry"):
                self.angle_item.update_angle_geometry()


class CrosshairCommand(Command):
    """
    Command for crosshair operations (add, remove).
    Uses composite key: (study_uid, series_uid, instance_identifier)
    """

    def __init__(self, crosshair_manager, action: str, crosshair_item, scene,
                 study_uid: str, series_uid: str, instance_identifier: int):
        """
        Initialize crosshair command.
        
        Args:
            crosshair_manager: CrosshairManager instance
            action: "add" or "remove"
            crosshair_item: CrosshairItem
            scene: QGraphicsScene
            study_uid: StudyInstanceUID
            series_uid: SeriesInstanceUID
            instance_identifier: InstanceNumber or slice_index
        """
        self.crosshair_manager = crosshair_manager
        self.action = action
        self.crosshair_item = crosshair_item
        self.scene = scene
        self.key = (study_uid, series_uid, instance_identifier)

    def _add_crosshair_to_manager_and_scene(self, *, restore_text: bool = False) -> bool:
        """
        Add the crosshair to the manager list and scene when not already present.

        Returns:
            True if newly added; False if already registered.
        """
        if self.scene is None:
            return False
        if self.key not in self.crosshair_manager.crosshairs:
            self.crosshair_manager.crosshairs[self.key] = []
        if self.crosshair_item in self.crosshair_manager.crosshairs[self.key]:
            return False
        self.crosshair_manager.crosshairs[self.key].append(self.crosshair_item)
        if self.crosshair_item.scene() != self.scene:
            self.scene.addItem(self.crosshair_item)
        if hasattr(self.crosshair_item, "text_item") and self.crosshair_item.text_item is not None:
            if self.crosshair_item.text_item.scene() != self.scene:
                self.scene.addItem(self.crosshair_item.text_item)
            if restore_text:
                self.crosshair_item.text_item.setVisible(True)
        return True

    def _remove_crosshair_from_manager_and_scene(self) -> None:
        """Drop the crosshair from the manager list and remove scene items."""
        if self.scene is None:
            return
        if self.key not in self.crosshair_manager.crosshairs:
            return
        if self.crosshair_item not in self.crosshair_manager.crosshairs[self.key]:
            return
        self.crosshair_manager.crosshairs[self.key].remove(self.crosshair_item)
        if self.crosshair_item.scene() != self.scene:
            return
        if hasattr(self.crosshair_item, "text_item") and self.crosshair_item.text_item is not None:
            if self.crosshair_item.text_item.scene() == self.scene:
                if hasattr(self.crosshair_item.text_item, "mark_deleted"):
                    self.crosshair_item.text_item.mark_deleted()
                self.scene.removeItem(self.crosshair_item.text_item)
        self.scene.removeItem(self.crosshair_item)

    def execute(self) -> None:
        """Execute the command."""
        if self.scene is None:
            return
        if self.action == "add":
            self._add_crosshair_to_manager_and_scene()
        elif self.action == "remove":
            self._remove_crosshair_from_manager_and_scene()

    def undo(self) -> None:
        """Undo the command."""
        if self.scene is None:
            return
        if self.action == "add":
            self._remove_crosshair_from_manager_and_scene()
        elif self.action == "remove":
            self._add_crosshair_to_manager_and_scene(restore_text=True)


class CrosshairMoveCommand(Command):
    """
    Command for crosshair movement operations.
    """

    def __init__(self, crosshair_item, old_position: 'QPointF', new_position: 'QPointF', scene):
        """
        Initialize crosshair move command.
        
        Args:
            crosshair_item: CrosshairItem to move
            old_position: Original position (QPointF)
            new_position: New position (QPointF)
            scene: QGraphicsScene
        """
        self.crosshair_item = crosshair_item
        self.old_position = old_position
        self.new_position = new_position
        self.scene = scene

    def execute(self) -> None:
        """Execute the command - move to new position."""
        if self.crosshair_item is None or self.scene is None:
            return
        if self.crosshair_item.scene() == self.scene:
            self.crosshair_item.setPos(self.new_position)
            self.crosshair_item.position = self.new_position
            # Update text position if view is available
            if self.scene.views():
                view = self.scene.views()[0]
                if hasattr(self.crosshair_item, 'update_text_position'):
                    self.crosshair_item.update_text_position(view)

    def undo(self) -> None:
        """Undo the command - move back to old position."""
        if self.crosshair_item is None or self.scene is None:
            return
        if self.crosshair_item.scene() == self.scene:
            self.crosshair_item.setPos(self.old_position)
            self.crosshair_item.position = self.old_position
            # Update text position if view is available
            if self.scene.views():
                view = self.scene.views()[0]
                if hasattr(self.crosshair_item, 'update_text_position'):
                    self.crosshair_item.update_text_position(view)


class CompositeCommand(Command):
    """
    Command that executes multiple commands as a single operation.
    Useful for batch operations like "delete all" or "clear all".
    """

    def __init__(self, commands: list[Command]):
        """
        Initialize composite command.
        
        Args:
            commands: List of commands to execute together
        """
        self.commands = commands

    def execute(self) -> None:
        """Execute all commands in order."""
        for command in self.commands:
            command.execute()

    def undo(self) -> None:
        """Undo all commands in reverse order."""
        for command in reversed(self.commands):
            command.undo()


from utils.undo_redo_tag_commands import TagEditCommand  # noqa: F401 (re-exported)

