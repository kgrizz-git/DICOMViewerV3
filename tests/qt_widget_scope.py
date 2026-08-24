"""
Destroy Qt top-level widgets created inside a scope.

Tests that build a ``MainWindow`` or ``DICOMViewerApp`` and simply return leave
those windows alive for the rest of the worker process: ``QApplication`` keeps
every top-level widget reachable, so a run accumulates hundreds of them. The
cost is not only memory. Tests that scan ``QApplication.topLevelWidgets()`` or
read global focus/modal state then walk every stale window, and xdist workers
have crashed under the accumulated load (see the pytest-xdist item in
``dev-docs/TO_DO.md``).

Only widgets that appear *during* the scope are destroyed, so widgets owned by
session- or module-scoped fixtures are left untouched.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any


def top_level_widgets() -> list[Any]:
    """Current top-level widgets, or an empty list when Qt is unavailable."""
    from PySide6.QtWidgets import QApplication

    qapp = QApplication.instance()
    return list(qapp.topLevelWidgets()) if qapp is not None else []


def destroy_widgets(widgets: list[Any]) -> None:
    """Close, unparent, and delete ``widgets``, then flush DeferredDelete."""
    from PySide6.QtCore import QEvent
    from PySide6.QtWidgets import QApplication

    qapp = QApplication.instance()
    if qapp is None:
        return
    for widget in widgets:
        try:
            widget.close()
            widget.setParent(None)
            widget.deleteLater()
        except RuntimeError:
            # Qt already destroyed it (a parent took it along); nothing to do.
            pass
    # deleteLater only queues; the posted DeferredDelete events must be
    # delivered before the widgets actually go away.
    qapp.processEvents()
    qapp.sendPostedEvents(None, QEvent.Type.DeferredDelete.value)
    qapp.processEvents()


@contextmanager
def widget_scope() -> Iterator[None]:
    """Destroy any top-level widget created inside the block."""
    # Retain the wrappers as well as their identities until teardown.  Without
    # the strong references, CPython can reclaim a wrapper during the scope and
    # reuse its ``id`` for a newly created widget, causing that widget to be
    # mistaken for a pre-existing one and left alive.
    before_widgets = top_level_widgets()
    before = {id(widget) for widget in before_widgets}
    try:
        yield
    finally:
        destroy_widgets([w for w in top_level_widgets() if id(w) not in before])
