# Dependency License Policy & Check

**Last updated:** 2026-06-09

This is the **single source of documentation** for the automated dependency
license check. It explains what the check does, the policy it enforces, how to
run it, how exceptions work, and how it is wired into pre-commit and CI.

- **Gate script (pre-commit, stdlib-only):** [`scripts/check_dependency_licenses.py`](../../scripts/check_dependency_licenses.py)
- **Editable policy data:** [`dependency_license_policy.json`](dependency_license_policy.json)
- **Attribution SBOM generator:** [`scripts/generate_third_party_licenses.py`](../../scripts/generate_third_party_licenses.py)
- **Why this exists / full strategy:** [`LICENSE_AND_COMPLIANCE_PLAN.md`](../plans/supporting/LICENSE_AND_COMPLIANCE_PLAN.md) (this check implements **Phase 6**)
- **Per-package inventory & rationale:** [`BUNDLED_PACKAGES_AND_FONTS_LICENSES.md`](BUNDLED_PACKAGES_AND_FONTS_LICENSES.md)

## Two tools, two jobs

| | Gate (`check_dependency_licenses.py`) | SBOM (`generate_third_party_licenses.py`) |
|---|---|---|
| Purpose | **Block** a new GPL/AGPL dependency | **List** all deps + license text for attribution |
| Dependencies | None (stdlib `importlib.metadata`) | `pip-licenses` (dev dependency) |
| Runs | Every commit (pre-commit) + CI | At release / packaging time |
| Output | Pass/fail + report | `THIRD_PARTY_LICENSES.md` (Phases 3a/5) |

The gate is deliberately zero-dependency so it always runs in the hook. The SBOM
generator wraps `pip-licenses` because it can extract full license **text**,
which the gate does not need.

> **Not legal advice.** This check is an engineering guardrail to catch a *new*
> copyleft dependency before it lands. It does not replace the legal review
> tracked in the compliance plan.

---

## What it does

The project intends a closed-source commercial release. Under that model the
hard constraint is: **no new strong-copyleft (GPL / AGPL) dependency may enter
the bundle unnoticed.** The checker scans every Python distribution installed in
the active virtual environment, classifies each one's license, and **fails
(exit 1)** if a strong-copyleft package appears that is not explicitly accepted
in the policy file.

It is **zero-dependency** (standard-library `importlib.metadata` only — no
`pip-licenses` install, no network) so it runs anywhere the venv runs, including
in the pre-commit hook.

### License categories

| Category | Examples | Result |
|----------|----------|--------|
| `PERMISSIVE` | MIT, BSD, Apache-2.0, ISC, Zlib, PSF, SIL OFL, public domain | Pass |
| `OBLIGATION` | LGPL, MPL-2.0, EPL, CDDL (weak copyleft) | Pass, but **reported** — these carry notice / relinking obligations you must satisfy in the distribution (see Qt/PySide6 in the compliance plan, Phase 2) |
| `FORBIDDEN` | GPL, AGPL (strong copyleft) | **Fail**, unless listed in `accepted_exceptions` |
| `UNKNOWN` | License metadata missing/unreadable | Warn (fails only with `--strict-unknown` or `fail_on_unknown: true`) |

### How a license is determined

Per distribution, in priority order:
1. PEP 639 `License-Expression` field (an SPDX expression).
2. `License :: ...` trove classifiers.
3. Free-text `License` field (only when short and single-line).

SPDX expressions are evaluated, not pattern-matched blindly:
- `OR` picks the **least restrictive** operand. This is why
  `LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only` (PySide6/shiboken6) reads as
  **OBLIGATION (LGPL)**, not forbidden — you may take the LGPL option.
- `AND` picks the **most restrictive** operand.

---

## Running it

From the repository root, in the project venv:

```bash
python scripts/check_dependency_licenses.py            # human-readable report
python scripts/check_dependency_licenses.py --json     # machine-readable
python scripts/check_dependency_licenses.py --strict-unknown   # also fail on UNKNOWN
```

Exit codes: `0` compliant · `1` policy violation · `2` usage/IO error.

> The check reflects **what is installed in the current venv**, which is the
> closest proxy to what gets bundled. Run it in the release venv before
> packaging. A package only in your dev venv (e.g. a GPL linter) will be flagged
> too — accept it as an exception if it is genuinely build-only and not shipped.

### Generating the attribution SBOM

`THIRD_PARTY_LICENSES.md` lists every shipped dependency with its license, for
inclusion in the distribution. It is **auto-generated and git-ignored** — build
it from the release venv at packaging time:

```bash
pip install -r requirements-dev.txt          # provides pip-licenses
python scripts/generate_third_party_licenses.py --release            # summary table
python scripts/generate_third_party_licenses.py --release --with-texts   # + full texts
```

Run **without** `--release` from a dev venv and the generator auto-excludes
known build/test tooling (semgrep, pip-audit, basedpyright, ...) and stamps a
"DEVELOPMENT venv" caveat in the header. For the artifact you actually ship, use
a clean `requirements.txt`-only venv with `--release`.

---

## Editing the policy

All policy lives in [`dependency_license_policy.json`](dependency_license_policy.json):

```jsonc
{
  "forbidden_categories": ["FORBIDDEN"],   // categories that fail the check
  "fail_on_unknown": false,                // treat UNKNOWN as a failure?
  "accepted_exceptions": {                  // GPL/AGPL packages knowingly allowed
    "<pep503-name>": { "license": "...", "reason": "...", "review_by": "..." }
  },
  "overrides": {                            // force a license for unreadable metadata
    "<pep503-name>": "MIT"
  }
}
```

- **`accepted_exceptions`** — the escape hatch for a forbidden package you have
  *consciously decided* to keep for now. Every entry should carry a `reason` and,
  ideally, where it is tracked. Keys are matched PEP 503-normalized (lowercase,
  `-_.` runs collapsed to `-`), so `pylibjpeg-libjpeg` and `pylibjpeg_libjpeg`
  are equivalent.
- **`overrides`** — for a package whose metadata the checker can't read; supply
  the correct SPDX expression so it classifies correctly instead of `UNKNOWN`.

### Current accepted exceptions

| Package | License | Why it's allowed (for now) |
|---------|---------|----------------------------|
| `pylibjpeg-libjpeg` | GPL-3.0 | **Unresolved Phase 0a blocker.** DICOM JPEG Baseline/Extended decoder. Must be removed or replaced (Pillow-only, or GDCM/LGPL) **before** commercial distribution. Tracked in the compliance plan, Phase 0a; detailed replacement strategy: [`PYLIBJPEG_ALTERNATIVES_AND_DICOM_DECODER_STRATEGY.md`](PYLIBJPEG_ALTERNATIVES_AND_DICOM_DECODER_STRATEGY.md). |

> Keep this table in sync with `accepted_exceptions` in the JSON when you add or
> remove an entry.

---

## Where it runs automatically

- **Pre-commit** (`.githooks/pre-commit`): runs as part of the repo-harness
  check chain on every commit, so a newly added GPL dependency fails fast,
  locally, before it is committed.
- **CI** (recommended, compliance plan Phase 6): add a step to a GitHub workflow
  that runs `python scripts/check_dependency_licenses.py` in the release venv so
  the gate also enforces on PRs and release builds.

---

## When the check fails

1. Read which package and license triggered it.
2. Decide:
   - **Remove it** if unused or replaceable.
   - **Replace it** with a permissive or LGPL alternative (see the compliance
     plan's Phase 0 tables for the JPEG/FFmpeg options already researched).
   - **Accept it** — only if you (or counsel) have decided the copyleft
     obligation is acceptable — by adding an `accepted_exceptions` entry *with a
     reason*, and updating the table above.
3. Never silence the check by deleting it or broadening `forbidden_categories`.
