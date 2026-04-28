"""
Shim: re-export dialog actions from ``core.actions.dialog_actions``.

``ExportAppFacade`` and smoke tests import ``core.dialog_action_handlers``;
implementations live in ``core.actions.dialog_actions`` to avoid duplication
and keep a stable import path.
"""

from core.actions.dialog_actions import (  # noqa: F401
    open_about_this_file,
    open_export,
    open_overlay_config,
    open_quick_window_level,
    open_slice_sync_dialog,
)
