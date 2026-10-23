#!/usr/bin/env python3
"""Advisory pip-audit gate for the isolated PHI-tooling environment.

``presidio-image-redactor`` caps ``pillow<13.0.0``, so ``requirements-phi-tools.txt``
resolves to Pillow 12.x while the app lock is on 13.0.0. Instead of ignoring
Pillow advisories one ID at a time, this script tolerates exactly one class of
finding: a Pillow advisory, with Pillow installed below 13, whose lowest fix
version is 13.0.0 (so the presidio cap is the only reason it is unfixed).

Everything else fails: other packages, Pillow advisories with no fix or a fix
above 13.0.0, an advisory that is fixable inside 12.x, and Pillow >= 13 being
installed (the exception is stale and should be removed).

Usage: ``audit_phi_tools.py [pip-audit-json-file]``. With no argument it runs
``pip-audit --requirement requirements-phi-tools.txt --format json``.
Exit codes: 0 clean, 1 findings, 2 tool or parse error.
Review the exception by 2026-12-31; see security/pip-audit-exceptions.md.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from packaging.version import InvalidVersion, Version

ROOT = Path(__file__).resolve().parents[1]
REQUIREMENTS = "requirements-phi-tools.txt"
CAP = Version("13.0.0")


class AuditError(Exception):
    """pip-audit could not be run or its output could not be understood."""


def _load(path: str | None) -> dict[str, Any]:
    if path is not None:
        text = Path(path).read_text(encoding="utf-8")
    else:
        try:
            proc = subprocess.run(
                ["pip-audit", "--requirement", REQUIREMENTS, "--format", "json"],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
        except OSError as exc:
            raise AuditError(f"could not run pip-audit: {exc}") from exc
        text = proc.stdout
        if not text.strip():
            raise AuditError(
                f"pip-audit produced no JSON (exit {proc.returncode}): {proc.stderr.strip()}"
            )
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise AuditError(f"malformed pip-audit JSON: {exc}") from exc
    if not isinstance(data, dict) or not isinstance(data.get("dependencies"), list):
        raise AuditError("pip-audit JSON has no 'dependencies' list")
    return data


def _is_tolerated(vuln: dict[str, Any]) -> bool:
    try:
        fixes = [Version(v) for v in vuln.get("fix_versions") or []]
    except InvalidVersion:
        return False
    return bool(fixes) and CAP <= min(fixes) <= CAP


def evaluate(data: dict[str, Any]) -> tuple[list[str], list[str], list[str]]:
    """Return (tolerated IDs, failure messages, skipped names)."""
    tolerated: list[str] = []
    failures: list[str] = []
    skipped: list[str] = []
    seen_pillow = False
    for dep in data["dependencies"]:
        if not isinstance(dep, dict):
            raise AuditError("dependency entry is not an object")
        name = str(dep.get("name", "?"))
        is_pillow = name.lower() == "pillow"
        seen_pillow = seen_pillow or is_pillow
        if is_pillow and "skip_reason" in dep:
            failures.append(
                f"pillow was skipped by pip-audit ({dep['skip_reason']}): "
                "the Pillow rule cannot be applied, so nothing was audited."
            )
            continue
        if "skip_reason" in dep:
            skipped.append(f"{name}: {dep['skip_reason']}")
            continue
        vulns = dep.get("vulns") or []
        if not is_pillow:
            for v in vulns:
                failures.append(
                    _describe(
                        name, dep.get("version"), v, "not covered by the exception"
                    )
                )
            continue
        _evaluate_pillow(dep, vulns, tolerated, failures)
    if not seen_pillow:
        failures.append(
            "pillow is absent from the pip-audit output: the audit covered nothing "
            "it was written to check."
        )
    return tolerated, failures, skipped


def _evaluate_pillow(
    dep: dict[str, Any],
    vulns: list[dict[str, Any]],
    tolerated: list[str],
    failures: list[str],
) -> None:
    """Apply the cap rule to the Pillow entry, appending to the result lists."""
    name = str(dep.get("name", "pillow"))
    try:
        installed = Version(str(dep.get("version")))
    except InvalidVersion as exc:
        raise AuditError(f"bad pillow version {dep.get('version')!r}") from exc
    if installed >= CAP:
        failures.append(
            f"pillow {installed} is installed: the Pillow 12.x exception is stale. "
            "Remove it from scripts/audit_phi_tools.py, ci.yml and "
            "security/pip-audit-exceptions.md."
        )
        for v in vulns:
            failures.append(_describe(name, dep.get("version"), v, "real finding"))
        return
    for v in vulns:
        if _is_tolerated(v):
            tolerated.append(str(v.get("id")))
        else:
            failures.append(
                _describe(
                    name,
                    dep.get("version"),
                    v,
                    "no fix, or a fix other than 13.0.0",
                )
            )


def _describe(name: str, version: object, vuln: dict[str, Any], why: str) -> str:
    return (
        f"{name} {version}: {vuln.get('id')} aliases={vuln.get('aliases', [])} "
        f"fix_versions={vuln.get('fix_versions', [])} ({why})"
    )


def sanitize_message(exc: BaseException) -> str:
    """Return a one-line, length-capped error text (tool diagnostics, no PHI)."""
    return " ".join(str(exc).split())[:500]


def main(argv: list[str]) -> int:
    try:
        tolerated, failures, skipped = evaluate(
            _load(argv[1] if len(argv) > 1 else None)
        )
    except (AuditError, OSError) as exc:
        sys.stderr.write(f"audit_phi_tools: error: {sanitize_message(exc)}\n")
        return 2
    for item in skipped:
        print(f"skipped: {item}")
    if tolerated:
        print(
            f"Tolerated {len(tolerated)} Pillow 12.x advisories fixed in 13.0.0 "
            f"(blocked by the presidio-image-redactor pillow<13 cap): {', '.join(sorted(tolerated))}"
        )
    for failure in failures:
        print(f"FAIL: {failure}")
    if failures:
        return 1
    print("PHI tooling audit clean apart from the tolerated Pillow cap findings.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
