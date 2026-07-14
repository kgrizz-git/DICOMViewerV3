"""
Unit tests for core.tag_edit_history (EditTagCommand + TagEditHistoryManager).
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from pydicom.dataset import Dataset
from pydicom.tag import Tag

from core.tag_edit_history import EditTagCommand, TagEditHistoryManager


class _FrameWrapper(Dataset):
    """Mimics a multi-frame wrapper that delegates edits to _original_dataset."""

    def __init__(self, original: Dataset):
        super().__init__()
        self._original_dataset = original


def _ds_with_patient_name(value="Doe^John") -> Dataset:
    ds = Dataset()
    ds.PatientName = value
    return ds


class TestParseTag:
    def test_accepts_tag_object_directly(self):
        ds = _ds_with_patient_name()
        cmd = EditTagCommand(ds, Tag(0x0010, 0x0010), "Doe^John", "Smith^Jane")
        assert cmd.tag == Tag(0x0010, 0x0010)

    def test_accepts_tuple(self):
        ds = _ds_with_patient_name()
        cmd = EditTagCommand(ds, (0x0010, 0x0010), "Doe^John", "Smith^Jane")
        assert cmd.tag == Tag(0x0010, 0x0010)

    def test_accepts_string_with_parens(self):
        ds = _ds_with_patient_name()
        cmd = EditTagCommand(ds, "(0010,0010)", "Doe^John", "Smith^Jane")
        assert cmd.tag == Tag(0x0010, 0x0010)

    def test_accepts_string_without_parens(self):
        ds = _ds_with_patient_name()
        cmd = EditTagCommand(ds, "0010,0010", "Doe^John", "Smith^Jane")
        assert cmd.tag == Tag(0x0010, 0x0010)

    def test_invalid_string_format_raises(self):
        ds = _ds_with_patient_name()
        with pytest.raises(ValueError):
            EditTagCommand(ds, "not-a-tag", "a", "b")

    def test_invalid_hex_in_string_raises(self):
        ds = _ds_with_patient_name()
        with pytest.raises(ValueError):
            EditTagCommand(ds, "(zzzz,0010)", "a", "b")

    def test_invalid_identifier_type_raises(self):
        ds = _ds_with_patient_name()
        with pytest.raises(ValueError):
            EditTagCommand(ds, 12345, "a", "b")


class TestGetTargetDataset:
    def test_plain_dataset_returns_itself(self):
        ds = _ds_with_patient_name()
        cmd = EditTagCommand(ds, (0x0010, 0x0010), "Doe^John", "Smith^Jane")
        assert cmd.get_target_dataset() is ds

    def test_wrapper_returns_original_dataset(self):
        original = _ds_with_patient_name()
        wrapper = _FrameWrapper(original)
        cmd = EditTagCommand(wrapper, (0x0010, 0x0010), "Doe^John", "Smith^Jane")
        assert cmd.get_target_dataset() is original


class TestExecuteAndUndo:
    def test_execute_updates_existing_tag(self):
        ds = _ds_with_patient_name("Doe^John")
        cmd = EditTagCommand(ds, (0x0010, 0x0010), "Doe^John", "Smith^Jane")
        cmd.execute()
        assert ds.PatientName == "Smith^Jane"

    def test_undo_restores_old_value(self):
        ds = _ds_with_patient_name("Doe^John")
        cmd = EditTagCommand(ds, (0x0010, 0x0010), "Doe^John", "Smith^Jane")
        cmd.execute()
        cmd.undo()
        assert ds.PatientName == "Doe^John"

    def test_execute_creates_new_tag_when_absent(self):
        ds = Dataset()
        cmd = EditTagCommand(ds, (0x0010, 0x0010), None, "Smith^Jane")
        cmd.execute()
        assert ds.PatientName == "Smith^Jane"

    def test_undo_deletes_tag_created_by_execute(self):
        ds = Dataset()
        cmd = EditTagCommand(ds, (0x0010, 0x0010), None, "Smith^Jane")
        cmd.execute()
        cmd.undo()
        assert Tag(0x0010, 0x0010) not in ds

    def test_execute_uses_explicit_vr_for_new_private_tag(self):
        ds = Dataset()
        cmd = EditTagCommand(ds, (0x0009, 0x0001), None, "custom", vr="LO")
        cmd.execute()
        assert ds[0x0009, 0x0001].VR == "LO"
        assert ds[0x0009, 0x0001].value == "custom"

    def test_execute_and_undo_are_noop_when_tag_is_none(self):
        ds = _ds_with_patient_name()
        cmd = EditTagCommand(ds, (0x0010, 0x0010), "Doe^John", "Smith^Jane")
        cmd.tag = None
        cmd.execute()
        cmd.undo()
        assert ds.PatientName == "Doe^John"

    def test_execute_and_undo_propagate_to_wrapper(self):
        original = _ds_with_patient_name("Doe^John")
        wrapper = _FrameWrapper(original)
        wrapper.PatientName = "Doe^John"
        cmd = EditTagCommand(wrapper, (0x0010, 0x0010), "Doe^John", "Smith^Jane")
        cmd.execute()
        assert original.PatientName == "Smith^Jane"
        assert wrapper.PatientName == "Smith^Jane"
        cmd.undo()
        assert original.PatientName == "Doe^John"
        assert wrapper.PatientName == "Doe^John"

    def test_execute_creates_tag_on_wrapper_with_explicit_vr(self):
        original = Dataset()
        wrapper = _FrameWrapper(original)
        cmd = EditTagCommand(wrapper, (0x0010, 0x0010), None, "Smith^Jane", vr="PN")
        cmd.execute()
        assert wrapper[0x0010, 0x0010].VR == "PN"
        assert original[0x0010, 0x0010].VR == "PN"

    def test_execute_creates_tag_on_wrapper_when_absent(self):
        original = Dataset()
        wrapper = _FrameWrapper(original)
        cmd = EditTagCommand(wrapper, (0x0010, 0x0010), None, "Smith^Jane")
        cmd.execute()
        assert original.PatientName == "Smith^Jane"
        assert wrapper.PatientName == "Smith^Jane"

    def test_undo_deletes_wrapper_tag_created_by_execute(self):
        original = Dataset()
        wrapper = _FrameWrapper(original)
        cmd = EditTagCommand(wrapper, (0x0010, 0x0010), None, "Smith^Jane")
        cmd.execute()
        cmd.undo()
        assert Tag(0x0010, 0x0010) not in original
        assert Tag(0x0010, 0x0010) not in wrapper

    def test_execute_falls_back_to_lo_vr_for_unknown_tag_on_wrapper(self):
        original = Dataset()
        wrapper = _FrameWrapper(original)
        cmd = EditTagCommand(wrapper, (0x0009, 0x0001), None, "custom")
        cmd.execute()
        assert original[0x0009, 0x0001].VR == "LO"
        assert wrapper[0x0009, 0x0001].VR == "LO"
        assert wrapper[0x0009, 0x0001].value == "custom"

    def test_undo_recreates_tag_with_old_value_when_absent_from_target(self):
        ds = Dataset()
        cmd = EditTagCommand(ds, (0x0009, 0x0001), "previous_custom", "new_custom")
        cmd.undo()
        assert ds[0x0009, 0x0001].VR == "LO"
        assert ds[0x0009, 0x0001].value == "previous_custom"

    def test_undo_recreates_tag_with_old_value_on_wrapper_when_absent(self):
        original = Dataset()
        wrapper = _FrameWrapper(original)
        cmd = EditTagCommand(wrapper, (0x0009, 0x0001), "previous_custom", "new_custom")
        cmd.undo()
        assert original[0x0009, 0x0001].value == "previous_custom"
        assert wrapper[0x0009, 0x0001].value == "previous_custom"
        assert wrapper[0x0009, 0x0001].VR == "LO"

    def test_undo_recreate_uses_explicit_vr_on_target(self):
        ds = Dataset()
        cmd = EditTagCommand(ds, (0x0010, 0x0010), "Doe^John", "Smith^Jane", vr="PN")
        cmd.undo()
        assert ds[0x0010, 0x0010].VR == "PN"
        assert ds[0x0010, 0x0010].value == "Doe^John"

    def test_undo_recreate_uses_explicit_vr_on_wrapper(self):
        original = Dataset()
        wrapper = _FrameWrapper(original)
        cmd = EditTagCommand(wrapper, (0x0010, 0x0010), "Doe^John", "Smith^Jane", vr="PN")
        cmd.undo()
        assert wrapper[0x0010, 0x0010].VR == "PN"
        assert wrapper[0x0010, 0x0010].value == "Doe^John"

    def test_undo_delete_noop_when_tag_missing_from_target(self):
        ds = Dataset()
        cmd = EditTagCommand(ds, (0x0010, 0x0010), None, "Smith^Jane")
        cmd.undo()
        assert Tag(0x0010, 0x0010) not in ds

    def test_undo_delete_noop_on_wrapper_when_tag_missing_there(self):
        original = _ds_with_patient_name("Doe^John")
        wrapper = _FrameWrapper(original)
        cmd = EditTagCommand(wrapper, (0x0010, 0x0010), None, "Smith^Jane")
        cmd.execute()
        del wrapper[Tag(0x0010, 0x0010)]
        cmd.undo()
        assert Tag(0x0010, 0x0010) not in original

    def test_execute_reraises_and_logs_on_unexpected_error(self):
        bad_dataset = MagicMock(spec=Dataset)
        bad_dataset.__contains__.return_value = False
        bad_dataset.add.side_effect = RuntimeError("boom")
        cmd = EditTagCommand(bad_dataset, (0x0010, 0x0010), None, "value", vr="LO")
        with pytest.raises(RuntimeError):
            cmd.execute()

    def test_undo_reraises_and_logs_on_unexpected_error(self):
        bad_dataset = MagicMock(spec=Dataset)
        bad_dataset.__contains__.return_value = False
        bad_dataset.add.side_effect = RuntimeError("boom")
        cmd = EditTagCommand(bad_dataset, (0x0010, 0x0010), "old_value", "new_value", vr="LO")
        with pytest.raises(RuntimeError):
            cmd.undo()


class TestTagEditHistoryManagerBasics:
    def test_execute_command_adds_to_undo_stack_and_marks_edited(self):
        manager = TagEditHistoryManager()
        ds = _ds_with_patient_name("Doe^John")
        cmd = EditTagCommand(ds, (0x0010, 0x0010), "Doe^John", "Smith^Jane")
        manager.execute_command(cmd)
        assert ds.PatientName == "Smith^Jane"
        assert manager.can_undo(ds)
        assert not manager.can_redo(ds)
        assert manager.is_tag_edited(ds, "(0010,0010)")

    def test_execute_command_clears_redo_stack(self):
        manager = TagEditHistoryManager()
        ds = _ds_with_patient_name("Doe^John")
        cmd1 = EditTagCommand(ds, (0x0010, 0x0010), "Doe^John", "Smith^Jane")
        manager.execute_command(cmd1)
        manager.undo(ds)
        assert manager.can_redo(ds)
        cmd2 = EditTagCommand(ds, (0x0010, 0x0010), "Smith^Jane", "Other^Name")
        manager.execute_command(cmd2)
        assert not manager.can_redo(ds)

    def test_undo_and_redo_round_trip(self):
        manager = TagEditHistoryManager()
        ds = _ds_with_patient_name("Doe^John")
        cmd = EditTagCommand(ds, (0x0010, 0x0010), "Doe^John", "Smith^Jane")
        manager.execute_command(cmd)
        assert manager.undo(ds) is True
        assert ds.PatientName == "Doe^John"
        assert manager.redo(ds) is True
        assert ds.PatientName == "Smith^Jane"

    def test_undo_returns_false_when_no_history(self):
        manager = TagEditHistoryManager()
        ds = _ds_with_patient_name()
        assert manager.undo(ds) is False

    def test_redo_returns_false_when_no_history(self):
        manager = TagEditHistoryManager()
        ds = _ds_with_patient_name()
        assert manager.redo(ds) is False

    def test_history_size_limited_to_max_history(self):
        manager = TagEditHistoryManager(max_history=2)
        ds = Dataset()
        ds.PatientName = "v0"
        for i in range(5):
            cmd = EditTagCommand(ds, (0x0010, 0x0010), f"v{i}", f"v{i + 1}")
            manager.execute_command(cmd)
        history = manager._get_history(ds)
        assert len(history["undo"]) == 2


class TestGetTagString:
    def test_falls_back_to_string_identifier_when_tag_none(self):
        manager = TagEditHistoryManager()
        ds = _ds_with_patient_name()
        cmd = EditTagCommand(ds, "(0010,0010)", "a", "b")
        cmd.tag = None
        assert manager._get_tag_string(cmd) == "(0010,0010)"

    def test_falls_back_to_tuple_identifier_when_tag_none(self):
        manager = TagEditHistoryManager()
        ds = _ds_with_patient_name()
        cmd = EditTagCommand(ds, (0x0010, 0x0010), "a", "b")
        cmd.tag = None
        assert manager._get_tag_string(cmd) == "(0010,0010)"

    def test_returns_none_when_no_match(self):
        manager = TagEditHistoryManager()
        ds = _ds_with_patient_name()
        cmd = EditTagCommand(ds, (0x0010, 0x0010), "a", "b")
        cmd.tag = None
        cmd.tag_identifier = 12345
        assert manager._get_tag_string(cmd) is None

    def test_returns_none_for_non_command_object(self):
        manager = TagEditHistoryManager()
        assert manager._get_tag_string(object()) is None


class TestEditedTagTracking:
    def test_mark_tag_edited_and_is_tag_edited(self):
        manager = TagEditHistoryManager()
        ds = _ds_with_patient_name()
        manager.mark_tag_edited(ds, "(0010,0010)")
        assert manager.is_tag_edited(ds, "(0010,0010)")
        assert not manager.is_tag_edited(ds, "(0010,0020)")

    def test_store_and_get_original_value_preserves_first(self):
        manager = TagEditHistoryManager()
        ds = _ds_with_patient_name()
        manager.store_original_value(ds, "(0010,0010)", "Doe^John")
        manager.store_original_value(ds, "(0010,0010)", "Smith^Jane")
        assert manager.get_original_value(ds, "(0010,0010)") == "Doe^John"

    def test_get_original_value_returns_none_when_unset(self):
        manager = TagEditHistoryManager()
        ds = _ds_with_patient_name()
        assert manager.get_original_value(ds, "(0010,0010)") is None

    def test_mark_tag_edited_removes_when_back_to_original(self):
        manager = TagEditHistoryManager()
        ds = _ds_with_patient_name()
        manager.store_original_value(ds, "(0010,0010)", "Doe^John")
        manager.mark_tag_edited(ds, "(0010,0010)", current_value="Smith^Jane")
        assert manager.is_tag_edited(ds, "(0010,0010)")
        manager.mark_tag_edited(ds, "(0010,0010)", current_value="Doe^John")
        assert not manager.is_tag_edited(ds, "(0010,0010)")

    def test_mark_tag_edited_noop_when_value_matches_original_and_not_yet_tracked(self):
        manager = TagEditHistoryManager()
        ds = _ds_with_patient_name()
        manager.store_original_value(ds, "(0010,0010)", "Doe^John")
        manager.mark_tag_edited(ds, "(0010,0010)", current_value="Doe^John")
        assert not manager.is_tag_edited(ds, "(0010,0010)")

    def test_clear_edited_tags_for_single_dataset(self):
        manager = TagEditHistoryManager()
        ds1 = _ds_with_patient_name()
        ds2 = _ds_with_patient_name()
        manager.mark_tag_edited(ds1, "(0010,0010)")
        manager.mark_tag_edited(ds2, "(0010,0010)")
        manager.clear_edited_tags(ds1)
        assert not manager.is_tag_edited(ds1, "(0010,0010)")
        assert manager.is_tag_edited(ds2, "(0010,0010)")

    def test_clear_edited_tags_also_clears_original_values(self):
        manager = TagEditHistoryManager()
        ds = _ds_with_patient_name()
        manager.store_original_value(ds, "(0010,0010)", "Doe^John")
        manager.mark_tag_edited(ds, "(0010,0010)")
        manager.clear_edited_tags(ds)
        assert manager.get_original_value(ds, "(0010,0010)") is None
        assert not manager.is_tag_edited(ds, "(0010,0010)")

    def test_clear_edited_tags_noop_when_dataset_never_tracked(self):
        manager = TagEditHistoryManager()
        ds = _ds_with_patient_name()
        manager.clear_edited_tags(ds)
        assert not manager.is_tag_edited(ds, "(0010,0010)")

    def test_update_edited_tags_noop_when_dataset_never_tracked(self):
        manager = TagEditHistoryManager()
        ds = _ds_with_patient_name()
        manager._update_edited_tags(ds, "(0010,0010)")
        assert id(ds) not in manager.edited_tags

    def test_update_edited_tags_loop_continues_past_non_matching_commands(self):
        manager = TagEditHistoryManager()
        ds = Dataset()
        ds.PatientName = "Doe^John"
        ds.PatientID = "123"
        cmd_other = EditTagCommand(ds, (0x0010, 0x0020), "123", "456")
        cmd_target1 = EditTagCommand(ds, (0x0010, 0x0010), "Doe^John", "Smith^Jane")
        cmd_target2 = EditTagCommand(ds, (0x0010, 0x0010), "Smith^Jane", "Other^Name")
        manager.execute_command(cmd_other)
        manager.execute_command(cmd_target1)
        manager.execute_command(cmd_target2)
        manager.undo(ds)
        assert manager.is_tag_edited(ds, "(0010,0010)")

    def test_clear_edited_tags_for_all_datasets(self):
        manager = TagEditHistoryManager()
        ds1 = _ds_with_patient_name()
        ds2 = _ds_with_patient_name()
        manager.mark_tag_edited(ds1, "(0010,0010)")
        manager.mark_tag_edited(ds2, "(0010,0010)")
        manager.clear_edited_tags(None)
        assert not manager.is_tag_edited(ds1, "(0010,0010)")
        assert not manager.is_tag_edited(ds2, "(0010,0010)")

    def test_undo_removes_edited_flag_when_no_other_commands_affect_tag(self):
        manager = TagEditHistoryManager()
        ds = _ds_with_patient_name("Doe^John")
        cmd = EditTagCommand(ds, (0x0010, 0x0010), "Doe^John", "Smith^Jane")
        manager.execute_command(cmd)
        assert manager.is_tag_edited(ds, "(0010,0010)")
        manager.undo(ds)
        assert not manager.is_tag_edited(ds, "(0010,0010)")

    def test_redo_marks_tag_edited_again(self):
        manager = TagEditHistoryManager()
        ds = _ds_with_patient_name("Doe^John")
        cmd = EditTagCommand(ds, (0x0010, 0x0010), "Doe^John", "Smith^Jane")
        manager.execute_command(cmd)
        manager.undo(ds)
        manager.redo(ds)
        assert manager.is_tag_edited(ds, "(0010,0010)")

    def test_undo_keeps_tag_edited_when_another_command_for_same_tag_remains(self):
        manager = TagEditHistoryManager()
        ds = _ds_with_patient_name("Doe^John")
        cmd1 = EditTagCommand(ds, (0x0010, 0x0010), "Doe^John", "Smith^Jane")
        cmd2 = EditTagCommand(ds, (0x0010, 0x0010), "Smith^Jane", "Other^Name")
        manager.execute_command(cmd1)
        manager.execute_command(cmd2)
        manager.undo(ds)
        assert manager.is_tag_edited(ds, "(0010,0010)")

    def test_execute_command_skips_marking_edited_when_tag_string_unavailable(self):
        manager = TagEditHistoryManager()
        ds = _ds_with_patient_name()
        cmd = EditTagCommand(ds, (0x0010, 0x0010), "a", "b")
        cmd.tag = None
        cmd.tag_identifier = 12345
        manager.execute_command(cmd)
        history = manager._get_history(ds)
        assert history["undo"] == [cmd]
        assert manager.edited_tags.get(id(ds), set()) == set()

    def test_undo_skips_updating_edited_tags_when_tag_string_unavailable(self):
        manager = TagEditHistoryManager()
        ds = _ds_with_patient_name("Doe^John")
        cmd = EditTagCommand(ds, (0x0010, 0x0010), "Doe^John", "Smith^Jane")
        manager.execute_command(cmd)
        cmd.tag = None
        cmd.tag_identifier = 12345
        assert manager.undo(ds) is True

    def test_redo_skips_marking_edited_when_tag_string_unavailable(self):
        manager = TagEditHistoryManager()
        ds = _ds_with_patient_name("Doe^John")
        cmd = EditTagCommand(ds, (0x0010, 0x0010), "Doe^John", "Smith^Jane")
        manager.execute_command(cmd)
        manager.undo(ds)
        cmd.tag = None
        cmd.tag_identifier = 12345
        assert manager.redo(ds) is True


class TestClearHistory:
    def test_clear_history_for_single_dataset(self):
        manager = TagEditHistoryManager()
        ds1 = _ds_with_patient_name("Doe^John")
        ds2 = _ds_with_patient_name("Doe^John")
        cmd1 = EditTagCommand(ds1, (0x0010, 0x0010), "Doe^John", "Smith^Jane")
        cmd2 = EditTagCommand(ds2, (0x0010, 0x0010), "Doe^John", "Smith^Jane")
        manager.execute_command(cmd1)
        manager.execute_command(cmd2)
        manager.clear_history(ds1)
        assert not manager.can_undo(ds1)
        assert manager.can_undo(ds2)

    def test_clear_history_for_all_datasets(self):
        manager = TagEditHistoryManager()
        ds1 = _ds_with_patient_name("Doe^John")
        ds2 = _ds_with_patient_name("Doe^John")
        cmd1 = EditTagCommand(ds1, (0x0010, 0x0010), "Doe^John", "Smith^Jane")
        cmd2 = EditTagCommand(ds2, (0x0010, 0x0010), "Doe^John", "Smith^Jane")
        manager.execute_command(cmd1)
        manager.execute_command(cmd2)
        manager.clear_history(None)
        assert not manager.can_undo(ds1)
        assert not manager.can_undo(ds2)

    def test_clear_history_noop_when_dataset_never_tracked(self):
        manager = TagEditHistoryManager()
        ds = _ds_with_patient_name()
        manager.clear_history(ds)
        assert not manager.can_undo(ds)
