"""Phase B metadata-tree chrome: header font/height, per-group stripes, perf growth."""

from __future__ import annotations

import time

from pydicom.dataset import Dataset
from pydicom.tag import Tag
from PySide6.QtCore import QRect
from PySide6.QtGui import QColor, QPainter, QPalette, QPixmap
from PySide6.QtWidgets import QStyle, QStyleOptionViewItem

from gui.metadata_panel import MetadataPanel
from gui.metadata_table_model import (
    GROUP_HEADER_BOTTOM_RULE_WIDTH,
    GROUP_HEADER_FONT_SCALE,
    GROUP_HEADER_TOP_RULE_WIDTH,
    STRIPE_PARITY_ROLE,
    group_header_bottom_rule_color,
    group_header_fill_color,
    group_header_top_rule_color,
)


def _dataset_with_two_groups() -> Dataset:
    """Two DICOM groups with several tags each so striping and reset are visible."""
    ds = Dataset()
    ds.PatientName = "Test^Patient"
    ds.PatientID = "12345"
    ds.PatientBirthDate = "20000101"
    ds.StudyDate = "20200101"
    ds.StudyTime = "120000"
    ds.StudyDescription = "Synthetic"
    return ds


def _dataset_with_tag_count(tag_count: int) -> Dataset:
    """Synthetic dataset with *tag_count* extra LO values spread across groups."""
    ds = Dataset()
    ds.PatientName = "Perf^Test"
    groups = (0x0010, 0x0018, 0x0020, 0x0028, 0x0040, 0x0054)
    for index in range(tag_count):
        group = groups[index % len(groups)]
        element = 0x1100 + (index // len(groups))
        ds.add_new(Tag(group, element), "LO", f"v{index}")
    return ds


def _group_items(panel: MetadataPanel):
    root = panel.tree_widget.invisibleRootItem()
    return [root.child(i) for i in range(root.childCount())]


def test_group_header_font_and_height_are_bumped(qapp) -> None:
    """Goal 1: headings are bold and ~10% larger, without extra vertical padding."""
    panel = MetadataPanel()
    panel.set_dataset(_dataset_with_two_groups())
    header = _group_items(panel)[0]
    header.setExpanded(True)
    tag_row = header.child(0)
    assert tag_row is not None

    header_font = header.font(0)
    tree_font = panel.tree_widget.font()
    assert header_font.bold()
    header_size = header_font.pointSizeF() or float(header_font.pointSize())
    tree_size = tree_font.pointSizeF() or float(tree_font.pointSize() or 12)
    if header_size > 0 and tree_size > 0:
        assert header_size >= tree_size * GROUP_HEADER_FONT_SCALE - 0.05

    delegate = panel.tree_widget.itemDelegate()
    option = QStyleOptionViewItem()
    option.initFrom(panel.tree_widget)
    option.font = panel.tree_widget.font()
    header_h = delegate.sizeHint(
        option, panel.tree_widget.indexFromItem(header, 0)
    ).height()
    tag_h = delegate.sizeHint(
        option, panel.tree_widget.indexFromItem(tag_row, 0)
    ).height()
    assert tag_h > 0
    assert header_h >= tag_h
    assert panel.tree_widget.isAnimated() is False
    assert panel.tree_widget.alternatingRowColors() is False


def test_stripe_parity_resets_per_group_and_on_collapse(qapp) -> None:
    """Goal 2: visible tag rows alternate 0/1 and restart at the next group."""
    panel = MetadataPanel()
    panel.set_dataset(_dataset_with_two_groups())
    groups = _group_items(panel)
    assert len(groups) >= 2

    groups[0].setExpanded(True)
    groups[1].setExpanded(True)

    first_parities = [
        groups[0].child(i).data(0, STRIPE_PARITY_ROLE)
        for i in range(groups[0].childCount())
        if not groups[0].child(i).isHidden()
    ]
    second_parities = [
        groups[1].child(i).data(0, STRIPE_PARITY_ROLE)
        for i in range(groups[1].childCount())
        if not groups[1].child(i).isHidden()
    ]
    assert first_parities
    assert second_parities
    assert first_parities[0] == 0
    assert second_parities[0] == 0
    for index, parity in enumerate(first_parities):
        assert parity == index % 2

    groups[0].setExpanded(False)
    assert groups[1].child(0).data(0, STRIPE_PARITY_ROLE) == 0


def test_odd_stripe_uses_alternate_base_in_paint(qapp) -> None:
    """Delegate fills odd visible tag rows with AlternateBase (O(1) paint)."""
    panel = MetadataPanel()
    panel.set_dataset(_dataset_with_two_groups())
    palette = panel.tree_widget.palette()
    stripe = QColor("#c8d0d8")
    palette.setColor(QPalette.ColorRole.AlternateBase, stripe)
    panel.tree_widget.setPalette(palette)

    header = _group_items(panel)[0]
    header.setExpanded(True)
    odd_row = header.child(1)
    assert odd_row is not None
    assert odd_row.data(0, STRIPE_PARITY_ROLE) == 1

    for column in (0, 1):
        index = panel.tree_widget.indexFromItem(odd_row, column)
        pixmap = QPixmap(240, 18)
        pixmap.fill(QColor("#000000"))
        painter = QPainter(pixmap)
        option = QStyleOptionViewItem()
        option.rect = QRect(0, 0, 240, 18)
        option.palette = palette
        option.state = QStyle.StateFlag.State_Enabled
        panel.tree_widget.itemDelegate().paint(painter, option, index)
        painter.end()
        sampled = pixmap.toImage().pixelColor(200, 9)
        assert abs(sampled.red() - stripe.red()) <= 30
        assert abs(sampled.green() - stripe.green()) <= 30
        assert abs(sampled.blue() - stripe.blue()) <= 30


def test_header_top_and_bottom_rules_are_one_px_and_full_width(qapp) -> None:
    """Top/bottom hairlines are 1px, distinct from the fill, and reach the left gutter.

    Dark theme lightens both rules relative to the fill; light theme darkens
    them instead — a light "highlight" edge had no headroom left above the
    fill before hitting the tag rows' white, so light theme's rules step
    toward black instead.
    """
    panel = MetadataPanel()
    panel.set_dataset(_dataset_with_two_groups())
    panel.resize(720, 420)
    panel.show()
    qapp.processEvents()
    tree = panel.tree_widget
    header = _group_items(panel)[0]
    palette = tree.palette()
    band = group_header_fill_color(palette)
    top_rule = group_header_top_rule_color(palette)
    bottom_rule = group_header_bottom_rule_color(palette)
    is_dark = palette.color(QPalette.ColorRole.Base).lightness() < 128
    if is_dark:
        assert top_rule.lightness() > band.lightness()
        assert bottom_rule.lightness() > band.lightness()
    else:
        assert top_rule.lightness() < band.lightness()
        assert bottom_rule.lightness() < band.lightness()
    assert GROUP_HEADER_TOP_RULE_WIDTH == 1.0
    assert GROUP_HEADER_BOTTOM_RULE_WIDTH == 1.0

    index = tree.indexFromItem(header, 0)
    option = QStyleOptionViewItem()
    option.initFrom(tree)
    option.rect = tree.visualRect(index)
    option.palette = palette
    option.state = QStyle.StateFlag.State_Enabled
    pixmap = QPixmap(tree.viewport().size())
    pixmap.fill(band)
    painter = QPainter(pixmap)
    tree.drawRow(painter, option, index)
    painter.end()
    image = pixmap.toImage()
    top_y = max(option.rect.top(), 0)
    bottom_y = min(option.rect.bottom(), image.height() - 1)
    left_pixel = image.pixelColor(2, top_y)
    mid_pixel = image.pixelColor(min(120, image.width() - 1), top_y)
    mid_bottom_pixel = image.pixelColor(min(120, image.width() - 1), bottom_y)
    assert abs(left_pixel.lightness() - top_rule.lightness()) <= 40
    assert abs(mid_pixel.lightness() - top_rule.lightness()) <= 40
    assert abs(mid_bottom_pixel.lightness() - bottom_rule.lightness()) <= 40


def test_panel_stripe_recompute_scales_near_linearly(qapp) -> None:
    """Two expanded trees: stripe recompute must stay near-linear (not O(n²))."""
    from gui.metadata_table_model import assign_group_stripe_parity

    small_n, large_n = 40, 160
    small_panel = MetadataPanel()
    large_panel = MetadataPanel()
    small_panel.set_dataset(_dataset_with_tag_count(small_n))
    large_panel.set_dataset(_dataset_with_tag_count(large_n))
    small_panel._set_all_expanded(True)
    large_panel._set_all_expanded(True)
    first_group = large_panel.tree_widget.invisibleRootItem().child(0)
    assert first_group is not None
    assert first_group.childCount() > 1
    assert first_group.child(1).data(0, STRIPE_PARITY_ROLE) == 1

    start = time.perf_counter()
    for _ in range(25):
        assign_group_stripe_parity(small_panel.tree_widget)
    small_s = time.perf_counter() - start

    start = time.perf_counter()
    for _ in range(25):
        assign_group_stripe_parity(large_panel.tree_widget)
    large_s = time.perf_counter() - start

    ratio = large_n / small_n
    assert small_s > 0.0
    assert large_s / small_s < ratio * 3.0
    assert large_s < 2.0


def test_themed_heading_fill_and_name_column_stripe(qapp) -> None:
    """With the real light QSS applied, heading fill and Name-column stripes show."""
    from gui.main_window_theme import get_theme_stylesheet
    from gui.metadata_table_model import group_header_colors

    previous = qapp.styleSheet()
    qapp.setStyleSheet(
        get_theme_stylesheet("light", "/dummy/w.png", "/dummy/b.png", accent_id="steel-blue")
    )
    try:
        panel = MetadataPanel()
        panel.resize(720, 420)
        panel.set_dataset(_dataset_with_two_groups())
        header = _group_items(panel)[0]
        header.setExpanded(True)
        panel.show()
        qapp.processEvents()
        tree = panel.tree_widget
        tree.setColumnWidth(0, 120)
        tree.setColumnWidth(1, 220)
        qapp.processEvents()

        pixmap = QPixmap(tree.viewport().size())
        tree.viewport().render(pixmap)
        image = pixmap.toImage()

        header_rect = tree.visualItemRect(header)
        heading_px = image.pixelColor(
            min(header_rect.left() + 180, header_rect.right() - 4),
            header_rect.center().y(),
        )
        band, _fg = group_header_colors(tree.palette())
        pane = QColor("#ffffff")
        assert abs(heading_px.lightness() - pane.lightness()) > 8
        assert abs(heading_px.lightness() - band.lightness()) <= 40

        odd_row = header.child(1)
        assert odd_row is not None
        odd_rect = tree.visualItemRect(odd_row)
        name_px = image.pixelColor(
            min(odd_rect.left() + 180, odd_rect.right() - 4),
            odd_rect.center().y(),
        )
        alt = tree.palette().color(QPalette.ColorRole.AlternateBase)
        assert abs(name_px.lightness() - pane.lightness()) > 4
        assert abs(name_px.lightness() - alt.lightness()) <= 50

        even_row = header.child(0)
        assert even_row is not None
        tree.setCurrentItem(even_row)
        qapp.processEvents()
        selected_map = QPixmap(tree.viewport().size())
        tree.viewport().render(selected_map)
        selected_rect = tree.visualItemRect(even_row)
        selected_px = selected_map.toImage().pixelColor(
            min(selected_rect.left() + 180, selected_rect.right() - 4),
            selected_rect.center().y(),
        )
        assert abs(selected_px.lightness() - pane.lightness()) > 20
    finally:
        qapp.setStyleSheet(previous)


# --- Phase C (tier ladder, mono Tag/VR, filter highlight, empty state, hover QSS) ---

from pathlib import Path

from pydicom.sequence import Sequence
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QTreeWidgetItem

from gui.main_window_theme import get_theme_stylesheet
from gui.metadata_tree_chrome import (
    METADATA_TIER_ROLE,
    FilterHighlightCache,
    casefold_source_index_map,
    folded_match_source_spans,
    is_metadata_value_empty,
    metadata_disabled_text_color,
    metadata_tag_mono_font,
    on_metadata_panel_palette_change,
    source_span_for_folded_span,
)


def _dataset_with_nested_code_sequence():
    from pydicom.dataset import Dataset

    ds = Dataset()
    ds.PatientName = "Test^Patient"
    ds.PatientID = "12345"
    item = Dataset()
    item.CodeValue = "113100"
    item.CodingSchemeDesignator = "DCM"
    item.CodeMeaning = "Basic Application Confidentiality Profile"
    ds.DeidentificationMethodCodeSequence = Sequence([item])
    return ds


def _dataset_with_empty_value_tag():
    from pydicom.dataset import Dataset
    from pydicom.tag import Tag

    ds = Dataset()
    ds.PatientName = "Test^Patient"
    ds.add_new(Tag(0x0010, 0x0021), "LO", "")
    return ds


def _find_sequence_parent(panel: MetadataPanel) -> QTreeWidgetItem | None:
    for group in _group_items(panel):
        for index in range(group.childCount()):
            child = group.child(index)
            if child.data(0, METADATA_TIER_ROLE) == "sequence":
                return child
    return None


def _find_first_leaf(panel: MetadataPanel) -> QTreeWidgetItem | None:
    for group in _group_items(panel):
        group.setExpanded(True)
        for index in range(group.childCount()):
            child = group.child(index)
            if child.data(0, METADATA_TIER_ROLE) == "element":
                return child
    return None


def test_sequence_parent_bolder_than_leaf(qapp) -> None:
    panel = MetadataPanel()
    panel.set_dataset(_dataset_with_nested_code_sequence())
    groups = _group_items(panel)
    groups[0].setExpanded(True)
    sequence = _find_sequence_parent(panel)
    assert sequence is not None
    sequence.setExpanded(True)
    leaf = None
    for index in range(sequence.childCount()):
        candidate = sequence.child(index)
        if candidate.data(0, METADATA_TIER_ROLE) == "element":
            leaf = candidate
            break
        candidate.setExpanded(True)
        for sub in range(candidate.childCount()):
            sub_child = candidate.child(sub)
            if sub_child.data(0, METADATA_TIER_ROLE) == "element":
                leaf = sub_child
                break
        if leaf is not None:
            break
    assert leaf is not None
    assert sequence.font(0).bold()
    assert not leaf.font(0).bold()
    assert sequence.font(0).weight() >= leaf.font(0).weight()


def test_tag_and_vr_columns_use_monospace_family(qapp) -> None:
    panel = MetadataPanel()
    panel.set_dataset(_dataset_with_two_groups())
    header = _group_items(panel)[0]
    header.setExpanded(True)
    row = header.child(0)
    mono = metadata_tag_mono_font(panel.tree_widget.font())
    expected = mono.families()[0].lower()
    assert expected in row.font(0).family().lower() or row.font(0).families()[0].lower() in (
        "consolas",
        "menlo",
        "monospace",
    )
    assert row.font(2).families()[0].lower() in ("consolas", "menlo", "monospace")


def test_empty_value_uses_disabled_foreground(qapp) -> None:
    panel = MetadataPanel()
    panel.set_dataset(_dataset_with_empty_value_tag())
    header = _group_items(panel)[0]
    header.setExpanded(True)
    value_item = None
    for index in range(header.childCount()):
        child = header.child(index)
        if child.text(3) == "":
            value_item = child
            break
    assert value_item is not None
    disabled = metadata_disabled_text_color(panel.tree_widget.palette())
    fg = value_item.foreground(3).color()
    assert fg.red() == disabled.red()
    assert fg.green() == disabled.green()
    assert fg.blue() == disabled.blue()
    assert is_metadata_value_empty("")


def test_casefold_source_map_handles_eszett_expansion() -> None:
    mapping = casefold_source_index_map("Straße")
    assert "".join(ch.casefold() for ch in "Straße") == "strasse"
    assert len(mapping) == len("strasse")
    start, end = source_span_for_folded_span(mapping, 4, 6)
    assert "Straße"[start:end] == "ß"


def test_folded_match_spans_coalesce_eszett_for_single_s() -> None:
    spans = folded_match_source_spans("Straße", "s")
    assert spans == [(0, 1), (4, 5)]
    assert "Straße"[0:1] == "S"
    assert "Straße"[4:5] == "ß"


def test_filter_highlight_cache_paints_match_without_qtextdocument(qapp) -> None:
    cache = FilterHighlightCache()
    pixmap = QPixmap(200, 20)
    pixmap.fill(QColor("#ffffff"))
    painter = QPainter(pixmap)
    fg = QColor("#101010")
    hl = QColor("#ffee88")
    font = QFont("Arial", 10)
    cache.draw(painter, QRect(2, 2, 180, 16), "PatientName", "name", fg, hl, font)
    painter.end()
    assert len(cache._cache) == 1
    image = pixmap.toImage()
    # Highlight band should differ from plain background.
    assert image.pixelColor(40, 10).lightness() != image.pixelColor(4, 10).lightness()


def test_delegate_filter_highlight_paints_on_match(qapp) -> None:
    panel = MetadataPanel()
    panel.set_dataset(_dataset_with_two_groups())
    panel.search_edit.setText("Patient")
    panel._populate_tags("Patient")
    assert panel._metadata_tree_delegate._filter_needle == "Patient"
    header = _group_items(panel)[0]
    header.setExpanded(True)
    row = header.child(0)
    delegate = panel._metadata_tree_delegate
    assert delegate is not None
    index = panel.tree_widget.indexFromItem(row, 1)
    pixmap = QPixmap(240, 20)
    pixmap.fill(QColor("#ffffff"))
    painter = QPainter(pixmap)
    option = QStyleOptionViewItem()
    option.rect = QRect(0, 0, 240, 20)
    option.palette = panel.tree_widget.palette()
    option.state = QStyle.StateFlag.State_Enabled
    delegate.paint(painter, option, index)
    painter.end()
    assert pixmap.toImage().pixelColor(60, 10).lightness() != pixmap.toImage().pixelColor(4, 10).lightness()


def test_filter_no_match_shows_clear_and_restores_rows(qapp) -> None:
    panel = MetadataPanel()
    panel.set_dataset(_dataset_with_two_groups())
    panel._populate_tags("zzznomatchzzz")
    panel.show()
    qapp.processEvents()
    banner = panel._filter_empty_banner
    assert banner is not None
    assert banner.isVisible()
    from PySide6.QtWidgets import QPushButton

    clear_btn = banner.findChild(QPushButton, "metadata_filter_clear_button")
    assert clear_btn is not None
    clear_btn.click()
    qapp.processEvents()
    assert not banner.isVisible()
    assert panel.search_edit.text() == ""
    header = _group_items(panel)[0]
    assert header.childCount() > 0


def test_clearing_dataset_hides_filter_empty_banner(qapp) -> None:
    panel = MetadataPanel()
    panel.set_dataset(_dataset_with_two_groups())
    panel._populate_tags("zzznomatchzzz")
    panel.show()
    qapp.processEvents()
    banner = panel._filter_empty_banner
    assert banner is not None
    assert banner.isVisible()
    panel.set_dataset(None)
    assert not banner.isVisible()


def test_empty_value_recolors_on_palette_change(qapp) -> None:
    panel = MetadataPanel()
    panel.set_dataset(_dataset_with_empty_value_tag())
    header = _group_items(panel)[0]
    header.setExpanded(True)
    value_item = None
    for index in range(header.childCount()):
        child = header.child(index)
        if child.text(3) == "":
            value_item = child
            break
    assert value_item is not None
    palette = panel.tree_widget.palette()
    palette.setColor(
        QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, QColor(11, 22, 33)
    )
    panel.tree_widget.setPalette(palette)
    on_metadata_panel_palette_change(panel)
    fg = value_item.foreground(3).color()
    assert fg.red() == 11
    assert fg.green() == 22
    assert fg.blue() == 33


def test_metadata_tag_tree_hover_rule_in_both_qss_files() -> None:
    root = Path(__file__).resolve().parents[1]
    for name in ("dark.qss", "light.qss"):
        text = (root / "resources" / "themes" / name).read_text(encoding="utf-8")
        assert "QTreeWidget#metadata_tag_tree::item:hover" in text
        assert "{metadata_tag_hover}" in text
        assert "background-color: transparent" not in text.split("metadata_tag_tree")[1].split("tag_export")[0]


def test_metadata_tag_tree_selection_token_in_theme_stylesheet() -> None:
    sheet = get_theme_stylesheet("light", "/w.png", "/b.png", accent_id="steel-blue")
    assert "QTreeWidget#metadata_tag_tree::item:selected" in sheet
    assert "metadata_tag_selection" not in sheet  # substituted
    assert "metadata_tag_selection_fg" not in sheet
    chunk = sheet.split("metadata_tag_tree::item:selected")[1][:180]
    assert "#" in chunk
    assert "color: #ffffff" not in chunk
