"""
Metadata panel — tree delegate and pure tag-list helpers (Phase 5D).

``MetadataPanel`` uses a ``QTreeWidget`` (historical plan wording referenced a
“table model”; there is no ``QAbstractTableModel`` here). This module holds:

- ``MetadataItemDelegate`` — column/indent painting for group vs tag rows.
- Pure functions to filter, group, and format tag dicts when building tree items.

Inputs / outputs are plain dicts and strings suitable for ``QTreeWidgetItem``
construction in ``metadata_panel.py``.

Requirements:
    PySide6 (delegate only); standard library + typing for helpers.
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

from PySide6.QtWidgets import QStyledItemDelegate, QStyleOptionViewItem, QTreeWidget
from PySide6.QtGui import QPainter

METADATA_VALUE_DISPLAY_MAX_LEN = 50


class MetadataItemDelegate(QStyledItemDelegate):
    """
    Custom delegate for metadata panel tree widget.

    Handles indentation rendering:

    - Group items: keep tree indentation.
    - Tag items: remove indentation in the first column so tags align left.
    - Other columns render normally.
    """

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index) -> None:
        tree_widget = option.widget
        if tree_widget is None or not isinstance(tree_widget, QTreeWidget):
            super().paint(painter, option, index)
            return

        item = tree_widget.itemFromIndex(index)
        if item is None:
            super().paint(painter, option, index)
            return

        parent = item.parent()
        is_tag_item = parent is not None and parent.text(0).startswith("Group ")
        is_first_column = index.column() == 0

        if is_tag_item and is_first_column:
            base_indent = tree_widget.indentation()
            adjusted_option = QStyleOptionViewItem(option)
            current_left = adjusted_option.rect.left()
            if current_left >= base_indent:
                adjusted_option.rect.setLeft(current_left - base_indent)
                adjusted_option.rect.setWidth(adjusted_option.rect.width() + base_indent)
            super().paint(painter, adjusted_option, index)
        else:
            super().paint(painter, option, index)


def filter_metadata_tags_by_search(
    tags: Dict[str, Any],
    search_text: str,
) -> Dict[str, Any]:
    """Return tags whose tag number, name, VR, or value contains *search_text* (case-insensitive)."""
    if not search_text:
        return tags
    search_lower = search_text.lower()
    filtered_tags: Dict[str, Any] = {}
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
            filtered_tags[tag_str] = tag_data
    return filtered_tags


def group_metadata_tags_sorted(
    tags: Dict[str, Any],
) -> List[Tuple[str, List[Tuple[str, Dict[str, Any]]]]]:
    """
    Sort tags by tag string and group by a short prefix ``tag_str[:5]`` (e.g.
    ``(0008`` for ``(0008,0016)``).

    Returns:
        Ordered ``(group_key, [(tag_str, tag_data), ...])`` list sorted by group.
    """
    sorted_tags = sorted(tags.items(), key=lambda x: x[0])
    groups: Dict[str, List[Tuple[str, Dict[str, Any]]]] = {}
    for tag_str, tag_data in sorted_tags:
        group = tag_str[:5]
        if group not in groups:
            groups[group] = []
        groups[group].append((tag_str, tag_data))
    return sorted(groups.items(), key=lambda x: x[0])


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
