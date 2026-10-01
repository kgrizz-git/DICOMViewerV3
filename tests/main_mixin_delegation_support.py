"""
Shared scaffolding for the ``main.py`` facade-mixin wiring tests.

The mixins under ``src/main_app_*.py`` are thin Qt-signal seams, so their tests
build a bare mixin instance (no ``__init__``) and assert what the slot forwards.
This module holds the pieces every one of those test modules needs: the mixin
registry, the two case shapes, and the stub/owner-resolution helpers.
"""

from __future__ import annotations

import importlib
from typing import Any, NamedTuple


class HandlerCase(NamedTuple):
    """A mixin method that forwards to a module-level handler function."""

    mixin_class: str
    method: str
    handler: str
    args: tuple[Any, ...]
    kwargs: dict[str, Any] | None = None


class CollaboratorCase(NamedTuple):
    """A mixin method that forwards to a method on a ``self``-held collaborator."""

    mixin_class: str
    method: str
    attribute: str
    target: str
    args: tuple[Any, ...]
    kwargs: dict[str, Any] | None = None
    returns: Any = None


#: mixin_class -> importable module that defines it
MIXIN_MODULES: dict[str, str] = {
    "DisplayProjectionMixin": "main_app_display_settings",
    "SettingsLayoutMixin": "main_app_display_settings",
    "UIHandlersMixin": "main_app_ui_and_files",
    "FileOperationsMixin": "main_app_ui_and_files",
    "TagEditingMixin": "main_app_tag_roi",
    "ROIWorkflowMixin": "main_app_tag_roi",
    "SubwindowManagementMixin": "main_app_subwindow_management",
    "MPRNavigationMixin": "main_app_subwindow_management",
}


def _mixin_class(name: str) -> type:
    """Import and return the mixin class registered under *name*."""
    module = importlib.import_module(MIXIN_MODULES[name])
    return getattr(module, name)


def _resolve_owner(mixin_class_name: str, dotted: str) -> tuple[Any, str]:
    """Walk *dotted* from the mixin module; return ``(owner_object, attribute_name)``."""
    parts = dotted.split(".")
    owner: Any = importlib.import_module(MIXIN_MODULES[mixin_class_name])
    for part in parts[:-1]:
        owner = getattr(owner, part)
    return owner, parts[-1]


def _stub_for(mixin_class_name: str, **attrs: Any) -> Any:
    """Build a bare mixin instance (no ``__init__``) with mock collaborators."""
    mixin = _mixin_class(mixin_class_name)
    stub = mixin.__new__(mixin)
    for name, value in attrs.items():
        setattr(stub, name, value)
    return stub
