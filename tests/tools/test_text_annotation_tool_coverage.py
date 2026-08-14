"""Coverage tests for tools.text_annotation_tool: item, tool, and scene helpers."""

from __future__ import annotations

import time
from unittest.mock import MagicMock

from PySide6.QtCore import QEvent, QPointF, Qt
from PySide6.QtGui import QFocusEvent, QInputMethodEvent, QKeyEvent
from PySide6.QtWidgets import (
    QGraphicsScene,
    QGraphicsSceneMouseEvent,
    QGraphicsTextItem,
)

from tools.text_annotation_tool import (
    TextAnnotationItem,
    TextAnnotationTool,
    is_any_text_annotation_editing,
)

# ---------------------------------------------------------------------------
# TextAnnotationItem – construction and flags
# ---------------------------------------------------------------------------

class TestTextAnnotationItemInit:
    def test_default_font(self, qapp):
        item = TextAnnotationItem("hello")
        assert item.toPlainText() == "hello"
        assert item._editing is False
        assert item._is_new_annotation is False

    def test_with_config_manager(self, qapp):
        cfg = MagicMock()
        cfg.get_text_annotation_font_size.return_value = 16
        cfg.get_text_annotation_color.return_value = (0, 255, 0)
        cfg.get_text_annotation_font_family.return_value = "IBM Plex Sans"
        cfg.get_text_annotation_font_variant.return_value = "Regular"
        item = TextAnnotationItem("cfg", config_manager=cfg)
        assert item.toPlainText() == "cfg"

    def test_with_callback(self, qapp):
        cb = MagicMock()
        item = TextAnnotationItem("cb", on_editing_finished=cb)
        assert item.on_editing_finished is cb

    def test_flags_set(self, qapp):
        from PySide6.QtWidgets import QGraphicsItem
        item = TextAnnotationItem()
        assert item.flags() & QGraphicsItem.GraphicsItemFlag.ItemIsSelectable
        assert item.flags() & QGraphicsItem.GraphicsItemFlag.ItemIsMovable
        assert item.flags() & QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges
        assert item.flags() & QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations
        assert item.zValue() == 160


# ---------------------------------------------------------------------------
# start_editing / finish_editing
# ---------------------------------------------------------------------------

class TestStartFinishEditing:
    def test_start_editing(self, qapp):
        item = TextAnnotationItem("abc")
        scene = QGraphicsScene()
        scene.addItem(item)
        item.start_editing()
        assert item._editing is True
        assert item._original_text == "abc"
        item.finish_editing(accept=True)
        assert item._editing is False

    def test_finish_editing_reject_reverts(self, qapp):
        item = TextAnnotationItem("original")
        scene = QGraphicsScene()
        scene.addItem(item)
        item.start_editing()
        item.setPlainText("changed")
        item.finish_editing(accept=False)
        assert item.toPlainText() == "original"
        assert item._editing is False

    def test_finish_editing_not_editing(self, qapp):
        item = TextAnnotationItem("abc")
        item.finish_editing(accept=True)
        assert item._editing is False

    def test_finish_editing_with_on_editing_finished_callback(self, qapp):
        cb = MagicMock()
        item = TextAnnotationItem("abc", on_editing_finished=cb)
        scene = QGraphicsScene()
        scene.addItem(item)
        item.start_editing()
        item.finish_editing(accept=True)
        cb.assert_called_once_with(True)

    def test_finish_editing_reject_callback(self, qapp):
        cb = MagicMock()
        item = TextAnnotationItem("abc", on_editing_finished=cb)
        scene = QGraphicsScene()
        scene.addItem(item)
        item.start_editing()
        item.finish_editing(accept=False)
        cb.assert_called_once_with(False)

    def test_finish_editing_existing_annotation_triggers_edit_finished(self, qapp):
        item = TextAnnotationItem("old")
        item.on_editing_finished = None
        item.on_text_edit_finished = MagicMock()
        scene = QGraphicsScene()
        scene.addItem(item)
        item.start_editing()
        # on_editing_finished is None → existing annotation path
        assert item.on_editing_finished is None
        item.setPlainText("new text")
        item.finish_editing(accept=True)
        # on_text_edit_finished should be called because text changed
        item.on_text_edit_finished.assert_called_once()

    def test_finish_editing_existing_no_text_change(self, qapp):
        item = TextAnnotationItem("same")
        item.on_editing_finished = None
        item.on_text_edit_finished = MagicMock()
        scene = QGraphicsScene()
        scene.addItem(item)
        item.start_editing()
        item.finish_editing(accept=True)
        item.on_text_edit_finished.assert_not_called()

    def test_start_editing_new_annotation_grace_period(self, qapp):
        item = TextAnnotationItem("new")
        item._is_new_annotation = True
        item.on_editing_finished = MagicMock()
        scene = QGraphicsScene()
        scene.addItem(item)
        item.start_editing()
        assert item._ignore_focus_loss_until is not None
        assert item._ignore_focus_loss_until > time.time()

    def test_start_editing_existing_clears_new_flag(self, qapp):
        item = TextAnnotationItem("old")
        item.on_editing_finished = None
        scene = QGraphicsScene()
        scene.addItem(item)
        item.start_editing()
        assert item._is_new_annotation is False


# ---------------------------------------------------------------------------
# keyPressEvent
# ---------------------------------------------------------------------------

class TestKeyPressEvent:
    def _key_event(self, key, modifiers=Qt.KeyboardModifier.NoModifier):
        return QKeyEvent(QKeyEvent.Type.KeyPress, key, modifiers)

    def test_enter_finishes_editing(self, qapp):
        item = TextAnnotationItem("abc")
        scene = QGraphicsScene()
        scene.addItem(item)
        item.start_editing()
        ev = self._key_event(Qt.Key.Key_Return)
        item.keyPressEvent(ev)
        assert item._editing is False

    def test_escape_reverts(self, qapp):
        item = TextAnnotationItem("abc")
        scene = QGraphicsScene()
        scene.addItem(item)
        item.start_editing()
        item.setPlainText("xyz")
        ev = self._key_event(Qt.Key.Key_Escape)
        item.keyPressEvent(ev)
        assert item.toPlainText() == "abc"
        assert item._editing is False

    def test_ctrl_z_undo(self, qapp):
        item = TextAnnotationItem("")
        scene = QGraphicsScene()
        scene.addItem(item)
        item.start_editing()
        cursor = item.textCursor()
        cursor.insertText("abc")
        item.setTextCursor(cursor)
        ev = self._key_event(Qt.Key.Key_Z, Qt.KeyboardModifier.ControlModifier)
        item.keyPressEvent(ev)
        assert item.toPlainText() == ""

    def test_meta_z_undo(self, qapp):
        item = TextAnnotationItem("")
        scene = QGraphicsScene()
        scene.addItem(item)
        item.start_editing()
        cursor = item.textCursor()
        cursor.insertText("abc")
        item.setTextCursor(cursor)
        ev = self._key_event(Qt.Key.Key_Z, Qt.KeyboardModifier.MetaModifier)
        item.keyPressEvent(ev)
        assert item.toPlainText() == ""

    def test_ctrl_shift_z_redo(self, qapp):
        item = TextAnnotationItem("")
        scene = QGraphicsScene()
        scene.addItem(item)
        item.start_editing()
        cursor = item.textCursor()
        cursor.insertText("abc")
        item.setTextCursor(cursor)
        # Undo first
        ev_undo = self._key_event(Qt.Key.Key_Z, Qt.KeyboardModifier.ControlModifier)
        item.keyPressEvent(ev_undo)
        assert item.toPlainText() == ""
        # Redo
        ev_redo = self._key_event(
            Qt.Key.Key_Z,
            Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier,
        )
        item.keyPressEvent(ev_redo)
        assert item.toPlainText() == "abc"

    def test_meta_shift_z_redo(self, qapp):
        item = TextAnnotationItem("")
        scene = QGraphicsScene()
        scene.addItem(item)
        item.start_editing()
        cursor = item.textCursor()
        cursor.insertText("abc")
        item.setTextCursor(cursor)
        # Undo
        ev_undo = self._key_event(Qt.Key.Key_Z, Qt.KeyboardModifier.MetaModifier)
        item.keyPressEvent(ev_undo)
        assert item.toPlainText() == ""
        # Redo availability is platform-dependent for Meta-modified Qt key events.
        ev_redo = self._key_event(
            Qt.Key.Key_Z,
            Qt.KeyboardModifier.MetaModifier | Qt.KeyboardModifier.ShiftModifier,
        )
        item.keyPressEvent(ev_redo)
        assert item._editing is True
        assert item.toPlainText() in {"", "abc"}

# ---------------------------------------------------------------------------
# inputMethodEvent / insertFromMimeData
# ---------------------------------------------------------------------------

class TestInputMethods:
    def test_input_method_newline(self, qapp):
        item = TextAnnotationItem("")
        scene = QGraphicsScene()
        scene.addItem(item)
        item.start_editing()
        event = QInputMethodEvent()
        event.setCommitString("\n")
        item.inputMethodEvent(event)
        assert item._editing is False

    def test_input_method_normal(self, qapp):
        item = TextAnnotationItem("")
        scene = QGraphicsScene()
        scene.addItem(item)
        item.start_editing()
        event = QInputMethodEvent()
        event.setCommitString("abc")
        item.inputMethodEvent(event)

    def test_input_method_no_commit_string(self, qapp):
        item = TextAnnotationItem("")
        scene = QGraphicsScene()
        scene.addItem(item)
        item.start_editing()
        event = QInputMethodEvent()
        # Empty commit string
        item.inputMethodEvent(event)

    def test_insert_from_mime_with_newline(self, qapp):
        item = TextAnnotationItem("")
        scene = QGraphicsScene()
        scene.addItem(item)
        item.start_editing()
        source = MagicMock()
        source.hasText.return_value = True
        source.text.return_value = "line1\nline2"
        item.insertFromMimeData(source)
        assert item._editing is False

    def test_insert_from_mime_without_newline(self, qapp):
        item = TextAnnotationItem("")
        scene = QGraphicsScene()
        scene.addItem(item)
        item.start_editing()
        source = MagicMock()
        source.hasText.return_value = True
        source.text.return_value = "hello"
        item.insertFromMimeData(source)
        assert item.toPlainText() == "hello"

    def test_insert_from_mime_not_editing(self, qapp):
        item = TextAnnotationItem("")
        scene = QGraphicsScene()
        scene.addItem(item)
        source = MagicMock()
        source.hasText.return_value = True
        source.text.return_value = "world"
        item.insertFromMimeData(source)
        assert item.toPlainText() == "world"

    def test_insert_from_mime_no_text(self, qapp):
        item = TextAnnotationItem("")
        scene = QGraphicsScene()
        scene.addItem(item)
        item.start_editing()
        source = MagicMock()
        source.hasText.return_value = False
        item.insertFromMimeData(source)


# ---------------------------------------------------------------------------
# focusOutEvent
# ---------------------------------------------------------------------------

class TestFocusOutEvent:
    def test_focus_out_new_annotation_mouse_empty(self, qapp):
        item = TextAnnotationItem("")
        scene = QGraphicsScene()
        scene.addItem(item)
        item._is_new_annotation = True
        item._editing = True
        item.on_editing_finished = MagicMock()
        item._ignore_focus_loss_until = time.time() + 10  # future → ignore
        event = QFocusEvent(QEvent.Type.FocusOut, Qt.FocusReason.MouseFocusReason)
        item.focusOutEvent(event)
        # Grace period active → should not finish
        item.on_editing_finished.assert_not_called()

    def test_focus_out_new_annotation_mouse_with_text(self, qapp):
        item = TextAnnotationItem("hi")
        scene = QGraphicsScene()
        scene.addItem(item)
        item._is_new_annotation = True
        item._editing = True
        item.on_editing_finished = MagicMock()
        item._ignore_focus_loss_until = None
        event = QFocusEvent(QEvent.Type.FocusOut, Qt.FocusReason.MouseFocusReason)
        item.focusOutEvent(event)
        item.on_editing_finished.assert_called_once_with(True)

    def test_focus_out_new_annotation_mouse_empty_text(self, qapp):
        item = TextAnnotationItem("")
        scene = QGraphicsScene()
        scene.addItem(item)
        item._is_new_annotation = True
        item._editing = True
        item.on_editing_finished = MagicMock()
        item._ignore_focus_loss_until = None
        event = QFocusEvent(QEvent.Type.FocusOut, Qt.FocusReason.MouseFocusReason)
        item.focusOutEvent(event)
        item.on_editing_finished.assert_called_once_with(False)

    def test_focus_out_other_reason(self, qapp):
        item = TextAnnotationItem("hi")
        scene = QGraphicsScene()
        scene.addItem(item)
        item._is_new_annotation = True
        item._editing = True
        item.on_editing_finished = MagicMock()
        item._ignore_focus_loss_until = None
        event = QFocusEvent(QEvent.Type.FocusOut, Qt.FocusReason.TabFocusReason)
        item.focusOutEvent(event)
        item.on_editing_finished.assert_called_once_with(True)

    def test_focus_out_not_new_annotation(self, qapp):
        item = TextAnnotationItem("existing")
        item._is_new_annotation = False
        item._editing = False
        event = QFocusEvent(QEvent.Type.FocusOut, Qt.FocusReason.MouseFocusReason)
        item.focusOutEvent(event)


# ---------------------------------------------------------------------------
# eventFilter
# ---------------------------------------------------------------------------

class TestEventFilter:
    def test_enter_key_filtered(self, qapp):
        item = TextAnnotationItem("")
        scene = QGraphicsScene()
        scene.addItem(item)
        item.start_editing()
        event = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Return, Qt.KeyboardModifier.NoModifier)
        result = item.eventFilter(item, event)
        assert result is True
        assert item._editing is False

    def test_enter_key_not_editing(self, qapp):
        item = TextAnnotationItem("")
        event = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Return, Qt.KeyboardModifier.NoModifier)
        result = item.eventFilter(item, event)
        assert result is False

    def test_other_object_not_filtered(self, qapp):
        item = TextAnnotationItem("")
        other = QGraphicsTextItem("other")
        event = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Return, Qt.KeyboardModifier.NoModifier)
        result = item.eventFilter(other, event)
        assert result is False

    def test_non_key_event(self, qapp):
        from PySide6.QtCore import QEvent
        item = TextAnnotationItem("")
        event = QEvent(QEvent.Type.FocusIn)
        result = item.eventFilter(item, event)
        assert result is False


# ---------------------------------------------------------------------------
# _on_contents_changed
# ---------------------------------------------------------------------------

class TestOnContentsChanged:
    def test_newline_removed(self, qapp):
        item = TextAnnotationItem("")
        scene = QGraphicsScene()
        scene.addItem(item)
        item.start_editing()
        item.setPlainText("abc\ndef")
        # _on_contents_changed should have stripped newlines
        assert "\n" not in item.toPlainText()

    def test_not_editing_ignored(self, qapp):
        item = TextAnnotationItem("abc\ndef")
        item._editing = False
        item._on_contents_changed(0, 0, 1)
        assert "\n" in item.toPlainText()

    def test_carriage_return_removed(self, qapp):
        item = TextAnnotationItem("")
        scene = QGraphicsScene()
        scene.addItem(item)
        item.start_editing()
        item.setPlainText("abc\rdef")
        assert "\r" not in item.toPlainText()


# ---------------------------------------------------------------------------
# itemChange
# ---------------------------------------------------------------------------

class TestItemChange:
    def test_position_changed_with_callback(self, qapp):
        cb = MagicMock()
        item = TextAnnotationItem("x")
        item.on_moved_callback = cb
        from PySide6.QtWidgets import QGraphicsItem
        item.itemChange(QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged, QPointF(5, 5))
        cb.assert_called_once_with(item)

    def test_position_changed_callback_raises(self, qapp):
        item = TextAnnotationItem("x")
        item.on_moved_callback = MagicMock(side_effect=RuntimeError("boom"))
        from PySide6.QtWidgets import QGraphicsItem
        item.itemChange(QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged, QPointF(5, 5))

    def test_position_changed_no_callback(self, qapp):
        item = TextAnnotationItem("x")
        from PySide6.QtWidgets import QGraphicsItem
        item.itemChange(QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged, QPointF(5, 5))

    def test_non_position_change(self, qapp):
        item = TextAnnotationItem("x")
        from PySide6.QtWidgets import QGraphicsItem
        result = item.itemChange(QGraphicsItem.GraphicsItemChange.ItemZValueChange, 10.0)
        assert result == 10.0


# ---------------------------------------------------------------------------
# mouseDoubleClickEvent
# ---------------------------------------------------------------------------

class TestDoubleClick:
    def test_mouse_double_click_starts_editing(self, qapp):
        item = TextAnnotationItem("dbl")
        scene = QGraphicsScene()
        scene.addItem(item)
        assert item._editing is False
        event = QGraphicsSceneMouseEvent(QEvent.Type.GraphicsSceneMouseDoubleClick)
        event.setButton(Qt.MouseButton.LeftButton)
        event.setButtons(Qt.MouseButton.LeftButton)
        event.setScenePos(QPointF(4, 5))
        item.mouseDoubleClickEvent(event)
        assert item._editing is True

    def test_already_editing_no_restart(self, qapp):
        item = TextAnnotationItem("dbl")
        scene = QGraphicsScene()
        scene.addItem(item)
        item.start_editing()
        # start_editing while already editing is idempotent
        item.start_editing()
        assert item._editing is True


# ---------------------------------------------------------------------------
# is_any_text_annotation_editing
# ---------------------------------------------------------------------------

class TestIsAnyTextAnnotationEditing:
    def test_none_scene(self):
        assert is_any_text_annotation_editing(None) is False

    def test_empty_scene(self, qapp):
        scene = QGraphicsScene()
        assert is_any_text_annotation_editing(scene) is False

    def test_editing_item(self, qapp):
        scene = QGraphicsScene()
        item = TextAnnotationItem("x")
        scene.addItem(item)
        item._editing = True
        assert is_any_text_annotation_editing(scene) is True

    def test_not_editing_item(self, qapp):
        scene = QGraphicsScene()
        item = TextAnnotationItem("x")
        scene.addItem(item)
        item._editing = False
        assert is_any_text_annotation_editing(scene) is False

    def test_non_text_item(self, qapp):
        scene = QGraphicsScene()
        other = QGraphicsTextItem("y")
        scene.addItem(other)
        assert is_any_text_annotation_editing(scene) is False


# ---------------------------------------------------------------------------
# TextAnnotationTool – full lifecycle
# ---------------------------------------------------------------------------

class TestTextAnnotationTool:
    def test_set_current_slice(self, qapp):
        tool = TextAnnotationTool()
        tool.set_current_slice("st", "se", 0)
        assert tool.current_study_uid == "st"
        assert tool.current_series_uid == "se"
        assert tool.current_instance_identifier == 0
        assert ("st", "se", 0) in tool.annotations

    def test_start_and_finish(self, qapp):
        tool = TextAnnotationTool()
        tool.set_current_slice("st", "se", 0)
        scene = QGraphicsScene()
        tool.start_annotation(QPointF(10, 10))
        assert tool.current_item is not None
        tool.current_item.setPlainText("note")
        item = tool.finish_annotation(scene)
        assert item is not None
        assert item.toPlainText() == "note"

    def test_finish_empty_cancels(self, qapp):
        tool = TextAnnotationTool()
        tool.set_current_slice("st", "se", 0)
        scene = QGraphicsScene()
        tool.start_annotation(QPointF(0, 0))
        item = tool.finish_annotation(scene)
        assert item is None
        assert tool.current_item is None

    def test_finish_double_call_guard(self, qapp):
        tool = TextAnnotationTool()
        tool.set_current_slice("st", "se", 0)
        scene = QGraphicsScene()
        tool.start_annotation(QPointF(0, 0))
        tool.current_item.setPlainText("note")
        item = tool.finish_annotation(scene)
        assert item is not None
        assert tool.finish_annotation(scene) is None
        assert tool.get_annotations_for_slice("st", "se", 0) == [item]

    def test_cancel(self, qapp):
        tool = TextAnnotationTool()
        tool.set_current_slice("st", "se", 0)
        scene = QGraphicsScene()
        tool.start_annotation(QPointF(0, 0))
        tool.cancel_annotation(scene)
        assert tool.current_item is None

    def test_cancel_no_current(self, qapp):
        tool = TextAnnotationTool()
        scene = QGraphicsScene()
        tool.cancel_annotation(scene)

    def test_edit_annotation(self, qapp):
        tool = TextAnnotationTool()
        tool.set_current_slice("st", "se", 0)
        scene = QGraphicsScene()
        tool.start_annotation(QPointF(0, 0))
        tool.current_item.setPlainText("text")
        item = tool.finish_annotation(scene)
        assert item is not None
        tool.edit_annotation(item)
        assert item._editing is True

    def test_delete_annotation(self, qapp):
        tool = TextAnnotationTool()
        tool.set_current_slice("st", "se", 0)
        scene = QGraphicsScene()
        tool.start_annotation(QPointF(0, 0))
        tool.current_item.setPlainText("del")
        item = tool.finish_annotation(scene)
        assert item is not None
        tool.delete_annotation(item, scene)
        assert tool.get_annotations_for_slice("st", "se", 0) == []

    def test_delete_annotation_not_in_scene(self, qapp):
        tool = TextAnnotationTool()
        tool.set_current_slice("st", "se", 0)
        scene = QGraphicsScene()
        tool.start_annotation(QPointF(0, 0))
        tool.current_item.setPlainText("del")
        item = tool.finish_annotation(scene)
        scene2 = QGraphicsScene()
        tool.delete_annotation(item, scene2)
        assert item.scene() is scene
        assert tool.get_annotations_for_slice("st", "se", 0) == []

    def test_get_annotations_for_unknown_slice(self, qapp):
        tool = TextAnnotationTool()
        assert tool.get_annotations_for_slice("x", "y", 0) == []

    def test_clear_annotations_from_other_slices(self, qapp):
        tool = TextAnnotationTool()
        tool.set_current_slice("st", "se", 0)
        scene = QGraphicsScene()
        tool.start_annotation(QPointF(0, 0))
        tool.current_item.setPlainText("a")
        tool.finish_annotation(scene)

        tool.set_current_slice("st", "se", 1)
        tool.start_annotation(QPointF(0, 0))
        tool.current_item.setPlainText("b")
        tool.finish_annotation(scene)

        tool.clear_annotations_from_other_slices("st", "se", 0, scene)
        items = [i for i in scene.items() if isinstance(i, TextAnnotationItem)]
        assert len(items) == 1
        assert items[0].toPlainText() == "a"

    def test_clear_annotations_from_other_slices_not_in_scene(self, qapp):
        tool = TextAnnotationTool()
        tool.set_current_slice("st", "se", 0)
        scene = QGraphicsScene()
        tool.start_annotation(QPointF(0, 0))
        tool.current_item.setPlainText("a")
        item = tool.finish_annotation(scene)
        # Remove from scene manually
        scene.removeItem(item)
        # Should not crash
        tool.clear_annotations_from_other_slices("st", "se", 1, scene)

    def test_display_annotations_for_slice(self, qapp):
        tool = TextAnnotationTool()
        tool.set_current_slice("st", "se", 0)
        scene = QGraphicsScene()
        tool.start_annotation(QPointF(0, 0))
        tool.current_item.setPlainText("show")
        item = tool.finish_annotation(scene)
        # Remove from scene
        scene.removeItem(item)
        assert item.scene() is None
        # Display should add it back
        tool.display_annotations_for_slice("st", "se", 0, scene)
        assert item.scene() is scene

    def test_display_annotations_already_in_scene(self, qapp):
        tool = TextAnnotationTool()
        tool.set_current_slice("st", "se", 0)
        scene = QGraphicsScene()
        tool.start_annotation(QPointF(0, 0))
        tool.current_item.setPlainText("show")
        item = tool.finish_annotation(scene)
        # Already in scene → should not crash
        tool.display_annotations_for_slice("st", "se", 0, scene)
        assert item.scene() is scene

    def test_clear_slice_annotations(self, qapp):
        tool = TextAnnotationTool()
        tool.set_current_slice("st", "se", 0)
        scene = QGraphicsScene()
        tool.start_annotation(QPointF(0, 0))
        tool.current_item.setPlainText("clear")
        tool.finish_annotation(scene)
        tool.clear_slice_annotations("st", "se", 0, scene)
        assert tool.get_annotations_for_slice("st", "se", 0) == []

    def test_clear_annotations(self, qapp):
        tool = TextAnnotationTool()
        tool.set_current_slice("st", "se", 0)
        scene = QGraphicsScene()
        tool.start_annotation(QPointF(0, 0))
        tool.current_item.setPlainText("a")
        tool.finish_annotation(scene)
        tool.start_annotation(QPointF(10, 10))
        tool.current_item.setPlainText("b")
        tool.finish_annotation(scene)
        tool.clear_annotations(scene)
        assert len(tool.annotations) == 0

    def test_update_all_annotation_styles(self, qapp):
        tool = TextAnnotationTool()
        tool.set_current_slice("st", "se", 0)
        scene = QGraphicsScene()
        tool.start_annotation(QPointF(0, 0))
        tool.current_item.setPlainText("styled")
        tool.finish_annotation(scene)
        cfg = MagicMock()
        cfg.get_text_annotation_font_size.return_value = 14
        cfg.get_text_annotation_color.return_value = (0, 128, 255)
        cfg.get_text_annotation_font_family.return_value = "IBM Plex Sans"
        cfg.get_text_annotation_font_variant.return_value = "Bold"
        tool.update_all_annotation_styles(cfg)

    def test_update_styles_none_config(self, qapp):
        tool = TextAnnotationTool()
        tool.update_all_annotation_styles(None)

    def test_update_styles_empty_annotations(self, qapp):
        tool = TextAnnotationTool()
        cfg = MagicMock()
        tool.update_all_annotation_styles(cfg)

    def test_finish_annotation_item_not_in_scene_adds(self, qapp):
        tool = TextAnnotationTool()
        tool.set_current_slice("st", "se", 0)
        scene = QGraphicsScene()
        tool.start_annotation(QPointF(0, 0))
        tool.current_item.setPlainText("add")
        # finish_annotation checks item.scene() != scene and adds
        item = tool.finish_annotation(scene)
        assert item is not None
        assert item.scene() is scene

    def test_finish_annotation_clears_flags(self, qapp):
        tool = TextAnnotationTool()
        tool.set_current_slice("st", "se", 0)
        scene = QGraphicsScene()
        tool.start_annotation(QPointF(0, 0))
        tool.current_item.setPlainText("flags")
        item = tool.finish_annotation(scene)
        assert item._is_new_annotation is False
        assert item.on_editing_finished is None
