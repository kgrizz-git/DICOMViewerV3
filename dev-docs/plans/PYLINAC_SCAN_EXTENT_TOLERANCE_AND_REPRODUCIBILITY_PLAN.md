# Pylinac scan-extent tolerance + reproducibility metadata — implementation plan

**Goal:** Keep **stock pylinac behavior as the default** (no global offset hacks, no silent deviation from upstream). Offer an **optional, explicit** relaxation of the **physical scan extent** check when DICOM z metadata is slightly short of pylinac’s strict gate. **Record every non-vanilla choice** in **`QAResult`** and **JSON export** so physicists can distinguish “library-equivalent” runs from viewer-assisted runs.

**Context:** [PYLINAC_FLEXIBILITY_AND_WORKAROUNDS.md](../info/PYLINAC_FLEXIBILITY_AND_WORKAROUNDS.md) (technical background), [PYLINAC_INTEGRATION_OVERVIEW.md](../info/PYLINAC_INTEGRATION_OVERVIEW.md) (integration scope + JSON guidance after this plan lands).

**Primary pain:** `ACRMRILarge.localize()` → `CatPhanBase._ensure_physical_scan_extent()` raises when nominal module z-range (from fixed mm offsets) is not strictly inside stack min/max z (0.1 mm rounding). **ACR CT** uses the same base check and may benefit from the same machinery later.

---

## 1. Principles

| Principle | Implementation hint |
|-----------|---------------------|
| **Vanilla default** | `scan_extent_tolerance_mm = 0` (or `None` meaning “use stock pylinac class”) and **no** subclass unless user opts in or confirms retry. |
| **Explicit opt-in** | User checks a dialog option **or** confirms a **post-failure** “Retry with tolerance…” prompt. Never apply tolerance without a recorded flag. |
| **Full audit trail** | Every run populates a structured **`pylinac_analysis_profile`** (name TBD) on `QAResult` and in JSON: engine class, tolerance mm, retry generation, optional notes. |
| **No `pylinac.acr` offset globals** | Do not mutate `MR_*_OFFSET_MM` / `CT_*_OFFSET` for this feature; tolerance applies only to the **extent gate**, not phantom geometry constants. |

---

## 2. Data model (`src/qa/analysis_types.py`)

### 2.1 `QARequest` extensions

Add optional fields (names can be finalized in implementation):

- **`scan_extent_tolerance_mm: float | None`** — `None` or `0` = strict / vanilla extent check. Suggested allowed UI range when non-zero: **0.5–2.0 mm** (upper cap to avoid masking real missing coverage).
- **`use_relaxed_scan_extent: bool`** (optional alternative to tolerance-only) — if `True` and tolerance > 0, use subclass analyzer; if `False`, use stock `ACRMRILarge` / `ACRCT`. Could be folded into “tolerance > 0 implies relaxed” to avoid redundancy; **prefer a single source of truth**: e.g. **`scan_extent_tolerance_mm: float = 0.0`** only.

### 2.2 `QAResult` extensions

Add a dedicated dict or dataclass, e.g. **`pylinac_analysis_profile: Dict[str, Any]`**, always present (even for vanilla runs) with at least:

| Key | Example | Notes |
|-----|---------|--------|
| `engine` | `"ACRMRILarge"` / `"ACRMRILargeRelaxedExtent"` | Which class actually ran. |
| `vanilla_equivalent` | `true` / `false` | `true` only if tolerance == 0 and stock class. |
| `scan_extent_tolerance_mm` | `0` / `1.0` | Value used for the extent check. |
| `attempt` | `1` / `2` | Increment on user-confirmed retry after failure. |
| `parent_attempt_outcome` | `"failed_strict_extent"` | Set on attempt 2+ when applicable. |

**Rule:** Any field on `QARequest` that affects analysis (echo, `check_uid`, `origin_slice`, tolerance, future x/y/angle) should either appear in **`pylinac_analysis_profile`** or remain duplicated under JSON **`inputs`** for backward compatibility; **profile** is the canonical “what differed from stock pylinac defaults.”

### 2.3 JSON export (`_export_qa_json` in `src/main.py`)

- Bump **`schema_version`** to **`"1.1"`** when `pylinac_analysis_profile` is introduced (document migration: consumers may assume `1.0` without profile).
- Add top-level **`pylinac_analysis_profile`** mirroring `QAResult` (not only nested under `metrics`).
- Keep existing **`inputs`** object; merge or cross-reference so exports stay human-readable.

---

## 3. Runner (`src/qa/pylinac_runner.py`)

### 3.1 Subclass placement

Add a small module, e.g. **`src/qa/pylinac_extent_subclasses.py`**, defining:

- **`ACRMRILargeRelaxedExtent`** — subclasses **`ACRMRILarge`**, overrides **`_ensure_physical_scan_extent`** to replicate stock logic from `pylinac.ct.CatPhanBase` but widen the allowed scan range by **`scan_extent_tolerance_mm`** on **both** ends (min and max), or equivalent `numpy.isclose` / epsilon comparison consistent with pylinac’s 0.1 mm rounding behavior.

**Implementation detail:** Store tolerance on the instance (`__init__` or set before `analyze()` from `QARequest`) so the subclass stays thread-safe and testable.

### 3.2 Selection logic

```text
if request.scan_extent_tolerance_mm and request.scan_extent_tolerance_mm > 0:
    analyzer_cls = ACRMRI...RelaxedExtent
else:
    analyzer_cls = stock ACRMRILarge
```

Same pattern later for **`ACRCT`** if product wants parity (**`ACRCTRelaxedExtent`**).

### 3.3 Building `pylinac_analysis_profile`

Centralize a helper, e.g. **`build_pylinac_analysis_profile(request, *, attempt=1, parent_failure_reason=None) -> dict`**, called from both CT and MRI runners so CT/MRI stay consistent.

---

## 4. Worker (`src/qa/worker.py`)

- Pass through new `QARequest` fields unchanged.
- No thread logic change unless retry is implemented **inside** the worker (prefer **not**—keep worker single-pass; see §5).

---

## 5. GUI / UX (`src/gui/dialogs/acr_mri_qa_dialog.py`, `src/main.py`)

### 5.1 Proactive option (before run)

In **`AcrMrIQaOptionsDialog`** (or a nested group “Geometry / scan extent”):

- Checkbox: **“Allow small scan-extent tolerance (DICOM z rounding)”** — unchecked by default.
- When checked: **`QDoubleSpinBox`** or combo (0.5 / 1.0 / 1.5 / 2.0 mm); default **1.0 mm**.
- Short tooltip: links to physicist responsibility; not a substitute for rescan if modules are missing.

Thread **`scan_extent_tolerance_mm`** into **`QARequest`** and **`json_inputs`** / profile builder.

### 5.2 Reactive path (after failure)

In **`on_result`** (or a small helper called from it) for MRI (and later CT):

1. If **`result.success`** or tolerance already > 0: existing flow (dialog + JSON).
2. If **failure** and **error text** matches the known **physical scan extent** `ValueError` (substring or structured check if we wrap exceptions in the runner):
   - Show **`QMessageBox`**: explain strict check failed; offer **“Retry with 1.0 mm tolerance”** / **“Choose tolerance…”** / **Cancel**.
   - On accept: rebuild **`QARequest`** with same paths + **`scan_extent_tolerance_mm`** set, **`attempt`** 2 in profile metadata (pass via `QARequest` optional `qa_attempt` / or only in `json_inputs` for second run).
   - Restart **`QAAnalysisWorker`** (same pattern as `_start_qa_worker` but skip duplicate PDF prompt or reuse last path—product decision: **re-prompt PDF** only on first run is simplest).

**Cancel / dismiss:** Export JSON for the **failed** run still includes **`pylinac_analysis_profile`** with `vanilla_equivalent: true` and `attempt: 1`.

### 5.3 Result dialog

- If `not result.pylinac_analysis_profile.get("vanilla_equivalent", True)`: append one line, e.g. **“Non-vanilla pylinac path: see JSON pylinac_analysis_profile.”**

---

## 6. Testing

- **Unit:** `ACRMRILargeRelaxedExtent._ensure_physical_scan_extent` with synthetic z lists (min/max bracketing) vs stock behavior—**mock** or minimal stack if full construction is heavy.
- **Integration (optional):** Mark `@pytest.mark.skipif` without pylinac or golden folder.
- **Manual:** Real 11-slice MRI series that fails strict and passes with 1 mm tolerance.

---

## 7. Documentation updates (checklist)

- [ ] [PYLINAC_INTEGRATION_OVERVIEW.md](../info/PYLINAC_INTEGRATION_OVERVIEW.md) — reproducibility / JSON guidance (see plan handoff in repo).
- [ ] [PYLINAC_FLEXIBILITY_AND_WORKAROUNDS.md](../info/PYLINAC_FLEXIBILITY_AND_WORKAROUNDS.md) — link to this plan under §1 / §5.
- [ ] [PYLINAC_AND_AUTOMATED_QA_STAGE1_PLAN.md](PYLINAC_AND_AUTOMATED_QA_STAGE1_PLAN.md) — optional pointer “Stage 1b+ extent tolerance” if still active.
- [ ] `CHANGELOG.md` — user-visible behavior + schema_version bump when implemented.

---

## 8. Future (out of scope for this plan)

- **Upstream PR** to pylinac: `extent_tolerance_mm` on `localize()` / `analyze()`—would let us delete subclass if merged.
- **Canonical 11-slice index mode** (separate plan): index-based module assignment when protocol guarantees ACR slice 1–11 order.
- **CatPhan** relaxed extent for CBCT—same subclass pattern on `CatPhan504` etc.

---

## 9. Exit criteria

- Default MRI (and optionally CT) run is **byte-for-byte equivalent** to stock pylinac with respect to extent logic when tolerance is **0** and user does not opt in.
- User can opt in **before** run or **after** extent failure.
- JSON **`1.1`** includes **`pylinac_analysis_profile`** sufficient to reproduce **which** code path ran without reading the rest of the payload twice.
