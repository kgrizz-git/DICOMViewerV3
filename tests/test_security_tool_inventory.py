"""Tests for the canonical security/privacy tool inventory validator."""

from __future__ import annotations

import importlib.util
import json
from copy import deepcopy
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_SCRIPT = _ROOT / "scripts" / "check_security_tool_inventory.py"
_spec = importlib.util.spec_from_file_location("check_security_tool_inventory", _SCRIPT)
assert _spec and _spec.loader
inventory = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(inventory)


def _data() -> dict:
    return json.loads((_ROOT / inventory.INVENTORY_PATH).read_text(encoding="utf-8"))


def test_tracked_inventory_is_valid() -> None:
    assert inventory.validate_inventory(_ROOT, _data()) == []


def test_missing_required_tool_is_rejected() -> None:
    data = deepcopy(_data())
    data["tools"] = [tool for tool in data["tools"] if tool["id"] != "gitleaks"]

    errors = inventory.validate_inventory(_ROOT, data)

    assert any("missing required tool ids: gitleaks" in error for error in errors)


def test_missing_referenced_path_is_rejected() -> None:
    data = deepcopy(_data())
    data["tools"][0]["entrypoints"] = ["scripts/not-present.py"]

    errors = inventory.validate_inventory(_ROOT, data)

    assert any("path does not exist" in error for error in errors)


def test_external_upload_services_remain_prohibited() -> None:
    data = deepcopy(_data())
    data["prohibited_external_services"].remove("Codecov")

    errors = inventory.validate_inventory(_ROOT, data)

    assert any("missing prohibited external services: codecov" in error for error in errors)
