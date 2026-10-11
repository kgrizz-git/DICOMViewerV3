"""Versioned drag payload for MPR navigator tiles (pure core, no Qt).

One schema carries a stable view ID, an operation and a drag-origin token
across the navigator tile, the drop target, and the app dispatcher. The
payload is a small JSON object
``{"v": 1, "op": "move", "view": <view_id>, "origin": "<token>"}`` under its
own MIME type.

There is deliberately no pane index in the payload. A pane index can name a
different view by drop time (the pane may have been cleared or replaced);
a view ID keeps meaning "that view" or resolves to nothing. The earlier
bare-integer ``application/x-dv3-mpr-assign`` MIME was ambiguous (pane index
vs. negative detached key) and is no longer produced or accepted.

View IDs are only unique within one controller, and every controller starts
at view 1. A drag from another running instance (or another controller)
could therefore name a view ID that exists here. The origin token closes
that: each controller owns one random, opaque token (``new_drag_origin``,
generated once per controller, never reset, never derived from patient or
study data) and the destination dispatcher rejects any payload whose origin
is not its own. View IDs are monotonic within a controller and the token is
not regenerated, so IDs are never reused under the same token.

Decoding is strict and bounded: oversized, malformed, wrong-version,
unknown-operation, extra-key, missing or malformed origin, or
non-positive/non-integer IDs all decode to ``None`` and callers treat that as
a no-op.
"""

from __future__ import annotations

import json
import re
import secrets
from dataclasses import dataclass

MPR_VIEW_MIME = "application/x-dv3-mpr-view"
SCHEMA_VERSION = 1
MAX_PAYLOAD_BYTES = 128
MAX_VIEW_ID = 2**31 - 1

#: Move an attached view to another pane, or attach a detached view.
OP_MOVE = "move"
_OPERATIONS = frozenset({OP_MOVE})
_KEYS = frozenset({"v", "op", "view", "origin"})
#: URL-safe token alphabet and length bounds (``secrets.token_urlsafe(16)`` is 22 chars).
_ORIGIN_RE = re.compile(r"[A-Za-z0-9_-]{16,32}")


@dataclass(frozen=True)
class ViewDragPayload:
    """A decoded, validated drag request."""

    view_id: int
    operation: str
    origin: str


def new_drag_origin() -> str:
    """A fresh random opaque token for one controller (128 bits, URL-safe, no content)."""
    return secrets.token_urlsafe(16)


def same_origin(candidate: str, own: str) -> bool:
    """Constant-time comparison of a payload origin against this controller's token."""
    return secrets.compare_digest(candidate.encode("ascii"), own.encode("ascii"))


def _valid_origin(value: object) -> bool:
    return isinstance(value, str) and _ORIGIN_RE.fullmatch(value) is not None


def _valid_view_id(value: object) -> bool:
    return type(value) is int and 1 <= value <= MAX_VIEW_ID


def encode_view_drag(view_id: int, origin: str, operation: str = OP_MOVE) -> bytes:
    """ASCII payload for *view_id*; raises ValueError for an invalid ID, origin or operation."""
    if not _valid_view_id(view_id):
        raise ValueError(f"invalid view id: {view_id!r}")
    if not _valid_origin(origin):
        raise ValueError("invalid drag origin token")
    if operation not in _OPERATIONS:
        raise ValueError(f"unknown drag operation: {operation!r}")
    body = {"v": SCHEMA_VERSION, "op": operation, "view": view_id, "origin": origin}
    return json.dumps(body, separators=(",", ":"), sort_keys=True).encode("ascii")


def decode_view_drag(raw: object) -> ViewDragPayload | None:
    """Validated payload, or None for anything malformed, oversized or foreign."""
    if not isinstance(raw, (bytes, bytearray, memoryview)):
        return None
    if len(raw) > MAX_PAYLOAD_BYTES:
        return None
    try:
        body = json.loads(bytes(raw).decode("ascii"))
    except (UnicodeDecodeError, ValueError):
        return None
    if not isinstance(body, dict) or body.keys() != _KEYS:
        return None
    if type(body["v"]) is not int or body["v"] != SCHEMA_VERSION:
        return None
    operation = body["op"]
    if not isinstance(operation, str) or operation not in _OPERATIONS:
        return None
    if not _valid_view_id(body["view"]) or not _valid_origin(body["origin"]):
        return None
    return ViewDragPayload(view_id=body["view"], operation=operation, origin=body["origin"])


__all__ = [
    "MAX_PAYLOAD_BYTES",
    "MAX_VIEW_ID",
    "MPR_VIEW_MIME",
    "OP_MOVE",
    "SCHEMA_VERSION",
    "ViewDragPayload",
    "decode_view_drag",
    "encode_view_drag",
    "new_drag_origin",
    "same_origin",
]
