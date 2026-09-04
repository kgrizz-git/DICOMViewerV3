"""
Load committed ACR ``results_data`` dumps (P0-T1 / R0-9) and prove flatten
families (P1-F4 / G2).

No live ``analyze()``, no DICOM pixels. Assertions use key names and counts
only — never dump matched string values (paths, UIDs, identifiers).
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any

from qa.analysis_types import QAResult
from qa.qa_result_flatten import build_metric_rows, build_run_provenance

_FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "qa"
_CT_DUMP = _FIXTURES / "acr_ct_results_data.json"
_MRI_DUMP = _FIXTURES / "acr_mri_results_data.json"

_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "pylinac_spike_common.py"
_SPEC = importlib.util.spec_from_file_location("pylinac_spike_common", _SCRIPT)
assert _SPEC is not None and _SPEC.loader is not None
_common = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_common)

_looks_like_absolute_path = _common._looks_like_absolute_path
_is_dump_drop_key = _common._is_dump_drop_key

_UID_LIKE = _common._UID_LIKE

_CT_TOP_KEYS = frozenset(
    {
        "ct_module",
        "date_of_analysis",
        "low_contrast_module",
        "num_images",
        "origin_slice",
        "phantom_model",
        "phantom_roll_deg",
        "pylinac_version",
        "spatial_resolution_module",
        "uniformity_module",
        "warnings",
    }
)
_MRI_TOP_KEYS = frozenset(
    {
        "date_of_analysis",
        "geometric_distortion_module",
        "low_contrast_multi_slice_module",
        "num_images",
        "origin_slice",
        "phantom_model",
        "phantom_roll_deg",
        "pylinac_version",
        "sagittal_localizer_module",
        "slice1",
        "slice11",
        "uniformity_module",
        "warnings",
    }
)

# G2: ≥1 flatten key per family present on the committed dumps.
_CT_FAMILY_PREFIXES = (
    "ct_module.rois.",
    "uniformity_module.rois.",
    "low_contrast_module.",
    "spatial_resolution_module.",
    "phantom_roll_deg",
    "origin_slice",
    "num_images",
)
_MRI_FAMILY_PREFIXES = (
    "slice1.measured_slice_thickness_mm",
    "slice1.slice_shift_mm",
    "slice1.row_mtf_50",
    "slice1.col_mtf_50",
    "slice1.row_mtf_lp_mm.",
    "uniformity_module.piu",
    "uniformity_module.psg",
    "geometric_distortion_module.distances.",
    "low_contrast_multi_slice_module.score",
    "slice11.",
    "phantom_roll_deg",
)


def _load_dump(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


def _walk(obj: Any, path: str = "$") -> list[tuple[str, Any]]:
    leaves: list[tuple[str, Any]] = []
    if isinstance(obj, dict):
        for key, value in obj.items():
            leaves.extend(_walk(value, f"{path}.{key}"))
    elif isinstance(obj, list):
        for index, value in enumerate(obj):
            leaves.extend(_walk(value, f"{path}[{index}]"))
    else:
        leaves.append((path, obj))
    return leaves


def _has_prefix(keys: list[str], prefix: str) -> bool:
    if prefix.endswith("."):
        return any(key.startswith(prefix) for key in keys)
    return prefix in keys


def _assert_dump_hygiene(payload: dict[str, Any]) -> None:
    """Fail on dropped keys / absolute paths / UID-like strings; report paths only."""
    dropped_key_paths: list[str] = []
    abs_path_locations: list[str] = []
    uid_locations: list[str] = []
    for json_path, value in _walk(payload):
        leaf = json_path.rsplit(".", 1)[-1]
        if _is_dump_drop_key(leaf):
            dropped_key_paths.append(json_path)
        if isinstance(value, str):
            if _looks_like_absolute_path(value) or value.startswith("/Users/") or ":\\" in value:
                abs_path_locations.append(json_path)
            if _UID_LIKE.search(value):
                uid_locations.append(json_path)
    assert dropped_key_paths == []
    assert abs_path_locations == []
    assert uid_locations == []


def test_ct_dump_shape_and_hygiene() -> None:
    payload = _load_dump(_CT_DUMP)
    assert frozenset(payload) == _CT_TOP_KEYS
    assert isinstance(payload["phantom_model"], str) and payload["phantom_model"]
    assert isinstance(payload["pylinac_version"], str) and payload["pylinac_version"]
    assert isinstance(payload["warnings"], list)
    _assert_dump_hygiene(payload)


def test_mri_dump_shape_and_hygiene() -> None:
    payload = _load_dump(_MRI_DUMP)
    assert frozenset(payload) == _MRI_TOP_KEYS
    assert isinstance(payload["phantom_model"], str) and payload["phantom_model"]
    assert isinstance(payload["pylinac_version"], str) and payload["pylinac_version"]
    assert isinstance(payload["warnings"], list)
    # T1-only axial dump still emits the sagittal module as empty dicts.
    sagittal = payload["sagittal_localizer_module"]
    assert isinstance(sagittal, dict)
    _assert_dump_hygiene(payload)


def test_ct_flatten_includes_present_families() -> None:
    payload = _load_dump(_CT_DUMP)
    keys = [key for key, _ in build_metric_rows(
        QAResult(success=True, analysis_type="acr_ct", raw_pylinac=payload)
    )]
    missing = [prefix for prefix in _CT_FAMILY_PREFIXES if not _has_prefix(keys, prefix)]
    assert missing == []
    assert "warnings" not in keys


def test_mri_flatten_includes_present_families() -> None:
    payload = _load_dump(_MRI_DUMP)
    keys = [key for key, _ in build_metric_rows(
        QAResult(success=True, analysis_type="acr_mri_large", raw_pylinac=payload)
    )]
    missing = [prefix for prefix in _MRI_FAMILY_PREFIXES if not _has_prefix(keys, prefix)]
    assert missing == []
    assert "warnings" not in keys
    # Empty sagittal dicts must not invent flatten leaves.
    assert not any(key.startswith("sagittal_localizer_module.") for key in keys)


def test_golden_dump_failed_run_still_returns_provenance() -> None:
    result = QAResult(
        success=False,
        analysis_type="acr_ct",
        errors=["physical scan extent does not cover the extent of module configuration"],
        raw_pylinac={},
        warnings=[],
    )
    assert build_metric_rows(result) == []
    provenance = build_run_provenance(result)
    assert provenance["success"] is False
    assert provenance["warnings"] == []
    assert len(provenance["errors"]) == 1
