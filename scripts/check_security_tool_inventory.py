#!/usr/bin/env python3
"""Validate the canonical repository security/privacy tool inventory."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

try:
    from scripts.privacy_console import print_redacted
except ModuleNotFoundError:
    from privacy_console import print_redacted

INVENTORY_PATH = Path("security/security-tool-inventory.json")
REQUIRED_TOOL_IDS = frozenset(
    {
        "basedpyright",
        "detect-secrets",
        "dicom-phi-scan",
        "direnv",
        "docker",
        "easyocr",
        "exiftool",
        "gitleaks",
        "grype",
        "hounddog",
        "lizard",
        "phi-scan",
        "pip-audit",
        "pip-licenses",
        "presidio-analyzer",
        "presidio-image-redactor",
        "pytest-cov",
        "ruff",
        "semgrep",
        "sonar-scanner-cli",
        "sonarqube-community-build",
        "spacy",
        "tesseract",
        "trufflehog",
    }
)
REQUIRED_CONTROL_IDS = frozenset(
    {
        "commit-message-privacy-gate",
        "conditional-privacy-reviews",
        "local-sonarqube-runner",
        "phi-artifact-gate",
        "privacy-output-gate",
        "remote-privacy-preflight",
        "security-scan-runner",
        "tool-inventory-validator",
    }
)
REQUIRED_PROHIBITED_SERVICES = frozenset(
    {"codecov", "coveralls", "deepsource", "sentry", "sonarcloud"}
)
REQUIRED_TOOL_FIELDS = frozenset(
    {
        "id",
        "category",
        "purpose",
        "install_scope",
        "install_reference",
        "tested_version",
        "enforcement",
        "network_policy",
        "entrypoints",
        "tracked_configuration",
    }
)
SAFE_ID = re.compile(r"^[a-z0-9][a-z0-9-]*$")


def _duplicates(values: list[str]) -> list[str]:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for value in values:
        if value in seen:
            duplicates.add(value)
        seen.add(value)
    return sorted(duplicates)


def _tracked_path_errors(
    repo_root: Path, tool_id: str, field: str, values: Any
) -> list[str]:
    if not isinstance(values, list) or not all(
        isinstance(value, str) and value for value in values
    ):
        return [f"{tool_id}: {field} must be a list of non-empty strings"]
    errors: list[str] = []
    for value in values:
        path = Path(value)
        if path.is_absolute() or ".." in path.parts:
            errors.append(f"{tool_id}: {field} contains unsafe path: {value}")
        elif not (repo_root / path).exists():
            errors.append(f"{tool_id}: {field} path does not exist: {value}")
    return errors


def validate_inventory(repo_root: Path, data: Any) -> list[str]:
    """Return schema, coverage, and referenced-path errors."""
    if not isinstance(data, dict):
        return ["inventory root must be a JSON object"]
    errors: list[str] = []
    if data.get("schema_version") != 1:
        errors.append("schema_version must be 1")

    tools = data.get("tools")
    if not isinstance(tools, list):
        return [*errors, "tools must be a list"]
    ids: list[str] = []
    for index, tool in enumerate(tools):
        if not isinstance(tool, dict):
            errors.append(f"tools[{index}] must be an object")
            continue
        missing = sorted(REQUIRED_TOOL_FIELDS - tool.keys())
        tool_id = tool.get("id", f"tools[{index}]")
        if missing:
            errors.append(f"{tool_id}: missing fields: {', '.join(missing)}")
        if not isinstance(tool_id, str) or not SAFE_ID.fullmatch(tool_id):
            errors.append(f"tools[{index}]: invalid id")
            continue
        ids.append(tool_id)
        for field in (
            "category",
            "purpose",
            "install_scope",
            "install_reference",
            "tested_version",
            "network_policy",
        ):
            if not isinstance(tool.get(field), str) or not tool[field].strip():
                errors.append(f"{tool_id}: {field} must be a non-empty string")
        enforcement = tool.get("enforcement")
        if not isinstance(enforcement, list) or not enforcement or not all(
            isinstance(item, str) and item for item in enforcement
        ):
            errors.append(f"{tool_id}: enforcement must be a non-empty string list")
        errors.extend(
            _tracked_path_errors(repo_root, tool_id, "entrypoints", tool.get("entrypoints"))
        )
        errors.extend(
            _tracked_path_errors(
                repo_root,
                tool_id,
                "tracked_configuration",
                tool.get("tracked_configuration"),
            )
        )
        install_reference = tool.get("install_reference")
        if isinstance(install_reference, str):
            errors.extend(
                _tracked_path_errors(
                    repo_root, tool_id, "install_reference", [install_reference]
                )
            )

    for duplicate in _duplicates(ids):
        errors.append(f"duplicate tool id: {duplicate}")
    missing_tools = sorted(REQUIRED_TOOL_IDS - set(ids))
    if missing_tools:
        errors.append(f"missing required tool ids: {', '.join(missing_tools)}")

    controls = data.get("repository_controls")
    if not isinstance(controls, list):
        errors.append("repository_controls must be a list")
    else:
        control_ids: list[str] = []
        for index, control in enumerate(controls):
            if not isinstance(control, dict):
                errors.append(f"repository_controls[{index}] must be an object")
                continue
            control_id = control.get("id")
            path = control.get("path")
            role = control.get("role")
            if not isinstance(control_id, str) or not SAFE_ID.fullmatch(control_id):
                errors.append(f"repository_controls[{index}]: invalid id")
                continue
            control_ids.append(control_id)
            if not isinstance(role, str) or not role.strip():
                errors.append(f"{control_id}: role must be a non-empty string")
            errors.extend(
                _tracked_path_errors(repo_root, control_id, "path", [path])
                if isinstance(path, str)
                else [f"{control_id}: path must be a string"]
            )
        for duplicate in _duplicates(control_ids):
            errors.append(f"duplicate repository control id: {duplicate}")
        missing_controls = sorted(REQUIRED_CONTROL_IDS - set(control_ids))
        if missing_controls:
            errors.append(
                f"missing required repository control ids: {', '.join(missing_controls)}"
            )

    services = data.get("prohibited_external_services")
    if not isinstance(services, list) or not all(
        isinstance(service, str) for service in services
    ):
        errors.append("prohibited_external_services must be a string list")
    else:
        normalized = {service.casefold() for service in services}
        missing_services = sorted(REQUIRED_PROHIBITED_SERVICES - normalized)
        if missing_services:
            errors.append(
                "missing prohibited external services: " + ", ".join(missing_services)
            )
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parent.parent,
        help="Repository root",
    )
    args = parser.parse_args()
    repo_root = args.root.resolve()
    inventory_path = repo_root / INVENTORY_PATH
    try:
        data = json.loads(inventory_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print_redacted(f"Tool inventory check failed: {exc}", file=sys.stderr)
        return 1
    errors = validate_inventory(repo_root, data)
    if errors:
        print("Tool inventory check failed:", file=sys.stderr)
        for error in errors:
            print_redacted(f"  {error}", file=sys.stderr)
        return 1
    print(
        "OK: security/privacy tool inventory "
        f"({len(data['tools'])} tools, {len(data['models'])} models, "
        f"{len(data['repository_controls'])} repository controls)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
