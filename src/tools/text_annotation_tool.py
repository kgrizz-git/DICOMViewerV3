"""
Text Annotation Tool

This module provides text annotation functionality for adding text labels to images.

Inputs:
    - User mouse clicks for text placement
    - Text input from user
    
Outputs:
    - Text annotation graphics items
    - Editable text overlays
    
Requirements:
    - PySide6 for graphics
    - ConfigManager for annotation settings
"""

from PySide6.QtWidgets import QGraphicsTextItem, QGraphicsItem, QGraphicsSceneMouseEvent, QInputDialog
from PySide6.QtCore import Qt, QPointF, QRectF
from PySide6.QtGui import QColor, QFont, QKeyEvent, QTextCursor
from typing import List, Optional, Tuple, Dict, Callable
from utils.config_manager import ConfigManager


class TextAnnotationItem(QGraphicsTextItem):
    """
    Custom QGraphicsTextItem for text annotations with inline editing support.
    """
    
    def __init__(self, text: str = "", config_manager: Optional[ConfigManager] = None, 
                 on_editing_finished: Optional[Callable[[bool], None]] = None):
        """
        Initialize text annotation item.
        
        Args:
            text: Initial text content
            config_manager: Optional ConfigManager for font settings
            on_editing_finished: Optional callback when editing finishes (accept: bool)
        """
        super().__init__(text)
        
        self.config_manager = config_manager
        self._editing = False
        self._original_text = text
        self.on_editing_finished = on_editing_finished
        
        # Get font settings from config
        font_size = 12  # Default
        font_color = (255, 255, 0)  # Default yellow
        if self.config_manager:
            # Use measurement font settings as default (or add text-specific settings later)
            font_size = self.config_manager.get_measurement_font_size()
            font_color = self.config_manager.get_measurement_font_color()
        
        # Set font
        font = QFont("Arial", font_size)
        font.setBold(True)
        self.setFont(font)
        self.setDefaultTextColor(QColor(*font_color))
        
        # Make item selectable and movable
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        
        # Use ItemIgnoresTransformations for consistent font size (like measurement text)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations, True)
        
        # Set z-value above measurements but below overlays
        self.setZValue(160)
        
        # Enable text interaction for editing
        self.setTextInteractionFlags(Qt.TextInteractionFlag.TextEditorInteraction)
    
    def mouseDoubleClickEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        """
        Handle double-click to start inline editing.
        
        Args:
            event: Mouse event
        """
        if not self._editing:
            self.start_editing()
        super().mouseDoubleClickEvent(event)
    
    def start_editing(self) -> None:
        """Start inline editing mode."""
        self._editing = True
        self._original_text = self.toPlainText()
        # Set focus to enable text editing
        self.setFocus()
        # Select all text for easy replacement using text cursor
        text_cursor = self.textCursor()
        text_cursor.movePosition(QTextCursor.MoveOperation.Start)
        text_cursor.movePosition(QTextCursor.MoveOperation.End, QTextCursor.MoveMode.KeepAnchor)
        self.setTextCursor(text_cursor)
    
    def finish_editing(self, accept: bool = True) -> None:
        """
        Finish inline editing mode.
        
        Args:
            accept: If True, keep changes; if False, revert to original text
        """
        if not self._editing:
            return
        
        if not accept:
            self.setPlainText(self._original_text)
        
        self._editing = False
        self.clearFocus()
        # Clear selection
        text_cursor = self.textCursor()
        text_cursor.clearSelection()
        self.setTextCursor(text_cursor)
        
        # Call callback if provided
        if self.on_editing_finished:
            self.on_editing_finished(accept)
    
    def keyPressEvent(self, event: QKeyEvent) -> None:
        """
        Handle key press events during editing.
        
        Args:
            event: Key event
        """
        if self._editing:
            if event.key() == Qt.Key.Key_Return or event.key() == Qt.Key.Key_Enter:
                # Finish editing on Enter
                self.finish_editing(accept=True)
                event.accept()
                return
            elif event.key() == Qt.Key.Key_Escape:
                # Cancel editing on Escape
                self.finish_editing(accept=False)
                event.accept()
                return
        
        super().keyPressEvent(event)
    
    def focusOutEvent(self, event) -> None:
        """
        Handle focus loss - finish editing.
        
        Args:
            event: Focus event
        """
        if self._editing:
            self.finish_editing(accept=True)
        super().focusOutEvent(event)


class TextAnnotationTool:
    """
    Manages text annotations on images.
    
    Features:
    - Create text annotations
    - Edit text annotations inline
    - Delete text annotations
    - Per-slice storage
    """
    
    def __init__(self, config_manager: Optional[ConfigManager] = None):
        """
        Initialize the text annotation tool.
        
        Args:
            config_manager: Optional ConfigManager for annotation settings
        """
        # Key format: (StudyInstanceUID, SeriesInstanceUID, instance_identifier)
        self.annotations: Dict[Tuple[str, str, int], List[TextAnnotationItem]] = {}
        self.current_study_uid = ""
        self.current_series_uid = ""
        self.current_instance_identifier = 0
        self.config_manager = config_manager
        self.current_item: Optional[TextAnnotationItem] = None  # For preview during creation
    
    def set_current_slice(self, study_uid: str, series_uid: str, instance_identifier: int) -> None:
        """
        Set the current slice using composite key.
        
        Args:
            study_uid: StudyInstanceUID
            series_uid: SeriesInstanceUID
            instance_identifier: InstanceNumber from DICOM or slice_index as fallback
        """
        self.current_study_uid = study_uid
        self.current_series_uid = series_uid
        self.current_instance_identifier = instance_identifier
        key = (study_uid, series_uid, instance_identifier)
        if key not in self.annotations:
            self.annotations[key] = []
    
    def start_annotation(self, pos: QPointF, on_editing_finished: Optional[Callable[[bool], None]] = None) -> None:
        """
        Start a new text annotation.
        
        Creates the text item but does NOT start editing yet. Editing should be started
        after the item is added to the scene (setFocus requires item to be in scene).
        
        Args:
            pos: Starting position
            on_editing_finished: Optional callback when editing finishes (accept: bool)
        """
        # Create a temporary text item for preview
        self.current_item = TextAnnotationItem("", self.config_manager, on_editing_finished=on_editing_finished)
        self.current_item.setPos(pos)
        # Don't start editing here - coordinator will do it after adding to scene
    
    def finish_annotation(self, scene, initial_text: str = "") -> Optional[TextAnnotationItem]:
        """
        Finish current text annotation.
        
        Args:
            scene: QGraphicsScene to add annotation to
            initial_text: Optional initial text (if not using inline editing)
        
        Returns:
            Created text annotation item or None
        """
        if self.current_item is None:
            return None
        
        # Get final text
        final_text = self.current_item.toPlainText().strip()
        
        # If text is empty, cancel the annotation
        if not final_text:
            if self.current_item.scene() == scene:
                scene.removeItem(self.current_item)
            self.current_item = None
            return None
        
        # Finish editing
        self.current_item.finish_editing(accept=True)
        
        # Add to scene if not already there
        if self.current_item.scene() != scene:
            scene.addItem(self.current_item)
        
        # Store annotation
        key = (self.current_study_uid, self.current_series_uid, self.current_instance_identifier)
        if key not in self.annotations:
            self.annotations[key] = []
        self.annotations[key].append(self.current_item)
        
        item = self.current_item
        self.current_item = None
        
        return item
    
    def cancel_annotation(self, scene) -> None:
        """
        Cancel current annotation.
        
        Args:
            scene: QGraphicsScene to remove items from
        """
        if self.current_item is not None:
            if self.current_item.scene() == scene:
                scene.removeItem(self.current_item)
            self.current_item = None
    
    def edit_annotation(self, item: TextAnnotationItem) -> None:
        """
        Start editing an existing annotation.
        
        Args:
            item: TextAnnotationItem to edit
        """
        item.start_editing()
    
    def delete_annotation(self, item: TextAnnotationItem, scene) -> None:
        """
        Delete a text annotation.
        
        Args:
            item: TextAnnotationItem to delete
            scene: QGraphicsScene to remove item from
        """
        # Remove from scene
        if item.scene() == scene:
            scene.removeItem(item)
        
        # Remove from storage
        for key, annotation_list in list(self.annotations.items()):
            if item in annotation_list:
                annotation_list.remove(item)
                # If list is empty, remove the key
                if not annotation_list:
                    del self.annotations[key]
                break
    
    def get_annotations_for_slice(self, study_uid: str, series_uid: str, instance_identifier: int) -> List[TextAnnotationItem]:
        """
        Get all text annotations for a slice using composite key.
        
        Args:
            study_uid: StudyInstanceUID
            series_uid: SeriesInstanceUID
            instance_identifier: InstanceNumber from DICOM or slice_index as fallback
            
        Returns:
            List of text annotation items
        """
        key = (study_uid, series_uid, instance_identifier)
        return self.annotations.get(key, [])
    
    def clear_annotations_from_other_slices(self, study_uid: str, series_uid: str, instance_identifier: int, scene) -> None:
        """
        Clear annotations from other slices (not the current one) from the scene.
        
        Args:
            study_uid: StudyInstanceUID of current slice
            series_uid: SeriesInstanceUID of current slice
            instance_identifier: InstanceNumber of current slice
            scene: QGraphicsScene to remove items from
        """
        current_key = (study_uid, series_uid, instance_identifier)
        
        # Get all annotations currently in the scene
        scene_items = list(scene.items())
        for item in scene_items:
            # Check if this is a text annotation item
            if isinstance(item, TextAnnotationItem):
                # Check if this annotation belongs to a different slice
                belongs_to_current = False
                for key, annotation_list in self.annotations.items():
                    if item in annotation_list:
                        if key == current_key:
                            belongs_to_current = True
                        break
                
                # Remove from scene if it doesn't belong to current slice
                if not belongs_to_current and item.scene() == scene:
                    scene.removeItem(item)
    
    def display_annotations_for_slice(self, study_uid: str, series_uid: str, instance_identifier: int, scene) -> None:
        """
        Display annotations for a slice.
        
        Ensures all annotations for the current slice are visible in the scene.
        
        Args:
            study_uid: StudyInstanceUID
            series_uid: SeriesInstanceUID
            instance_identifier: InstanceNumber from DICOM or slice_index as fallback
            scene: QGraphicsScene to add items to
        """
        key = (study_uid, series_uid, instance_identifier)
        annotations = self.annotations.get(key, [])
        
        for annotation in annotations:
            # Add annotation if not already in scene
            if annotation.scene() != scene:
                scene.addItem(annotation)
                annotation.setZValue(160)
            
            # Ensure annotation is visible
            annotation.show()
    
    def clear_slice_annotations(self, study_uid: str, series_uid: str, instance_identifier: int, scene) -> None:
        """
        Clear all annotations from a slice using composite key.
        
        Args:
            study_uid: StudyInstanceUID
            series_uid: SeriesInstanceUID
            instance_identifier: InstanceNumber from DICOM or slice_index as fallback
            scene: QGraphicsScene to remove items from
        """
        key = (study_uid, series_uid, instance_identifier)
        if key in self.annotations:
            for annotation in self.annotations[key]:
                # Only remove if item actually belongs to this scene
                if annotation.scene() == scene:
                    scene.removeItem(annotation)
            del self.annotations[key]
    
    def clear_annotations(self, scene) -> None:
        """
        Clear all annotations from all slices.
        
        Args:
            scene: QGraphicsScene to remove items from
        """
        for annotation_list in self.annotations.values():
            for annotation in annotation_list:
                # Only remove if item actually belongs to this scene
                if annotation.scene() == scene:
                    scene.removeItem(annotation)
        self.annotations.clear()
    
    def update_all_annotation_styles(self, config_manager: ConfigManager) -> None:
        """
        Update styles (font size, font color) for all existing annotations.
        
        Args:
            config_manager: ConfigManager instance to get current settings
        """
        if config_manager is None:
            return
        
        # Get new settings from config
        font_size = config_manager.get_measurement_font_size()
        font_color = config_manager.get_measurement_font_color()
        
        # Update all annotations
        for key, annotation_list in self.annotations.items():
            for annotation in annotation_list:
                # Update text item font and color
                annotation.setDefaultTextColor(QColor(*font_color))
                font = QFont("Arial", font_size)
                font.setBold(True)
                annotation.setFont(font)
