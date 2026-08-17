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
    GROUP_HEADER_EXTRA_HEIGHT,
    GROUP_HEADER_FONT_SCALE,
    GROUP_HEADER_TOP_RULE_WIDTH,
    STRIPE_PARITY_ROLE,
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
    """Goal 1: headings are bold, ~10% larger, and slightly taller than a tag row."""
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
    assert header_h >= tag_h + GROUP_HEADER_EXTRA_HEIGHT
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


def test_heavier_top_rule_is_visible_on_header(qapp) -> None:
    """HiDPI-style smoke: the top rule is thicker than the bottom rule."""
    panel = MetadataPanel()
    panel.set_dataset(_dataset_with_two_groups())
    header = _group_items(panel)[0]
    band, _fg = panel._group_header_colors()
    top_rule = group_header_top_rule_color(panel.tree_widget.palette())

    index = panel.tree_widget.indexFromItem(header, 0)
    height = 22
    pixmap = QPixmap(240, height)
    pixmap.fill(band)
    painter = QPainter(pixmap)
    option = QStyleOptionViewItem()
    option.rect = QRect(0, 0, 240, height)
    option.palette = panel.tree_widget.palette()
    option.state = QStyle.StateFlag.State_Enabled
    panel.tree_widget.itemDelegate().paint(painter, option, index)
    painter.end()
    image = pixmap.toImage()
    top_pixel = image.pixelColor(120, 1)
    assert abs(top_pixel.lightness() - top_rule.lightness()) <= 40
    assert GROUP_HEADER_TOP_RULE_WIDTH >= 2.0


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
