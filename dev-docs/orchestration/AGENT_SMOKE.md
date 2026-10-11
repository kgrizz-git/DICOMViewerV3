# Agent manual smoke checklist

**Last updated:** 2026-10-11

**Automated prelude:** `python scripts/agent_smoke_harness.py --write-report` (see [`../HARNESS.md`](../HARNESS.md)).

Pending plan-complete smokes are inventoried in [`../TO_DO.md`](../TO_DO.md) → **Manual Smoke Checks**; use this checklist for the general launch/load/interaction prelude.

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
- [ ] If a MONOCHROME1 secondary-capture series is available: load it, verify
  screen polarity matches export (still + cine). Manual Invert toggle should
  flip without double-inverting. Status bar shows `(MI)` marker.
- [ ] **LUT**: toolbar **LUT** / **L** → select Linear (no visible change);
  select a color map (RGB output, correct orientation; toggle **I** — no
  double-invert); **Adjust Parameters…** moves the gamma slider; **Edit Curve…**
  → drag/add a breakpoint, draw a freehand stroke, switch interpolation, Undo.
  Histogram (**Ctrl+Shift+H**) shows the W/L ramp, LUT, and composed curves with
  the three checkboxes; drag a bend of the composed curve and the pane's window
  follows. **Edit Curve…** shows the dashed display result behind the curve.
  **Save Current As…** → restart → the LUT is listed under **Saved**, and
  selecting it reapplies it (after a restart a pane starts on its modality
  default, or Linear when none is set).
  On a color map, **Edit Colors…** → add a stop, recolor it, switch to step.
  **Import Colormap…** from a small `.csv` → it appears under **Saved**.
  **Use as Default for** the pane's modality → another series of that modality
  opens with it. **View → Show LUT Label** names the LUT at the top of the pane.
  On a file with a VOI LUT Sequence, **From DICOM (VOI LUT)** changes the image.
  With privacy mode on, a saved LUT's label reads "Custom".
  Export → PNG on that pane, and a short cine export, match the viewport.

---

## MPR multiple sessions and detached views

Needs a CT/MR series with consistent geometry (a de-identified QC phantom is fine) and a real display. These steps back the three MPR items in [`../TO_DO.md`](../TO_DO.md) → **Manual Smoke Checks**. User behavior: [`USER_GUIDE_MPR.md`](../../user-docs/USER_GUIDE_MPR.md). Use a 2×2 layout (`4`).

**Sessions, detach, drag**

- [ ] Build an **axial** MPR in window 1 and a **coronal** MPR in window 2 (**Tools → Create MPR View…**). The status bar shows `MPR: n/8 sessions, m/16 views, about … MiB (estimate)` while building and after.
- [ ] Right-click each MPR's background → **Clear This Window**. Both windows revert; the navigator shows two MPR tiles after the source series, in creation order, with `S1` and `S2` tags and no window digit.
- [ ] Drag only the second tile onto window 3: only it attaches (digit `3` appears); the first stays a tile.
- [ ] Build another MPR **from the same series** into window 3 (it already shows an MPR): the earlier MPR remains as a tile; three tiles exist and none were lost.
- [ ] Drag a tile onto a window that shows an **MPR**: the displaced MPR becomes a tile. Drag a tile onto a window showing an **ordinary series**, then **Clear MPR View**: the series returns.
- [ ] Close the source series (navigator context menu): every dependent MPR window and tile disappears; reopening the series shows no stale tile. Repeat with **File → Close All** and a replace-open.

**Limits and memory**

- [ ] **Edit → Settings… → MPR Limits**: set sessions 2 and views 3, **OK**. A third MPR is refused with a message naming the limit, the counts and an approximate MiB figure, and no extra confirmation. Lower the limits below current use: nothing closes. Raise them: the next build succeeds without a restart. Confirm the views box cannot go below the sessions box.

---

## Record results

Report the app version (`src/version.py`), branch, and pass/fail directly in the
task or PR summary. Do not create a separate test ledger.
