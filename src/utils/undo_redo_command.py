"""
Abstract command base for the undo/redo stack.

Lives in a tiny module so ``undo_redo_tag_commands`` can import ``Command``
without creating an import cycle with ``utils.undo_redo`` (which re-exports
``TagEditCommand`` from the tag-command module at load time).
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class Command(ABC):
    """Single undoable user action."""

    @abstractmethod
    def execute(self) -> None:
        """Apply the command."""

    @abstractmethod
    def undo(self) -> None:
        """Revert the command."""
