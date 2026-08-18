"""
Phase C metadata tag-tree chrome: tier ladder, filter highlight cache, empty state.

Targets ``QTreeWidget#metadata_tag_tree`` only (not the tag-export picker).
Helpers here keep ``metadata_panel.py`` under its line grandfather and extend
``GroupHeaderDelegate`` without growing ``metadata_table_model.py`` further.

Inputs:
    - ``QTreeWidget`` / ``QTreeWidgetItem`` rows built by ``MetadataPanel``
    - Active filter needle (case-insensitive substring)
    - Theme palette (for disabled text, tier bars, highlight colors)

Outputs:
    - ``METADATA_TIER_ROLE`` on column 0 for delegate paint
    - Mono Tag/VR fonts, tier weight ladder, dimmed empty values
    - Cached substring-highlight pixmaps (no ``QTextDocument`` in ``paint()``)
    - Optional filter-empty banner with Clear → ``clear_filter()``

Requirements:
    PySide6
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontMetrics,
    QPainter,
    QPalette,
    QPixmap,
)
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QStyle,
    QStyleOptionViewItem,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from gui.metadata_table_model import (
    GROUP_HEADER_KEY_ROLE,
    STRIPE_PARITY_ROLE,
    GroupHeaderDelegate,
    _index_has_item_background,
    _palette_mix,
    _row_index,
    format_metadata_value_for_tree,
    metadata_row_kind,
)

# Column indices (Tag=0, Name=1, VR=2, Value=3).
METADATA_COL_TAG = 0
METADATA_COL_NAME = 1
METADATA_COL_VR = 2
METADATA_COL_VALUE = 3

# UserRole+4 — tier string for delegate paint (group uses GROUP_HEADER_KEY_ROLE).
METADATA_TIER_ROLE = Qt.ItemDataRole.UserRole + 4

TIER_SEQUENCE = "sequence"
TIER_ITEM = "item"
TIER_ELEMENT = "element"

TIER_BAR_WIDTH = 3
SEQUENCE_BAR_STRENGTH = 0.42
ITEM_BAR_STRENGTH = 0.22

MONO_FONT_FAMILIES = ("Consolas", "Menlo", "monospace")

_FILTER_HIGHLIGHT_CACHE_MAX = 256


def metadata_tag_mono_font(base: QFont) -> QFont:
    """Return a platform monospace fallback for Tag and VR columns."""
    font = QFont(base)
    font.setFamilies(list(MONO_FONT_FAMILIES))
    return font


def _column_font(base: QFont, column: int) -> QFont:
    if column in (METADATA_COL_TAG, METADATA_COL_VR):
        return metadata_tag_mono_font(base)
    return QFont(base)


def is_metadata_value_empty(value: Any) -> bool:
    """True when a tag value is null/blank (dim with Disabled palette text)."""
    if value is None:
        return True
    if isinstance(value, (list, bytes, bytearray)):
        return len(value) == 0
    if isinstance(value, str):
        return value.strip() == ""
    return False


def metadata_disabled_text_color(palette: QPalette) -> QColor:
    """Token-aligned disabled foreground (``--fg-disabled`` maps to Disabled Text)."""
    return palette.color(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text)


def metadata_filter_highlight_color(palette: QPalette) -> QColor:
    """Subtle highlight fill for filter substring matches (accent-derived mix)."""
    base = palette.color(QPalette.ColorRole.Base)
    highlight = palette.color(QPalette.ColorRole.Highlight)
    mixed = QColor(
        round(base.red() + (highlight.red() - base.red()) * 0.55),
        round(base.green() + (highlight.green() - base.green()) * 0.55),
        round(base.blue() + (highlight.blue() - base.blue()) * 0.55),
    )
    return mixed


def metadata_tier_bar_color(palette: QPalette, tier: str) -> QColor | None:
    """Return a 3px left-bar color for sequence/item parents, or None for leaves."""
    if tier == TIER_SEQUENCE:
        return _palette_mix(palette, SEQUENCE_BAR_STRENGTH)
    if tier == TIER_ITEM:
        return _palette_mix(palette, ITEM_BAR_STRENGTH)
    return None


def apply_metadata_row_tier(
    tag_item: QTreeWidgetItem,
    tree: QTreeWidget,
    tag_data: dict[str, Any],
    *,
    is_edited: bool,
) -> None:
    """
    Store tier role and apply the restrained weight ladder (no Value italics).

    Group headers are styled separately via ``style_group_header_item``.
    """
    kind = metadata_row_kind(tag_data)
    tag_item.setData(METADATA_COL_TAG, METADATA_TIER_ROLE, kind)
    tree_font = tree.font()

    if kind == TIER_SEQUENCE:
        row_font = QFont(tree_font)
        row_font.setBold(True)
    elif kind == TIER_ITEM:
        row_font = QFont(tree_font)
        row_font.setWeight(QFont.Weight.Medium)
    else:
        row_font = QFont(tree_font)
        row_font.setWeight(QFont.Weight.Normal)

    for column in range(4):
        tag_item.setFont(column, _column_font(row_font, column))

    if not is_edited and is_metadata_value_empty(tag_data.get("value")):
        disabled = metadata_disabled_text_color(tree.palette())
        tag_item.setForeground(METADATA_COL_VALUE, disabled)


def casefold_source_index_map(text: str) -> list[int]:
    """Map each ``str.casefold()`` index back to the source character index.

    Needed because casefold can expand (``ß`` → ``ss``), so folded match
    offsets are not valid slices of the original display string.
    """
    mapping: list[int] = []
    for index, char in enumerate(text):
        mapping.extend([index] * len(char.casefold()))
    return mapping


def source_span_for_folded_span(
    mapping: list[int], start: int, end: int
) -> tuple[int, int]:
    """Convert a ``[start, end)`` span in casefold space to a source slice."""
    if start >= end or not mapping:
        return (0, 0)
    return mapping[start], mapping[end - 1] + 1


def coalesce_source_spans(spans: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """Merge overlapping or touching source spans so each glyph is painted once."""
    if not spans:
        return []
    merged: list[tuple[int, int]] = [spans[0]]
    for start, end in spans[1:]:
        last_start, last_end = merged[-1]
        if start <= last_end:
            merged[-1] = (last_start, max(last_end, end))
        else:
            merged.append((start, end))
    return merged


def folded_match_source_spans(text: str, needle: str) -> list[tuple[int, int]]:
    """Return coalesced source spans for case-insensitive substring matches."""
    needle_cf = needle.casefold()
    if not text or not needle_cf:
        return []
    lower = text.casefold()
    src_of = casefold_source_index_map(text)
    spans: list[tuple[int, int]] = []
    pos = 0
    while pos < len(lower):
        match_at = lower.find(needle_cf, pos)
        if match_at < 0:
            break
        match_end = match_at + len(needle_cf)
        spans.append(source_span_for_folded_span(src_of, match_at, match_end))
        pos = match_end
    return coalesce_source_spans(spans)


class FilterHighlightCache:
    """
  Cache draw results for case-insensitive substring highlights.

  Keys: (text, needle_lower, fg_name, hl_name, font_key). Values: QPixmap.
  No ``QTextDocument`` — segments are measured with ``QFontMetrics``.
    """

    def __init__(self, max_entries: int = _FILTER_HIGHLIGHT_CACHE_MAX) -> None:
        self._max_entries = max_entries
        self._cache: dict[tuple[str, ...], QPixmap] = {}

    def clear(self) -> None:
        self._cache.clear()

    def _cache_key(
        self,
        text: str,
        needle: str,
        fg: QColor,
        hl: QColor,
        font: QFont,
    ) -> tuple[str, ...]:
        return (
            text,
            needle.casefold(),
            fg.name(QColor.NameFormat.HexArgb),
            hl.name(QColor.NameFormat.HexArgb),
            font.key(),
        )

    def _evict_if_needed(self) -> None:
        if len(self._cache) > self._max_entries:
            # Drop oldest half — cheap bounded cache for theme/filter churn.
            keys = list(self._cache.keys())
            for key in keys[: len(keys) // 2]:
                del self._cache[key]

    def draw(
        self,
        painter: QPainter,
        rect: QRect,
        text: str,
        needle: str,
        fg: QColor,
        hl: QColor,
        font: QFont,
    ) -> None:
        if not text:
            return
        needle_cf = needle.casefold()
        if not needle_cf:
            painter.setPen(fg)
            painter.setFont(font)
            painter.drawText(rect, int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft), text)
            return

        key = self._cache_key(text, needle, fg, hl, font)
        pixmap = self._cache.get(key)
        if pixmap is None:
            pixmap = self._render_pixmap(text, needle_cf, fg, hl, font)
            self._cache[key] = pixmap
            self._evict_if_needed()
        painter.drawPixmap(rect.topLeft(), pixmap)

    def _render_pixmap(
        self,
        text: str,
        needle_cf: str,
        fg: QColor,
        hl: QColor,
        font: QFont,
    ) -> QPixmap:
        metrics = QFontMetrics(font)
        width = metrics.horizontalAdvance(text) + 2
        height = max(metrics.height(), 1)
        pixmap = QPixmap(max(width, 1), height)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setFont(font)
        x = 0
        y = metrics.ascent()
        cursor = 0
        for start, end in folded_match_source_spans(text, needle_cf):
            if start > cursor:
                segment = text[cursor:start]
                painter.setPen(fg)
                painter.drawText(x, y, segment)
                x += metrics.horizontalAdvance(segment)
            matched = text[start:end]
            match_width = metrics.horizontalAdvance(matched)
            painter.fillRect(x, 0, match_width, height, hl)
            painter.setPen(fg)
            painter.drawText(x, y, matched)
            x += match_width
            cursor = end
        if cursor < len(text):
            segment = text[cursor:]
            painter.setPen(fg)
            painter.drawText(x, y, segment)
        painter.end()
        return pixmap


class MetadataTagTreeDelegate(GroupHeaderDelegate):
    """
    Phase B heading/stripe delegate extended with Phase C tier bars and filter paint.

    Headings still suppress hover/selection washout. Tag rows get optional left
    bars for sequence/item parents and cached filter substring highlights.
    """

    def __init__(self, parent: QTreeWidget | None = None) -> None:
        super().__init__(parent)
        self._filter_needle: str = ""
        self._highlight_cache = FilterHighlightCache()

    def set_filter_needle(self, needle: str) -> None:
        """Set the active filter substring; clears highlight cache on change."""
        normalized = needle or ""
        if normalized != self._filter_needle:
            self._filter_needle = normalized
            self._highlight_cache.clear()

    def clear_theme_caches(self) -> None:
        """Drop cached highlight pixmaps after a palette/theme flip."""
        self._highlight_cache.clear()

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index) -> None:
        row = _row_index(index)
        if row.data(GROUP_HEADER_KEY_ROLE) is not None:
            super().paint(painter, option, index)
            return

        option = QStyleOptionViewItem(option)
        if (
            not _index_has_item_background(row)
            and row.data(STRIPE_PARITY_ROLE) == 1
        ):
            stripe = option.palette.color(QPalette.ColorRole.AlternateBase)
            painter.fillRect(option.rect, stripe)

        tier = row.data(METADATA_TIER_ROLE)
        bar_color = metadata_tier_bar_color(option.palette, tier or "")
        if bar_color is not None:
            bar_rect = QRect(
                option.rect.left(),
                option.rect.top(),
                TIER_BAR_WIDTH,
                option.rect.height(),
            )
            painter.fillRect(bar_rect, bar_color)

        text = index.data(Qt.ItemDataRole.DisplayRole)
        text_str = "" if text is None else str(text)
        needle = self._filter_needle

        if needle and text_str and needle.casefold() in text_str.casefold():
            # Background + selection chrome via style; text drawn with cache.
            opt = QStyleOptionViewItem(option)
            self.initStyleOption(opt, index)
            opt.text = ""
            widget = opt.widget
            if widget is not None:
                widget.style().drawControl(
                    QStyle.ControlElement.CE_ItemViewItem,
                    opt,
                    painter,
                    widget,
                )
            fg = opt.palette.color(QPalette.ColorRole.Text)
            if opt.state & QStyle.StateFlag.State_Selected:
                fg = opt.palette.color(QPalette.ColorRole.HighlightedText)
            hl = metadata_filter_highlight_color(opt.palette)
            text_rect = option.rect.adjusted(4, 0, -2, 0)
            self._highlight_cache.draw(
                painter,
                text_rect,
                text_str,
                needle,
                fg,
                hl,
                opt.font,
            )
            return

        super().paint(painter, option, index)


class MetadataFilterEmptyBanner(QWidget):
    """Shown when a non-empty filter hides every tag row; Clear calls ``clear_filter``."""

    def __init__(
        self,
        clear_filter: Callable[[], None],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("metadata_filter_empty_banner")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        label = QLabel("No tags match the filter.")
        label.setObjectName("metadata_filter_empty_label")
        layout.addWidget(label)
        layout.addStretch()
        clear_button = QPushButton("Clear")
        clear_button.setObjectName("metadata_filter_clear_button")
        clear_button.clicked.connect(clear_filter)
        layout.addWidget(clear_button)
        self.hide()


def tree_has_visible_tag_rows(tree: QTreeWidget) -> bool:
    """True when at least one non-header tag row is visible in the tree."""
    root = tree.invisibleRootItem()

    def walk(item: QTreeWidgetItem) -> bool:
        for index in range(item.childCount()):
            child = item.child(index)
            if child.isHidden():
                continue
            if child.data(METADATA_COL_TAG, GROUP_HEADER_KEY_ROLE) is None:
                if child.data(METADATA_COL_TAG, Qt.ItemDataRole.UserRole) is not None:
                    return True
                if walk(child):
                    return True
            elif child.isExpanded() and walk(child):
                return True
        return False

    for index in range(root.childCount()):
        group = root.child(index)
        if group.isHidden():
            continue
        if group.isExpanded() and walk(group):
            return True
    return False


def update_filter_empty_banner(
    banner: MetadataFilterEmptyBanner,
    tree: QTreeWidget,
    search_text: str,
) -> None:
    """Show the empty-state banner only for a non-empty filter with zero tag rows."""
    if search_text and not tree_has_visible_tag_rows(tree):
        banner.show()
    else:
        banner.hide()


def build_metadata_tag_tree_item(
    panel: Any,
    parent_item: QTreeWidgetItem,
    tag_str: str,
    tag_data: dict[str, Any],
    children_by_parent: dict[str | None, list[tuple[str, dict[str, Any]]]],
    force_expand_sequences: bool,
) -> QTreeWidgetItem:
    """
    Create one metadata tag row and recurse into children.

    Extracted from ``MetadataPanel._build_tag_tree_item`` to keep the panel file
    under its line grandfather while centralizing Phase C chrome application.
    """
    from gui.tag_edit_support import edited_tag_row_colors

    tag_item = QTreeWidgetItem(parent_item)
    tag_item.setText(METADATA_COL_TAG, tag_str)

    tag_name = tag_data.get("name", "")
    is_edited = False
    if panel.history_manager and panel.dataset:
        is_edited = panel.history_manager.is_tag_edited(panel.dataset, tag_str)
    if is_edited:
        tag_name = tag_name + "*"

    tag_item.setText(METADATA_COL_NAME, tag_name)
    tag_item.setText(METADATA_COL_VR, tag_data.get("VR", ""))
    tag_item.setTextAlignment(
        METADATA_COL_TAG,
        Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
    )

    value_str = format_metadata_value_for_tree(tag_data.get("value", ""))
    tag_item.setText(METADATA_COL_VALUE, value_str)

    if is_edited:
        edited_color, edited_text_color = edited_tag_row_colors(panel.config_manager)
        for col in range(4):
            tag_item.setBackground(col, edited_color)
            tag_item.setForeground(col, edited_text_color)

    tag_item.setData(METADATA_COL_TAG, Qt.ItemDataRole.UserRole, tag_str)
    tag_item.setData(METADATA_COL_TAG, Qt.ItemDataRole.UserRole + 1, tag_data)

    apply_metadata_row_tier(tag_item, panel.tree_widget, tag_data, is_edited=is_edited)

    children = children_by_parent.get(tag_str, [])
    if children:
        tag_item.setChildIndicatorPolicy(
            QTreeWidgetItem.ChildIndicatorPolicy.ShowIndicator
        )

    kind = metadata_row_kind(tag_data)
    if kind == TIER_SEQUENCE:
        tag_item.setExpanded(force_expand_sequences)
    elif kind == TIER_ITEM:
        tag_item.setExpanded(True)

    for child_key, child_data in children:
        build_metadata_tag_tree_item(
            panel,
            tag_item,
            child_key,
            child_data,
            children_by_parent,
            force_expand_sequences,
        )

    return tag_item


def clear_metadata_panel_for_empty_dataset(panel: Any) -> None:
    """Clear parser, tree, search, and the no-match banner when the dataset is None."""
    panel.parser = None
    panel.editor = None
    panel._cached_tags = None
    panel._cached_search_text = ""
    panel.search_edit.clear()
    panel.tree_widget.clear()
    banner = getattr(panel, "_filter_empty_banner", None)
    if banner is not None:
        banner.hide()


def _recolor_empty_metadata_value_row(
    item: QTreeWidgetItem,
    disabled: QColor,
    history: Any,
    dataset: Any,
) -> None:
    """Dim empty Value cells; leave edited-row foreground unchanged."""
    if item.data(METADATA_COL_TAG, GROUP_HEADER_KEY_ROLE) is not None:
        return
    tag_data = item.data(METADATA_COL_TAG, Qt.ItemDataRole.UserRole + 1)
    if not isinstance(tag_data, dict):
        return
    tag_str = item.data(METADATA_COL_TAG, Qt.ItemDataRole.UserRole)
    is_edited = False
    if history is not None and dataset is not None and tag_str is not None:
        is_edited = bool(history.is_tag_edited(dataset, tag_str))
    if is_edited:
        return
    if is_metadata_value_empty(tag_data.get("value")):
        item.setForeground(METADATA_COL_VALUE, disabled)


def _recolor_empty_metadata_values(panel: Any) -> None:
    """Recompute disabled Value color for empty non-edited rows from the live palette."""
    tree = panel.tree_widget
    disabled = metadata_disabled_text_color(tree.palette())
    history = getattr(panel, "history_manager", None)
    dataset = getattr(panel, "dataset", None)

    def walk(parent: QTreeWidgetItem) -> None:
        for index in range(parent.childCount()):
            child = parent.child(index)
            _recolor_empty_metadata_value_row(child, disabled, history, dataset)
            walk(child)

    walk(tree.invisibleRootItem())


def attach_metadata_tree_chrome(panel: Any) -> MetadataFilterEmptyBanner:
    """
    Wire Phase C chrome onto an existing ``MetadataPanel`` instance.

    Returns the filter-empty banner widget (inserted above the tree).
    """
    tree = panel.tree_widget
    delegate = MetadataTagTreeDelegate(tree)
    tree.setItemDelegate(delegate)
    panel._metadata_tree_delegate = delegate

    banner = MetadataFilterEmptyBanner(panel.clear_filter, panel)
    layout: QVBoxLayout = panel.layout()
    tree_index = layout.indexOf(tree)
    layout.insertWidget(tree_index, banner)
    panel._filter_empty_banner = banner
    return banner


def on_metadata_panel_palette_change(panel: Any) -> None:
    """Invalidate highlight caches and refresh empty-value colors on theme flip."""
    delegate = getattr(panel, "_metadata_tree_delegate", None)
    if delegate is not None:
        delegate.clear_theme_caches()
    _recolor_empty_metadata_values(panel)
