"""
Tests for the left-pane metadata panel: group collapse memory, nested sequence
rendering, and read-only gating for nested rows.
"""

from __future__ import annotations

import time

import pydicom
from pydicom.dataset import Dataset
from pydicom.sequence import Sequence
from PySide6.QtCore import QEvent, QRect, Qt
from PySide6.QtGui import QColor, QPainter, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QTreeWidgetItem,
)

from core.tag_edit_history import TagEditHistoryManager
from gui.metadata_panel import MetadataPanel
from gui.metadata_table_model import group_header_rule_color


def _dataset_with_nested_code_sequence() -> Dataset:
    """PatientName at root, plus a Code Meaning that exists ONLY inside a sequence."""
    ds = Dataset()
    ds.PatientName = "Test^Patient"
    ds.PatientID = "12345"
    ds.Rows = 512
    item = Dataset()
    item.CodeValue = "113100"
    item.CodingSchemeDesignator = "DCM"
    item.CodeMeaning = "Basic Application Confidentiality Profile"
    ds.DeidentificationMethodCodeSequence = Sequence([item])
    return ds


def _other_dataset() -> Dataset:
    ds = Dataset()
    ds.PatientName = "Other^Patient"
    ds.PatientID = "99999"
    ds.Rows = 256
    return ds


def _group_items(panel: MetadataPanel) -> list[QTreeWidgetItem]:
    root = panel.tree_widget.invisibleRootItem()
    return [root.child(i) for i in range(root.childCount())]


def _group_item_labelled(panel: MetadataPanel, group_key: str) -> QTreeWidgetItem | None:
    for item in _group_items(panel):
        if item.data(0, Qt.ItemDataRole.UserRole + 2) == group_key:
            return item
    return None


def _find_item_by_tag_str(item: QTreeWidgetItem, tag_str: str) -> QTreeWidgetItem | None:
    for i in range(item.childCount()):
        child = item.child(i)
        if child.data(0, Qt.ItemDataRole.UserRole) == tag_str:
            return child
        found = _find_item_by_tag_str(child, tag_str)
        if found is not None:
            return found
    return None


def _find_in_tree(panel: MetadataPanel, tag_str: str) -> QTreeWidgetItem | None:
    for group_item in _group_items(panel):
        found = _find_item_by_tag_str(group_item, tag_str)
        if found is not None:
            return found
    return None


def test_groups_start_collapsed_on_fresh_panel(qapp) -> None:
    """A fresh panel starts all-collapsed — expansion is never restored from disk."""
    panel = MetadataPanel()
    panel.set_dataset(_dataset_with_nested_code_sequence())

    groups = _group_items(panel)
    assert groups, "expected at least one group header"
    assert all(not group.isExpanded() for group in groups)


def test_group_expansion_survives_a_series_switch(qapp) -> None:
    """Session memory: collapse/expand state is remembered across set_dataset."""
    panel = MetadataPanel()
    panel.set_dataset(_dataset_with_nested_code_sequence())

    patient_group = _group_item_labelled(panel, "(0010")
    assert patient_group is not None
    assert not patient_group.isExpanded()

    # A real user expansion emits itemExpanded, which records session state.
    patient_group.setExpanded(True)
    assert panel._group_expanded.get("(0010") is True

    # Switching series/images rebuilds the tree; the group must stay expanded.
    panel.set_dataset(_other_dataset())

    patient_group_after = _group_item_labelled(panel, "(0010")
    assert patient_group_after is not None
    assert patient_group_after.isExpanded(), "group expansion should survive a series switch"

    # ...while a group the user never touched stays collapsed.
    image_group_after = _group_item_labelled(panel, "(0028")
    assert image_group_after is not None
    assert not image_group_after.isExpanded()


class _FakeConfig:
    """Stands in for ConfigManager; `store` survives a panel, like the config file does."""

    def __init__(self, store: dict | None = None) -> None:
        self.store: dict = store if store is not None else {}
        self.writes = 0

    def get_metadata_panel_group_expanded(self) -> dict[str, bool]:
        return dict(self.store)

    def set_metadata_panel_group_expanded(self, expanded: dict[str, bool]) -> None:
        self.store = dict(expanded)
        self.writes += 1

    def get_metadata_panel_column_widths(self) -> list[int]:
        return [100, 200, 50, 200]

    def get_metadata_panel_column_order(self) -> list[int]:
        return [0, 1, 2, 3]

    def set_metadata_panel_column_widths(self, widths: list[int]) -> None: ...
    def set_metadata_panel_column_order(self, order: list[int]) -> None: ...


def test_expansion_without_a_config_manager_is_session_only(qapp) -> None:
    """No config manager (e.g. a bare panel in a test) means nothing to restore from."""
    panel = MetadataPanel()
    panel.set_dataset(_dataset_with_nested_code_sequence())
    group = _group_item_labelled(panel, "(0010")
    assert group is not None
    group.setExpanded(True)

    fresh_panel = MetadataPanel()
    fresh_panel.set_dataset(_dataset_with_nested_code_sequence())

    assert fresh_panel._group_expanded == {}
    assert all(not g.isExpanded() for g in _group_items(fresh_panel))


def test_group_expansion_is_restored_on_the_next_launch(qapp) -> None:
    """Expanding a group must survive a restart, not just a series switch."""
    config = _FakeConfig()

    panel = MetadataPanel(config_manager=config)
    panel.set_dataset(_dataset_with_nested_code_sequence())
    group = _group_item_labelled(panel, "(0010")
    assert group is not None
    assert not group.isExpanded()
    group.setExpanded(True)

    assert config.store == {"(0010": True}

    # A new panel built from the same config = the next app launch.
    relaunched = MetadataPanel(config_manager=config)
    relaunched.set_dataset(_dataset_with_nested_code_sequence())

    restored = _group_item_labelled(relaunched, "(0010")
    assert restored is not None
    assert restored.isExpanded(), "an expanded group must come back expanded"
    # A group never touched stays collapsed.
    untouched = _group_item_labelled(relaunched, "(0028")
    assert untouched is not None
    assert not untouched.isExpanded()


def test_sequences_always_reopen_collapsed_even_inside_a_restored_group(qapp) -> None:
    """Groups persist; sequences never do.

    A sequence can hold tens of thousands of rows (per-frame functional groups), so
    restoring one expanded would make opening a study feel broken. Only the group comes
    back open — the sequence inside it is collapsed again.
    """
    config = _FakeConfig()
    seq_key = str(pydicom.tag.Tag("DeidentificationMethodCodeSequence"))

    panel = MetadataPanel(config_manager=config)
    panel.set_dataset(_dataset_with_nested_code_sequence())
    group = _group_item_labelled(panel, "(0012")
    assert group is not None
    group.setExpanded(True)
    seq_item = _find_in_tree(panel, seq_key)
    assert seq_item is not None
    seq_item.setExpanded(True)

    # The sequence's expansion is not written anywhere.
    assert config.store == {"(0012": True}

    relaunched = MetadataPanel(config_manager=config)
    relaunched.set_dataset(_dataset_with_nested_code_sequence())

    restored_group = _group_item_labelled(relaunched, "(0012")
    assert restored_group is not None
    assert restored_group.isExpanded()

    restored_seq = _find_in_tree(relaunched, seq_key)
    assert restored_seq is not None
    assert not restored_seq.isExpanded(), "a sequence must always reopen collapsed"


def test_expand_all_persists_every_group_in_one_write(qapp) -> None:
    """Expand All emits a signal per row; persisting on each would rewrite the config
    file once per group for a single click."""
    config = _FakeConfig()
    panel = MetadataPanel(config_manager=config)
    panel.set_dataset(_dataset_with_nested_code_sequence())

    config.writes = 0
    panel._on_expand_all_clicked()

    assert config.writes == 1, "Expand All must write config exactly once"
    groups = {g.data(0, Qt.ItemDataRole.UserRole + 2) for g in _group_items(panel)}
    assert config.store == dict.fromkeys(groups, True)

    panel._on_collapse_all_clicked()
    assert config.writes == 2
    assert config.store == dict.fromkeys(groups, False)


def test_group_header_shows_depth_zero_count_only(qapp) -> None:
    """The per-group count must not include nested sequence rows."""
    panel = MetadataPanel()
    panel.set_dataset(_dataset_with_nested_code_sequence())

    # Group 0012 holds exactly one depth-0 row (the SQ parent itself); its three
    # nested children (CodeValue/CodingSchemeDesignator/CodeMeaning) live under it
    # and must not be counted, nor bucketed into their own group 0008.
    deid_group = _group_item_labelled(panel, "(0012")
    assert deid_group is not None
    assert deid_group.text(0) == "Group 0012 — 1 tags"


def test_nested_sequence_rows_hang_under_their_sequence_parent(qapp) -> None:
    """Mode B tree shape: SQ parent -> Item N -> leaves, not flattened into a group."""
    panel = MetadataPanel()
    panel.set_dataset(_dataset_with_nested_code_sequence())

    seq_key = str(pydicom.tag.Tag("DeidentificationMethodCodeSequence"))
    code_meaning_key = f"{seq_key}[0].{pydicom.tag.Tag('CodeMeaning')!s}"

    seq_item = _find_in_tree(panel, seq_key)
    assert seq_item is not None

    nested = _find_in_tree(panel, code_meaning_key)
    assert nested is not None, "nested Code Meaning should be present in Mode B"

    # Its ancestor chain is Item node -> sequence parent (not a group header).
    item_node = nested.parent()
    assert item_node.data(0, Qt.ItemDataRole.UserRole) == f"{seq_key}[0]"
    assert item_node.parent() is seq_item


def test_filter_leaves_no_empty_groups(qapp) -> None:
    """Groups with no match (and no matching descendant) drop out entirely."""
    panel = MetadataPanel()
    panel.set_dataset(_dataset_with_nested_code_sequence())

    panel._populate_tags("Test^Patient")

    groups = _group_items(panel)
    assert groups, "the matching group should survive"
    for group in groups:
        assert group.childCount() > 0, f"{group.text(0)} is empty and should be hidden"
    # The unrelated image group has nothing matching and must be gone.
    assert _group_item_labelled(panel, "(0028") is None


def test_filter_reaches_nested_values_and_expands_ancestors(qapp) -> None:
    """A match inside a sequence stays reachable: ancestors survive and open."""
    panel = MetadataPanel()
    panel.set_dataset(_dataset_with_nested_code_sequence())

    panel._populate_tags("Basic Application Confidentiality")

    seq_key = str(pydicom.tag.Tag("DeidentificationMethodCodeSequence"))
    code_meaning_key = f"{seq_key}[0].{pydicom.tag.Tag('CodeMeaning')!s}"

    nested = _find_in_tree(panel, code_meaning_key)
    assert nested is not None, "nested match must survive the filter"

    seq_item = _find_in_tree(panel, seq_key)
    assert seq_item is not None
    assert seq_item.isExpanded(), "sequence parent must open so the match is visible"

    deid_group = _group_item_labelled(panel, "(0012")
    assert deid_group is not None
    assert deid_group.isExpanded(), "group must open so the match is visible"


def test_sequence_rows_reject_edits_but_nested_leaf_is_editable(qapp) -> None:
    """Sequence parents and item nodes stay read-only; nested scalar leaves edit."""
    panel = MetadataPanel()
    ds = _dataset_with_nested_code_sequence()
    panel.set_dataset(ds)

    seq_key = str(pydicom.tag.Tag("DeidentificationMethodCodeSequence"))
    code_meaning_tag = pydicom.tag.Tag("CodeMeaning")
    code_meaning_key = f"{seq_key}[0].{code_meaning_tag!s}"

    assert code_meaning_tag not in ds  # nested-only, before any edit attempt

    seq_item = _find_in_tree(panel, seq_key)
    item_node = _find_in_tree(panel, f"{seq_key}[0]")
    nested = _find_in_tree(panel, code_meaning_key)
    assert seq_item is not None and item_node is not None and nested is not None

    assert panel._is_editable_item(seq_item) is False
    assert panel._is_editable_item(item_node) is False
    assert panel._is_editable_item(nested) is True
    assert panel._is_editable_item(_group_items(panel)[0]) is False

    # A genuine root-level scalar is still editable.
    patient_name = _find_in_tree(panel, str(pydicom.tag.Tag("PatientName")))
    assert patient_name is not None
    assert panel._is_editable_item(patient_name) is True


def test_nested_leaf_edit_uses_path_key_and_does_not_create_root_tag(qapp, monkeypatch) -> None:
    panel = MetadataPanel()
    ds = _dataset_with_nested_code_sequence()
    panel.set_dataset(ds)

    class _AcceptingDialog:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def exec(self):
            return QDialog.DialogCode.Accepted

        def get_value(self):
            return "Changed nested meaning"

    class _ExecutingUndoManager:
        def __init__(self) -> None:
            self.command = None

        def execute_command(self, command) -> None:
            self.command = command
            command.execute()

    undo_manager = _ExecutingUndoManager()
    panel.undo_redo_manager = undo_manager
    monkeypatch.setattr("gui.metadata_panel.TagEditDialog", _AcceptingDialog)

    seq_key = str(pydicom.tag.Tag("DeidentificationMethodCodeSequence"))
    code_meaning_tag = pydicom.tag.Tag("CodeMeaning")
    nested = _find_in_tree(panel, f"{seq_key}[0].{code_meaning_tag!s}")
    assert nested is not None
    assert code_meaning_tag not in ds

    panel._on_item_double_clicked(nested, 3)

    assert undo_manager.command is not None
    assert undo_manager.command.path_key == f"{seq_key}[0].{code_meaning_tag!s}"
    assert code_meaning_tag not in ds
    assert ds.DeidentificationMethodCodeSequence[0].CodeMeaning == "Changed nested meaning"


def test_nested_leaf_fallback_stores_raw_original_before_direct_update(qapp, monkeypatch) -> None:
    panel = MetadataPanel()
    ds = _dataset_with_nested_code_sequence()
    panel.set_dataset(ds)
    history = TagEditHistoryManager()
    panel.history_manager = history
    panel.undo_redo_manager = None

    class _AcceptingDialog:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def exec(self):
            return QDialog.DialogCode.Accepted

        def get_value(self):
            return "Changed nested meaning"

    monkeypatch.setattr("gui.metadata_panel.TagEditDialog", _AcceptingDialog)

    seq_key = str(pydicom.tag.Tag("DeidentificationMethodCodeSequence"))
    code_meaning_tag = pydicom.tag.Tag("CodeMeaning")
    nested_key = f"{seq_key}[0].{code_meaning_tag!s}"
    nested = _find_in_tree(panel, nested_key)
    assert nested is not None

    panel._on_item_double_clicked(nested, 3)

    assert history.get_original_value(ds, nested_key) == (
        "Basic Application Confidentiality Profile"
    )
    assert ds.DeidentificationMethodCodeSequence[0].CodeMeaning == "Changed nested meaning"


def test_nested_patient_tag_is_blocked_by_privacy(qapp) -> None:
    panel = MetadataPanel()
    panel.privacy_mode = True

    assert panel._is_edit_blocked_by_privacy("(0012, 0064)[0].(0010, 0010)") is True


def test_enabling_privacy_closes_active_nested_patient_tag_dialog(qapp) -> None:
    panel = MetadataPanel()

    class _VisibleDialog:
        def __init__(self) -> None:
            self.rejected = False

        def isVisible(self) -> bool:
            return True

        def reject(self) -> None:
            self.rejected = True

    dialog = _VisibleDialog()
    panel._active_tag_edit_dialog = dialog
    panel._active_tag_edit_tag = "(0012, 0064)[0].(0010, 0010)"

    assert panel.close_active_tag_edit_dialog_due_to_privacy() is True
    assert dialog.rejected is True
    assert panel._active_tag_edit_dialog is None
    assert panel._active_tag_edit_tag is None


def test_panel_population_perf_gate_enhanced_multiframe(qapp) -> None:
    """Guards against a reintroduced O(n^2) child lookup (see plan PERF FINDING).

    Resolving each parent's children by rescanning the tag dict cost ~19s on this
    dataset in the tag viewer; the shared child index makes it ~0.2s. The panel
    reuses those helpers and must not regress. Allow 2s for 24k QTreeWidgetItem
    allocations on slower CI Qt backends; the known O(n^2) regression is still
    nearly an order of magnitude above this gate.
    """
    frames = []
    for frame_index in range(2000):
        plane_position = Dataset()
        plane_position.ImagePositionPatient = [0.0, 0.0, float(frame_index)]
        pixel_measures = Dataset()
        pixel_measures.PixelSpacing = [0.5, 0.5]
        pixel_measures.SliceThickness = "1.0"
        frame_content = Dataset()
        frame_content.InStackPositionNumber = frame_index + 1
        frame_content.StackID = "1"

        frame = Dataset()
        frame.PlanePositionSequence = Sequence([plane_position])
        frame.PixelMeasuresSequence = Sequence([pixel_measures])
        frame.FrameContentSequence = Sequence([frame_content])
        frames.append(frame)

    ds = Dataset()
    ds.PerFrameFunctionalGroupsSequence = Sequence(frames)

    panel = MetadataPanel()
    panel.set_dataset(ds)  # primes the parser cache (Mode B, ~24k rows)
    assert panel._cached_tags is not None
    assert len(panel._cached_tags) > 20000

    start = time.perf_counter()
    panel._populate_tags("")
    elapsed_ms = (time.perf_counter() - start) * 1000

    print(
        f"\n[perf] metadata_panel widget population: {elapsed_ms:.1f} ms "
        f"for {len(panel._cached_tags)} rows"
    )
    assert elapsed_ms < 2000


def test_group_headers_span_full_width_and_are_visually_distinct(qapp) -> None:
    """Headings must not be clipped to the narrow Tag column ("Group 0002 — 7 t...")."""
    panel = MetadataPanel()
    panel.set_dataset(_dataset_with_nested_code_sequence())

    headers = _group_items(panel)
    assert headers, "expected at least one group heading"

    background, foreground = panel._group_header_colors()
    assert background != foreground, "heading band must contrast with its own text"

    for header in headers:
        assert header.isFirstColumnSpanned()
        assert header.font(0).bold()
        assert header.background(0).style() != Qt.BrushStyle.NoBrush
        assert header.background(0).color() == background
        assert header.foreground(0).color() == foreground
        # A tag row must NOT carry the band, or headings stop reading as dividers.
        # Tested on the brush *style*, not its color: an unset brush reports its color
        # as black, which would spuriously equal a black band.
        tag_row = header.child(0)
        assert not tag_row.isFirstColumnSpanned()
        assert tag_row.background(0).style() == Qt.BrushStyle.NoBrush


def test_expandable_rows_show_a_disclosure_triangle(qapp) -> None:
    """Root decorations must stay on.

    With them off, a group heading and a sequence row render with no triangle, and the
    custom delegate that used to accompany that setting painted tag text over the branch
    column — so the only way to expand anything was a double-click with no visible hint.
    """
    panel = MetadataPanel()
    panel.set_dataset(_dataset_with_nested_code_sequence())

    assert panel.tree_widget.rootIsDecorated()
    assert panel.tree_widget.indentation() > 0, "tag rows need a visible indent"
    # Single-click toggles headings, so Qt's double-click expand must be off or it
    # would fire a second toggle and cancel the first.
    assert panel.tree_widget.expandsOnDoubleClick() is False


def test_single_click_on_a_group_header_toggles_it(qapp) -> None:
    panel = MetadataPanel()
    panel.set_dataset(_dataset_with_nested_code_sequence())

    header = _group_items(panel)[0]
    assert header.isExpanded() is False  # groups start collapsed

    panel._on_tree_item_clicked(header, 0)
    assert header.isExpanded() is True
    panel._on_tree_item_clicked(header, 0)
    assert header.isExpanded() is False

    # ...and the toggle is remembered for the session, like any other group expansion.
    panel._on_tree_item_clicked(header, 0)
    group_key = header.data(0, Qt.ItemDataRole.UserRole + 2)
    assert panel._group_expanded[group_key] is True

    # A tag row is not a heading: clicking it must not toggle anything.
    tag_row = header.child(0)
    was_expanded = tag_row.isExpanded()
    panel._on_tree_item_clicked(tag_row, 0)
    assert tag_row.isExpanded() == was_expanded


def _render_row(panel: MetadataPanel, item: QTreeWidgetItem, state) -> QColor:
    """Paint one row through the tree's delegate and sample its background pixel."""
    index = panel.tree_widget.indexFromItem(item, 0)
    pixmap = QPixmap(240, 18)
    pixmap.fill(QColor("#000000"))
    painter = QPainter(pixmap)
    option = QStyleOptionViewItem()
    option.rect = QRect(0, 0, 240, 18)
    option.state = state
    panel.tree_widget.itemDelegate().paint(painter, option, index)
    painter.end()
    return pixmap.toImage().pixelColor(200, 9)


def _close(a: QColor, b: QColor, tol: int = 2) -> bool:
    """QColor round-trips through float, so an exact == on a rendered pixel is brittle."""
    return (
        abs(a.red() - b.red()) <= tol
        and abs(a.green() - b.green()) <= tol
        and abs(a.blue() - b.blue()) <= tol
    )


def test_group_header_background_survives_hover_and_selection(qapp) -> None:
    """Regression: Qt paints hover/selection *over* the item's background brush, so a
    hovered heading was replaced by a pale highlight block while keeping its own text
    color — unreadable on a light theme. A heading must render as the pane background in
    every state."""
    panel = MetadataPanel()
    panel.set_dataset(_dataset_with_nested_code_sequence())
    header = _group_items(panel)[0]
    band, _fg = panel._group_header_colors()

    idle = QStyle.StateFlag.State_Enabled
    hovered = idle | QStyle.StateFlag.State_MouseOver
    selected = idle | QStyle.StateFlag.State_Selected

    assert _close(_render_row(panel, header, idle), band)
    assert _close(_render_row(panel, header, hovered), band)
    assert _close(_render_row(panel, header, selected), band)


def test_only_headings_opt_out_of_hover_and_selection(qapp, monkeypatch) -> None:
    """A tag row must keep its hover/selection state, or the delegate has suppressed
    cursor feedback across the whole panel rather than just on the headings.

    Asserted on the state the delegate hands to the base painter, not on rendered
    pixels: the offscreen style paints no hover fill at all, so a pixel comparison here
    would pass regardless of what the delegate did.
    """
    panel = MetadataPanel()
    panel.set_dataset(_dataset_with_nested_code_sequence())
    header = _group_items(panel)[0]
    header.setExpanded(True)
    tag_row = header.child(0)

    seen: list = []
    monkeypatch.setattr(
        QStyledItemDelegate,
        "paint",
        lambda _self, _painter, option, _index: seen.append(option.state),
    )
    hovered = (
        QStyle.StateFlag.State_Enabled
        | QStyle.StateFlag.State_MouseOver
        | QStyle.StateFlag.State_Selected
    )

    _render_row(panel, header, hovered)
    _render_row(panel, tag_row, hovered)
    heading_state, tag_state = seen

    assert not (heading_state & QStyle.StateFlag.State_MouseOver)
    assert not (heading_state & QStyle.StateFlag.State_Selected)
    assert tag_state & QStyle.StateFlag.State_MouseOver
    assert tag_state & QStyle.StateFlag.State_Selected


def _apply_theme(panel: MetadataPanel, base: str, text: str) -> None:
    """Mimic the app's QSS theming, which resolves into the tree's palette."""
    panel.tree_widget.setStyleSheet(
        f"QTreeWidget {{ background-color: {base}; color: {text}; }}"
    )
    QApplication.processEvents()


def test_heading_text_follows_the_theme_not_a_hardcoded_pair(qapp) -> None:
    """A heading must never carry light text while its tag rows carry dark text.

    The band was originally a single dark color with light text baked in, so light mode
    rendered white heading text among black-on-white tag rows.
    """
    panel = MetadataPanel()
    panel.set_dataset(_dataset_with_nested_code_sequence())

    _apply_theme(panel, "#141414", "#e0e0e0")
    dark_band, dark_text = panel._group_header_colors()
    assert dark_text.lightness() > 128, "dark theme needs light heading text"
    assert dark_band.lightness() < 128

    _apply_theme(panel, "#ffffff", "#000000")
    light_band, light_text = panel._group_header_colors()
    assert light_text.lightness() < 128, "light theme needs dark heading text"
    assert light_band.lightness() > 128

    # The band always stays on the same side of the contrast as its own text.
    assert (dark_band.lightness() < dark_text.lightness())
    assert (light_band.lightness() > light_text.lightness())


def test_theme_switch_recolors_existing_headings(qapp) -> None:
    """Colors are resolved when the tree is built, so a live theme flip must repaint
    them — otherwise the old band survives with the new theme's tag rows around it."""
    panel = MetadataPanel()
    _apply_theme(panel, "#141414", "#e0e0e0")
    panel.set_dataset(_dataset_with_nested_code_sequence())

    header = _group_items(panel)[0]
    dark_band, _ = panel._group_header_colors()
    assert header.background(0).color() == dark_band
    assert header.foreground(0).color().lightness() > 128

    _apply_theme(panel, "#ffffff", "#000000")
    panel.changeEvent(QEvent(QEvent.Type.PaletteChange))

    light_band, _ = panel._group_header_colors()
    assert light_band != dark_band
    assert header.background(0).color() == light_band
    assert header.foreground(0).color().lightness() < 128


def test_heading_takes_the_pane_background_and_is_ruled_off(qapp) -> None:
    """A heading has no fill of its own — it is separated by rules, not by color.

    Set explicitly to Base rather than left unset, so a heading can't pick up the
    accent-tinted alternating-row color on odd rows.
    """
    panel = MetadataPanel()

    for base, text in (("#141414", "#e0e0e0"), ("#ffffff", "#000000")):
        _apply_theme(panel, base, text)
        band, fg = panel._group_header_colors()
        assert _close(band, QColor(base)), "heading must be the pane background"
        assert _close(fg, QColor(text)), "heading text must agree with the tag rows"

        # The rule is what actually separates it, so it must be visible against the pane.
        rule = group_header_rule_color(panel.tree_widget.palette())
        assert abs(rule.lightness() - QColor(base).lightness()) >= 30
        assert rule.saturation() <= 8, "rules stay neutral against any accent preset"
