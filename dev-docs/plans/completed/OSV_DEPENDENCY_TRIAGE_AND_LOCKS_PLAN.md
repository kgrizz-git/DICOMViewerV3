# OSV dependency triage and hashed locks

**Status:** Implemented 2026-10-21 (follow-ups open, tracked in `TO_DO.md`)

**Priority:** P1 (security)

**Created:** 2026-10-20

**Related:** [`security/pip-audit-exceptions.md`](../../../security/pip-audit-exceptions.md); [`scripts/compile_requirements.py`](../../../scripts/compile_requirements.py); [`scripts/check_requirements_lock.py`](../../../scripts/check_requirements_lock.py); [`osv-scanner.toml`](../../../osv-scanner.toml); [maintenance log](../../MAINTENANCE_LOG.md). Commits `142ed95`, `6746d15`, `e406932`.

## Verdict

An osv-scanner run on the repository found Pillow 12.3.0 (nine image-decoder advisories, fixed in 13.0.0) and several stale packages. The root cause was unlocked version floors plus a drifted local venv, not a missing advisory database. CI's `pip-audit` already resolved floors to clean latest versions. Nothing pinned what users install or what the frozen build ships, so a build scanned clean one month could be vulnerable the next.

## Decisions

- **Hashed universal uv locks.** Floor files became `requirements.in`, `requirements-dev.in`, and `requirements-build.in`. Hashed `.txt` locks are compiled with `uv pip compile --universal --python-version 3.12 --generate-hashes --strip-extras` (uv pinned in the script). Installs use `--require-hashes`. The dev lock is compiled against the app lock (`-c`) so both use the same versions, and every file is hashed because one hashed file turns on hash checking for the whole install.
- **pip-compile per-platform locks were rejected.** `pip-compile` resolves for the host only. A Linux lock dropped `colorama` (win32), `pywin32-ctypes` and `pefile` (win32), and `macholib` (darwin), so the Windows and macOS builds would fail under `--require-hashes`. One universal lock with environment markers serves all three platforms, and `pip install --dry-run --require-hashes` accepted all three locks.
- **Lock drift check.** The **Requirements locks match** CI job recompiles each `.in` file and fails on a stale or hand-edited `.txt`. Launchers and CI read the zensical and PyYAML floors from the `.in` files, because compiled lines carry hash continuations.
- **Pillow 13.** `requirements.in` requires `Pillow>=13.0.0`. All app dependents are cap-free. Regression tests: `tests/test_pillow_floor.py`, `tests/utils/test_pillow13_paths.py`. A manual smoke is tracked in `TO_DO.md`.
- **PHI-lane cap.** `presidio-image-redactor 0.0.60` caps `pillow<13.0.0`, so the isolated, never-shipped PHI-tooling environment stays on Pillow 12.x. The advisory `pip-audit-phi-tools` step ignores the eight PyPI-feed IDs. `GHSA-8g5g-8vmr-9782` is OSV-only. The blocking `pip-audit` job has no Pillow exception.
- **Semgrep transitives.** `mcp`, `pyjwt`, `anyio`, and `cryptography` come in through Semgrep (run via uvx) and the PHI lane. They get no floors in `requirements-dev`, following PR #167, which moved Semgrep out of the audited set. Risk in that lane is upstream's to fix.
- **pydicom** keeps its existing exception (`pylinac` caps `<3`). Phantom `pip`, `tqdm`, `py`, and `setuptools` findings came from osv-scanner double-parsing a requirements file and are false positives.
- **OSV as an advisory job over the locks.** The **osv-scanner (locked dependencies)** job scans the committed locks, not a fresh resolve (which is always green and duplicates pip-audit). It uses a SHA-256-pinned osv-scanner 2.7.0 release binary, `contents: read` only, and uploads nothing. OSV reads every pin regardless of platform markers, so it covers Windows- and macOS-only packages that Linux `pip-audit` skips. `security/pip-audit-exceptions.md` stays the single source of truth for suppressions; `osv-scanner.toml` must match, enforced by `tests/test_osv_scanner_config.py`. The tool is in `security/security-tool-inventory.json`.

## Open follow-ups

All are tracked in [`TO_DO.md`](../../TO_DO.md).

- Confirm Dependabot regenerates the uv locks on its first Python PR (unverified; the lock check is the fallback).
- Promote the OSV job to required by 2026-11-30 (it starts with `continue-on-error`).
- Run the manual Pillow 13 smoke: ACR QA, PNG/JPG export, cine, combined PDF.
- Lift the PHI-lane Pillow exception when `presidio-image-redactor` allows Pillow 13 (review by 2026-12-31).

Not pursued: moving `requirements-phi-tools.txt` to the `.in` layout, and scanning the frozen build's bundled environment.

## Checklist

- [x] Hashed universal uv locks, compile script, drift check, CI job.
- [x] `Pillow>=13.0.0` floor and tests.
- [x] PHI-lane exception recorded in the CI step and `pip-audit-exceptions.md`.
- [x] Advisory osv-scanner job, config, inventory entry, and consistency test.
- [x] Changelog, maintenance-log, and TO_DO closeout.
