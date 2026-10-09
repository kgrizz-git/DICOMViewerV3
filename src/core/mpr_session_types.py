"""MPR session/view value types (pure core, no Qt).

Shared dataclasses and errors for the P1 multiple-MPR-sessions registry
(``core.mpr_session_registry``). Importing ``gui/`` or Qt here is forbidden;
``result``/``lut`` fields stay opaque ``Any`` references held without copying.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

DEFAULT_SESSION_CAP = 8
DEFAULT_VIEW_CAP = 16


class AdmissionError(Exception):
    """Raised when a reservation or creation would exceed a cap."""

    def __init__(self, limit_name: str, current: int, limit: int) -> None:
        self.limit_name = limit_name
        self.current = current
        self.limit = limit
        super().__init__(
            f"MPR {limit_name} limit reached ({current}/{limit}); "
            "discard a session or view before creating another."
        )


class ReservationError(Exception):
    """Raised when confirming an unknown or already-finalized reservation."""


class UnknownSessionError(KeyError):
    """Raised when a session ID is not in the registry."""


class UnknownViewError(KeyError):
    """Raised when a view ID is not in the registry."""


class LinkGroupError(ValueError):
    """Raised for invalid link-group operations (foreign session, etc.)."""


@dataclass
class MprCombineState:
    """Per-view slab-combine settings (copied on duplication, never shared)."""

    enabled: bool = False
    mode: str = "aip"
    slice_count: int = 4


@dataclass
class MprDisplayState:
    """Per-view display settings snapshot contract.

    Plain values only; ``lut`` is an opaque read-only view-LUT reference held
    without copying. Registry copies (``dataclasses.replace``) are shallow by
    design: the LUT keeps its identity across copies and is never deep-copied.
    Treat it as an immutable handle; the registry never mutates through it.
    The controller layer translates to/from live managers.
    """

    window_center: float | None = None
    window_width: float | None = None
    wl_user_modified: bool = False
    use_rescaled: bool = True
    rescale_slope: float | None = None
    rescale_intercept: float | None = None
    rescale_type: str = ""
    inverted: bool = False
    lut: Any = None


@dataclass
class MprSession:
    """One independently built MPR result shared by reference by its views."""

    session_id: int
    creation_seq: int
    source_study_uid: str
    source_series_uid: str
    orientation: str
    result: Any


@dataclass
class MprView:
    """One attached or detached rendering of a session's shared result."""

    view_id: int
    session_id: int
    creation_seq: int
    pane_index: int | None
    slice_index: int = 0
    combine: MprCombineState = field(default_factory=MprCombineState)
    display: MprDisplayState = field(default_factory=MprDisplayState)
    link_group_id: int | None = None


@dataclass
class MprViewSnapshot:
    """Value snapshot of a view's slice/combine/display state (no arrays)."""

    view_id: int
    session_id: int
    slice_index: int
    combine: MprCombineState
    display: MprDisplayState
