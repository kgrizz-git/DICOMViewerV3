"""
Safe traversal helpers for ``QTreeWidgetItem`` trees.

PySide6 6.11.2+ stubs type ``child()`` and ``parent()`` as optional because the
Qt C++ API can return null. These helpers skip null slots without asserting.

Inputs:
    - Parent ``QTreeWidgetItem`` nodes from any tree widget in the app

Outputs:
    - Iterators of non-null direct children

Requirements:
    - PySide6.QtWidgets.QTreeWidgetItem
"""

from __future__ import annotations

from collections.abc import Iterator

from PySide6.QtWidgets import QTreeWidgetItem


def iter_tree_children(parent: QTreeWidgetItem) -> Iterator[QTreeWidgetItem]:
    """Yield each non-null direct child of *parent*."""
    for index in range(parent.childCount()):
        child = parent.child(index)
        if child is not None:
            yield child
