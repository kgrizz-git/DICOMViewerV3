"""Paste offset policy: same-slice copy nudges; same-slice cut does not."""

from __future__ import annotations

from utils.annotation_clipboard import AnnotationClipboard

_SLICE_A = ("study-1", "series-1", 0)
_SLICE_B = ("study-1", "series-1", 1)


def _populate_clipboard(
    clipboard: AnnotationClipboard,
    *,
    operation: str,
    source_key: tuple[str, str, int],
) -> None:
    study_uid, series_uid, instance_id = source_key
    clipboard.copy_annotations(
        [],
        [],
        [],
        study_uid,
        series_uid,
        instance_id,
        operation=operation,  # type: ignore[arg-type]
    )


def test_same_slice_copy_offset_is_10px() -> None:
    clipboard = AnnotationClipboard()
    _populate_clipboard(clipboard, operation="copy", source_key=_SLICE_A)
    offset = clipboard.get_paste_offset(_SLICE_A)
    assert offset.x() == 10.0
    assert offset.y() == 10.0


def test_same_slice_cut_offset_is_zero() -> None:
    clipboard = AnnotationClipboard()
    _populate_clipboard(clipboard, operation="cut", source_key=_SLICE_A)
    offset = clipboard.get_paste_offset(_SLICE_A)
    assert offset.x() == 0.0
    assert offset.y() == 0.0


def test_different_slice_offset_is_zero_for_copy_and_cut() -> None:
    for operation in ("copy", "cut"):
        clipboard = AnnotationClipboard()
        _populate_clipboard(clipboard, operation=operation, source_key=_SLICE_A)
        offset = clipboard.get_paste_offset(_SLICE_B)
        assert offset.x() == 0.0
        assert offset.y() == 0.0


def test_paste_offset_zero_when_clipboard_empty() -> None:
    clipboard = AnnotationClipboard()
    offset = clipboard.get_paste_offset(_SLICE_A)
    assert offset.x() == 0.0
    assert offset.y() == 0.0
