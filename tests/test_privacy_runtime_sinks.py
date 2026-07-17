"""Canary tests for protected diagnostic and high-risk DICOM runtime sinks."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

from utils import debug_log as debug_log_module


def _contains_candidate(payload: bytes, candidate: str) -> bool:
    return candidate.encode("utf-8") in payload


def test_opt_in_debug_log_uses_protected_redacted_storage(
    monkeypatch, tmp_path: Path
) -> None:
    protected = tmp_path / "private-diagnostics"
    monkeypatch.setattr(debug_log_module, "_debug_log_enabled", True)
    monkeypatch.setattr(debug_log_module, "_debug_log_path_override", None)
    monkeypatch.setattr(
        debug_log_module,
        "get_private_app_dir",
        lambda _category: protected,
    )

    debug_log_module.debug_log(
        "/Users/runtime-canary/src/loader.py:42",
        "PatientName=RUNTIME-PATIENT-CANARY",
        {
            "filename": "runtime-patient-canary.dcm",
            "study_uid": "2.25.98765432109876543210",
            "ip_address": "10.23.45.67",
        },
    )

    path = protected / "debug.jsonl"
    raw = path.read_text(encoding="utf-8")
    payload = json.loads(raw)
    for canary in (
        "runtime-canary",
        "RUNTIME-PATIENT-CANARY",
        "runtime-patient-canary.dcm",
        "2.25.98765432109876543210",
        "10.23.45.67",
    ):
        assert canary not in raw
    assert payload["data"]["filename"] == "[REDACTED]"
    assert (protected / ".privacy-retention.json").exists()

    debug_log_module.clear_debug_log(path=path)
    assert not path.exists()


def test_disabled_debug_log_has_no_side_effect(monkeypatch, tmp_path: Path) -> None:
    protected = tmp_path / "private-diagnostics"
    monkeypatch.setattr(debug_log_module, "_debug_log_enabled", False)
    monkeypatch.setattr(debug_log_module, "_debug_log_path_override", None)
    monkeypatch.setattr(
        debug_log_module,
        "get_private_app_dir",
        lambda _category: protected,
    )

    debug_log_module.debug_log("location", "message", {"patient_name": "canary"})

    assert not protected.exists()


def test_legacy_environment_cannot_override_persisted_diagnostics_off(
    monkeypatch, tmp_path: Path
) -> None:
    path = tmp_path / "private-diagnostics" / "debug.jsonl"
    monkeypatch.setenv("DICOMVIEWER_DEBUG_LOG", "1")

    debug_log_module.configure_debug_logging(False, path=path)
    debug_log_module.debug_log("location", "message", {"count": 1})

    assert not path.exists()


def test_diagnostics_off_does_not_touch_an_existing_log(tmp_path: Path) -> None:
    path = tmp_path / "private-diagnostics" / "debug.jsonl"
    path.parent.mkdir()
    existing = b"malformed-existing-content\n"
    path.write_bytes(existing)

    debug_log_module.configure_debug_logging(False, path=path)

    assert path.read_bytes() == existing


def test_non_boolean_runtime_diagnostics_enable_fails_closed(tmp_path: Path) -> None:
    path = tmp_path / "private-diagnostics" / "debug.jsonl"

    debug_log_module.configure_debug_logging(cast(Any, "true"), path=path)
    debug_log_module.debug_log("location", "message", {"count": 1})

    assert not path.exists()


def test_nested_arbitrary_diagnostic_free_text_is_absent_from_persisted_jsonl(
    monkeypatch, tmp_path: Path
) -> None:
    protected = tmp_path / "private-diagnostics"
    marker = "-".join(("SYNTHETIC", "FREE", "TEXT", "MARKER"))
    filename = ".".join(("synthetic-sensitive-filename", "dcm"))
    monkeypatch.setattr(debug_log_module, "_debug_log_enabled", True)
    monkeypatch.setattr(debug_log_module, "_debug_log_path_override", None)
    monkeypatch.setattr(
        debug_log_module,
        "get_private_app_dir",
        lambda _category: protected,
    )

    debug_log_module.debug_log(
        "diagnostic:step",
        " ".join(("Synthetic diagnostic event", marker, filename)),
        {
            "operation": "diagnostic.persist",
            "count": 1,
            "nested": {
                "error": " ".join(("failure", marker, filename)),
                marker: filename,
            },
        },
    )

    persisted = (protected / "debug.jsonl").read_bytes()
    payload = json.loads(persisted)
    assert not _contains_candidate(persisted, marker)
    assert not _contains_candidate(persisted, filename)
    assert payload["data"]["operation"] == "diagnostic.persist"
    assert payload["data"]["count"] == 1
    assert payload["data"]["nested"]["error"] == "[REDACTED]"
