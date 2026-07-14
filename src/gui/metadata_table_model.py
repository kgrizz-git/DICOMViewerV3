"""
Metadata panel — group-heading delegate and pure tag-list helpers.

``MetadataPanel`` uses a ``QTreeWidget`` (historical plan wording referenced a
“table model”; there is no ``QAbstractTableModel`` here). This module holds:

- ``GroupHeaderDelegate`` — keeps a heading's colored band under hover/selection.
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
from PySide6.QtGui import QColor, QPainter, QPalette, QPen
from PySide6.QtWidgets import QStyle, QStyledItemDelegate, QStyleOptionViewItem

METADATA_VALUE_DISPLAY_MAX_LEN = 50

# Group heading rows carry their bucket key here; nothing else does.
GROUP_HEADER_KEY_ROLE = Qt.ItemDataRole.UserRole + 2

# How far from the tree's Base toward its Text the heading rules sit. Derived rather than
# hardcoded so the rules land on the correct side of the contrast in either theme.
GROUP_HEADER_RULE_STRENGTH = 0.38


def group_header_rule_color(palette: QPalette) -> QColor:
    """Color of the rules above and below a group heading: Base stepped toward Text."""
    base = palette.color(QPalette.ColorRole.Base)
    text = palette.color(QPalette.ColorRole.Text)
    step = GROUP_HEADER_RULE_STRENGTH
    return QColor(
        round(base.red() + (text.red() - base.red()) * step),
        round(base.green() + (text.green() - base.green()) * step),
        round(base.blue() + (text.blue() - base.blue()) * step),
    )


class GroupHeaderDelegate(QStyledItemDelegate):
    """
    Rule off group headings, and keep them out of hover/selection.

    A heading takes the tree's own background — no fill of its own — so what separates it
    from the rows around it is a horizontal rule at its top and bottom. That works whether
    the group is expanded (rules bracket its tag rows) or collapsed (consecutive headings
    still read as separate bands, which a fill-free heading otherwise would not).

    Hover and selection are dropped for headings: Qt paints those highlights *over* an
    item's background, which previously washed a heading's fill out to a pale block while
    leaving its text color untouched — unreadable on a light theme. Headings are
    structure, not selectable content. Every other row paints normally.
    """

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index) -> None:
        if index.data(GROUP_HEADER_KEY_ROLE) is None:
            super().paint(painter, option, index)
            return

        option = QStyleOptionViewItem(option)
        option.state &= ~QStyle.StateFlag.State_MouseOver
        option.state &= ~QStyle.StateFlag.State_Selected
        super().paint(painter, option, index)

        painter.save()
        painter.setPen(QPen(group_header_rule_color(option.palette)))
        rect = option.rect
        painter.drawLine(rect.left(), rect.top(), rect.right(), rect.top())
        painter.drawLine(rect.left(), rect.bottom(), rect.right(), rect.bottom())
        painter.restore()


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
