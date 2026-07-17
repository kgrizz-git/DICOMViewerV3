# Agent manual smoke checklist

**Last updated:** 2026-07-16
**Automated prelude:** `python scripts/agent_smoke_harness.py --write-report` (see [`../HARNESS.md`](../HARNESS.md)).

Use this after UX, loading, MPR, 3D volume render, SR, study index, or navigator changes when automated tests pass but behavior needs human or browser-agent eyes.

---

## Setup

- [ ] Virtual environment activated (`.venv` / `venv`).
- [ ] `python scripts/agent_smoke_harness.py` exits 0.
- [ ] `python -m pytest tests/ -q` green (or targeted modules if slice is narrow).

---

## Launch

- [ ] `python src/main.py` starts without traceback.
- [ ] Main window title and menu bar visible; no modal blocking startup (disclaimer OK once).

---

## Load data

- [ ] **File → Open** (or folder): load `tests/fixtures/dicom_rdsr/synthetic_ct_dose_comprehensive_sr.dcm` (SR, no pixels) — navigator shows study/series; SR hint or browser path works.
- [ ] If local `test-DICOM-data/` exists: open one CT/MR series — image displays, slice scroll works.

---

## Core interactions (spot-check)

- [ ] **Space** cycles overlay mode on a normal image pane.
- [ ] **Space** on **MPR** pane cycles overlay (regression for TO_DO overlay-on-MPR).
- [ ] Privacy toggle masks PHI in metadata and overlays.
- [ ] Focus second subwindow (2×2): W/L and series independent where expected.

---

## Optional deep smoke

- [ ] **File → Open Study Index…** (or toolbar **Index**) opens when SQLCipher available; **Search all text** visible.
- [ ] **Tools → ACR CT Phantom (pylinac)…** or **ACR MRI…** on a suitable phantom folder (or cancel at folder prompt).
- [ ] **Tools → Structured Report…** on RDSR fixture.
- [ ] **Toolbar → 3D View** on a multi-slice CT/MR series (VTK installed): dialog builds volume; rotate/zoom; close without crash.
- [ ] Export → PNG on a loaded slice (path dialog appears).

---

## Record results

Report the app version (`src/version.py`), branch, and pass/fail directly in the
task or PR summary. Do not create a separate test ledger.
