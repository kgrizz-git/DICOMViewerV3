"""Additional bounded coverage for the DICOM tag viewer's Qt presentation layer."""

from __future__ import annotations

from types import SimpleNamespace

from pydicom.dataset import Dataset
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QMessageBox

from gui.dialogs.tag_viewer_dialog import TagViewerDialog

PATIENT_TAG = "(0010,0010)"
PRIVATE_TAG = "(0019,1001)"
SEQUENCE_TAG = "(0008,1111)"
ITEM_KEY = f"{SEQUENCE_TAG}[0]"
NESTED_TAG = f"{ITEM_KEY}.(0008,1155)"


def _tag(
    name: str,
    value: object,
    vr: str = "LO",
    *,
    depth: int = 0,
    parent_key: str | None = None,
    row_kind: str = "element",
) -> dict[str, object]:
    return {
        "name": name,
        "value": value,
        "VR": vr,
        "depth": depth,
        "parent_key": parent_key,
        "row_kind": row_kind,
    }


def _tags(*, private: bool = True, privacy: bool = False) -> dict[str, dict[str, object]]:
    return {
        "(0008,0016)": _tag("SOPClassUID", "1.2.3", "UI"),
        PATIENT_TAG: _tag("PatientName", "[REDACTED]" if privacy else "Synthetic^Patient", "PN"),
        "(0010,0020)": _tag("PatientID", "[REDACTED]" if privacy else "SYNTH-001", "LO"),
        **({PRIVATE_TAG: _tag("PrivateNote", "synthetic-private")} if private else {}),
        SEQUENCE_TAG: _tag("SourceImageSequence", "1 item(s)", "SQ", row_kind="sequence"),
        ITEM_KEY: _tag("Item 1", "", depth=1, parent_key=SEQUENCE_TAG, row_kind="item"),
        NESTED_TAG: _tag(
            "ReferencedSOPInstanceUID",
            "9.8.7",
            "UI",
            depth=2,
            parent_key=ITEM_KEY,
        ),
    }


class _RecordingParser:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []
        self._tag_cache: dict[str, object] = {}

    def get_all_tags(self, **kwargs: object) -> dict[str, dict[str, object]]:
        self.calls.append(kwargs)
        return _tags(
            private=bool(kwargs["include_private"]),
            privacy=bool(kwargs["privacy_mode"]),
        )


def _dialog_with_parser() -> tuple[TagViewerDialog, _RecordingParser]:
    dialog = TagViewerDialog()
    parser = _RecordingParser()
    dialog.parser = parser  # type: ignore[assignment]
    dialog.dataset = Dataset()
    return dialog, parser


def _item(dialog: TagViewerDialog, key: str):
    for candidate in dialog.all_tag_items:
        if candidate.data(0, Qt.ItemDataRole.UserRole) == key:
            return candidate
    return None


def test_population_groups_tree_rows_and_search_ancestors(qapp) -> None:
    dialog, parser = _dialog_with_parser()

    dialog._populate_tags()

    assert [parser.calls[0][name] for name in ("include_private", "privacy_mode", "include_sequences")] == [
        True,
        False,
        True,
    ]
    assert [dialog.tree_widget.topLevelItem(i).text(0) for i in range(dialog.tree_widget.topLevelItemCount())] == [
        "Group (0008",
        "Group (0010",
        "Group (0019",
    ]
    assert _item(dialog, NESTED_TAG) is not None
    assert dialog.tree_widget.topLevelItem(0).child(1).text(0) == SEQUENCE_TAG

    dialog._populate_tags()
    assert len(parser.calls) == 1

    dialog._populate_tags("9.8.7")
    assert _item(dialog, NESTED_TAG) is not None
    assert _item(dialog, SEQUENCE_TAG).isExpanded() is True
    assert _item(dialog, PATIENT_TAG) is None

    dialog._populate_tags("does-not-exist")
    assert dialog.tree_widget.topLevelItemCount() == 0


def test_private_and_privacy_controls_reload_and_present_masked_values(qapp) -> None:
    dialog, parser = _dialog_with_parser()
    dialog._populate_tags()

    dialog._on_private_tags_toggled(False)
    assert parser.calls[-1]["include_private"] is False
    assert _item(dialog, PRIVATE_TAG) is None

    dialog.set_privacy_mode(True)
    patient = _item(dialog, PATIENT_TAG)
    assert parser.calls[-1]["privacy_mode"] is True
    assert patient is not None
    assert patient.text(3) == "[REDACTED]"
    assert dialog._cached_privacy_mode is True

    dialog._on_show_sequences_toggled(False)
    assert dialog.show_sequences is False
    assert _item(dialog, SEQUENCE_TAG) is not None
    assert _item(dialog, NESTED_TAG) is None
    assert len(parser.calls) == 3


def test_filter_timer_and_clear_filter_preserve_requested_state(qapp) -> None:
    dialog, _parser = _dialog_with_parser()
    dialog._populate_tags()

    dialog._on_search_changed("patient")
    assert dialog._search_timer.isActive()
    dialog.search_edit.setText("patient")
    dialog.clear_filter()
    assert dialog.search_edit.text() == ""
    assert dialog._cached_search_text == ""
    assert dialog._search_timer.isActive()


def test_selection_copy_and_edit_guards_cover_visible_details(qapp, monkeypatch) -> None:
    dialog, _parser = _dialog_with_parser()
    dialog._populate_tags()
    patient = _item(dialog, PATIENT_TAG)
    group = dialog.tree_widget.topLevelItem(0)
    assert patient is not None
    assert group is not None

    dialog._copy_to_clipboard(patient, 1)
    assert QApplication.clipboard().text() == "PatientName"
    dialog._copy_all_to_clipboard(patient)
    assert QApplication.clipboard().text() == f"{PATIENT_TAG}\tPatientName\tPN\tSynthetic^Patient"

    dialog.tree_widget.setCurrentItem(patient, 3)
    dialog._copy_selected_to_clipboard()
    assert QApplication.clipboard().text() == "Synthetic^Patient"
    dialog.tree_widget.setCurrentItem(group)
    dialog._copy_selected_to_clipboard()
    assert QApplication.clipboard().text() == "Synthetic^Patient"

    messages: list[str] = []
    monkeypatch.setattr(
        QMessageBox,
        "information",
        lambda _parent, title, _text: messages.append(title),
    )
    dialog.tree_widget.setCurrentItem(group)
    dialog._edit_selected_tag()
    assert messages[-1] == "Invalid Selection"
    dialog.tree_widget.setCurrentItem(None)
    dialog._edit_selected_tag()
    assert messages[-1] == "No Selection"

    edited: list[object] = []
    monkeypatch.setattr(dialog, "_edit_tag_item", edited.append)
    dialog._on_item_double_clicked(patient, 2)
    assert edited == []
    dialog._on_item_double_clicked(patient, 3)
    assert edited == [patient]


def test_privacy_closes_visible_patient_editor_and_blocks_edit(qapp, monkeypatch) -> None:
    dialog, _parser = _dialog_with_parser()
    editor = SimpleNamespace(isVisible=lambda: True, rejected=False)
    editor.reject = lambda: setattr(editor, "rejected", True)
    dialog._active_tag_edit_dialog = editor  # type: ignore[assignment]
    dialog._active_tag_edit_tag = PATIENT_TAG

    assert dialog.close_active_tag_edit_dialog_due_to_privacy() is True
    assert editor.rejected is True
    assert dialog._active_tag_edit_dialog is None
    assert dialog.close_active_tag_edit_dialog_due_to_privacy() is False

    dialog.privacy_mode = True
    dialog._populate_tags()
    patient = _item(dialog, PATIENT_TAG)
    assert patient is not None
    monkeypatch.setattr(QMessageBox, "information", lambda *_args: None)
    dialog._edit_tag_item(patient)
    assert dialog._active_tag_edit_dialog is None


def test_undo_redo_callbacks_and_safe_empty_parser_paths(qapp) -> None:
    dialog = TagViewerDialog()
    dialog._populate_tags()
    assert dialog.tree_widget.topLevelItemCount() == 0

    dialog._cached_tags = None
    dialog.parser = SimpleNamespace(
        get_all_tags=lambda **_kwargs: None,
        _tag_cache={},
    )  # type: ignore[assignment]
    dialog._populate_tags()
    assert dialog.tree_widget.topLevelItemCount() == 0

    dialog, _parser = _dialog_with_parser()
    dialog._populate_tags()
    calls: list[str] = []
    dialog.set_undo_redo_callbacks(
        lambda: calls.append("undo"),
        lambda: calls.append("redo"),
        lambda: True,
        lambda: True,
    )
    dialog._on_undo_requested()
    dialog._on_redo_requested()
    dialog._undo_tag_edit()
    dialog._redo_tag_edit()
    assert calls == ["undo", "redo", "undo", "redo"]
