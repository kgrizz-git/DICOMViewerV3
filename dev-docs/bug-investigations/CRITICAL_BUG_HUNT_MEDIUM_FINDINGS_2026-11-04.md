# Critical bug hunt — medium findings (2026-11-04)

**Last updated:** 2026-11-06  
**HEAD reviewed:** `7016f3b` (`main`)  
**Automation:** critical-bug cron; no critical-bar bugs; no fix PR from that run  
**Status:** re-checked in code on 2026-11-06 — six P2 items confirmed, cine filename claim narrowed (see Verification). Not yet fixed.  
**Plan:** [`MEDIUM_BUG_HUNT_2026-11-04_FIX_PLAN.md`](../plans/MEDIUM_BUG_HUNT_2026-11-04_FIX_PLAN.md)  
**Tracked in:** [`TO_DO.md`](../TO_DO.md) §Bugs / Correctness

## Verification (2026-11-06)

Read against the same `src/` as `7016f3b` (PR branch `2816eae` is docs-only).

| Item | Result |
|------|--------|
| 1 CT dialog slot | Confirmed. `on_destroyed` always assigns `None`. MRI guards `is dialog`. Dialog uses `WA_DeleteOnClose`. |
| 2 Relocate | Confirmed. Commit uses `any(os.path.isfile)`. Out-of-prefix rows still get `study_root_path` rewritten. Open then passes `new_root` to `_open_paths`. |
| 3 Fusion stretch | Confirmed for 2D `uint8` only. Float min-max is an existing test contract and stays. |
| 4 Formula bypass | Confirmed. `value[:1]` misses tab, CR, and other leading whitespace/controls. |
| 5 Projection fallback | Confirmed for PNG/JPG names and for cine **pixels**. Cine's save name comes from `SeriesDescription`, not `_MIP_Nslices`. |
| 6 AutoText labels | Confirmed for the series-navigator study label and overlay corner labels. |
| MPR near-misses | Code gaps confirmed; normal studies with a real Study Instance UID do not hit the empty-key path. Still optional. |

## Scope

Re-traced high-blast recent `src/` work (MPR multi-session/links, cine FFmpeg
resolution, spreadsheet formula neutralization, projection/3D export,
study-index relocate/open, CT/MRI batch dialog lifecycle). Nothing met the
critical bar (data loss / crash / security hole / significant user-facing
breakage with a concrete high-confidence trigger). The items below cleared a
**medium** bar only.

## Medium backlog (actionable)

### 1. CT batch result dialog deferred-destroy slot wipe — P2

- **Trigger:** Run a second ACR CT batch while the first batch-result dialog is
  still open (or close/replace quickly under `WA_DeleteOnClose`).
- **Path:** `gui.qa_app_facade.QAAppFacade.show_ct_batch_result_dialog` —
  `on_destroyed` always sets `app._ct_batch_result_dialog = None`.
- **Impact:** Live dialog reference can be cleared after a replacement is
  shown; subsequent batches may leave an orphaned dialog. Temp cleanup still
  targets the closed worker only.
- **Fix sketch:** Mirror MRI —
  `gui.qa_mri_batch_flow` guards with
  `if app._mri_batch_result_dialog is dialog` before clearing the slot.

### 2. Study-index `relocate_study_paths` any-file commit — P2

- **Trigger:** Relocate a study whose files only partially exist under the
  chosen `new_root`, or pick another study’s folder that shares one relative
  filename (e.g. `CT/1.dcm`).
- **Path:** `core.study_index.sqlcipher_store.StudyIndexStore.relocate_study_paths`
  → Study Index Open folder-rescans `new_root`.
- **Impact:** Index commits **all** path rewrites when **any** relocated path
  exists. Catalog row can keep study A identity while Open loads folder B.
  Viewer overlays re-parse DICOM from disk (not wrong-patient on-image
  labeling); this is index/catalog integrity + wrong-folder open risk.
- **Fix sketch:** Require all (or a threshold of) relocated paths to exist;
  optionally verify SOP UID at the new path before commit; refresh index
  identity after a successful relocate/open.

### 3. Fusion grayscale base min-max re-stretch — P2

- **Trigger:** CT (or other grayscale) base with a narrow soft-tissue W/L,
  enable fusion; compare base contrast with fusion on vs off.
- **Path:** fusion blend path passes `base_wl=None` into a helper that
  min-max normalizes 2-D L arrays when the base is already display-final.
- **Impact:** Base appearance stretches under fusion (display-only; same
  patient). RGB / float base paths that divide by 255 are asymmetric.
- **Fix sketch:** Treat uint8 L like RGB (`/255`) when input is display-final,
  or pass through without auto-normalize.

### 4. Spreadsheet formula neutralization first-character-only bypass — P2 (AppSec)

- **Trigger:** Export CSV/XLSX containing a cell that starts with whitespace
  then a formula trigger (e.g. `"\t=cmd|..."` / `"\r=..."`).
- **Path:** `core.spreadsheet_safety.neutralize_spreadsheet_value` checks
  `value[:1]` only.
- **Impact:** Leading tab/CR can still be evaluated by some spreadsheet
  clients. Study-index / SR / ROI writers are covered for bare `=+-@`; this is
  residual bypass, not a missing-writer hole.
- **Fix sketch:** Strip or neutralize after leading whitespace / control chars
  (keep import round-trip rules explicit for study-index CSV).

### 5. PNG/cine MIP-named single-slice fallback — P2

- **Trigger:** Export a projection (MIP/AIP/MinIP) when the slab has fewer than
  two contributing slices so projection build returns `None`.
- **Path:** export / cine rasterize falls back to a single slice while
  `export_filename` still adds a `_MIP_Nslices`-style token.
- **Impact:** Same-patient pixels, but the filename claims a projection that
  was not built. DICOM projection path fail-closes / labels derived singles
  more carefully.
- **Fix sketch:** Name the fallback as a single-slice export, or refuse the
  projection container when the slab is too thin.

### 6. Series-navigator / overlay `QLabel` AutoText + DICOM text — P2 (AppSec)

- **Trigger:** Open a study whose `StudyDescription` (or overlay tag text)
  contains HTML-like markup (`<img …>`, rich-text tags).
- **Path:** `gui.series_navigator_view` study label `QLabel.setText` without
  `PlainText`; overlay corner labels similarly use default AutoText.
- **Impact:** Qt may interpret AutoText as rich text (UI spoofing / unwanted
  resource fetch). Local desktop AppSec medium, not RCE by itself.
- **Fix sketch:** `setTextFormat(Qt.TextFormat.PlainText)` on all DICOM-driven
  labels (same pattern as `gui.lut_pane_label`).

## Lower-confidence MPR near-misses (optional hardening)

These did **not** clear a concrete critical trigger on normal studies; track
only if touching MPR admission/sync soon:

1. Empty `(study_uid, series_uid)` source keys can evade source-closure matching.
2. `SliceSyncCoordinator._get_slice_index` ignores `mpr_slice_index` after a
   failed linked redraw.
3. Registry-only pending admission tokens are not UID-swept on study close
   without a pane map entry (GUI-thread activation makes this low risk today).

## Explicitly out of scope here

- Critical-bar issues (none found on this HEAD).
- Already-fixed formula neutralization for study-index CSV, SR dose-event, and
  ROI XLSX label-value rows (`04d7cae` / `80d7eb2`).
