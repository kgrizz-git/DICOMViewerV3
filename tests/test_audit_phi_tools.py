"""Unit tests for scripts/audit_phi_tools.py (JSON fixtures, no network)."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

_SPEC = importlib.util.spec_from_file_location(
    "audit_phi_tools",
    Path(__file__).resolve().parents[1] / "scripts" / "audit_phi_tools.py",
)
assert _SPEC is not None and _SPEC.loader is not None
audit = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(audit)


def _vuln(ident: str, fixes: list[str]) -> dict[str, object]:
    return {"id": ident, "fix_versions": fixes, "aliases": [], "description": "x"}


def _run(
    tmp_path: Path, deps: list[dict[str, object]], capsys: pytest.CaptureFixture[str]
) -> tuple[int, str]:
    path = tmp_path / "audit.json"
    path.write_text(json.dumps({"dependencies": deps, "fixes": []}), encoding="utf-8")
    code = audit.main(["audit_phi_tools.py", str(path)])
    return code, capsys.readouterr().out


def test_all_pillow_cap_findings_tolerated(tmp_path, capsys) -> None:
    deps = [
        {
            "name": "pillow",
            "version": "12.3.0",
            "vulns": [_vuln("CVE-1", ["13.0.0"]), _vuln("GHSA-2", ["13.0.0"])],
        }
    ]
    code, out = _run(tmp_path, deps, capsys)
    assert code == 0
    assert "Tolerated 2 Pillow 12.x advisories" in out
    assert "CVE-1" in out


def test_non_pillow_finding_fails(tmp_path, capsys) -> None:
    deps = [
        {"name": "typer", "version": "0.24.1", "vulns": [_vuln("CVE-9", ["13.0.0"])]}
    ]
    code, out = _run(tmp_path, deps, capsys)
    assert code == 1
    assert "CVE-9" in out


def test_pillow_without_fix_fails(tmp_path, capsys) -> None:
    deps = [{"name": "pillow", "version": "12.3.0", "vulns": [_vuln("CVE-3", [])]}]
    code, out = _run(tmp_path, deps, capsys)
    assert code == 1
    assert "CVE-3" in out


def test_pillow_fix_above_cap_fails(tmp_path, capsys) -> None:
    deps = [
        {"name": "pillow", "version": "12.3.0", "vulns": [_vuln("CVE-4", ["13.1.0"])]}
    ]
    code, _ = _run(tmp_path, deps, capsys)
    assert code == 1


def test_pillow_fixable_inside_cap_fails(tmp_path, capsys) -> None:
    deps = [
        {
            "name": "pillow",
            "version": "12.3.0",
            "vulns": [_vuln("CVE-5", ["12.3.1", "13.0.0"])],
        }
    ]
    code, _ = _run(tmp_path, deps, capsys)
    assert code == 1


def test_pillow_13_installed_is_stale(tmp_path, capsys) -> None:
    deps = [{"name": "pillow", "version": "13.0.0", "vulns": []}]
    code, out = _run(tmp_path, deps, capsys)
    assert code == 1
    assert "stale" in out


def test_skipped_dependencies_are_ok(tmp_path, capsys) -> None:
    deps = [
        {"name": "en-core-web-lg", "skip_reason": "Dependency not found on PyPI"},
        {"name": "typer", "version": "0.24.1", "vulns": []},
    ]
    code, out = _run(tmp_path, deps, capsys)
    assert code == 0
    assert "skipped: en-core-web-lg" in out


def test_malformed_json_exits_2(tmp_path, capsys) -> None:
    path = tmp_path / "bad.json"
    path.write_text("{not json", encoding="utf-8")
    assert audit.main(["audit_phi_tools.py", str(path)]) == 2
    assert "malformed" in capsys.readouterr().err


def test_missing_dependencies_key_exits_2(tmp_path, capsys) -> None:
    path = tmp_path / "odd.json"
    path.write_text("{}", encoding="utf-8")
    assert audit.main(["audit_phi_tools.py", str(path)]) == 2
