"""
Metadata panel — group-heading delegate and pure tag-list helpers.

``MetadataPanel`` uses a ``QTreeWidget`` (historical plan wording referenced a
“table model”; there is no ``QAbstractTableModel`` here). This module holds:

- ``GroupHeaderDelegate`` — heading fill + 1px top hairline; per-group stripe fills.
- Pure functions to filter, group, and format tag dicts when building tree items.

An earlier ``MetadataItemDelegate`` repainted each tag row's first column at x=0 to
cancel out the tree's indentation. It also painted that text over the branch column,
hiding the expand triangle of every group heading and sequence row. It is gone; the
panel lets the tree indent normally.

Inputs / outputs are plain dicts and strings suitable for ``QTreeWidgetItem``
construction in ``metadata_panel.py``.

Requirements:
    PySide6 (delegate only); standard library + typing for helpers.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPalette, QPen
from PySide6.QtWidgets import (
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QTreeWidget,
    QTreeWidgetItem,
)

from gui.qt_tree_widget_utils import iter_tree_children

METADATA_VALUE_DISPLAY_MAX_LEN = 50

# Group heading rows carry their bucket key here; nothing else does.
GROUP_HEADER_KEY_ROLE = Qt.ItemDataRole.UserRole + 2

# 0/1 among currently visible non-header rows, resetting at each group.
# Distinct from UserRole (tag key), UserRole+1 (tag dict / export leaf count).
STRIPE_PARITY_ROLE = Qt.ItemDataRole.UserRole + 3

# Heading fill: start at Base mixed toward Text, then step toward black (dark
# theme) or #ffffff (light theme). The 10% Text mix alone sat on the window
# chrome (#1e1e1e / #f0f0f0); the extra step separates the heading from that
# chrome without a new hue.
GROUP_HEADER_FILL_STRENGTH = 0.10
GROUP_HEADER_FILL_TOWARD_EXTREME = 0.65

# 1px top hairline, faintly lighter than the heading fill (toward #ffffff).
# Kept close to the fill so dark-theme lines are less bright and light-theme
# lines stay a soft highlight rather than a dark rule. No bottom rule.
GROUP_HEADER_TOP_RULE_WIDTH = 1.0
GROUP_HEADER_TOP_RULE_LIGHTEN = 0.16
GROUP_HEADER_FONT_SCALE = 1.1


def _palette_mix(palette: QPalette, strength: float) -> QColor:
    """Return Base stepped toward Text by *strength* (0..1)."""
    base = palette.color(QPalette.ColorRole.Base)
    text = palette.color(QPalette.ColorRole.Text)
    step = max(0.0, min(1.0, strength))
    return QColor(
        round(base.red() + (text.red() - base.red()) * step),
        round(base.green() + (text.green() - base.green()) * step),
        round(base.blue() + (text.blue() - base.blue()) * step),
    )


def _mix_colors(start: QColor, end: QColor, strength: float) -> QColor:
    """Return *start* stepped toward *end* by *strength* (0..1)."""
    step = max(0.0, min(1.0, strength))
    return QColor(
        round(start.red() + (end.red() - start.red()) * step),
        round(start.green() + (end.green() - start.green()) * step),
        round(start.blue() + (end.blue() - start.blue()) * step),
    )


def group_header_fill_color(palette: QPalette) -> QColor:
    """Heading band: Phase B mix, then most of the way toward black or #ffffff."""
    current = _palette_mix(palette, GROUP_HEADER_FILL_STRENGTH)
    extreme = (
        QColor(0, 0, 0)
        if palette.color(QPalette.ColorRole.Base).lightness() < 128
        else QColor(255, 255, 255)
    )
    return _mix_colors(current, extreme, GROUP_HEADER_FILL_TOWARD_EXTREME)


def group_header_top_rule_color(palette: QPalette) -> QColor:
    """1px top hairline, faintly lighter than the heading fill."""
    return _mix_colors(
        group_header_fill_color(palette),
        QColor(255, 255, 255),
        GROUP_HEADER_TOP_RULE_LIGHTEN,
    )


def group_header_colors(palette: QPalette) -> tuple[QColor, QColor]:
    """Return (background, foreground) for a group heading row."""
    return (
        group_header_fill_color(palette),
        palette.color(QPalette.ColorRole.Text),
    )


def _row_index(index):
    """Return the column-0 index for *index*'s row (roles live on column 0)."""
    return index.siblingAtColumn(0)


def style_group_header_item(item: QTreeWidgetItem, tree: QTreeWidget) -> None:
    """Apply tokenized fill and a bold relative font bump.

    Row height follows the bold ~10% font bump; no extra padding.
    """
    font = QFont(tree.font())
    font.setBold(True)
    point_size = font.pointSizeF()
    if point_size <= 0:
        point_size = float(font.pointSize() or 12)
    font.setPointSizeF(point_size * GROUP_HEADER_FONT_SCALE)
    item.setFont(0, font)
    background, foreground = group_header_colors(tree.palette())
    item.setBackground(0, background)
    item.setForeground(0, foreground)


def apply_group_header_colors(tree: QTreeWidget) -> None:
    """Push the current theme's heading colors onto every existing heading row."""
    background, foreground = group_header_colors(tree.palette())
    root = tree.invisibleRootItem()
    for item in iter_tree_children(root):
        if item.data(0, GROUP_HEADER_KEY_ROLE) is not None:
            item.setBackground(0, background)
            item.setForeground(0, foreground)


def _walk_visible_descendants(item: QTreeWidgetItem):
    """Yield currently visible descendants (skips hidden; enters expanded only)."""
    for child in iter_tree_children(item):
        if child.isHidden():
            continue
        yield child
        if child.isExpanded():
            yield from _walk_visible_descendants(child)


def assign_group_stripe_parity(tree: QTreeWidget) -> None:
    """
    Assign STRIPE_PARITY_ROLE 0/1 among visible non-header rows, resetting at
    each group. O(n) over the visible tree; paint() only reads the role.
    """
    root = tree.invisibleRootItem()
    for group_item in iter_tree_children(root):
        group_item.setData(0, STRIPE_PARITY_ROLE, None)
        if group_item.isHidden():
            continue
        if not group_item.isExpanded():
            continue
        for parity, child in enumerate(_walk_visible_descendants(group_item)):
            child.setData(0, STRIPE_PARITY_ROLE, parity % 2)


def _index_has_item_background(index) -> bool:
    """True when the row already carries a brush (e.g. edited-tag highlight)."""
    value = index.data(Qt.ItemDataRole.BackgroundRole)
    if value is None:
        return False
    if isinstance(value, QBrush):
        return value.style() != Qt.BrushStyle.NoBrush
    return isinstance(value, QColor)


class MetadataTagTree(QTreeWidget):
    """
    Metadata tag tree whose row backgrounds honor heading fill and per-group
    stripe parity across the full row (indent gutter included).

    ``QStyleSheetStyle`` paints ``PE_PanelItemViewRow`` for the row, then the
    delegate paints each cell. Filling here is what covers the branch column
    and any gap past the last section; the delegate still fills cells so a
    ``::item`` rule cannot leave Name/VR/Value on the pane Base.
    """

    def drawRow(self, painter: QPainter, option: QStyleOptionViewItem, index) -> None:
        row = _row_index(index)
        is_header = row.data(GROUP_HEADER_KEY_ROLE) is not None
        if is_header:
            painter.fillRect(option.rect, group_header_colors(option.palette)[0])
        elif (
            not _index_has_item_background(row)
            and row.data(STRIPE_PARITY_ROLE) == 1
        ):
            painter.fillRect(
                option.rect,
                option.palette.color(QPalette.ColorRole.AlternateBase),
            )
        super().drawRow(painter, option, index)
        if is_header:
            self._paint_header_top_rule(painter, option)


    def _paint_header_top_rule(
        self, painter: QPainter, option: QStyleOptionViewItem
    ) -> None:
        """Draw a 1px lighter top hairline across the full row, including the gutter."""
        fill = group_header_colors(option.palette)[0]
        viewport_width = self.viewport().width()
        painter.fillRect(0, option.rect.bottom(), viewport_width, 1, fill)
        painter.save()
        top_pen = QPen(group_header_top_rule_color(option.palette))
        top_pen.setWidthF(GROUP_HEADER_TOP_RULE_WIDTH)
        painter.setPen(top_pen)
        painter.drawLine(0, option.rect.top(), viewport_width - 1, option.rect.top())
        painter.restore()


class GroupHeaderDelegate(QStyledItemDelegate):
    """
    Heading chrome plus O(1) per-group stripe fills.

    Headings use a palette-mixed fill stepped toward black or #ffffff and a 1px
    lighter top hairline painted in ``drawRow`` so it reaches the pane's left
    edge. Hover/selection are dropped for headings so Qt cannot wash the band
    out. Tag rows with stripe parity 1 fill AlternateBase unless they already
    have an item background (edited highlight). Roles are stored on column 0
    and read via ``siblingAtColumn(0)`` so every cell of the row gets the same
    treatment.
    """

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index) -> None:
        row = _row_index(index)
        if row.data(GROUP_HEADER_KEY_ROLE) is None:
            option = QStyleOptionViewItem(option)
            if (
                not _index_has_item_background(row)
                and row.data(STRIPE_PARITY_ROLE) == 1
            ):
                stripe = option.palette.color(QPalette.ColorRole.AlternateBase)
                painter.fillRect(option.rect, stripe)
            super().paint(painter, option, index)
            return

        option = QStyleOptionViewItem(option)
        option.state &= ~QStyle.StateFlag.State_MouseOver
        option.state &= ~QStyle.StateFlag.State_Selected
        painter.fillRect(option.rect, group_header_colors(option.palette)[0])
        super().paint(painter, option, index)


def metadata_row_depth(tag_data: dict[str, Any]) -> int:
    """
    Return a row's nesting depth.

    Every parser row carries an explicit ``depth``. The default tolerates a
    hand-built dict (tests, synthetic rows), where absence means root-level.
    """
    return tag_data.get("depth", 0)


def metadata_row_parent_key(tag_data: dict[str, Any]) -> str | None:
    """
    Return a row's owning-row key, or ``None`` at the root.

    Absence means "no parent", same as an explicit ``None``.
    """
    return tag_data.get("parent_key")


def metadata_row_kind(tag_data: dict[str, Any]) -> str:
    """
    Return a row's kind: ``"element"``, ``"sequence"``, or ``"item"``.

    Absence defaults to ``"element"`` (a plain scalar row).
    """
    return tag_data.get("row_kind", "element")


def hide_nested_metadata_rows(tags: dict[str, Any]) -> dict[str, Any]:
    """
    Drop every nested (``depth > 0``) row, keeping SQ parents as childless summary
    rows.

    This is how an already-parsed view turns sequence *contents* off without
    re-parsing. ``get_all_tags(include_sequences=False)`` produces the same row set
    directly, and is the right call when the nested rows were never needed.
    """
    return {
        tag_str: tag_data
        for tag_str, tag_data in tags.items()
        if metadata_row_depth(tag_data) == 0
    }


def filter_metadata_tags_by_search(
    tags: dict[str, Any],
    search_text: str,
) -> dict[str, Any]:
    """
    Return tags whose tag number, name, VR, or value contains *search_text*
    (case-insensitive), retaining the full ancestor chain of every match.

    A nested row's sequence/item ancestors are re-added even when they don't
    themselves match, so a matching child stays reachable in a tree built from the
    result. Root-level rows have no ancestors to retain, so for a tree with no
    sequences this degrades to a plain substring filter.
    """
    if not search_text:
        return tags
    search_lower = search_text.lower()
    matched_keys: list[str] = []
    for tag_str, tag_data in tags.items():
        tag_match = tag_str.lower() if tag_str else ""
        name_match = tag_data.get("name", "").lower() if tag_data.get("name") else ""
        vr_match = tag_data.get("VR", "").lower() if tag_data.get("VR") else ""

        value = tag_data.get("value", "")
        if isinstance(value, list):
            value_str = ", ".join(str(v) for v in value)
        else:
            value_str = str(value)
        value_match = value_str.lower()

        if (
            search_lower in tag_match
            or search_lower in name_match
            or search_lower in vr_match
            or search_lower in value_match
        ):
            matched_keys.append(tag_str)

    if not matched_keys:
        return {}

    keep: set[str] = set()
    for tag_str in matched_keys:
        key: str | None = tag_str
        while key is not None and key not in keep:
            keep.add(key)
            key = metadata_row_parent_key(tags.get(key, {}))

    return {tag_str: tag_data for tag_str, tag_data in tags.items() if tag_str in keep}


def group_metadata_tags_sorted(
    tags: dict[str, Any],
) -> list[tuple[str, list[tuple[str, dict[str, Any]]]]]:
    """
    Sort **depth-0** tags by tag string and group by a short prefix ``tag_str[:5]``
    (e.g. ``(0008`` for ``(0008,0016)``).

    Nested rows (``depth > 0`` — sequence items and their contents) are excluded
    here; they hang off their sequence parent instead of getting their own group
    bucket. Use :func:`get_metadata_tag_children` to fetch them.

    Returns:
        Ordered ``(group_key, [(tag_str, tag_data), ...])`` list sorted by group.
    """
    sorted_tags = sorted(tags.items(), key=lambda x: x[0])
    groups: dict[str, list[tuple[str, dict[str, Any]]]] = {}
    for tag_str, tag_data in sorted_tags:
        if metadata_row_depth(tag_data) != 0:
            continue
        group = tag_str[:5]
        if group not in groups:
            groups[group] = []
        groups[group].append((tag_str, tag_data))
    return sorted(groups.items(), key=lambda x: x[0])


def index_metadata_tag_children(
    tags: dict[str, Any],
) -> dict[str | None, list[tuple[str, dict[str, Any]]]]:
    """
    Index every row by its ``parent_key`` in one pass, preserving depth-first
    insertion order (the order ``DICOMParser.get_all_tags`` builds rows in,
    and the order sequence items must be displayed in).

    Callers building a whole tree must use this rather than calling
    :func:`get_metadata_tag_children` per parent: that rescans the full dict for
    each parent, which is O(n²) and costs ~19s on a 24k-row enhanced multi-frame
    study. Indexing once is O(n).
    """
    children: dict[str | None, list[tuple[str, dict[str, Any]]]] = {}
    for tag_str, tag_data in tags.items():
        children.setdefault(metadata_row_parent_key(tag_data), []).append(
            (tag_str, tag_data)
        )
    return children


def get_metadata_tag_children(
    tags: dict[str, Any],
    parent_key: str,
) -> list[tuple[str, dict[str, Any]]]:
    """
    Return the rows whose ``parent_key`` is *parent_key*, in depth-first insertion
    order.

    Convenience for a single lookup. To walk an entire tree, use
    :func:`index_metadata_tag_children` instead — see its note on the O(n²) trap.
    """
    return index_metadata_tag_children(tags).get(parent_key, [])


def format_metadata_value_for_tree(value: Any) -> str:
    """Format a tag value for the Value column, truncating long strings."""
    if isinstance(value, list):
        value_str = ", ".join(str(v) for v in value)
    else:
        value_str = str(value)
    max_len = METADATA_VALUE_DISPLAY_MAX_LEN
    if len(value_str) > max_len:
        value_str = value_str[: max_len - 3] + "..."
    return value_str
