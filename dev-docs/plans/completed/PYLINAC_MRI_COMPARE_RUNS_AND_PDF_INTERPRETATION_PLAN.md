# Pylinac MRI — Multi-Run Low-Contrast Comparison and PDF Interpretation Notes

**Status:** Implemented (viewer **0.1.2+**); checklist below reflects verification.  
**Priority:** P2  

**Superseded / implementation notes (read before using this plan as a spec):**

- **PDF interpretation (Part 2):** The original design prioritized **`publish_pdf(notes=...)`** with a long string. In practice pylinac’s first-page notes area fits only ~**6 short lines**; the shipped single-run path uses **`list[str]`** (one line per element). For **compare mode**, interpretation text and the parameter table are delivered primarily via a **viewer-authored summary PDF + `pypdf` merge** ([`MRI_COMPARE_COMBINED_PDF_PLAN.md`](completed/MRI_COMPARE_COMBINED_PDF_PLAN.md) in `plans/completed/`), not only inline `notes=`.
- **Config (Phase B):** One tuple **`LC_COMPARE_MULTIPLIERS`** is used for both threshold and sanity multiplier combos (same numeric set as two separate constants in this plan).
- **API shape:** **`build_mri_pdf_notes` / `build_mri_compare_pdf_notes`** return **`List[str]`**, not **`str`**.
- **Results UI (§1.6):** Shipped as a **non-modal** dialog with a **QTableWidget** (metrics × runs), **Save comparison JSON…**, optional **Open PDF**, and a details area for full warnings/errors.
- **Automated tests:** Phase E items are covered in **`tests/test_mri_compare_phase_e.py`** (no DICOM fixtures; includes dialog wiring with **`@pytest.mark.qt`**).

**Related docs:**
- [PYLINAC_INTEGRATION_OVERVIEW.md](../info/PYLINAC_INTEGRATION_OVERVIEW.md)
- [PYLINAC_MRI_LOW_CONTRAST_DETECTABILITY.md](../info/PYLINAC_MRI_LOW_CONTRAST_DETECTABILITY.md)
- [PYLINAC_CUSTOMIZATION_AND_EXTENSIONS.md](../info/PYLINAC_CUSTOMIZATION_AND_EXTENSIONS.md)
- [PYLINAC_AND_AUTOMATED_QA_STAGE1_PLAN.md](PYLINAC_AND_AUTOMATED_QA_STAGE1_PLAN.md)

---

## Goal

Two independent features delivered as a single coherent Phase 2 extension to the ACR MRI pylinac flow:

1. **Compare mode**: run low-contrast detectability up to **3 times** on the same DICOM input with different parameter sets (method + threshold + sanity multiplier), then present a side-by-side comparison table and export a combined JSON.
2. **PDF interpretation notes**: append a viewer-generated explanation page after pylinac's standard analysis PDF. The explanation covers MTF, low-contrast score, and the meaning of colored circles.

Both features must preserve the existing single-run path as the default and leave the CT flow completely untouched.

---

## Design principles

- **One pylinac run per parameter set.** Pylinac analyzers are constructed and `analyze(...)` is called once per run; parameters are baked in at that point. Never reuse one analyzed object for different parameter sets.
- **Shared DICOM loading.** All runs in a comparison batch reuse the same analyzer construction (same paths/folder, same echo, same scan-extent behavior) but produce separate analyzed objects.
- **Explicit reproducibility.** Every run in a batch carries its own `QARequest`-equivalent config and `pylinac_analysis_profile`. The combined JSON export names each run and stores all three.
- **Backward compatibility.** The existing single-run MRI path is unchanged when the user leaves compare mode off. Existing JSON schema is extended, not replaced.
- **No changes to CT analysis.**

---

## Part 1 — Compare mode

### 1.1 New data structures (`src/qa/analysis_types.py`)

Add a `LcRunConfig` dataclass to hold one parameter set row in the comparison table:

```python
@dataclass
class LcRunConfig:
    """One low-contrast parameter set within a comparison batch."""
    label: str                             # e.g. "Run 1", user-editable later
    low_contrast_method: str               # one of ACR_MRI_LOW_CONTRAST_METHODS
    low_contrast_visibility_threshold: float
    low_contrast_visibility_sanity_multiplier: float
```

Add a `MRICompareRequest` dataclass (not a subclass of `QARequest` — keep `QARequest` simple) that the dialog returns alongside the existing options when compare mode is active:

```python
@dataclass
class MRICompareRequest:
    """Carries the per-run configs for a low-contrast comparison batch."""
    run_configs: List[LcRunConfig]  # 1–3 entries; guaranteed non-empty
```

No changes to `QARequest` itself. Each actual pylinac run is still driven by a standard `QARequest` with one parameter set, built at dispatch time.

Add `MRIBatchResult` to hold the full comparison output returned to the GUI:

```python
@dataclass
class MRIBatchResult:
    """Result container for a multi-run low-contrast comparison."""
    run_results: List[QAResult]            # parallel to MRICompareRequest.run_configs
    run_configs: List[LcRunConfig]
```

### 1.2 Runner changes (`src/qa/pylinac_runner.py`)

Add a new function `run_acr_mri_large_batch(...)` that:

1. Accepts the DICOM source info (paths / folder / echo / scan-extent config) and a `List[LcRunConfig]`.
2. Loads the analyzer once from `cls(request.dicom_paths, ...)` or `cls.from_folder(...)`.
3. Iterates over configs: for each `LcRunConfig`, calls `analyzer.analyze(...)` with that config's kwargs. Because pylinac does not guarantee idempotent multiple calls on the same object, **deep-copies or re-constructs the analyzer per run** before calling `analyze`.
4. Collects one `QAResult` per run and returns an `MRIBatchResult`.

> **Important:** Check in pylinac 3.42.0 whether calling `analyze(...)` twice on the same `ACRMRILarge` instance produces correct independent results (localization re-run, internal state cleared). If not, re-instantiate the analyzer for each run. The safest approach is always re-instantiating.

Because re-instantiation is the safe choice, the batch runner should:
- Keep the path-loading and scan-extent setup logic shared (extract a private helper `_build_mri_analyzer(request) -> ACRMRILarge`).
- Call that helper once per run, then call `analyze(...)` and collect results.

### 1.3 Worker changes (`src/qa/worker.py`)

Add a `QABatchWorker(QThread)` that accepts a base `QARequest` plus an `MRICompareRequest` and calls `run_acr_mri_large_batch(...)`. Emits `batch_result_ready = Signal(object)  # MRIBatchResult`.

Single-run `QAAnalysisWorker` is unchanged.

### 1.4 Dialog changes (`src/gui/dialogs/acr_mri_qa_dialog.py`)

Add a **"Compare low-contrast settings"** collapsible or checkable section **below** the existing Low-contrast detectability group. When unchecked (default), the compare table is hidden and behavior is exactly as today.

When enabled, show a table with up to 3 rows. Each row has:

| Column | Widget | Notes |
|--------|--------|-------|
| Run # | static label | "Run 1", "Run 2", "Run 3" |
| Contrast method | `QComboBox` | `ACR_MRI_LOW_CONTRAST_METHODS` |
| Visibility threshold | `QComboBox` | see multiplier options below |
| Sanity multiplier | `QComboBox` | see multiplier options below |
| Enable | `QCheckBox` | unchecking removes the row from the batch |

**Threshold options** for each row: a `QComboBox` whose items are computed from the pylinac default (0.001) multiplied by `[0.75, 0.8, 0.9, 1.0, 1.1, 1.2, 1.25]`. Display format: `"× 0.75 (= 0.00075)"`, with the exact computed value shown parenthetically. The first row pre-selects `× 1.0` (= pylinac default). Subsequent rows pre-select `× 0.9` and `× 1.1` by default to give a sensible initial comparison spread.

**Sanity multiplier options** for each row: same pattern relative to pylinac default (3.0): `[0.75, 0.8, 0.9, 1.0, 1.1, 1.2, 1.25]`. Display: `"× 0.75 (= 2.25)"`.

Add an `"Add row"` button that enables the next unchecked row (greyed out when 3 rows are already enabled) and a `"Reset rows to defaults"` button.

When compare mode is active, `get_options()` returns both the existing single-run config (for the first enabled row, so it also drives the standard pylinac PDF) and an `MRICompareRequest` containing all enabled rows.

Extend `prompt_acr_mri_options(...)` return type accordingly:

```python
# before (existing)
Optional[Tuple[Optional[int], bool, Optional[int], float, str, float, float]]

# after (extended)
Optional[Tuple[Optional[int], bool, Optional[int], float, str, float, float, Optional[MRICompareRequest]]]
```

`Optional[MRICompareRequest]` is `None` when compare mode is off (single-run behavior).

### 1.5 `main.py` changes (`_open_acr_mri_phantom_analysis`)

After unpacking `mri_opts`, check whether `compare_request is not None`. If so:
- Build the base `QARequest` from the first run's config (as usual) for the standard pylinac PDF path.
- Launch `QABatchWorker` instead of `QAAnalysisWorker`.
- On `batch_result_ready`: call `_show_mri_compare_result_dialog(...)` and `_export_mri_compare_json(...)`.

If `compare_request is None`, the existing single-run path is used unchanged.

### 1.6 Results dialog (new) — `_show_mri_compare_result_dialog`

Show a non-modal `QDialog` (or `QMessageBox` if layout is simple enough) with:

- A header row listing run labels.
- One row per key metric:
  - Low contrast score (run 1 / run 2 / run 3)
  - Pylinac `vanilla_equivalent` (yes/no per run)
  - `low_contrast_method` / `low_contrast_visibility_threshold` / `low_contrast_visibility_sanity_multiplier` per run
  - Any per-run warnings
- A "Save comparison JSON…" button.

### 1.7 JSON export (new) — `_export_mri_compare_json`

Schema extension (new top-level key alongside existing keys for backward compatibility):

```json
{
  "schema_version": "1.2",
  "compare_mode": true,
  "runs": [
    {
      "run_label": "Run 1",
      "run": { ... },
      "inputs": { ... },
      "pylinac_analysis_profile": { ... },
      "metrics": { ... },
      "warnings": [],
      "errors": [],
      "artifacts": {}
    },
    { ... }
  ]
}
```

Single-run exports remain `schema_version: "1.1"` with no `compare_mode` key, so existing consumers are unaffected.

---

## Part 2 — PDF interpretation notes

### 2.1 Interpretation text content

A viewer-generated block appended as the last PDF page(s). Split into two sections.

**Section A — MTF (high-contrast resolution)**

> The rMTF (relative modulation transfer function) curves show how well the system resolves fine spatial detail.
>
> - **Higher rMTF 50%** (the spatial frequency at which MTF falls to 50%) generally indicates better in-plane high-contrast spatial resolution.
> - **Row-wise vs column-wise MTF** values reflect resolution along each axis. A large difference between them may indicate directional asymmetry in the acquisition or reconstruction.
> - MTF values depend on acquisition parameters (field of view, matrix, slice thickness, reconstruction kernel). Comparisons are meaningful only when those parameters are held constant across sessions.
> - A practical clinical reference: the ACR MRI accreditation program specifies minimum high-contrast resolution requirements per accreditation section; consult your site's accreditation documentation for applicable thresholds.
>
> *Pylinac reports rMTF at 10%–90% in 10% increments. These are derived from high-contrast phantom features on Slice 1.*

**Section B — Low-contrast detectability**

> The low-contrast score counts how many spoke structures pylinac's algorithm considers "visible" on slices 8–11 of the ACR MRI Large phantom.
>
> - **Total score range:** 0–40 (up to 10 complete spokes per slice × 4 slices).
> - **Spoke counting rule:** A spoke counts as complete only if all 3 of its disks are visible. Counting starts at spoke 1 (largest, 7 mm diameter) and stops at the first incomplete spoke; later spokes are not counted even if they would pass.
> - **Circle overlay colors on the low-contrast slice images:**
>   - **Blue (large circle):** The outer boundary of the detected low-contrast region (~40 mm radius nominal).
>   - **Blue (small circles):** Background reference ROIs used to measure local contrast for each spoke.
>   - **Green circles:** Low-contrast disk ROIs that pylinac considers **visible** — they passed both the visibility threshold and the sanity cap.
>   - **Red circles:** Low-contrast disk ROIs that pylinac considers **not visible** — they fell below the visibility threshold or exceeded the sanity cap.
> - **Visibility threshold** (`low_contrast_visibility_threshold`, default 0.001): a disk is counted as seen only if its computed Rose-model visibility score exceeds this value. A lower threshold is more permissive (more disks count as seen); a higher threshold is stricter.
> - **Sanity multiplier** (`low_contrast_visibility_sanity_multiplier`, default 3.0): suppresses unrealistically large visibility values on tiny disks. A disk is rejected as seen if its visibility exceeds (max visibility of spoke-1 disks × this multiplier), regardless of threshold.
> - **Contrast method** (`low_contrast_method`, default Weber): determines how the signal-to-background ratio is calculated before visibility is computed. Different methods can give different scores on the same acquisition.
>
> *The score is sensitive to analysis settings. Always record which method, threshold, and multiplier were used (see the pylinac_analysis_profile field in the JSON export).*
>
> *This interpretation note is provided as a viewer aid only and does not constitute a clinical pass/fail determination. Consult ACR accreditation materials and your clinical physics team for applicable requirements.*

### 2.2 Run-settings summary block (added when compare mode was active)

When a batch run was performed, precede Section A with a table:

```
--- Analysis settings comparison ---
         Run 1        Run 2        Run 3
Method   Weber        Michelson    Weber
Thresh   0.001        0.001        0.0009
Sanity   3.0          3.0          2.7
Score    32           29           34
```

### 2.3 Implementation

- Interpretation notes are **always-on** — every MRI PDF (single-run and compare-mode) receives the notes block. There is no per-run toggle.
- In `src/qa/pylinac_runner.py`, add a helper `build_mri_pdf_notes(result: QAResult) -> List[str]` that composes Sections A and B as **one string per PDF line** (pylinac renders each list element separately), reading interpretation text from module-level string constants so the text can be updated without touching logic.
- The notes include links to the relevant pylinac documentation:
  - ACR MRI phantom analysis: `https://pylinac.readthedocs.io/en/latest/acr.html`
  - Contrast / Visibility topic: `https://pylinac.readthedocs.io/en/latest/topics/contrast.html`
- Pass the result of `build_mri_pdf_notes(result)` to `analyzer.publish_pdf(path, notes=...)`. Pylinac's `ACRMRILarge.publish_pdf` already accepts `notes: str | None` and renders it on the first page of the PDF; the text will appear there automatically.
- For compare-mode runs, add `build_mri_compare_pdf_notes(batch_result: MRIBatchResult) -> str` that prepends the comparison table to the same notes string for the primary run PDF.

> **Note on PDF layout:** pylinac's `publish_pdf` inserts `notes` as free text on the first page above the analysis images. If the note text is long, it will overflow. The implementation should either trim the notes to a safe character count, split across multiple text lines carefully, or accept that overflow wraps off-page and provide guidance that the full interpretation is in the JSON.

### 2.4 Alternative: viewer-generated appendix page

If `notes=` overflows badly in practice, the fallback is to:
1. Call `analyzer.publish_pdf(path)` without notes (pylinac standard PDF unchanged).
2. Open the PDF with a library such as `reportlab` or `pypdf` and append a viewer-generated page.
3. Save the combined file.

This requires adding `pypdf` or similar as a dependency. Plan the `notes=` approach first and only fall back to this if layout is unacceptable.

---

## Implementation checklist

### Phase A — Data structures and runner (no UI yet)

- [x] **`src/qa/analysis_types.py`**: add `LcRunConfig`, `MRICompareRequest`, `MRIBatchResult` dataclasses with docstrings. No changes to `QARequest` or `QAResult`.
- [x] **`src/qa/pylinac_runner.py`**: extract private `_build_mri_analyzer(request: QARequest, *, cls) -> ACRMRILarge` helper from `run_acr_mri_large_analysis` to avoid duplicating construction logic.
- [x] **`src/qa/pylinac_runner.py`**: add `run_acr_mri_large_batch(base_request: QARequest, run_configs: List[LcRunConfig]) -> MRIBatchResult`. Re-instantiate the analyzer for each run. Collect one `QAResult` per config. Each result carries its own `pylinac_analysis_profile`.
- [x] **`src/qa/pylinac_runner.py`**: add `build_mri_pdf_notes` / `build_mri_compare_pdf_notes` returning **`List[str]`** (see superseded note). Store interpretation text as module-level string constants.
- [x] **`src/qa/pylinac_runner.py`**: pass notes list to `analyzer.publish_pdf(...)` in `run_acr_mri_large_analysis` (the existing single-run path).
- [x] **`src/qa/worker.py`**: add `QABatchWorker(QThread)` that runs `run_acr_mri_large_batch(...)` and emits `batch_result_ready = Signal(object)`.
- [x] **`src/qa/mri_compare_export.py`**: `build_mri_compare_json_document(...)` for schema 1.2 payload (used by `main.py` and tests).

### Phase B — Dialog compare mode

- [x] **`src/utils/config/qa_pylinac_config.py`**: `LC_COMPARE_MULTIPLIERS` = `(0.75, 0.8, 0.9, 1.0, 1.1, 1.2, 1.25)` and row default indices (supersedes two separately named tuples in this plan).
- [x] **`src/gui/dialogs/acr_mri_qa_dialog.py`**: add **"Compare low-contrast settings"** `QGroupBox` (checkable). When unchecked, hide the compare table.
- [x] **`src/gui/dialogs/acr_mri_qa_dialog.py`**: build the compare table (3 rows). Each row: method `QComboBox` + threshold `QComboBox` + sanity `QComboBox` + enable `QCheckBox`.
- [x] **`src/gui/dialogs/acr_mri_qa_dialog.py`**: threshold / sanity combo items from defaults × multipliers; pre-select row defaults per plan.
- [x] **`src/gui/dialogs/acr_mri_qa_dialog.py`**: **"Enable next run"** and **"Reset all rows to defaults"** (equivalent to “Add row” / “Reset rows”).
- [x] **`src/gui/dialogs/acr_mri_qa_dialog.py`**: extend `get_options()` to return `Optional[MRICompareRequest]` as the final element. `None` when compare mode is unchecked.
- [x] **`src/gui/dialogs/acr_mri_qa_dialog.py`**: module / `prompt_acr_mri_options` / class docstrings updated.

### Phase C — Main flow and results

- [x] **`src/main.py` — `_open_acr_mri_phantom_analysis`**: unpack `Optional[MRICompareRequest]`; single-run path unchanged when `None`.
- [x] **`src/main.py`**: compare path launches `QABatchWorker` and connects `batch_result_ready`.
- [x] **`src/main.py`**: `_show_mri_compare_result_dialog` — non-modal table + **Save comparison JSON…** + optional **Open PDF** + vanilla row from `pylinac_analysis_profile` (§1.6).
- [x] **`src/main.py`**: `_export_mri_compare_json` — `schema_version: "1.2"`, `compare_mode: true`, `runs` array; default stem `qa-acr-mri-compare-{timestamp}.json`.
- [x] **`src/main.py`**: single-run path passes `notes=` via `run_acr_mri_large_analysis`.

### Phase D — Documentation and tracking

- [x] **`dev-docs/info/PYLINAC_CUSTOMIZATION_AND_EXTENSIONS.md`**: shipped rows for compare mode, PDF notes, combined PDF.
- [x] **`dev-docs/info/PYLINAC_MRI_LOW_CONTRAST_DETECTABILITY.md`**: **Compare mode** section.
- [x] **`dev-docs/TO_DO.md`**: item tracked (completed / `[x]`).
- [x] **`CHANGELOG.md`**: entries under `[Unreleased]` / releases for compare mode and combined PDF.

### Phase E — Verification

- [x] Smoke test: `tests/test_mri_compare_phase_e.py` — `run_acr_mri_large_batch` with 3 `LcRunConfig` → 3 `QAResult`; distinct LC fields verified via `build_pylinac_analysis_profile` on per-run `QARequest` replicas (batch failure path with missing pylinac may repeat the same base profile).
- [x] Dialog test: same file, `test_acr_mri_dialog_compare_mode_yields_mri_compare_request` (`@pytest.mark.qt`).
- [x] Single-run regression: `test_single_run_qa_json_schema_1_1_key_set` asserts stable top-level keys for schema 1.1.
- [x] Notes: `test_build_mri_pdf_notes_contains_interpretation_keywords` asserts non-empty notes list with MTF / pylinac doc cues (full PDF pixel check remains manual).
- [x] Compare JSON: `test_build_mri_compare_json_document_schema_and_runs_length` asserts `1.2`, `compare_mode`, `runs` length.
- [x] Lint/type-check: run `basedpyright` / CI on touched modules as needed.

---

## Dependency note

Single-run PDF notes use only pylinac. **Compare-mode combined PDF** requires **`pypdf>=4.0`** (and **reportlab** via pylinac) — see `requirements.txt` and `MRI_COMPARE_COMBINED_PDF_PLAN.md`.

---

## Out of scope for this plan

- Saving per-run PDFs (each run produces one standard pylinac PDF; that is a future option).
- Comparing CT results.
- Compare mode for scan-extent tolerance (extent retry is a different workflow).
- More than 3 runs per comparison batch.
- Automated "best method" selection from comparison results.
