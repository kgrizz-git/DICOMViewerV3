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
from utils.debug_log import debug_log, annotation_debug


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
        self._is_new_annotation = False  # Flag to distinguish new vs existing annotations
        self._ignore_focus_loss_until = None  # Timestamp to ignore focus loss until (for preventing premature focus loss)
        
        # Get font settings from config
        font_size = 12  # Default
        font_color = (255, 255, 0)  # Default yellow
        if self.config_manager:
            # Use text annotation specific settings
            font_size = self.config_manager.get_text_annotation_font_size()
            font_color = self.config_manager.get_text_annotation_color()
        
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
        
        # Text interaction will be enabled only when editing starts
        # Start with no text interaction to prevent accidental editing on mouseover
        self.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        
        # Enable undo/redo for text editing
        self.document().setUndoRedoEnabled(True)
        
        # Install event filter to catch Enter key before text editor processes it
        self.installEventFilter(self)
        
        # Connect to document's contents change to detect newlines
        self.document().contentsChange.connect(self._on_contents_changed)
        
        # Move tracking callback (set by coordinator)
        self.on_moved_callback = None
        # Text edit finished callback (set by coordinator for existing annotations)
        # Callback signature: (text_item, old_text: str, new_text: str) -> None
        self.on_text_edit_finished = None
    
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
        import time
        self._editing = True
        self._original_text = self.toPlainText()
        # If editing existing annotation (no callback), clear the new annotation flag
        if self.on_editing_finished is None:
            self._is_new_annotation = False
        # Set timestamp to ignore focus loss for 200ms after starting (prevents premature focus loss)
        if self._is_new_annotation:
            self._ignore_focus_loss_until = time.time() + 0.2  # 200ms grace period
        annotation_debug(f" TextAnnotationItem.start_editing: _is_new_annotation={self._is_new_annotation}, callback={'exists' if self.on_editing_finished is not None else 'None'}, ignore_focus_loss_until={self._ignore_focus_loss_until}")
        # Enable text interaction for editing
        self.setTextInteractionFlags(Qt.TextInteractionFlag.TextEditorInteraction)
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
        annotation_debug(f" TextAnnotationItem.finish_editing: called, _editing={self._editing}, accept={accept}, _is_new_annotation={self._is_new_annotation}, callback={'exists' if self.on_editing_finished is not None else 'None'}, text={repr(self.toPlainText())}")
        
        if not self._editing:
            annotation_debug(f" TextAnnotationItem.finish_editing: early return (not editing)")
            return
        
        if not accept:
            self.setPlainText(self._original_text)
            annotation_debug(f" TextAnnotationItem.finish_editing: reverted to original text")
        
        # Store current text before clearing state
        current_text = self.toPlainText()
        current_is_new = self._is_new_annotation
        has_callback = self.on_editing_finished is not None
        
        self._editing = False
        self._is_new_annotation = False  # Clear flag after finishing
        annotation_debug(f" TextAnnotationItem.finish_editing: state cleared, _is_new_annotation={self._is_new_annotation}, text={repr(current_text)}")
        
        # Disable text interaction to prevent accidental editing on mouseover
        self.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        
        self.clearFocus()
        # Clear selection
        text_cursor = self.textCursor()
        text_cursor.clearSelection()
        self.setTextCursor(text_cursor)
        
        # Check if text changed for existing annotation (not new annotation)
        # has_callback means it's a new annotation being created, not an existing one being edited
        annotation_debug(f" TextAnnotationItem.finish_editing: checking edit callback - has_callback={has_callback}, on_text_edit_finished={'exists' if self.on_text_edit_finished is not None else 'None'}, original_text='{self._original_text}', current_text='{current_text}'")
        if not has_callback and self.on_text_edit_finished is not None:
            # Existing annotation was edited - check if text changed
            if current_text != self._original_text:
                annotation_debug(f" TextAnnotationItem.finish_editing: text changed for existing annotation, old='{self._original_text}', new='{current_text}', calling on_text_edit_finished")
                self.on_text_edit_finished(self, self._original_text, current_text)
                annotation_debug(f" TextAnnotationItem.finish_editing: on_text_edit_finished returned")
            else:
                annotation_debug(f" TextAnnotationItem.finish_editing: text unchanged for existing annotation, not creating edit command")
        elif not has_callback and self.on_text_edit_finished is None:
            annotation_debug(f" TextAnnotationItem.finish_editing: existing annotation edited but on_text_edit_finished is None - callback not set up!")
        
        # Call callback if provided (for new annotations)
        if has_callback:
            annotation_debug(f" TextAnnotationItem.finish_editing: calling callback with accept={accept}")
            self.on_editing_finished(accept)
            annotation_debug(f" TextAnnotationItem.finish_editing: callback returned")
        else:
            annotation_debug(f" TextAnnotationItem.finish_editing: no callback to call")
    
    def keyPressEvent(self, event: QKeyEvent) -> None:
        """
        Handle key press events during editing.
        
        Args:
            event: Key event
        """
        if self._editing:
            # Handle Cmd+Z / Ctrl+Z for text editing undo
            if (event.key() == Qt.Key.Key_Z and 
                (event.modifiers() & Qt.KeyboardModifier.ControlModifier or 
                 event.modifiers() & Qt.KeyboardModifier.MetaModifier)):
                if self.document().isUndoAvailable():
                    self.document().undo()
                    event.accept()
                    return
            # Handle Cmd+Shift+Z / Ctrl+Shift+Z for text editing redo
            elif (event.key() == Qt.Key.Key_Z and 
                  (event.modifiers() & Qt.KeyboardModifier.ControlModifier or 
                   event.modifiers() & Qt.KeyboardModifier.MetaModifier) and
                  event.modifiers() & Qt.KeyboardModifier.ShiftModifier):
                if self.document().isRedoAvailable():
                    self.document().redo()
                    event.accept()
                    return
            elif event.key() == Qt.Key.Key_Return or event.key() == Qt.Key.Key_Enter:
                # Finish editing on Enter - prevent newline
                annotation_debug(f" TextAnnotationItem.keyPressEvent: Enter key pressed, _editing={self._editing}")
                self.finish_editing(accept=True)
                event.accept()
                return  # Don't call super() - prevent text editor from processing Enter
            elif event.key() == Qt.Key.Key_Escape:
                # Cancel editing on Escape
                annotation_debug(f" TextAnnotationItem.keyPressEvent: Escape key pressed, _editing={self._editing}")
                self.finish_editing(accept=False)
                event.accept()
                return  # Don't call super() - prevent text editor from processing Escape
        
        super().keyPressEvent(event)
    
    def inputMethodEvent(self, event) -> None:
        """
        Handle input method events (for intercepting Enter key before it becomes text).
        
        Args:
            event: Input method event
        """
        from PySide6.QtCore import Qt
        from PySide6.QtGui import QInputMethodEvent
        
        # Debug: Log all input method events
        commit_str = event.commitString() if hasattr(event, 'commitString') else None
        preedit_str = event.preeditString() if hasattr(event, 'preeditString') else None
        annotation_debug(f" TextAnnotationItem.inputMethodEvent: called, _editing={self._editing}, commitString={repr(commit_str)}, preeditString={repr(preedit_str)}")
        
        # Check if this is an Enter key input
        if commit_str:
            # Check if the commit string contains newline (Enter key)
            if '\n' in commit_str or '\r' in commit_str:
                annotation_debug(f" TextAnnotationItem.inputMethodEvent: Enter key detected in commitString, intercepting")
                # Finish editing instead of inserting newline
                if self._editing:
                    self.finish_editing(accept=True)
                    event.accept()
                    return
            else:
                annotation_debug(f" TextAnnotationItem.inputMethodEvent: Non-Enter input, commitString={repr(commit_str)}")
        
        # For other input, call super
        super().inputMethodEvent(event)
    
    def insertFromMimeData(self, source) -> None:
        """
        Override to intercept Enter key when pasting or inserting text.
        
        Args:
            source: MimeData source
        """
        if self._editing and source.hasText():
            text = source.text()
            # Check if text contains newline (Enter key)
            if '\n' in text or '\r' in text:
                annotation_debug(f" TextAnnotationItem.insertFromMimeData: Enter key detected in text, intercepting")
                # Finish editing instead of inserting newline
                self.finish_editing(accept=True)
                return
        
        super().insertFromMimeData(source)
    
    def focusOutEvent(self, event) -> None:
        """
        Handle focus loss - finish editing.
        
        Only processes focus loss for items that are currently being created (have on_editing_finished callback).
        Existing annotations should not trigger this callback.
        
        Args:
            event: Focus event
        """
        from PySide6.QtCore import Qt
        import time
        focus_reason = event.reason()
        current_text = self.toPlainText()
        
        # Check if we should ignore this focus loss (grace period after starting editing)
        ignore_focus_loss = False
        if self._ignore_focus_loss_until is not None:
            if time.time() < self._ignore_focus_loss_until:
                ignore_focus_loss = True
                annotation_debug(f" TextAnnotationItem.focusOutEvent: ignoring focus loss (grace period), reason={focus_reason}")
            else:
                self._ignore_focus_loss_until = None  # Clear after grace period
        
        annotation_debug(f" TextAnnotationItem.focusOutEvent: called, reason={focus_reason}, _editing={self._editing}, _is_new_annotation={self._is_new_annotation}, callback={'exists' if self.on_editing_finished is not None else 'None'}, text={repr(current_text)}, ignore_focus_loss={ignore_focus_loss}")
        
        # Check conditions for processing
        should_process = self._editing and self._is_new_annotation and self.on_editing_finished is not None and not ignore_focus_loss
        annotation_debug(f" TextAnnotationItem.focusOutEvent: should_process={should_process} (_editing={self._editing}, _is_new_annotation={self._is_new_annotation}, callback={'exists' if self.on_editing_finished is not None else 'None'}, ignore_focus_loss={ignore_focus_loss})")
        
        # Only finish editing if we're actually editing AND we're creating a new annotation
        # Existing annotations should have _is_new_annotation = False and on_editing_finished = None
        if should_process:
            # Check focus reason - if it's a mouse click, we might be selecting the item
            # In that case, only finish if text is not empty
            # If focus is lost due to mouse click and text is empty, cancel
            # Otherwise, accept the changes
            if focus_reason == Qt.FocusReason.MouseFocusReason:
                # Mouse click - check if text is empty
                text_stripped = current_text.strip()
                annotation_debug(f" TextAnnotationItem.focusOutEvent: MouseFocusReason, text_stripped={repr(text_stripped)}")
                if not text_stripped:
                    annotation_debug(f" TextAnnotationItem.focusOutEvent: Empty text, canceling")
                    self.finish_editing(accept=False)
                else:
                    annotation_debug(f" TextAnnotationItem.focusOutEvent: Non-empty text, accepting")
                    self.finish_editing(accept=True)
            else:
                # Other focus reasons (tab, window activation, etc.) - accept changes
                annotation_debug(f" TextAnnotationItem.focusOutEvent: Non-mouse focus loss, accepting")
                self.finish_editing(accept=True)
        else:
            annotation_debug(f" TextAnnotationItem.focusOutEvent: Skipping (should_process=False)")
        
        super().focusOutEvent(event)
    
    def eventFilter(self, obj, event) -> bool:
        """
        Event filter to intercept Enter key before text editor processes it.
        
        Args:
            obj: Object that received the event
            event: Event
            
        Returns:
            True if event was handled, False otherwise
        """
        from PySide6.QtCore import QEvent
        from PySide6.QtGui import QKeyEvent
        
        # Only filter events for this item
        if obj != self:
            return False
        
        # Check for key press events
        if event.type() == QEvent.Type.KeyPress:
            key_event = event
            if isinstance(key_event, QKeyEvent):
                if self._editing and (key_event.key() == Qt.Key.Key_Return or key_event.key() == Qt.Key.Key_Enter):
                    annotation_debug(f" TextAnnotationItem.eventFilter: Enter key intercepted in event filter")
                    # Finish editing instead of inserting newline
                    self.finish_editing(accept=True)
                    return True  # Event handled
        
        # Let other events through
        return False
    
    def _on_contents_changed(self, position: int, chars_removed: int, chars_added: int) -> None:
        """
        Handle document contents change - detect and remove newlines.
        
        Args:
            position: Position where change occurred
            chars_removed: Number of characters removed
            chars_added: Number of characters added
        """
        if not self._editing:
            return
        
        # Get the text that was just added
        text = self.toPlainText()
        
        # Check if text contains newlines
        if '\n' in text or '\r' in text:
            annotation_debug(f" TextAnnotationItem._on_contents_changed: Newline detected in text, removing and finishing editing")
            # Remove newlines
            text_without_newlines = text.replace('\n', '').replace('\r', '')
            # Set text without newlines
            self.setPlainText(text_without_newlines)
            # Finish editing
            self.finish_editing(accept=True)
    
    def itemChange(self, change: QGraphicsItem.GraphicsItemChange, value) -> object:
        """
        Handle item changes (e.g., position changes when moved).
        
        Args:
            change: Type of change
            value: New value
            
        Returns:
            Modified value
        """
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            # Call movement callback if set (for undo/redo tracking)
            if self.on_moved_callback:
                try:
                    debug_log("text_annotation_tool.py:itemChange", "Text annotation moved", {"item_id": str(id(self)), "position": str(self.pos()), "has_callback": self.on_moved_callback is not None}, hypothesis_id="C")
                    self.on_moved_callback(self)
                except Exception:
                    pass
        
        return super().itemChange(change, value)


def is_any_text_annotation_editing(scene) -> bool:
    """
    Check if any text annotation in the scene is currently being edited.
    
    Args:
        scene: QGraphicsScene to check
        
    Returns:
        True if any TextAnnotationItem in the scene has _editing = True, False otherwise
    """
    if scene is None:
        return False
    from tools.text_annotation_tool import TextAnnotationItem
    for item in scene.items():
        if isinstance(item, TextAnnotationItem) and getattr(item, '_editing', False):
            return True
    return False


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
        # Mark as new annotation
        self.current_item._is_new_annotation = True
        annotation_debug(f" TextAnnotationTool.start_annotation: created item, _is_new_annotation=True")
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
        annotation_debug(f" TextAnnotationTool.finish_annotation: called, current_item={'exists' if self.current_item is not None else 'None'}")
        
        # Guard against double-call
        if self.current_item is None:
            annotation_debug(f" TextAnnotationTool.finish_annotation: current_item is None, returning")
            return None
        
        # Get final text BEFORE any state changes
        final_text = self.current_item.toPlainText().strip()
        current_is_new = getattr(self.current_item, '_is_new_annotation', False)
        has_callback = self.current_item.on_editing_finished is not None
        annotation_debug(f" TextAnnotationTool.finish_annotation: current_item state - text='{final_text}', _is_new_annotation={current_is_new}, callback={'exists' if has_callback else 'None'}")
        
        # If text is empty, cancel the annotation (don't create undo command)
        # BUT still clear the callback to prevent issues
        if not final_text:
            annotation_debug(f" TextAnnotationTool.finish_annotation: empty text, canceling annotation")
            # Clear callback and flag even when canceling
            if self.current_item:
                self.current_item._is_new_annotation = False
                self.current_item.on_editing_finished = None
                annotation_debug(f" TextAnnotationTool.finish_annotation: cleared callback and flag on cancel")
            if self.current_item and self.current_item.scene() == scene:
                scene.removeItem(self.current_item)
            self.current_item = None
            return None
        
        # Store item reference BEFORE any state changes
        item = self.current_item
        annotation_debug(f" TextAnnotationTool.finish_annotation: stored item reference, item={item}")
        
        # Check if editing is still active (shouldn't be, but check)
        was_editing = self.current_item._editing
        annotation_debug(f" TextAnnotationTool.finish_annotation: was_editing={was_editing}")
        
        # Finish editing (this may trigger callback, but we'll handle that in coordinator)
        # Note: finish_editing will set _is_new_annotation = False and may call callback
        annotation_debug(f" TextAnnotationTool.finish_annotation: calling finish_editing")
        item.finish_editing(accept=True)
        annotation_debug(f" TextAnnotationTool.finish_annotation: finish_editing returned")
        
        # Check state after finish_editing (use item; self.current_item may be None if callback re-entered)
        after_is_new = getattr(item, '_is_new_annotation', False)
        after_callback = item.on_editing_finished is not None
        annotation_debug(f" TextAnnotationTool.finish_annotation: after finish_editing - _is_new_annotation={after_is_new}, callback={'exists' if after_callback else 'None'}")
        
        # Add to scene if not already there
        if item.scene() != scene:
            scene.addItem(item)
            annotation_debug(f" TextAnnotationTool.finish_annotation: added item to scene")
        
        # Store annotation
        key = (self.current_study_uid, self.current_series_uid, self.current_instance_identifier)
        if key not in self.annotations:
            self.annotations[key] = []
        self.annotations[key].append(item)
        annotation_debug(f" TextAnnotationTool.finish_annotation: stored in annotations dict, key={key}")
        
        # Clear the callback and flag after annotation is finished (prevent accidental deletion on focus loss)
        annotation_debug(f" TextAnnotationTool.finish_annotation: clearing callback and flag")
        item._is_new_annotation = False
        item.on_editing_finished = None
        annotation_debug(f" TextAnnotationTool.finish_annotation: callback and flag cleared")
        
        # Clear current_item reference
        self.current_item = None
        annotation_debug(f" TextAnnotationTool.finish_annotation: returning item={item}")
        
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
        
        # Get new settings from config (text annotation specific)
        font_size = config_manager.get_text_annotation_font_size()
        font_color = config_manager.get_text_annotation_color()
        
        # Update all annotations
        for key, annotation_list in self.annotations.items():
            for annotation in annotation_list:
                # Update text item font and color
                annotation.setDefaultTextColor(QColor(*font_color))
                font = QFont("Arial", font_size)
                font.setBold(True)
                annotation.setFont(font)
