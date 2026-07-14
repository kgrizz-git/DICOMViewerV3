"""Helpers for resolving parser path keys back to pydicom datasets."""

from __future__ import annotations

import re

from pydicom.dataset import Dataset
from pydicom.tag import BaseTag
from pydicom.tag import Tag as make_tag

_TAG_PATTERN = r"\(\s*([0-9a-fA-F]{4})\s*,\s*([0-9a-fA-F]{4})\s*\)"
_LEAF_RE = re.compile(rf"^{_TAG_PATTERN}$")
_ITEM_RE = re.compile(rf"^{_TAG_PATTERN}\[(\d+)\]$")


def _tag_from_match(match: re.Match[str]) -> BaseTag:
    return make_tag(int(match.group(1), 16), int(match.group(2), 16))


def resolve_tag_path(dataset: Dataset, path_key: str) -> tuple[Dataset, BaseTag] | None:
    """
    Resolve a parser row key to the dataset containing its final tag.

    Accepted keys are root tags like ``(0010, 0010)`` or nested sequence paths
    like ``(0012, 0064)[0].(0008, 0104)``. Invalid or stale paths return
    ``None`` rather than raising.
    """
    if not isinstance(dataset, Dataset):
        return None
    if not isinstance(path_key, str) or not path_key.strip():
        return None

    segments = path_key.strip().split(".")
    if not segments:
        return None

    current = dataset
    for segment in segments[:-1]:
        match = _ITEM_RE.fullmatch(segment)
        if match is None:
            return None

        tag = _tag_from_match(match)
        index = int(match.group(3))
        if tag not in current:
            return None

        elem = current[tag]
        if getattr(elem, "VR", None) != "SQ":
            return None

        try:
            item = elem.value[index]
        except (IndexError, TypeError):
            return None
        if not isinstance(item, Dataset):
            return None
        current = item

    final_match = _LEAF_RE.fullmatch(segments[-1])
    if final_match is None:
        return None
    return current, _tag_from_match(final_match)
