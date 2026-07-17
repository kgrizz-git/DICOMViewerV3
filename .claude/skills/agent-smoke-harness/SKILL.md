---
name: agent-smoke-harness
description: Run DICOM Viewer V3 automated and manual smoke checks after UX, loading, navigation, MPR, overlay, SR, or harness changes.
---

# Agent smoke harness

## When to use

- After changing loading, navigator, MPR, overlays, SR, or main-window UX.
- Before claiming a slice is merge-ready (with `pytest`).
- When `check_repo_harness.py` or CI **Repo harness** job fails.

## Automated steps

From repo root with venv activated:

```bash
python scripts/agent_smoke_harness.py --write-report
python scripts/check_repo_harness.py
python -m pytest tests/test_agent_smoke_harness.py tests/test_repo_harness.py -q
```

Optional Qt headless import check (local or CI with display libs):

```bash
python scripts/agent_smoke_harness.py --qt-smoke
```

Report path: `logs/agent-smoke-report.json` (gitignored if `logs/` is ignored).

## Manual UI smoke

Follow **[`dev-docs/orchestration/AGENT_SMOKE.md`](../../../dev-docs/orchestration/AGENT_SMOKE.md)**:

1. `python src/main.py`
2. Load `tests/fixtures/dicom_rdsr/synthetic_ct_dose_comprehensive_sr.dcm`
3. Spot-check **Space** overlay on image pane and MPR pane

## Full regression

```bash
python -m pytest tests/ -v
```

Use long timeout (~10 minutes) for full suite on slow machines (see **AGENTS.md**).

## Report

Report the command results and any failed manual step directly to the user. Do
not create role handoffs, orchestration state, or a test ledger.
