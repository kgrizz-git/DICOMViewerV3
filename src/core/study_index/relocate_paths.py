"""
Helpers for study-index relocate: path-prefix checks and DICOM header validation.

``StudyIndexStore.apply_study_path_updates`` applies already-verified path rows;
this module builds that list after ``os.path`` and ``pydicom.dcmread`` checks.
"""

from __future__ import annotations

import os

import pydicom
from pydicom.errors import InvalidDicomError


def path_is_strict_prefix_of_file(old_root: str, file_path: str) -> bool:
    """True when *file_path* is under *old_root* on a path-component boundary."""
    fp = file_path or ""
    try:
        relative_path = os.path.relpath(fp, old_root)
    except ValueError:
        return False
    return relative_path != os.pardir and not relative_path.startswith(os.pardir + os.sep)


def new_file_path_after_relocate(old_root: str, new_root: str, file_path: str) -> str:
    """Return the path under *new_root* mirroring *file_path* under *old_root*."""
    relative_path = os.path.relpath(file_path, old_root)
    return os.path.normpath(os.path.join(new_root, relative_path))


def every_new_path_is_existing_file(new_paths: list[str]) -> bool:
    return all(os.path.isfile(p) for p in new_paths)


def _read_study_and_sop_uids(path: str) -> tuple[str, str] | None:
    try:
        ds = pydicom.dcmread(path, stop_before_pixels=True)
    except (OSError, InvalidDicomError):
        return None
    except Exception:
        return None
    sop = getattr(ds, "SOPInstanceUID", None)
    stu = getattr(ds, "StudyInstanceUID", None)
    if sop is None or stu is None:
        return None
    return (str(sop), str(stu))


def dicom_headers_match_row(
    new_path: str, expected_sop_instance_uid: str, expected_study_uid: str
) -> bool:
    uids = _read_study_and_sop_uids(new_path)
    if uids is None:
        return False
    sop, stu = uids
    exp_sop = (expected_sop_instance_uid or "").strip()
    exp_stu = (expected_study_uid or "").strip()
    if not exp_sop:
        return False
    return sop == exp_sop and stu == exp_stu


def build_relocate_updates_or_none(
    study_uid: str,
    old_root: str,
    new_root: str,
    entries: list[tuple[int, str, str]],
) -> list[tuple[str, str, int]] | None:
    """
    Return ``(file_path, study_root_path, id)`` updates, or ``None`` when relocate must abort.

    *entries* are ``(row_id, file_path, sop_instance_uid)`` for one (study_uid, study_root).
    """
    if not entries:
        return None
    new_paths: list[str] = []
    updates: list[tuple[str, str, int]] = []
    for rid, fp, _sop_uid in entries:
        fp = fp or ""
        if not path_is_strict_prefix_of_file(old_root, fp):
            return None
        new_fp = new_file_path_after_relocate(old_root, new_root, fp)
        new_paths.append(new_fp)
        updates.append((new_fp, new_root, int(rid)))
    if not every_new_path_is_existing_file(new_paths):
        return None
    for i, (_rid, _fp, sop_uid) in enumerate(entries):
        if not dicom_headers_match_row(new_paths[i], sop_uid, study_uid):
            return None
    return updates
