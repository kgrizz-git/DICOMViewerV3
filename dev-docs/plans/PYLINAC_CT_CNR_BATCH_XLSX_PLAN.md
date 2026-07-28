# Pylinac CT — CNR Intermediates, Batch Processing, and XLSX Export Plan

Status: F1 + F3 + F2 implemented (commits 39dcd7a, 20c8f82, 5a5d3ed);
pre-merge live-phantom value check for F1 still open
Date: 2026-07-28
Branch: `feature/pylinac-ct-cnr-batch-xlsx`
Review: `tmp/PYLINAC_CT_CNR_BATCH_XLSX_PLAN_ASSESSMENT_2026-07-28-153637.md`
(refinements folded in below; factual corrections noted)

## Goals

Three user-requested capabilities for pylinac ACR CT analysis:

1. **CNR intermediates** — surface the intermediate values behind the
   contrast-to-noise ratio: mean of the object (low-contrast) ROI, mean of the
   background ROI, and the background noise (standard deviation).
2. **Batch pylinac** — run ACR CT analysis over multiple selected series in one
   action.
3. **XLSX export** — export pylinac results as `.xlsx`, embedding the analyzed
   image like the PDF.

A one-line `run.py` launcher fix (insert `src/` onto `sys.path` before
`runpy.run_path`, so `launch.bat` resolves imports the same as running
`src/main.py` directly) is folded into this branch to ship in the same PR / CI
run.

## Locked decisions

- **Batch selection UX:** a checkbox-list dialog of loaded CT series, plus an
  "Add folder…" affordance. (Chosen over navigator multi-select or a
  folders-only picker — smallest blast radius, reuses organizer data, still
  supports folder inputs.)
- **XLSX images:** embed pylinac's analyzed composite image per run (save to a
  temp PNG, embed via `openpyxl.drawing.image.Image`), degrading gracefully when
  no image is available.

## Grounding facts (verified against current code / installed pylinac 3.43.2)

- CT analysis: `src/qa/pylinac_acr_ct.py::run_acr_ct_analysis`, run off-thread by
  `QAAnalysisWorker` (`src/qa/worker.py`), orchestrated by
  `QAAppFacade.open_acr_ct_phantom_analysis` (`src/gui/qa_app_facade.py`).
- Results normalize into `QAResult` (`src/qa/analysis_types.py`); pure builders
  in `src/qa/qa_export.py` produce JSON / CSV. `openpyxl` 3.1.5 and `Pillow`
  12.3.0 are installed and declared in `requirements.txt`.
- **CNR source-of-truth (refined):**
  - `analyzer.results_data()` returns a **pydantic** `ACRCTResult` whose
    `low_contrast_module` exposes only the aggregate `cnr` (float). The current
    runner passes this object through `_jsonable`, which **stringifies** it — so
    `raw_pylinac` currently stores a text blob, not structured data. Fix by
    calling `results_data(as_dict=True)` so `raw_pylinac` becomes structured.
    Because `as_dict=True` returns a plain dict, the runner's existing
    `_jsonable(rd)` call still runs over it (the `isinstance(rd, dict)` branch),
    so JSON-safety is preserved end-to-end (resolves review r2 item 2).
  - **What `results_data(as_dict=True)` actually exposes for the low-contrast
    module (verified 3.43.2):** `LowContrastModuleOutput.model_fields` =
    `{offset, roi_distance_from_center_mm, roi_radius_mm, roi_settings,
    rois: dict[str, float], cnr: float}`. So the structured dict gives the
    module-level `cnr` and a per-object-ROI `rois` map — but has **no
    `background_rois` and no per-ROI `std`**.
  - **Therefore the background mean / σ (the noise term the user explicitly
    wants) is NOT in `results_data()` and requires the live analyzer** —
    live extraction is required, not redundant (resolves review r2 item 1
    sub-point). Attribute **names and shapes** confirmed via live source /
    introspection against installed pylinac 3.43.2 (resolves review r3 item 1):
    - `LowContrastModule.rois` and `.background_rois` are
      **`dict[str, LowContrastDiskROI]`** (via `CatPhanModule`:
      `self.rois: dict[str, HUDiskROI]`), keyed by ROI name — ACR CT has a
      **single `"ROI"` key** in each. They are **not** lists and **not**
      `dict[str, list[...]]`; extraction must iterate `.values()`.
    - `LowContrastModule.cnr` is a **method** (`def cnr(self) -> float`,
      `|A−B|/SD`), **not** a property → call `lcm.cnr()`, not `lcm.cnr`.
    - `LowContrastDiskROI` exposes `mean`, `std`, `pixel_value`
      (cached_property) and `contrast_to_noise` (property).
    A **live-phantom value check** (run against a real CatPhan dataset,
    confirming the numbers, not just the names) is a pre-merge checkpoint for F1.
  - **Source-of-truth split:** module `cnr` — take from `raw_pylinac`
    (as_dict) as canonical, cross-checked against the live value; object-ROI
    means and background mean/σ — harvest from the live analyzer inside the
    runner and stash on `QAResult.metrics["low_contrast_cnr"]`.
- **Correction to review issue 6:** `organizer.get_series_list(study_uid=None)`
  **does** exist (`src/core/dicom_organizer.py:702`), returning
  `list[tuple[study_uid, series_key]]`. Series datasets are reachable via
  `organizer.studies[study_uid][series_key]`; ordered paths via
  `get_file_path_for_dataset(dataset, study_uid, series_key, slice_index)`
  (see `resolve_focused_series_ordered_paths`, `src/gui/export_app_facade.py`).
- **Correction to review issue 9:** Pillow is already a declared/installed
  dependency; only a defensive import guard is needed, not a new dependency.
- `ACRCT.save_analyzed_image(path)` exists and produces the embedded PNG.
- The series navigator has **no** multi-select today.

## Step 0 — Branch setup

- **Done:** branch `feature/pylinac-ct-cnr-batch-xlsx` exists (currently checked
  out) and the raw `run.py` `sys.path` fix is already committed on it
  (`6fbce73`, alongside this plan doc). It is **not** on `origin/main`, so it
  still ships inside this branch's single PR / CI run as intended — nothing was
  merged to main behind the PR (resolves review r3 item 2, which read the
  committed fix as "already merged").
- **Remaining (optional):** the fix is an inline `sys.path.insert` at
  `run.py:10`. Refactor it into a tiny `_ensure_src_on_path()` helper so it can
  be unit-tested without launching the Qt app (see Testing). If skipped, drop
  `tests/test_run_launcher.py` from scope — but the helper is cheap and the test
  is the only guard against a regression of the `launch.bat` import breakage.

## Feature 1 — CNR intermediate values — **IMPLEMENTED**

**Status:** landed in `src/qa/pylinac_acr_ct.py` +
`src/gui/qa_app_facade.py`; tests green
(`tests/test_qa_pylinac_acr_ct_cnr.py`, 148 passed in the qa/acr/pylinac/facade
subset). What shipped matches the sketch below:
`_extract_low_contrast_cnr_details(analyzer)`, `_jsonable` numpy hardening,
`results_data(as_dict=True)`, `metrics["low_contrast_cnr"]`, and a CNR summary
block in `show_qa_result_dialog` via `_format_low_contrast_cnr_summary`.
**Pre-merge checkpoint still open:** live-phantom numeric value check against a
real CatPhan dataset (names/shapes already verified against installed 3.43.2).

**Canonical `metrics["low_contrast_cnr"]` shape (produced by F1 — F2/F3 consume
this exact structure):**

```python
{
    "cnr": 4.5,                      # float, module-level CNR (may be absent)
    "object_rois": [                 # list; absent if none harvestable
        {"mean": 100.0, "pixel_value": 100.0, "contrast_to_noise": 3.0},
    ],
    "background": {                  # absent if no background ROI harvestable
        "means": [10.0], "stds": [2.0],
        "mean": 10.0,                # aggregate background mean (noise floor)
        "std": 2.0,                  # aggregate background σ (noise term)
    },
}
```

Any key may be missing (defensive degradation); consumers must use `.get()` and
type-check. The single object-ROI mean shown in the UI is the average of
`object_rois[*].mean`.

**Extraction sketch** (as implemented, for reference):

```python
def _extract_low_contrast_cnr_details(analyzer) -> dict[str, Any]:
    """Harvest CNR intermediates from the live ACRCT low-contrast module.

    Every access is guarded; missing/renamed attributes degrade to a partial
    or empty dict rather than raising (pylinac minor-version drift).

    pylinac 3.43.2 shapes (verified against installed source):
      - lcm.rois / lcm.background_rois are dict[str, LowContrastDiskROI]
        (ACR CT: single "ROI" key each) -> iterate .values(), NOT as a list.
      - lcm.cnr is a METHOD (|A-B|/SD), not a property -> call lcm.cnr().
      - LowContrastDiskROI: .mean, .std, .pixel_value, .contrast_to_noise.
    """
    out: dict[str, Any] = {}
    lcm = getattr(analyzer, "low_contrast_module", None)
    if lcm is None:
        return out
    try:
        out["cnr"] = float(lcm.cnr())                     # module-level CNR (method!)
    except Exception:
        pass
    obj = []
    for roi in (getattr(lcm, "rois", {}) or {}).values():         # dict, not list
        try:
            obj.append({"mean": float(roi.mean),
                        "pixel_value": float(roi.pixel_value),
                        "contrast_to_noise": float(roi.contrast_to_noise)})
        except Exception:
            continue
    if obj:
        out["object_rois"] = obj
    bg_means, bg_stds = [], []
    for roi in (getattr(lcm, "background_rois", {}) or {}).values():   # dict, not list
        try:
            bg_means.append(float(roi.mean)); bg_stds.append(float(roi.std))
        except Exception:
            continue
    if bg_means:
        out["background"] = {
            "means": bg_means, "stds": bg_stds,
            "mean": sum(bg_means) / len(bg_means),        # aggregate noise floor
            "std": sum(bg_stds) / len(bg_stds),
        }
    return out
```

1. Add the helper above; store result under `metrics["low_contrast_cnr"]`
   (keys: `object_rois`, `background`, `cnr`). Flows into JSON and the flat CSV
   automatically via existing `_flatten`.
2. Also switch the `results_data()` capture to `as_dict=True` so `raw_pylinac`
   becomes structured (fixes the stringification noted above); keep the existing
   `metrics` cross-check for the module-level `cnr`.
   - **numpy-scalar safety (resolves review r3 item 4):** the installed numpy is
     **2.5.1**, where `np.float64` still subclasses `float` but `np.float32` /
     `np.int64` / `np.int32` do **not**. `_jsonable`
     (`src/qa/pylinac_acr_ct.py:33`) currently gates on
     `isinstance(v, (bool, int, float, str))`, so any non-`float64` numpy scalar
     surviving `as_dict=True` would be `str()`-ified into the JSON. Harden
     `_jsonable` to coerce numpy scalars first: `np.integer → int`,
     `np.floating → float` (guarded behind the existing optional-numpy import).
     The F1 harvest already calls `float(...)` on every value, so
     `metrics["low_contrast_cnr"]` is unaffected — this only protects the
     `raw_pylinac` passthrough.
3. Surface a short summary in the CT branch of `show_qa_result_dialog`
   (object mean / bg mean / bg σ / CNR).

Version guard: no hard pin; the defensive extraction is the guard. The plan
targets pylinac 3.43.2 attribute names verified above.

## Feature 2 — Batch pylinac CT

**Data model** — add to `src/qa/analysis_types.py` alongside the existing
compare-mode types (near `LcRunConfig`, `src/qa/analysis_types.py:517`):

```python
@dataclass
class CTBatchResult:
    run_results: list[QAResult] = field(default_factory=list)
    run_labels: list[str] = field(default_factory=list)   # parallel to run_results
```

The batch summary dialog's CNR columns read the same canonical
`metrics["low_contrast_cnr"]` shape documented in F1 (object mean = avg of
`object_rois[*].mean`, `background.mean`, `background.std`, `cnr`), via `.get()`
with blanks for absent keys — identical to the F3 Summary sheet columns.

(No per-series "config" — one CT options set applies to all series — so there is
no `run_configs` analogue; identity/modality already ride on each `QAResult`,
and `run_labels` carries the user-facing series label.)

**Label ownership (resolves review r2 item 3):** the worker must **not** hold an
`organizer` reference (it runs off the GUI thread). The selection dialog builds
the display labels on the GUI thread and passes them in. `QACTBatchWorker` takes
two parallel lists in its constructor:
`__init__(self, requests: list[QARequest], series_labels: list[str], *, app_version="")`.
Labels are **not** added to `QARequest` (which is per-series input, not display
metadata). The worker copies `series_labels` straight into `CTBatchResult.run_labels`.

1. **Selection dialog** `prompt_batch_series_selection`: checkbox list built from
   `organizer.get_series_list()`, **filtered to CT** by reading the first dataset
   of each series via `organizer.studies[study_uid][series_key][0]` and checking
   `Modality == "CT"`. **Cost (resolves review r3 item 9):** the datasets are the
   already-loaded in-memory pydicom objects — reading `Modality`,
   `SeriesDescription`, `SeriesNumber` is attribute access, no file I/O or pixel
   load — so the filter is cheap even for many series. Label =
   `str(SeriesDescription)` + ` #` + `str(SeriesNumber)`, each guarded with
   `getattr(ds, ..., "")`; fall back to `series_key` when both are empty
   (resolves review r3 item 7). Returns the parallel `(requests, labels)` lists.
   "Add folder…" appends folder-path pseudo-entries resolved to a
   `QARequest.folder_path` run (label = folder basename).
2. **Worker** `QACTBatchWorker` in `worker.py`:
   - **Concurrency: serial** (confirmed acceptable). Rationale: process-based
     parallelism is the only worthwhile kind (thread-based is unsafe because
     pylinac drives matplotlib's global `pyplot` state off-thread, and is
     GIL-bound anyway), but a process pool multiplies peak RAM — bypassing the
     app's memory-budgeted `StudyCache` — and adds frozen-app / Windows-`spawn`
     packaging and cancellation complexity that outweigh the wall-clock win at
     typical batch sizes (seconds per series, a handful to dozens of series). A
     bounded `ProcessPoolExecutor` remains a clean phase-2 upgrade if needed.
   - **Signals:** `series_completed(int done, int total, object QAResult)`
     emitted per series (drives N-of-M progress), then
     `batch_result_ready(object CTBatchResult)` at the end.
   - **Cancellation:** cooperative — a `_cancelled` flag checked **between**
     series; the in-flight series finishes, remaining series are skipped, and a
     partial `CTBatchResult` is emitted.
   - **Error isolation:** per-series exceptions produce a failed `QAResult`
     (not raised); the batch continues.
3. **Facade + dialog:** `open_acr_ct_batch_analysis` in `QAAppFacade`
   (progress dialog updated on `series_completed`; **no per-series modal** — all
   failures collected into the final dialog). New
   `src/gui/dialogs/ct_batch_result_dialog.py`. **Borrow the scaffolding
   (factory shape, `QTableWidget` + export-button row, window chrome) from
   `src/gui/dialogs/mri_compare_result_dialog.py`, but NOT its semantics**
   (resolves review r3 item 6): the MRI dialog is a side-by-side *compare* view;
   this is a *batch summary* — **one row per series**, columns = series label,
   status/warnings, and the key CNR block (object mean / bg mean / bg σ / CNR).
   A `create_ct_batch_result_dialog(...)` factory with separate XLSX / JSON
   export buttons. The XLSX button calls `build_qa_workbook` directly
   (Feature 3), reused rather than reimplemented.
4. **Signal wiring:** new `acr_ct_batch_requested` signal on the QA main window
   (no payload — the dialog resolves the selection), wired in
   `main_window_menu_builder.py` / `app_signal_wiring.py` beside the existing
   `acr_ct_phantom_requested`.

Out of initial scope (deferred; review issue 14): per-series PDF output. Single
run keeps `QARequest.output_pdf_path`; batch ships without a PDF-per-series
workflow to avoid naming/dir-picker scope creep.

## Feature 3 — XLSX export (with embedded image)

**Module boundary (review issue 7):** new `src/qa/qa_xlsx_export.py`, separate
from `qa_export.py`. Rationale: `qa_export.py` stays light (stdlib `csv`/`json`
only); `qa_xlsx_export.py` isolates the heavier `openpyxl` + `Pillow` imports and
the image-embed logic. Both remain Qt-free.

1. `build_qa_workbook(results: list[QAResult], labels: list[str] | None = None, *, app_version: str = "") -> Workbook`
   (returns an `openpyxl.Workbook`; the caller saves it, so the builder stays
   pure/Qt-free and testable via an in-memory round-trip). Single-run passes a
   1-element list; batch passes N. `labels`, when given, must be parallel to
   `results`; when `None`, fall back to `series_uid` per row. Sheets:
   - **Summary** — one row per run/series, first column **Series/Run ID**
     (label or `series_uid`), then key columns pulled from
     `metrics["low_contrast_cnr"]` (see canonical shape in F1): object ROI mean
     (avg of `object_rois[*].mean`), `background.mean`, `background.std`,
     `cnr` — plus status and a joined warnings cell. Use `.get()` throughout;
     blank cell when a key is absent.
   - **Per-run detail** — flat metric rows. **Reuse `qa_export._flatten`**
     (`src/qa/qa_export.py:98`) over `result.metrics` for the exact dotted-key /
     list-join shape the CSV export already produces; one detail block per run,
     separated by the Series/Run ID.
   - **Images** — one embedded PNG per run, each preceded by its Series/Run ID
     label cell (stacked vertically).
   - **Import note:** `_flatten` is currently module-private; the F3 agent may
     import it as `from qa.qa_export import _flatten` (same-package internal
     reuse) rather than duplicating it.
2. **Image lifecycle + ownership (resolves review r2 item 6).** `run_acr_ct_analysis`
   is a pure function that constructs the analyzer internally and lets it go out
   of scope — **the worker never sees the analyzer**, so it cannot call
   `save_analyzed_image` itself. Ownership split:
   - **Input:** add a **transient input** field
     `QARequest.analyzed_image_out_path: str | None = None` to the `QARequest`
     dataclass (`src/qa/analysis_types.py:449`, e.g. after
     `output_pdf_path` at line 457). When set, the runner calls
     `analyzer.save_analyzed_image(that_path)` right after `analyze()` in
     `run_acr_ct_analysis` (`src/qa/pylinac_acr_ct.py`, same block where F1 now
     calls `_extract_low_contrast_cnr_details` — all analyzer access stays inside
     the runner), guarded in try/except, and echoes the path onto the result.
   - **Output:** add a **transient, non-serialized** field
     `QAResult.analyzed_image_path: str | None = None` to the `QAResult`
     dataclass (`src/qa/analysis_types.py:493`, after
     `pylinac_analysis_profile` at line 509) — a local filesystem artifact.
     **Leak-safety is already guaranteed:** `build_single_run_document`
     (`src/qa/qa_export.py:69-92`) and `build_metrics_csv` (line 112, via
     `_flatten` over `result.metrics` only) both name their fields explicitly and
     never reflect arbitrary `QAResult` attributes, so a new field cannot leak
     into JSON/CSV. Add a `test_qa_xlsx_export` assertion that neither export
     contains the image path as a regression guard.
   - **Temp-dir owner:** the **caller** (`QAAppFacade` for single run;
     `QACTBatchWorker` for batch) creates one `tempfile.TemporaryDirectory`,
     puts a unique PNG path per run into `analyzed_image_out_path`, and keeps the
     directory **open until after `workbook.save()`**, cleaning it in a `finally`.
     This keeps the runner's impurity to a single explicit, opt-in side effect.
3. **Pillow guard (review issue 9):** wrap the image import/embed; if Pillow or
   the PNG is unavailable, skip the Images sheet and add a note cell — the rest
   of the workbook still writes.
4. Wire XLSX as a third filter in `export_qa_results` (single) and an
   "Export XLSX" button in both CT result dialogs.

## Sequencing (review issue 15)

F1 → F3 → F2. F1 must precede F2 (batch dialog shows CNR). F3 precedes F2 so the
`build_qa_workbook` builder exists for the batch dialog's multi-row XLSX export
path; F3 also delivers standalone value on the existing single-run flow. Each
feature is independently shippable. One branch → one PR → one CI run, `run.py`
fix folded in.

## Testing (review issue 16)

- `tests/test_qa_pylinac_acr_ct_cnr.py` — `_extract_low_contrast_cnr_details`
  against a mock analyzer (rois/background_rois/cnr present, partial, and
  empty); assert graceful degradation.
- `tests/test_qa_xlsx_export.py` — `build_qa_workbook` openpyxl round-trip
  (single + multi-row), Pillow-missing path skips Images sheet, no Qt import.
- `tests/test_qa_ct_batch_worker.py` — `QACTBatchWorker` per-series error
  isolation, `series_completed` count sequence, and cooperative cancellation
  producing a partial `CTBatchResult`.
- `tests/test_run_launcher.py` (resolves review r2 item 5) — call
  `run._ensure_src_on_path()` and assert `<repo>/src` is on `sys.path` and that a
  top-level package (e.g. `import utils.version` / `core`) then imports without
  `ModuleNotFoundError`. No Qt app launch (`run.py --version` is not viable — the
  app opens a window and has no such flag), so the extracted helper is what makes
  this testable.
- Extend `tests/conftest.py` with a mock-analyzer fixture; agent-smoke-harness
  for the UI paths (selection dialog, batch dialog, exports).

## Risks / mitigations

- **pylinac attribute drift** → defensive extraction; partial/empty degrade.
- **Temp-file lifecycle** → `TemporaryDirectory` held until after
  `workbook.save()`, cleaned in `finally`.
- **Thread safety / batch** → serial worker (matplotlib/temp global state);
  pure builders kept out of the Qt/GUI layer, matching the `qa_export` split.
- **Export leakage of transient image path** → new field excluded from the
  explicit-field JSON/CSV builders; verified by `test_qa_xlsx_export` /
  existing export tests.
- **JSON `raw_pylinac` shape change (resolves review r2 item 7)** → the
  `as_dict=True` fix changes `raw_pylinac` from an opaque string blob to a
  structured dict inside the single-run document (`build_single_run_document`,
  currently `schema_version "1.1"`; note "1.2" is already used by the MRI compare
  document). Decision: document `raw_pylinac` in the schema as an **opaque,
  pylinac-version-dependent passthrough** (not a stable contract) **and** bump the
  single-run `schema_version` to **"1.3"** to signal the change to any consumer.
  (Review r3 item 15 recommended "1.2"; rejected — "1.2" is already taken by the
  MRI compare document, so "1.3" avoids the collision.)
  Update the one place that reads `raw_pylinac` (none internally today beyond the
  dump) and the schema note in `qa_export.py`.
