"""
Phase 4/5 (sequence tag viewer plan) — "Include sequences" checkbox in the tag
export dialog.

Default off, toggling refreshes the tag tree, and — when on — the tree offers
root-level tags (scalar elements and SQ parents, each independently checkable,
the parent still exporting a single summary cell) *and* (Phase 5) the nested
``Item N`` / leaf path-keyed rows underneath each sequence parent, so a user
can select an individual nested leaf as its own export column.
"""

from __future__ import annotations

from pydicom.dataset import Dataset
from pydicom.sequence import Sequence
from pydicom.tag import Tag
from PySide6.QtCore import Qt

from gui.dialogs import tag_export_dialog
from gui.dialogs.tag_export_dialog import TagExportDialog


def _all_tag_rows(dialog: TagExportDialog) -> dict[str, dict]:
    """tag_str -> tag_data for every row currently offered in the tags tree,
    read back from the merged union the tree was built from (not reconstructed
    via ``Tag(tag_str)``, which rejects the ``"(gggg, eeee)"`` display form)."""
    merged = (
        dialog._tag_union_merged_sequences
        if dialog.include_sequences_checkbox.isChecked()
        else dialog._tag_union_merged_full
    )
    return dict(merged or {})


def _dataset_with_deid_sequence() -> Dataset:
    ds = Dataset()
    ds.PatientName = "Test^Patient"
    item = Dataset()
    item.CodeValue = "113100"
    item.CodingSchemeDesignator = "DCM"
    item.CodeMeaning = "Basic Application Confidentiality Profile"
    ds.DeidentificationMethodCodeSequence = Sequence([item])
    return ds


def _all_tag_keys(dialog: TagExportDialog) -> set[str]:
    """Every tag key offered in the picker, at any depth (group -> SQ parent ->
    Item N -> leaf), post-Phase-5."""
    keys: set[str] = set()
    root = dialog.tags_tree.invisibleRootItem()
    for item in dialog._iter_all_tag_items(root):
        tag_str = item.data(0, Qt.ItemDataRole.UserRole)
        if tag_str is not None:
            keys.add(tag_str)
    return keys


def test_include_sequences_checkbox_defaults_off(qapp) -> None:
    dialog = TagExportDialog(studies={}, config_manager=None)
    assert dialog.include_sequences_checkbox.isChecked() is False
    dialog.deleteLater()


def test_sq_parent_always_offered_contents_only_when_toggled_on(qapp) -> None:
    """The checkbox gates a sequence's *contents*, not the sequence itself.

    The SQ parent is always selectable (exporting its summary cell); only the nested
    ``Item N`` / leaf columns come and go. It used to vanish entirely when the box was
    off, which is why a de-identified file offered no (0012,0064) column at all.
    """
    ds = _dataset_with_deid_sequence()
    studies = {"study1": {"series1": [ds]}}
    dialog = TagExportDialog(studies=studies, config_manager=None)

    deid_key = str(Tag("DeidentificationMethodCodeSequence"))
    item_key = f"{deid_key}[0]"
    leaf_key = f"{item_key}.{Tag('CodeMeaning')!s}"

    # Off by default: the SQ parent is offered, its contents are not.
    assert deid_key in _all_tag_keys(dialog)
    assert item_key not in _all_tag_keys(dialog)
    assert leaf_key not in _all_tag_keys(dialog)

    # Toggling on offers the nested Item N / leaf rows as independently selectable
    # export columns, without disturbing the parent.
    dialog.include_sequences_checkbox.setChecked(True)
    assert deid_key in _all_tag_keys(dialog)
    assert item_key in _all_tag_keys(dialog)
    assert leaf_key in _all_tag_keys(dialog)

    # Toggling back off withdraws only the contents.
    dialog.include_sequences_checkbox.setChecked(False)
    assert deid_key in _all_tag_keys(dialog)
    assert leaf_key not in _all_tag_keys(dialog)

    dialog.deleteLater()


def test_toggling_sequences_does_not_lose_private_filter_state(qapp) -> None:
    ds = _dataset_with_deid_sequence()
    ds.add_new((0x0009, 0x0010), "LO", "Private Creator")  # arbitrary private tag block
    studies = {"study1": {"series1": [ds]}}
    dialog = TagExportDialog(studies=studies, config_manager=None)

    dialog.private_tags_checkbox.setChecked(False)
    dialog.include_sequences_checkbox.setChecked(True)

    merged = _all_tag_rows(dialog)
    for tag_str in _all_tag_keys(dialog):
        assert merged[tag_str]["is_private"] is False

    dialog.deleteLater()


def test_sync_populate_caches_the_private_superset_and_filters_at_render(qapp) -> None:
    """The union caches hold the superset; private rows are dropped per-render.

    The sync path used to build its cache with the checkbox's *current* value, which
    would bake "no private tags" into the cache — and since ticking Include private only
    re-renders from that cache, the private rows could never come back. Unreachable as
    the dialog stands (the box is checked when this runs), so this pins the invariant
    rather than a live symptom.
    """
    ds = _dataset_with_deid_sequence()
    ds.add_new((0x0009, 0x0010), "LO", "Private Creator")
    studies = {"study1": {"series1": [ds]}}
    dialog = TagExportDialog(studies=studies, config_manager=None)
    private_key = str(Tag(0x0009, 0x0010))

    dialog.private_tags_checkbox.setChecked(False)
    dialog._tag_union_merged_full = None
    dialog._populate_tags_sync()

    assert private_key in (dialog._tag_union_merged_full or {})  # cached anyway...
    assert private_key not in _all_tag_keys(dialog)  # ...just not shown

    dialog.private_tags_checkbox.setChecked(True)
    assert private_key in _all_tag_keys(dialog)

    dialog.deleteLater()


def test_loading_a_preset_keeps_the_nested_rows_when_sequences_are_on(qapp, monkeypatch) -> None:
    """A preset adds its missing tags to whichever union is on screen.

    Merging only into the flat union and re-rendering from it collapsed the tree back to
    root-level rows while Include sequences was still ticked, so the preset's own nested
    leaf keys had nothing to match against.
    """

    # Absent from the dataset *and* from the standard-tag supplement, so loading the
    # preset genuinely has to add a row — and therefore re-render the tree.
    preset_key = str(Tag("ContrastBolusAgent"))

    class _Config:
        def get_tag_export_presets(self) -> dict[str, list[str]]:
            return {"p": [preset_key]}

    # _load_preset ends with a modal "Preset loaded" box; left alone it blocks the run.
    monkeypatch.setattr(tag_export_dialog.QMessageBox, "information", lambda *a, **k: None)

    ds = _dataset_with_deid_sequence()
    studies = {"study1": {"series1": [ds]}}
    dialog = TagExportDialog(studies=studies, config_manager=_Config())
    dialog.include_sequences_checkbox.setChecked(True)

    leaf_key = f"{Tag('DeidentificationMethodCodeSequence')!s}[0].{Tag('CodeMeaning')!s}"
    assert preset_key not in _all_tag_keys(dialog)
    assert leaf_key in _all_tag_keys(dialog)

    dialog.preset_combo.setCurrentText("p")
    dialog._load_preset()

    keys = _all_tag_keys(dialog)
    assert preset_key in keys  # the preset's missing tag was added...
    assert leaf_key in keys  # ...without collapsing the sequence contents

    dialog.deleteLater()
