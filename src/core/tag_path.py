"""Compatibility exports for DICOM tag path helpers."""

from __future__ import annotations

from utils.dicom_tag_keys import leaf_tag_from_key
from utils.dicom_tag_path import resolve_tag_path

__all__ = ["leaf_tag_from_key", "resolve_tag_path"]
