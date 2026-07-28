# Pylinac CT — CNR Intermediates, Batch Processing, and XLSX Export Plan

Status: proposed (refined after review)
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
    sub-point). Attribute **names** are confirmed via class introspection:
    `LowContrastModule` has `rois`, `background_rois`, `cnr`;
    `LowContrastDiskROI` has `mean`, `std`, `contrast_to_noise`, `pixel_value`.
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

- Create `feature/pylinac-ct-cnr-batch-xlsx` off `main`.
- Carry the `run.py` `sys.path` fix into this branch. Factor the insertion into a
  tiny `_ensure_src_on_path()` helper in `run.py` (rather than an inline
  statement) so it can be unit-tested without launching the Qt app (see Testing).
  The fix inserts `<repo>/src` at `sys.path[0]` before `runpy.run_path`, so
  top-level `core`/`gui`/… imports resolve identically via `launch.bat`→`run.py`
  and via `python src/main.py`.

## Feature 1 — CNR intermediate values

**Extraction sketch** (in `src/qa/pylinac_acr_ct.py`, called after
`analyzer.analyze()`):

```python
def _extract_low_contrast_cnr_details(analyzer) -> dict[str, Any]:
    """Harvest CNR intermediates from the live ACRCT low-contrast module.

    Every access is guarded; missing/renamed attributes degrade to a partial
    or empty dict rather than raising (pylinac minor-version drift).
    """
    out: dict[str, Any] = {}
    lcm = getattr(analyzer, "low_contrast_module", None)
    if lcm is None:
        return out
    try:
        out["cnr"] = float(lcm.cnr)                       # module-level CNR
    except Exception:
        pass
    obj = []
    for roi in getattr(lcm, "rois", []) or []:
        try:
            obj.append({"mean": float(roi.mean),
                        "contrast_to_noise": float(roi.contrast_to_noise)})
        except Exception:
            continue
    if obj:
        out["object_rois"] = obj
    bg_means, bg_stds = [], []
    for roi in getattr(lcm, "background_rois", []) or []:
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
3. Surface a short summary in the CT branch of `show_qa_result_dialog`
   (object mean / bg mean / bg σ / CNR).

Version guard: no hard pin; the defensive extraction is the guard. The plan
targets pylinac 3.43.2 attribute names verified above.

## Feature 2 — Batch pylinac CT

**Data model** — add to `src/qa/analysis_types.py`:

```python
@dataclass
class CTBatchResult:
    run_results: list[QAResult] = field(default_factory=list)
    run_labels: list[str] = field(default_factory=list)   # parallel to run_results
```

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
   `organizer.get_series_list()`, **filtered to CT** (first dataset's
   `Modality == "CT"` via `organizer.studies[...]`); label =
   `SeriesDescription` + `SeriesNumber` (fallback to series_key). Returns the
   parallel `(requests, labels)` lists. "Add folder…" appends folder-path
   pseudo-entries resolved to a `QARequest.folder_path` run (label = folder name).
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
   `src/gui/dialogs/ct_batch_result_dialog.py`, **modeled on the existing
   `src/gui/dialogs/mri_compare_result_dialog.py`** (confirmed present) — a
   `create_ct_batch_result_dialog(...)` factory with a `QTableWidget`
   (series × key metrics incl. the CNR block + status/warnings) and separate
   XLSX / JSON export buttons. The XLSX button calls `build_qa_workbook`
   directly (Feature 3), reused rather than reimplemented.
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

1. `build_qa_workbook(results: list[QAResult], labels: list[str] | None, ...)`.
   Single-run passes a 1-element list; batch passes N. Sheets:
   - **Summary** — one row per run/series, first column **Series/Run ID**
     (label or `series_uid`), then metrics incl. CNR intermediates.
   - **Per-run detail** — flat metric rows reusing the `_flatten` output shape.
   - **Images** — one embedded PNG per run, each preceded by its Series/Run ID
     label cell (stacked vertically).
2. **Image lifecycle + ownership (resolves review r2 item 6).** `run_acr_ct_analysis`
   is a pure function that constructs the analyzer internally and lets it go out
   of scope — **the worker never sees the analyzer**, so it cannot call
   `save_analyzed_image` itself. Ownership split:
   - **Input:** add a **transient input** field
     `QARequest.analyzed_image_out_path: str | None = None`. When set, the
     runner calls `analyzer.save_analyzed_image(that_path)` right after
     `analyze()` (same place F1 harvests CNR — all analyzer access stays inside
     the runner), guarded in try/except, and echoes it onto the result.
   - **Output:** add a **transient, non-serialized** field
     `QAResult.analyzed_image_path: str | None = None` (review r1 item 1) — a
     local filesystem artifact, **not** emitted by the JSON/CSV builders (those
     name fields explicitly, so it never leaks into exports).
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
  Update the one place that reads `raw_pylinac` (none internally today beyond the
  dump) and the schema note in `qa_export.py`.
