"""
MainWindow recent-files menu manager (refactor Extraction #4).

Owns the "Recent" submenu rebuild, its right-click context menu (Remove /
Move Up / Move Down), and the "Edit Recent List..." dialog launch. Extracted
from ``gui/main_window.py`` so MainWindow stays a layout + signal surface,
mirroring ``main_window_toast_controller`` and ``main_window_status_controller``.

The context-menu behavior previously lived in ``MainWindow.eventFilter``,
installed via ``main_window.recent_menu.installEventFilter(main_window)`` in
``main_window_menu_builder.py``. This manager is itself a ``QObject`` so it
can install its own event filter directly on the recent-files ``QMenu`` in
its constructor, letting ``MainWindow.eventFilter`` be deleted entirely.

Ownership: the manager is constructed once, inside
``main_window_menu_builder.build_menu_bar``, immediately after the "Recent"
QMenu is created, and stored as ``main_window._recent_files``. MainWindow
keeps thin wrapper methods (``_update_recent_menu``, ``_remove_recent_file``,
``_move_recent_file``, ``_open_edit_recent_list_dialog``, and the public
``update_recent_menu``) that delegate to this manager for backward
compatibility with the menu builder, toolbar builder, ``file_operations_handler``,
and the ``tests/test_main_window_recent_files.py`` characterization tests.

Inputs:
    - ``host``: MainWindow instance (or compatible object) providing
      ``open_recent_file_requested`` (a ``Signal(str)``) to emit when a recent
      entry is chosen, and usable as the QWidget parent for the Edit Recent
      List dialog. Duck-typed (no import of MainWindow or the ``main``
      package) to keep this module a leaf `gui` dependency.
    - ``recent_menu``: the "Recent" QMenu built by ``main_window_menu_builder``.
    - ``config_manager``: ConfigManager providing recent-file persistence
      (get/add/remove/move recent files).

Outputs:
    - Rebuilt QMenu contents, config mutations (remove/move recent files),
      and the Edit Recent List dialog invocation.

Requirements:
    - PySide6 (QObject, QEvent, QAction, QMenu, QContextMenuEvent)
    - gui.dialogs.edit_recent_list_dialog.EditRecentListDialog
"""

from __future__ import annotations

import os

from PySide6.QtCore import QEvent, QObject
from PySide6.QtGui import QAction, QContextMenuEvent
from PySide6.QtWidgets import QMenu

from gui.dialogs.edit_recent_list_dialog import EditRecentListDialog


class MainWindowRecentFilesManager(QObject):
    """Owns the Recent-files QMenu rebuild, its context menu, and edit dialog.

    A ``QObject`` (rather than a plain class) so it can install itself as an
    event filter on ``recent_menu`` to intercept right-click context-menu
    events for individual recent-file entries.
    """

    def __init__(self, host, recent_menu: QMenu, config_manager) -> None:
        """
        Args:
            host: MainWindow instance (or compatible object) exposing
                ``open_recent_file_requested`` (Signal(str)) and usable as a
                QWidget parent for the Edit Recent List dialog.
            recent_menu: The "Recent" QMenu to manage. The manager is parented
                to it, so it is destroyed together with the menu.
            config_manager: ConfigManager instance providing recent-file
                persistence APIs (get/add/remove/move).
        """
        super().__init__(recent_menu)
        self._host = host
        self._recent_menu = recent_menu
        self._config_manager = config_manager
        self._recent_menu.installEventFilter(self)

    @property
    def recent_menu(self) -> QMenu:
        """The managed "Recent" QMenu."""
        return self._recent_menu

    def update(self) -> None:
        """Rebuild the Recent Files submenu with current recent files."""
        menu = self._recent_menu
        if menu is None:
            return
        menu.clear()

        recent_files = self._config_manager.get_recent_files()

        if not recent_files:
            no_recent_action = QAction("No recent files", menu)
            no_recent_action.setEnabled(False)
            menu.addAction(no_recent_action)
        else:
            for file_path in recent_files:
                display_name = os.path.basename(file_path)

                # Handle edge case where basename returns empty string
                # (e.g., root directory, trailing slashes, etc.)
                if not display_name:
                    display_name = file_path
                    if len(display_name) > 50:
                        display_name = display_name[:47] + "..."

                    if not display_name or display_name in (os.path.sep, "/"):
                        display_name = "Folder" if os.path.isdir(file_path) else "File"
                else:
                    if len(display_name) > 50:
                        display_name = display_name[:47] + "..."

                recent_action = QAction(display_name, menu)
                # Store file path in action data for the context-menu event filter.
                recent_action.setData(file_path)
                recent_action.triggered.connect(
                    lambda checked, path=file_path: self._host.open_recent_file_requested.emit(
                        path
                    )
                )
                menu.addAction(recent_action)

    def eventFilter(self, obj, event) -> bool:
        """
        Event filter for handling context-menu events on recent menu items.

        Args:
            obj: Object that received the event.
            event: Event.

        Returns:
            True if event was handled, False otherwise.
        """
        # Only handle events for the recent menu.
        if obj != self._recent_menu:
            return super().eventFilter(obj, event)

        if event.type() == QEvent.Type.ContextMenu:
            context_event = QContextMenuEvent(event)
            action = self._recent_menu.actionAt(
                self._recent_menu.mapFromGlobal(context_event.globalPos())
            )

            # Only show context menu if it's a recent file action (has data).
            if action is not None and action.data():
                file_path = action.data()
                recent_files = self._config_manager.get_recent_files()
                file_idx = recent_files.index(file_path) if file_path in recent_files else -1

                # Parent new actions to recent_menu (a real QMenu/QObject), not
                # context_menu — tests substitute a plain Python fake for
                # QMenu here, which cannot serve as a QObject parent.
                context_menu = QMenu(self._recent_menu)

                move_up_action = QAction("Move Up", self._recent_menu)
                move_up_action.setEnabled(file_idx > 0)
                move_up_action.triggered.connect(
                    lambda checked=False, fp=file_path: self.move(fp, direction="up")
                )
                context_menu.addAction(move_up_action)

                move_down_action = QAction("Move Down", self._recent_menu)
                move_down_action.setEnabled(0 <= file_idx < len(recent_files) - 1)
                move_down_action.triggered.connect(
                    lambda checked=False, fp=file_path: self.move(fp, direction="down")
                )
                context_menu.addAction(move_down_action)

                context_menu.addSeparator()

                remove_action = QAction("Remove", self._recent_menu)
                remove_action.triggered.connect(
                    lambda checked=False, fp=file_path: self.remove(fp)
                )
                context_menu.addAction(remove_action)

                context_menu.exec(context_event.globalPos())
                return True

        return super().eventFilter(obj, event)

    def remove(self, file_path: str) -> None:
        """
        Remove a file from the recent files list.

        Args:
            file_path: Path to file or folder to remove.
        """
        self._config_manager.remove_recent_file(file_path)
        self.update()

    def move(self, file_path: str, direction: str) -> None:
        """
        Move a recent file one position up or down in the recent files list.

        Args:
            file_path: Path of the recent file entry to move.
            direction: "up" to move toward the top, "down" to move toward the bottom.
        """
        if direction == "up":
            self._config_manager.move_recent_file_up(file_path)
        else:
            self._config_manager.move_recent_file_down(file_path)
        self.update()

    def open_edit_dialog(self) -> None:
        """Open the Edit Recent List dialog and refresh the menu afterward."""
        dialog = EditRecentListDialog(self._config_manager, self._host)
        dialog.exec()
        # Update the recent menu after dialog closes (in case items were removed).
        self.update()
