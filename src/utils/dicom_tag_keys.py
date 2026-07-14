"""Parsing helpers for DICOM tag display keys."""

from __future__ import annotations

import re

from pydicom.tag import BaseTag
from pydicom.tag import Tag as make_tag

_TAG_PATTERN = r"\(\s*([0-9a-fA-F]{4})\s*,\s*([0-9a-fA-F]{4})\s*\)"
_LEAF_RE = re.compile(rf"^{_TAG_PATTERN}$")


def leaf_tag_from_key(path_key: str) -> BaseTag | None:
    """Return the final tag from a root or nested parser key, if valid."""
    if not isinstance(path_key, str) or not path_key.strip():
        return None

    leaf_segment = path_key.strip().split(".")[-1]
    match = _LEAF_RE.fullmatch(leaf_segment)
    if match is None:
        return None
    return make_tag(int(match.group(1), 16), int(match.group(2), 16))
