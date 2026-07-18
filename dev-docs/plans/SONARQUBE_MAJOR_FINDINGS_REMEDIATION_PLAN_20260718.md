# Plan: Remediate Important Local SonarQube Major Findings

**Last updated:** 2026-07-18 (revised after implementation-readiness nits)
**Status:** Active (staged on `fix/sonarqube-major-findings-20260718`)
**Source analysis:** `2026-07-18T17:12:01+0000`, revision `9484958196fcd183a88407f5f312d77bb521f8df`
**Revision notes:**
- (rev 1) Phase 2 partitioned per-site (safe-collapse vs needs-review);
  Phase 3 reframed from "tolerance refactor" to "per-site NOSONAR suppression
  with rationale" after inspection showed every flagged site uses exact equality
  against a DICOM-stored decimal, a documented VTK sentinel, or a configuration
  / label sentinel. See `tmp/sonarqube_remediation_plan_assessment_20260718_140945.md`.
- (rev 2) Corrected stale Goal/scope; flipped Phase 2b slice-sync advice from
  "restore direct `planes[idx]`" (unsafe — would desync) to "collapse to the
  shared mapper path"; resolved the 2a/2b contradiction on
  `image_viewer_view.py:1295`; replaced invented test paths with real ones;
  specified `# NOSONAR(S1244)` recipe for compound / generator sites; softened
  measurement Phase 2b from "recover alternate behavior" to "confirm sameness →
  collapse"; added CHANGELOG / SemVer / MAINTENANCE_LOG tracking and a fresh
  Sonar-analysis verification step. See
  `tmp/sonarqube_remediation_plan_assessment_20260718_142725.md`.
- (rev 3) Implementation-readiness polish: Phase 2 intro no longer claims a
  missing alternate algorithm; annotation regressions prefer
  `tests/gui/test_annotation_options_dialog.py`; SemVer bump is optional until
  an intentional version advance / release cut (Unreleased CHANGELOG entry is
  enough for this pass).

## Goal and scope

The local reporter (`scripts/report_local_sonarqube_issues.py`) was extended to
surface MAJOR findings (all types), not only BLOCKER and CRITICAL
BUG/VULNERABILITY. The refreshed scan returned **140** DICOM-Viewer-scoped
findings: 0 BLOCKER, 0 CRITICAL, 25 MAJOR BUG, 1 MAJOR VULNERABILITY, and 114
MAJOR CODE_SMELL.

This plan remediates the **substantive** findings in three stages:
- **Phase 1 — Security:** the 1 S2245 insecure-randomness finding.
- **Phase 2 — Logic bugs:** all 6 S3923 identical-branch findings.
- **Phase 3 — Float equality:** all 19 S1244 findings, addressed via documented
  `# NOSONAR(S1244)` suppression with per-site rationale (no `math.isclose`
  refactors — see Phase 3 for why).

Only the 114 MAJOR CODE_SMELL findings are explicitly deferred to a separate
cleanup pass, to keep this branch reviewable and behavior stable.

## Triage summary

| Rule | Severity / Type | Count | Disposition |
|------|-----------------|-------|-------------|
| `python:S2245` | MAJOR VULNERABILITY | 1 | **Fix — Phase 1 (security)** |
| `python:S3923` | MAJOR BUG (duplicate/identical branch) | 6 | **Fix — Phase 2 (logic bugs)** — partition per-site (see Phase 2) |
| `python:S1244` | MAJOR BUG (float `==`) | 19 | **Suppress per-site — Phase 3** — no tolerance refactor (see Phase 3) |
| `python:S*` CODE_SMELL | MAJOR CODE_SMELL | 114 | Deferred (separate cleanup pass) |

> S1244 count note: 19 findings map to 18 distinct source lines because
> `src/gui/image_viewer_view.py:177` (`if sx != 1.0 or sy != 1.0:`) raises two
> findings on a single line (two float comparisons).

## Phase 1 — Security: insecure randomness in the anonymizer

- [x] `src/utils/deep_anonymizer.py:281` (`python:S2245`): date-shift jitter is
      drawn from the non-cryptographic `random.randint`. Replace with
      `secrets.randbelow(DATE_JITTER_MAX_DAYS + 1)` (semantically equivalent
      range: both cover `[0, DATE_JITTER_MAX_DAYS]`) so the batch-wide jitter
      that hides the real date baseline is not predictable.
- [x] Add `import secrets` and **remove the now-dead `import random`** at
      `src/utils/deep_anonymizer.py:20`. Verified: `random` has exactly one call
      site in the file (line 281); all other `random` references at lines 52 and
      277 are comments. Removing the import prevents a future contributor from
      re-introducing `random` into the de-identification path.
- [x] Update the now-stale module comments at `:52–55` and `:277` that still say
      "random" / "± jitter" — the implementation only subtracts jitter
      (`DATE_ANCHOR - timedelta(days=jitter)`), so the `±` claim is already
      inaccurate and switching to `secrets` is a natural moment to fix the
      comments so "random" breadcrumbs are not left behind.
- [x] Keep `random` out of any de-identification path; confirm the module still
      imports and the date-offset unit tests in `tests/test_deep_anonymizer.py`
      (which already has jitter / near-1900 coverage) pass.

## Phase 2 — Logic bugs: identical if/else branches (`python:S3923`)

Six sites where both branches of a conditional do the same work (redundant
structure / copy-paste leftover). Git history shows no divergent alternate
bodies to restore; the fix is to collapse to one path. They are partitioned by
risk:

### Phase 2a — Safe collapse (behavior-preserving)

The redundant branch is provably unreachable or the if/else dispatches on a
semantic flag whose both arms intentionally do the same work; collapse to a
single path, no behavior change.

- [x] `src/gui/dialogs/annotation_options_dialog.py:455` — both arms assign
      `roi_color = roi_line_color`; collapse. Also rewrite the now-false comment
      at `:450–454` (still claims "fallback to font color") so the next Sonar
      pass does not leave lying docs. Add a regression in
      `tests/gui/test_annotation_options_dialog.py` asserting the displayed ROI
      color equals the configured line color regardless of whether font color
      matches.
- [x] `src/gui/dialogs/annotation_options_dialog.py:483` — same pattern for
      `measurement_color`; mirror the ROI collapse, fix the comment at
      `:478–482`, and add the parallel measurement-color assertion.
- [x] `src/gui/image_viewer_view.py:1295` — both arms of the inner `if/else`
      (inside the `len(array_shape) == 3` branch) assign
      `frame_array = pixel_array`. Later code branches on
      `frame_array.shape`; a true 2-D grayscale array never enters the
      `len(array_shape) == 3` path, so the speculation that the grayscale branch
      should slice is not supported. Collapse to a single assignment. Add a
      regression in `tests/gui/test_image_viewer_fit_helpers.py` (or a new
      `tests/gui/test_image_viewer_view.py`) covering the 3-D single-frame
      color/grayscale shape paths.

### Phase 2b — Confirm-then-collapse (verified sameness, no speculative restoration)

Git history shows both arms at these three sites were byte-identical from the
initial commit (`15de4f6`) — there is no prior divergent body to "restore."
The right disposition is almost certainly **collapse the redundant if/else**,
*not* reconstruct a missing algorithm from speculation. Each site still requires
reviewer confirmation that handle-drag vs. group-drag (measurement) or in-range
vs. out-of-range dispatch (slice-sync) were never intended to differ; if they
were, treat that as a new behavioral spec, not a Sonar fix.

- [x] `src/core/slice_sync_coordinator.py:195` — both arms of the outer
      `if source_slice_idx < 0 or >= len(source_stack.planes):` call
      `_dataset_idx_to_sorted_pos(source_idx, source_slice_idx, source_stack)`
      then index `source_stack.planes[sorted_pos]`. The sibling
      `get_current_plane()` (`:101–118`) **always** goes through
      `_dataset_idx_to_sorted_pos` before indexing `planes` and never uses the
      raw dataset index as a plane subscript; `SliceStack.planes` is sorted by
      anatomic position while `original_indices` maps sorted_pos → dataset index
      (`src/core/slice_geometry.py:174–191`). Using
      `source_stack.planes[source_slice_idx]` directly — as a prior draft of
      this plan suggested — would desync linked panes whenever
      `original_indices` is a non-identity permutation (common once slices are
      spatially sorted). **Collapse** both arms to the shared mapper path:
      ```python
      sorted_pos = self._dataset_idx_to_sorted_pos(
          source_idx, source_slice_idx, source_stack
      )
      if sorted_pos is None:
          return
      source_plane = source_stack.planes[sorted_pos]
      ```
      Add / extend `tests/core/test_slice_sync_coordinator_unit.py` with a
      regression where `original_indices` is a non-identity permutation
      (e.g. `[2, 0, 1]`) and assert both in-range and out-of-range source
      slice indices resolve to the same plane the mapper yields today.
- [x] `src/gui/measurement_coordinator.py:383` — `AngleMeasurementItem`
      branch: the `_updating_handles` if/else bodies are byte-identical (handle
      creation body and "update current p1/p2/p3" body both run regardless of
      the flag). Verify the undo-batch tracking was never intended to differ
      for handle-drag vs. group-drag (per the commit that introduced
      `_updating_handles` on `AngleMeasurementItem`); if not, collapse the
      redundant if/else. Add a regression under `tests/gui/` asserting undo
      captures the right initial/current points for both drag modes.
- [x] `src/gui/measurement_coordinator.py:417` — linear-measurement branch:
      same confirmation-then-collapse as `:383`; history shows the
      handle-drag and group-drag bodies landed identical. Collapse and add the
      parallel linear-measurement regression.

## Phase 3 — Float equality (`python:S1244`): suppress per-site, do not refactor to tolerance

Per-site inspection of every flagged S1244 location shows that the exact
`== 0.0` / `!= 0.0` / `== 1.0` / `!= 1.0` comparisons are **semantically
correct** at each site and that replacing them with `math.isclose(...)` would
either change behavior or mask a real vendor-encoded sentinel. The blanket
"replace with isclose" guidance from the original draft was wrong; this phase
adds **rule-scoped** `# NOSONAR(S1244)` suppression plus a one-line rationale
comment per site. Prefer `# NOSONAR(S1244)` over bare `# NOSONAR` so the
suppression does not silently mask other rules on the same line (e.g. the
`np.isfinite` portion of the `volume_renderer.py:129` compound guard). The
existing bare `# NOSONAR` at `src/core/dicom_window_level.py:229` should be
upgraded to `# NOSONAR(S1244)` for parity.

### Suppression recipe (use exactly this form for auditability)

- Single-line compare: append `  # NOSONAR(S1244): <rationale>` to the line.
- Compound guard on one line (`A or B or slope == 0.0`): split the float-equality
  sub-clause onto its own line, then suppress only that line. *Do not* suppress
  the whole compound expression.
- Generator form (`if all(v == 0.0 for v in bounds):`): append
  `  # NOSONAR(S1244): <rationale>` to the line containing the generator.
- Each rationale comment should be ≤ 80 chars and cite the source of the exact
  value (DS-VR, VTK contract, configuration sentinel, label sentinel).

### Phase 3a — DICOM-stored `RescaleSlope` / `RescaleIntercept` exact-zero guards

`get_rescale_parameters` (`src/core/dicom_rescale.py:54-115`) returns
`float(dataset.RescaleSlope)` / `float(dataset.RescaleIntercept)` directly from
the DICOM DS (Decimal String) VR — no arithmetic, no accumulated drift. A
vendor-stored `0` maps to exact `0.0`; exact equality is the correct test for
"would dividing by this slope raise a ZeroDivisionError". Suppress with
`# NOSONAR(S1244): RescaleSlope is a DICOM DS-VR stored value, exact 0.0 is
well-defined`.

- [x] `src/core/dicom_window_level.py:113` (`if slope == 0.0:` divide guard)
- [x] `src/core/dicom_window_level.py:174` (`rescale_slope != 0.0` rescale-applicability guard)
- [x] `src/core/dicom_window_level.py:381` (same)
- [x] `src/core/dicom_window_level.py:229` — upgrade the existing bare
      `# NOSONAR` to `# NOSONAR(S1244)` plus the rationale comment for parity
      with the siblings (currently bare NOSONAR suppresses *all* rules on that
      line, which is unnecessary breadth).
- [x] `src/core/slice_display_lut.py:36` (same rescale-applicability guard)
- [x] `src/core/window_level_preset_handler.py:42` (same)
- [x] `src/core/wl_preset_catalog.py:148` (same)
- [x] `src/core/volume_renderer.py:129` — `slope` comes from the same
      `get_rescale_parameters(dataset)` call, so the `slope == 0.0` portion of
      the `np.isfinite(...) or slope == 0.0` compound guard is also a
      DICOM-stored-decimal exact-equality test. **Split the compound guard** so
      the `slope == 0.0` check lives on its own line and suppress only that
      line; leave the `not np.isfinite(...)` guard unsuppressed (it is the
      genuinely computed-float check).
- [x] `src/gui/view_state_manager.py:443` — `self.rescale_slope` is populated
      from `get_rescale_parameters`; same DS-VR suppression rationale.
- [x] `src/gui/view_state_manager.py:492` (same)
- [x] `src/gui/view_state_manager.py:693` (same)
- [x] `src/gui/view_state_manager.py:762` (same)

### Phase 3b — VTK empty-scene bounds sentinels

`vtkRenderer.ComputeVisiblePropBounds()` is documented to return an all-zero
6-tuple when the scene is empty. The `all(v == 0.0 for v in bounds)` test is a
contract match against a documented sentinel, not a numeric-drift comparison.
Replacing with `isclose` risks classifying a legitimately small but real volume
as empty and routing the camera through `ResetCamera()`. Suppress with
`# NOSONAR(S1244): VTK ComputeVisiblePropBounds returns all-zero as the empty-scene sentinel`.

- [x] `src/core/volume_renderer.py:1002`
- [x] `src/core/volume_renderer.py:1046`
- [x] `src/gui/volume_viewer_widget.py:1446`

### Phase 3c — Display-label / configuration-sentinel comparisons

The exact value carries the semantic meaning ("native scale", "exactly zero
degrees", "no flip requested", "magnifier identity path skipped"). Tolerance-
based replacement would change user-visible labels or skip an identity fast
path. Suppress with `# NOSONAR(S1244): <exact-value sentinel rationale>`.

- [x] `src/gui/image_viewer_view.py:177` — `sx != 1.0 or sy != 1.0` where
      `sx`/`sy` are `-1.0`/`1.0` selected from `self._flip_h`/`self._flip_v`
      booleans; both comparisons are exact-sentinel. Raises **two** S1244
      findings on one line — a single `# NOSONAR(S1244)` trailing comment
      suppresses both findings on that line.
- [x] `src/gui/image_viewer_view.py:1078` — `if zoom_factor != 1.0:` skips the
      magnifier identity path; `zoom_factor` is caller-supplied configuration
      (`self.zoom_factor = 1.08`) so exact `1.0` is a sentinel, not a computed
      comparison.
- [x] `src/gui/dialogs/export_dialog.py:697` — `if s == 1.0: return "Native"`
      is a label lookup keyed on exact identity scale.
- [x] `src/tools/angle_measurement_items.py:63` — `degrees == 0.0` selects
      the zero-angle label format. `degrees` is a computed value
      (`math.degrees(math.atan2(...))`) that *can* be exact `0.0` for
      collinear points; this is a label-format sentinel, not pixel math —
      tolerance would only change display precision, not correctness.

### Phase 3 — No `math.isclose` refactors remain

After per-site review, no S1244 site in this checkout is a legitimate
tolerance-replacement candidate. The Phase 3 work is therefore: add
`# NOSONAR(S1244)` + a one-line rationale comment at each of the sites above
(splitting compound guards first where needed), and confirm the scanner no
longer reports S1244 for those paths. **No `math.isclose` import is added
anywhere.**

### Resolves `dicom_window_level.py:229` inconsistency

The original `:229` bare `# NOSONAR` suppression was inconsistent with the
unsuppressed siblings at `:113`, `:174`, `:381`, `slice_display_lut.py:36`,
`wl_preset_catalog.py:148`, `window_level_preset_handler.py:42`. Phase 3a makes
the disposition uniform: all of them suppressed with the same DS-VR rationale
comment via rule-scoped `# NOSONAR(S1244)`.

## Explicitly out of scope

- The 114 MAJOR CODE_SMELL findings (e.g. `python:S107`, `python:S1854`,
  `python:S3358`). Track separately; do not mix into this fix branch. **Add a
  follow-up backlog entry to `dev-docs/TO_DO.md`** so the deferral is tracked
  rather than forgotten.
- Re-running the scanner with `--with-coverage` is a verification step, not a
  code change.

## Verification (after each phase)

> **Verification note (2026-07-18):** Code remediation is complete in the working
> tree and focused tests pass. A fresh `run_local_sonarqube.py` submission at
> 19:02 UTC still analyzed SCM revision `0dc60b5` (pre-remediation tip) because
> the fixes were not yet committed — Sonar reported missing blame for dirty
> files. Re-run analysis **after commit** to confirm S2245/S3923/S1244 clearance.


- [ ] `python -m pytest tests/ -q` green (focus: anonymizer, slice sync,
      window/level, volume).
- [ ] `ruff` and `basedpyright` clean for touched modules.
- [ ] `python scripts/git_hook_privacy_checks.py --staged` passes (privacy-
      relevant: Phase 1 touches de-identification).
- [ ] **Fresh local Sonar analysis required first:** submit/process a new
      analysis of the branch tip through `python scripts/run_local_sonarqube.py`
      (or the project's standard local analysis entrypoint) so the scanner has
      seen the `# NOSONAR(S1244)` comments and the S3923 collapses, *then*
      re-run `python scripts/report_local_sonarqube_issues.py --output
      tmp/sonar-current-findings.md` and confirm S2245, S3923, and S1244 no
      longer appear for the fixed paths. Without a fresh analysis the reporter
      will re-serve the stale revision's findings.
- [ ] `python scripts/agent_smoke_harness.py` — **N/A only if Phases 2 and 3
      stay behavior-preserving collapses / suppression-only edits.** Mandatory
      if anyone implements a non-collapse alternative for
      `slice_sync_coordinator.py:195` or `measurement_coordinator.py:383/417`
      that changes slice-sync or measurement-undo semantics. Tie the N/A decision
      to the actual fix chosen at each 2b site and state it in the PR description.
- [ ] `python scripts/check_repo_harness.py` — run before merge.
- [ ] `python scripts/check_architecture_boundaries.py` — marked **N/A** for
      this branch (no cross-domain imports introduced or removed); document the
      N/A decision in the PR description.
- [ ] `python scripts/check_user_docs_links.py` — run only if user-docs are
      edited; N/A for this branch otherwise.

## Release tracking / SemVer / CHANGELOG

- [x] **SemVer impact:** patch-class (security hardening + bug-code collapses +
      static analysis suppression; no public API change and no deliberate
      behavior change). Escalate to minor if any Phase 2b site ends up changing
      slice-sync or measurement-undo semantics.
- [x] **`CHANGELOG.md`:** add an **[Unreleased]** entry for Phase 1 (anonymizer
      now uses `secrets`-based jitter — relevant to anyone inspecting the export
      pipeline) and for Phase 2 if any user-visible measurement/annotation
      behavior actually changes. Phase 3 NOSONAR edits do not need a CHANGELOG
      line (no behavior change) but should be captured in `MAINTENANCE_LOG.md`.
- [x] **`dev-docs/MAINTENANCE_LOG.md`:** record the Sonar MAJOR remediation pass
      (rules addressed: S2245, S3923, S1244; the blanket-suppression rationale;
      the `:229` parity fix; the deferred 114 CODE_SMELL follow-up pointer).
- [x] **`dev-docs/TO_DO.md`:** add a follow-up backlog item for the 114 deferred
      MAJOR CODE_SMELL findings so they are not lost.
- [ ] **Version bump:** optional for this pass. (deferred — staying on 0.4.0 / Unreleased) Keep work under **[Unreleased]**
      without bumping `src/version.py` / CHANGELOG **Current version** unless
      cutting a release or intentionally advancing the project version. If
      bumping, keep both in sync per
      `dev-docs/info/SEMANTIC_VERSIONING_GUIDE.md`.

## Files changed on this branch

### Already landed (pre-remediation, on `fix/sonarqube-major-findings-20260718` tip today)

- `scripts/report_local_sonarqube_issues.py` — reporter now also fetches MAJOR findings.
- `tests/test_report_local_sonarqube_issues.py` — updated policy-class assertion.
- `dev-docs/plans/SONARQUBE_MAJOR_FINDINGS_REMEDIATION_PLAN_20260718.md` — this plan.

### Expected remediation touch list (per phase)

- **Phase 1:** `src/utils/deep_anonymizer.py` (call site + import swap + comment
  hygiene).
- **Phase 2a:** `src/gui/dialogs/annotation_options_dialog.py`,
  `src/gui/image_viewer_view.py`; new/extended tests under `tests/gui/`.
- **Phase 2b:** `src/core/slice_sync_coordinator.py`,
  `src/gui/measurement_coordinator.py`; extend
  `tests/core/test_slice_sync_coordinator_unit.py` and add a `tests/gui/`
  measurement regression.
- **Phase 3:** `src/core/dicom_window_level.py`, `src/core/slice_display_lut.py`,
  `src/core/volume_renderer.py`, `src/core/window_level_preset_handler.py`,
  `src/core/wl_preset_catalog.py`, `src/gui/view_state_manager.py`,
  `src/gui/volume_viewer_widget.py`, `src/gui/image_viewer_view.py`,
  `src/gui/dialogs/export_dialog.py`, `src/tools/angle_measurement_items.py`
  (suppression + rationale-comment only; compound-guard split at
  `volume_renderer.py:129`).
- Release: `CHANGELOG.md`, `dev-docs/MAINTENANCE_LOG.md`,
  `dev-docs/TO_DO.md`; bump `src/version.py` only if intentionally advancing
  the project version / cutting a release.
