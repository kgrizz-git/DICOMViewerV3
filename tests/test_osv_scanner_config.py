"""Keep osv-scanner.toml, the pip-audit ignores and the exceptions record in sync.

security/pip-audit-exceptions.md is the single source of truth. Every OSV
ignore needs a reason, a future ``ignoreUntil`` and a row there, and every
app-lane row must be suppressed by pip-audit or osv-scanner (or both).
"""

from __future__ import annotations

import datetime as dt
import re
import tomllib
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
OSV_CONFIG = ROOT / "osv-scanner.toml"
EXCEPTIONS = ROOT / "security" / "pip-audit-exceptions.md"
CI_WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"

_ID = re.compile(r"`([A-Z]+-[0-9]{4}-[0-9]+|GHSA-[0-9a-z-]+)`")


def _ignores() -> list[dict]:
    data = tomllib.loads(OSV_CONFIG.read_text(encoding="utf-8"))
    return data.get("IgnoredVulns", [])


def _exception_rows() -> list[tuple[set[str], bool]]:
    """Return (advisory IDs, is_phi_lane) for each row of the exceptions table."""
    rows = []
    for line in EXCEPTIONS.read_text(encoding="utf-8").splitlines():
        if not line.startswith("| `"):
            continue
        advisory_cell = line.split("|")[1]
        ids = set(_ID.findall(advisory_cell))
        if ids:
            rows.append((ids, "PHI-tooling lane" in advisory_cell))
    return rows


def _pip_audit_ignores(job: str) -> set[str]:
    workflow = yaml.safe_load(CI_WORKFLOW.read_text(encoding="utf-8"))
    found: set[str] = set()
    for step in workflow["jobs"][job]["steps"]:
        found |= set(re.findall(r"--ignore-vuln\s+(\S+)", step.get("run", "")))
    return found


def test_exceptions_table_is_parsed() -> None:
    rows = _exception_rows()
    assert any(not phi for _, phi in rows), "no app-lane rows found"
    assert any(phi for _, phi in rows), "no PHI-lane rows found"


def test_osv_ignores_have_reason_and_future_expiry() -> None:
    ignores = _ignores()
    assert ignores, "osv-scanner.toml has no ignores; delete this check deliberately"
    today = dt.date.today()
    for entry in ignores:
        ident = entry.get("id")
        assert ident, f"ignore without id: {entry}"
        assert str(entry.get("reason", "")).strip(), f"{ident}: missing reason"
        until = entry.get("ignoreUntil")
        assert until is not None, f"{ident}: missing ignoreUntil"
        assert isinstance(until, dt.date), f"{ident}: ignoreUntil must be a TOML date"
        assert until >= today, f"{ident}: ignoreUntil {until} is in the past"


def test_osv_ignores_have_a_row_in_the_exceptions_record() -> None:
    recorded = set().union(*(ids for ids, _ in _exception_rows()))
    for entry in _ignores():
        assert entry["id"] in recorded, (
            f"{entry['id']} has no row in security/pip-audit-exceptions.md"
        )


def test_osv_ignores_are_app_lane_only() -> None:
    phi_only = set().union(*(ids for ids, phi in _exception_rows() if phi))
    for entry in _ignores():
        assert entry["id"] not in phi_only, f"{entry['id']} is a PHI-lane exception"


def test_every_app_lane_exception_is_suppressed_by_a_scanner() -> None:
    suppressed = _pip_audit_ignores("pip-audit") | {e["id"] for e in _ignores()}
    for ids, phi in _exception_rows():
        if phi:
            continue
        assert ids & suppressed, (
            f"app-lane exception {sorted(ids)} is in neither the ci.yml pip-audit "
            "--ignore-vuln list nor osv-scanner.toml"
        )


def test_app_pip_audit_ignores_are_recorded() -> None:
    recorded = set().union(*(ids for ids, _ in _exception_rows()))
    for ident in _pip_audit_ignores("pip-audit"):
        assert ident in recorded, f"{ident} has no row in pip-audit-exceptions.md"
