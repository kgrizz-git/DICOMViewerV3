#!/usr/bin/env python3
"""Generate the third-party attribution SBOM (``THIRD_PARTY_LICENSES.md``).

This is the *attribution* artifact required by Phases 3a/5 of
``dev-docs/plans/supporting/LICENSE_AND_COMPLIANCE_PLAN.md``. It is a different
concern from the pre-commit **license gate**
(``scripts/check_dependency_licenses.py``), which is stdlib-only and forbids new
GPL dependencies. This generator instead lists every installed package with its
license and (optionally) the full license text, for inclusion in the
distribution.

It wraps the third-party ``pip-licenses`` tool (a dev dependency — see
``requirements-dev.txt``) with consistent flags and a stamped header.

**Accuracy:** ``pip-licenses`` reports whatever is installed in the *current*
environment. The dev venv contains build/test tooling (semgrep, pip-audit,
basedpyright, ...) that is NOT shipped. For a release-accurate SBOM, run this in
a clean venv installed from ``requirements.txt`` only. The generated header
records which mode was used.

Usage (from repository root)::

    python scripts/generate_third_party_licenses.py              # summary table
    python scripts/generate_third_party_licenses.py --with-texts # + full license texts
    python scripts/generate_third_party_licenses.py --ignore pytest semgrep

Exit code: 0 on success, 2 if ``pip-licenses`` is not installed or fails.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import os
import subprocess
import sys
from pathlib import Path

# Dev/build-only packages that should not appear in a shipped SBOM. Used as the
# default ignore set so a run from the dev venv approximates the release set.
DEFAULT_IGNORE = (
    "semgrep",
    "detect-secrets",
    "pip-audit",
    "pip-api",
    "pip_audit",
    "basedpyright",
    "pip-licenses",
    "prettytable",
    "wcwidth",
    "cyclonedx-python-lib",
    "pytest",
    "Pygments",
)


def run_pip_licenses(python: str, extra: list[str]) -> str:
    """Invoke ``pip-licenses`` via the current interpreter, returning stdout."""
    cmd = [python, "-m", "piplicenses", *extra]
    # Force UTF-8 in the child: pip-licenses prints package metadata (author
    # names, license text) that fails on Windows' default cp1252 stdout.
    env = {**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True, encoding="utf-8", env=env)
    except FileNotFoundError:
        raise SystemExit("[sbom] python interpreter not found.") from None
    except subprocess.CalledProcessError as exc:
        sys.stderr.write(exc.stderr or "")
        if "No module named" in (exc.stderr or ""):
            raise SystemExit(
                "[sbom] pip-licenses is not installed. Install dev deps:\n"
                "  pip install -r requirements-dev.txt"
            ) from exc
        raise SystemExit(f"[sbom] pip-licenses failed (exit {exc.returncode}).") from exc
    return result.stdout


def build_header(release_mode: bool, ignored: list[str]) -> str:
    today = _dt.date.today().isoformat()
    scope = (
        "Generated from a release venv (requirements.txt only)."
        if release_mode
        else "Generated from a DEVELOPMENT venv. Dev/build-only packages were "
        "excluded via --ignore, but this may not exactly match the shipped set. "
        "Re-generate in a clean requirements.txt-only venv before distribution."
    )
    ignored_note = f"\nExcluded packages: {', '.join(sorted(ignored))}\n" if ignored else "\n"
    return (
        "# Third-Party Licenses\n\n"
        f"**Generated:** {today}  \n"
        f"**Scope:** {scope}\n"
        f"{ignored_note}\n"
        "This file is auto-generated. Regenerate with:\n\n"
        "```\npython scripts/generate_third_party_licenses.py --release\n```\n\n"
        "Policy and the pre-commit license gate are documented in "
        "[dev-docs/info/DEPENDENCY_LICENSE_POLICY.md](dev-docs/info/DEPENDENCY_LICENSE_POLICY.md).\n\n"
        "---\n\n"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--root", type=Path, default=None, help="Repository root (default: auto-detect).")
    parser.add_argument("--output", type=Path, default=None, help="Output path (default: <root>/THIRD_PARTY_LICENSES.md).")
    parser.add_argument("--with-texts", action="store_true", help="Append the full license text of each package.")
    parser.add_argument("--release", action="store_true", help="Assert this is a release venv; skips the default dev-tool ignore list and stamps the header accordingly.")
    parser.add_argument("--ignore", nargs="*", default=None, help="Extra package names to exclude (added to the default dev-tool list unless --release).")
    args = parser.parse_args(argv)

    root = args.root or Path(__file__).resolve().parent.parent
    output = args.output or (root / "THIRD_PARTY_LICENSES.md")

    if args.release:
        ignored: list[str] = list(args.ignore or [])
    else:
        ignored = sorted(set(DEFAULT_IGNORE) | set(args.ignore or []))

    ignore_args = ["--ignore-packages", *ignored] if ignored else []

    table = run_pip_licenses(
        sys.executable,
        ["--format=markdown", "--with-urls", "--with-authors", "--order=license", *ignore_args],
    )

    parts = [build_header(args.release, ignored), table.strip(), "\n"]

    if args.with_texts:
        texts = run_pip_licenses(
            sys.executable,
            ["--format=plain-vertical", "--with-license-file", "--no-license-path", *ignore_args],
        )
        parts.append("\n---\n\n## Full license texts\n\n```\n" + texts.strip() + "\n```\n")

    output.write_text("".join(parts), encoding="utf-8")
    print(f"[sbom] wrote {output} ({'release' if args.release else 'dev'} venv)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
