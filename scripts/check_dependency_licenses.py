#!/usr/bin/env python3
"""Dependency license compliance gate.

Scans the Python distributions installed in the active environment and fails if
a *strong copyleft* (GPL/AGPL) dependency appears that is not explicitly
accepted in the policy file. This enforces Phase 6 of
``dev-docs/plans/supporting/LICENSE_AND_COMPLIANCE_PLAN.md``: a closed-source
commercial build must not silently gain a new GPL dependency.

**Single documentation home:** ``dev-docs/info/DEPENDENCY_LICENSE_POLICY.md``.
**Editable policy data:** ``dev-docs/info/dependency_license_policy.json``.

Design notes
------------
- Zero third-party dependencies: uses only the standard library
  (``importlib.metadata``), so it runs in any venv without installing
  ``pip-licenses`` and never touches the network.
- License is resolved per distribution from, in priority order:
  1. the PEP 639 ``License-Expression`` field (an SPDX expression),
  2. ``License :: ...`` trove classifiers,
  3. the free-text ``License`` field (only when short and single-line).
- SPDX expressions are evaluated: ``OR`` picks the least restrictive operand
  (so ``LGPL-3.0-only OR GPL-3.0-only`` reads as LGPL), ``AND`` picks the most
  restrictive. Classifier lists are treated conservatively (most restrictive).

Categories
----------
- ``PERMISSIVE``  MIT, BSD, Apache, ISC, Zlib, PSF, OFL, public domain, ...
- ``OBLIGATION``  weak copyleft (LGPL, MPL, EPL, CDDL) — allowed, but carries
                  notice / relinking obligations (reported, never fails).
- ``FORBIDDEN``   strong copyleft (GPL, AGPL) — fails unless accepted in policy.
- ``UNKNOWN``     license could not be determined — warns (fails only with
                  ``--strict-unknown`` or ``fail_on_unknown`` in policy).

Usage (from repository root)::

    python scripts/check_dependency_licenses.py            # human report
    python scripts/check_dependency_licenses.py --json     # machine output
    python scripts/check_dependency_licenses.py --strict-unknown

Exit code: 0 if compliant, 1 on a policy violation, 2 on a usage/IO error.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from importlib import metadata
from pathlib import Path
from typing import Any

try:
    from scripts.privacy_console import (
        print_license_accepted,
        print_license_obligation,
        print_license_violation,
    )
except ModuleNotFoundError:
    import privacy_console  # pyright: ignore[reportImplicitRelativeImport]

    print_license_accepted = privacy_console.print_license_accepted
    print_license_obligation = privacy_console.print_license_obligation
    print_license_violation = privacy_console.print_license_violation

# Category severity ordering: higher == more restrictive. Used to combine
# operands of SPDX expressions and lists of trove classifiers.
PERMISSIVE = "PERMISSIVE"
OBLIGATION = "OBLIGATION"
UNKNOWN = "UNKNOWN"
FORBIDDEN = "FORBIDDEN"

SEVERITY = {
    PERMISSIVE: 0,
    OBLIGATION: 1,
    UNKNOWN: 2,
    FORBIDDEN: 3,
}

# Ordered classification rules. Order matters: AGPL and LGPL must be tested
# before the bare GPL rule, since all three contain "GPL".
CLASSIFIER_RULES: tuple[tuple[str, str], ...] = (
    (r"AGPL|AFFERO", FORBIDDEN),
    (r"LGPL|LESSER\s+GENERAL\s+PUBLIC", OBLIGATION),
    (r"\bGPL\b|GPL-?V?\d|GENERAL\s+PUBLIC\s+LICENSE", FORBIDDEN),
    (r"MPL|MOZILLA\s+PUBLIC", OBLIGATION),
    (r"\bEPL\b|ECLIPSE\s+PUBLIC", OBLIGATION),
    (r"CDDL|COMMON\s+DEVELOPMENT\s+AND\s+DISTRIBUTION", OBLIGATION),
    (
        r"\bMIT\b|\bBSD\b|APACHE|\bISC\b|ZLIB|0BSD|CC0|UNLICENSE|"
        r"PYTHON\s+SOFTWARE\s+FOUNDATION|PSF|PYTHON-2|MIT-CMU|"
        r"\bOFL\b|OPEN\s+FONT|SIL|HPND|PUBLIC\s+DOMAIN|WTFPL|"
        r"BOOST|\bBSL\b|POSTGRESQL",
        PERMISSIVE,
    ),
)

# Tokens that split an SPDX license expression into operands we evaluate.
_SPDX_OR = re.compile(r"\bOR\b", re.IGNORECASE)
_SPDX_AND = re.compile(r"\bAND\b", re.IGNORECASE)


def normalize_name(name: str) -> str:
    """PEP 503 normalized distribution name (lowercase, runs of -_. -> -)."""
    return re.sub(r"[-_.]+", "-", name).lower()


def classify_token(text: str) -> str:
    """Classify a single license token / free-text fragment into a category."""
    if not text or not text.strip():
        return UNKNOWN
    for pattern, category in CLASSIFIER_RULES:
        if re.search(pattern, text, re.IGNORECASE):
            return category
    return UNKNOWN


def classify_expression(expr: str) -> str:
    """Classify an SPDX-style expression, honoring OR (least restrictive) and
    AND (most restrictive). Falls back to single-token classification."""
    expr = expr.strip().strip("()")
    if not expr:
        return UNKNOWN

    # WITH exceptions (e.g. "GPL-2.0 WITH Classpath-exception"): the exception
    # rarely removes the copyleft obligation for our purposes, so classify the
    # base license (left of WITH) and keep it conservative.
    if re.search(r"\bWITH\b", expr, re.IGNORECASE):
        expr = re.split(r"\bWITH\b", expr, maxsplit=1, flags=re.IGNORECASE)[0]

    if _SPDX_OR.search(expr):
        cats = [classify_expression(part) for part in _SPDX_OR.split(expr)]
        return min(cats, key=lambda c: SEVERITY[c])  # least restrictive wins
    if _SPDX_AND.search(expr):
        cats = [classify_expression(part) for part in _SPDX_AND.split(expr)]
        return max(cats, key=lambda c: SEVERITY[c])  # most restrictive wins
    return classify_token(expr)


def resolve_license(meta: metadata.PackageMetadata) -> tuple[str, str, str]:
    """Return ``(category, raw_license, source)`` for one distribution.

    Sources, in priority order: ``License-Expression`` (SPDX), license trove
    classifiers, then the free-text ``License`` field.
    """
    expr = (meta.get("License-Expression") or "").strip()
    if expr:
        return classify_expression(expr), expr, "expression"

    classifiers = [
        c.split("::")[-1].strip()
        for c in (meta.get_all("Classifier") or [])
        if c.startswith("License")
    ]
    # Drop the uninformative umbrella classifier when a specific one exists.
    specific = [c for c in classifiers if c not in ("OSI Approved",)]
    if specific:
        # Treat multiple classifiers conservatively: most restrictive wins.
        cats = [classify_token(c) for c in specific]
        worst = max(cats, key=lambda c: SEVERITY[c])
        return worst, "; ".join(specific), "classifier"

    raw = (meta.get("License") or "").strip()
    # Free-text License fields are often the full license body or copyright
    # banner — only trust short, single-line values as an identifier.
    if raw and "\n" not in raw and len(raw) <= 60:
        return classify_token(raw), raw, "license-field"

    return UNKNOWN, raw[:60] if raw else "", "none"


def load_policy(path: Path) -> dict[str, Any]:
    """Load policy JSON, falling back to safe built-in defaults if absent."""
    defaults: dict[str, Any] = {
        "forbidden_categories": [FORBIDDEN],
        "fail_on_unknown": False,
        "accepted_exceptions": {},
        "overrides": {},
    }
    if not path.exists():
        return defaults
    try:
        data = json.loads(path.read_text(encoding="utf-8"))  # NOSONAR - path is an explicit --policy CLI arg for this local dev tool, not attacker-controlled input
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit("[license check] failed to read the selected policy") from exc
    merged = {**defaults, **data}
    # Normalize exception / override keys to PEP 503 form for matching.
    merged["accepted_exceptions"] = {
        normalize_name(k): v for k, v in merged.get("accepted_exceptions", {}).items()
    }
    merged["overrides"] = {
        normalize_name(k): v for k, v in merged.get("overrides", {}).items()
    }
    return merged


def scan(policy: dict[str, Any]) -> list[dict[str, Any]]:
    """Classify every installed distribution; return a list of result rows."""
    overrides = policy["overrides"]
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for dist in metadata.distributions():
        meta = dist.metadata
        name = meta["Name"]
        if not name:
            continue
        key = normalize_name(name)
        if key in seen:  # editable installs can appear twice
            continue
        seen.add(key)

        if key in overrides:
            raw = str(overrides[key])
            category, source = classify_expression(raw), "override"
        else:
            category, raw, source = resolve_license(meta)

        rows.append(
            {
                "name": name,
                "key": key,
                "version": meta["Version"] or "?",
                "category": category,
                "license": raw,
                "source": source,
            }
        )
    rows.sort(key=lambda r: r["key"])
    return rows


def evaluate(rows: list[dict[str, Any]], policy: dict[str, Any], strict_unknown: bool) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Split rows into ``(violations, accepted_exception_hits)``."""
    forbidden = set(policy["forbidden_categories"])
    exceptions = policy["accepted_exceptions"]
    fail_unknown = strict_unknown or policy.get("fail_on_unknown", False)

    violations: list[dict[str, Any]] = []
    accepted: list[dict[str, Any]] = []
    for row in rows:
        is_forbidden = row["category"] in forbidden
        is_unknown_fail = fail_unknown and row["category"] == UNKNOWN
        if not (is_forbidden or is_unknown_fail):
            continue
        if row["key"] in exceptions:
            accepted.append({**row, "exception": exceptions[row["key"]]})
        else:
            violations.append(row)
    return violations, accepted


def render_report(rows: list[dict[str, Any]], violations: list[dict[str, Any]], accepted: list[dict[str, Any]], doc_ref: str) -> None:
    counts: dict[str, int] = {}
    for row in rows:
        counts[row["category"]] = counts.get(row["category"], 0) + 1

    print("Dependency license check")
    print("=" * 60)
    print(f"Scanned {len(rows)} installed distributions.")
    summary = "  ".join(
        f"{cat}={counts.get(cat, 0)}"
        for cat in (PERMISSIVE, OBLIGATION, UNKNOWN, FORBIDDEN)
    )
    print(f"  {summary}")
    print()

    obligations = [r for r in rows if r["category"] == OBLIGATION]
    if obligations:
        print(f"Weak copyleft / notice obligations ({len(obligations)}):")
        for r in obligations:
            print_license_obligation(
                package=r.get("name", ""),
                version=r.get("version", ""),
                license_name=r.get("license", ""),
                source=r.get("source", ""),
            )
        print("  (allowed; ensure license notices ship with the distribution)")
        print()

    if accepted:
        print(f"Accepted exceptions ({len(accepted)}):")
        for r in accepted:
            if r.get("category") == UNKNOWN:
                print_license_accepted(
                    "UNKNOWN",
                    package=r.get("name", ""),
                    version=r.get("version", ""),
                    license_name=r.get("license", ""),
                    source=r.get("source", ""),
                )
            else:
                print_license_accepted(
                    "FORBIDDEN",
                    package=r.get("name", ""),
                    version=r.get("version", ""),
                    license_name=r.get("license", ""),
                    source=r.get("source", ""),
                )
        print()

    if violations:
        print(f"POLICY VIOLATIONS ({len(violations)}):")
        for r in violations:
            if r.get("category") == UNKNOWN:
                print_license_violation(
                    "UNKNOWN",
                    package=r.get("name", ""),
                    version=r.get("version", ""),
                    license_name=r.get("license", ""),
                    source=r.get("source", ""),
                )
            else:
                print_license_violation(
                    "FORBIDDEN",
                    package=r.get("name", ""),
                    version=r.get("version", ""),
                    license_name=r.get("license", ""),
                    source=r.get("source", ""),
                )
        print()
        print("A new strong-copyleft (GPL/AGPL) dependency would make a")
        print("closed-source commercial build non-compliant. Either remove it,")
        print("replace it with a permissive/LGPL alternative, or -- if it is")
        print("knowingly accepted -- add it to accepted_exceptions in the policy.")
        _ = doc_ref
        print("See the dependency license policy documentation.")
    else:
        print("OK: no un-accepted strong-copyleft dependencies found.")

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--root", type=Path, default=None, help="Repository root (default: auto-detect from this file).")
    parser.add_argument("--policy", type=Path, default=None, help="Policy JSON path (default: dev-docs/info/dependency_license_policy.json).")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON instead of a text report.")
    parser.add_argument("--strict-unknown", action="store_true", help="Treat UNKNOWN-license packages as violations.")
    args = parser.parse_args(argv)

    root = args.root or Path(__file__).resolve().parent.parent
    policy_path = args.policy or (root / "dev-docs" / "info" / "dependency_license_policy.json")
    doc_ref = "dev-docs/info/DEPENDENCY_LICENSE_POLICY.md"

    policy = load_policy(policy_path)
    rows = scan(policy)
    violations, accepted = evaluate(rows, policy, args.strict_unknown)

    if args.json:
        print(json.dumps(
            {
                "scanned": len(rows),
                "violations": violations,
                "accepted_exceptions": accepted,
                "packages": rows,
            },
            indent=2,
        ))
    else:
        render_report(rows, violations, accepted, doc_ref)

    return 1 if violations else 0


if __name__ == "__main__":
    sys.exit(main())
