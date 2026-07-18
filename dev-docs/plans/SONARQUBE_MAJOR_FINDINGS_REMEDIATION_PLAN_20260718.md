# Plan: Remediate Important Local SonarQube Major Findings

**Last updated:** 2026-07-18 (revised after assessment review)
**Status:** Active (staged on `fix/sonarqube-major-findings-20260718`)
**Source analysis:** `2026-07-18T17:12:01+0000`, revision `9484958196fcd183a88407f5f312d77bb521f8df`
**Revision notes:** Phase 2 partitioned per-site (safe-collapse vs needs-review);
Phase 3 reframed from "tolerance refactor" to "per-site NOSONAR suppression with
rationale" after inspection showed every flagged site uses exact equality
against a DICOM-stored decimal, a documented VTK sentinel, or a configuration /
label sentinel. See `tmp/sonarqube_remediation_plan_assessment_20260718_140945.md`.

## Goal and scope

The local reporter (`scripts/report_local_sonarqube_issues.py`) was extended to
surface MAJOR findings (all types), not only BLOCKER and CRITICAL
BUG/VULNERABILITY. The refreshed scan returned **140** DICOM-Viewer-scoped
findings: 0 BLOCKER, 0 CRITICAL, 25 MAJOR BUG, 1 MAJOR VULNERABILITY, and 114
MAJOR CODE_SMELL.

This plan fixes only the **substantive** findings — the vulnerability and the
genuine logic bugs — in a staged, low-risk way. The 114 CODE_SMELL items and the
lower-risk float-equality duplicates are explicitly out of scope for this pass to
keep the change reviewable and the behavior stable.

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

- [ ] `src/utils/deep_anonymizer.py:281` (`python:S2245`): date-shift jitter is
      drawn from the non-cryptographic `random.randint`. Replace with
      `secrets.randbelow(DATE_JITTER_MAX_DAYS + 1)` (or `os.urandom`-based) so the
      batch-wide jitter that hides the real date baseline is not predictable.
- [ ] Add `import secrets` and **remove the now-dead `import random`** at
      `src/utils/deep_anonymizer.py:20`. Verified: `random` has exactly one call
      site in the file (line 281); all other `random` references at lines 52 and
      277 are comments. Removing the import prevents a future contributor from
      re-introducing `random` into the de-identification path.
- [ ] Keep `random` out of any de-identification path; confirm the module still
      imports and the date-offset unit tests pass.

## Phase 2 — Logic bugs: identical if/else branches (`python:S3923`)

Six sites where both branches of a conditional do the same work, indicating a
copy/paste leftover that drops the intended alternate behavior. They are
partitioned by risk:

### Phase 2a — Safe collapse (behavior-preserving)

The redundant branch is provably unreachable or the if/else dispatches on a
semantic flag whose both arms intentionally do the same work; collapse to a
single path, no behavior change.

- [ ] `src/gui/dialogs/annotation_options_dialog.py:455` — both arms assign
      `roi_color = roi_line_color`; collapse and add a `tests/gui/` assertion that
      the displayed ROI color equals the configured line color regardless of
      whether font color matches.
- [ ] `src/gui/dialogs/annotation_options_dialog.py:483` — same pattern for
      `measurement_color`; mirror the ROI test.
- [ ] `src/gui/image_viewer_view.py:1295` — both arms assign
      `frame_array = pixel_array`; the in-source comment ("Likely single-frame
      color" vs "Single-frame grayscale (shouldn't happen with 3D, but handle
      it") suggests the intended grayscale branch should slice or dispatch
      differently. **Verify intent first;** if the slice was genuinely redundant,
      collapse and add a pixel-array shape regression test under
      `tests/gui/image_viewer_view_test.py`.

### Phase 2b — Needs reviewer-confirmed intent (design decision per site)

Collapsing could change runtime behavior. Do not edit until an reviewer has
documented the original intent (preferably from git history of when the
`_updating_handles` / sorted-pos dispatch was introduced).

- [ ] `src/core/slice_sync_coordinator.py:195` — both arms call
      `_dataset_idx_to_sorted_pos(...)` then index `source_stack.planes[...]`.
      The guard tests `source_slice_idx < 0 or >= len(planes)`, suggesting the
      in-range arm should use `source_stack.planes[source_slice_idx]` directly.
      Confirm against `core/slice_geometry.SliceStack` semantics and the original
      slice-sync commit before restoring.
- [ ] `src/gui/measurement_coordinator.py:383` — `AngleMeasurementItem` branch:
      the `_updating_handles` if/else bodies are byte-identical. Intent was to
      differentiate handle-drag tracking from group-drag tracking. Recover from
      the commit that introduced `_updating_handles` on `AngleMeasurementItem`.
- [ ] `src/gui/measurement_coordinator.py:417` — linear-measurement branch:
      same pattern as `:383`; the `else` group-drag body collapsed onto the
      handle-drag body. Recover intent from the same history.

## Phase 3 — Float equality (`python:S1244`): suppress per-site, do not refactor to tolerance

Per-site inspection of every flagged S1244 location shows that the exact
`== 0.0` / `!= 0.0` / `== 1.0` / `!= 1.0` comparisons are **semantically
correct** at each site and that replacing them with `math.isclose(...)` would
either change behavior or mask a real vendor-encoded sentinel. The blanket
"replace with isclose" guidance from the original draft was wrong; this phase
adds `# NOSONAR` suppression plus a one-line rationale comment per site,
matching the existing `src/core/dicom_window_level.py:229` precedent.

### Phase 3a — DICOM-stored `RescaleSlope` / `RescaleIntercept` exact-zero guards

`get_rescale_parameters` (`src/core/dicom_rescale.py:54-115`) returns
`float(dataset.RescaleSlope)` / `float(dataset.RescaleIntercept)` directly from
the DICOM DS (Decimal String) VR — no arithmetic, no accumulated drift. A
vendor-stored `0` maps to exact `0.0`; exact equality is the correct test for
"would dividing by this slope raise a ZeroDivisionError". Suppress with
`# NOSONAR` and a comment citing the DS-VR origin.

- [ ] `src/core/dicom_window_level.py:113` (`if slope == 0.0:` divide guard)
- [ ] `src/core/dicom_window_level.py:174, 381` (`rescale_slope != 0.0` rescale-applicability guard)
- [ ] `src/core/slice_display_lut.py:36` (same rescale-applicability guard)
- [ ] `src/core/window_level_preset_handler.py:42` (same)
- [ ] `src/core/wl_preset_catalog.py:148` (same)
- [ ] `src/core/volume_renderer.py:129` — `slope` comes from the same
      `get_rescale_parameters(dataset)` call, so the `slope == 0.0` portion of
      the `np.isfinite(...) or slope == 0.0` guard is also a DICOM-stored-decimal
      exact-equality test. Suppress the S1244 portion only; keep the
      `not np.isfinite(...)` guard unsuppressed.
- [ ] `src/gui/view_state_manager.py:443, 492, 693, 762` — `self.rescale_slope`
      is populated from `get_rescale_parameters`; same suppression rationale.

### Phase 3b — VTK empty-scene bounds sentinels

`vtkRenderer.ComputeVisiblePropBounds()` is documented to return an all-zero
6-tuple when the scene is empty. The `all(v == 0.0 for v in bounds)` test is a
contract match against a documented sentinel, not a numeric-drift comparison.
Replacing with `isclose` risks classifying a legitimately small but real volume
as empty and routing the camera through `ResetCamera()`. Suppress with
`# NOSONAR` plus a comment citing the VTK contract.

- [ ] `src/core/volume_renderer.py:1002`
- [ ] `src/core/volume_renderer.py:1046`
- [ ] `src/gui/volume_viewer_widget.py:1446`

### Phase 3c — Display-label / configuration-sentinel comparisons

The exact value carries the semantic meaning ("native scale", "exactly zero
degrees", "no flip requested"). Tolerance-based replacement would change
user-visible labels or skip the identity-transform fast path. Suppress with
`# NOSONAR` and a one-line rationale.

- [ ] `src/gui/image_viewer_view.py:177` — `sx != 1.0 or sy != 1.0` where
      `sx`/`sy` are `-1.0`/`1.0` selected from `self._flip_h`/`self._flip_v`
      booleans; both comparisons are exact-sentinel. Raises **two** S1244
      findings on one line — suppress once covers both.
- [ ] `src/gui/image_viewer_view.py:1078` — `if zoom_factor != 1.0:` skips the
      magnifier identity path; `zoom_factor` is caller-supplied configuration
      (`self.zoom_factor = 1.08`) so exact `1.0` is a sentinel, not a computed
      comparison.
- [ ] `src/gui/dialogs/export_dialog.py:697` — `if s == 1.0: return "Native"`
      is a label lookup keyed on exact identity scale.
- [ ] `src/tools/angle_measurement_items.py:63` — `degrees == 0.0` selects the
      zero-angle label format; the angle is a computed display value but the
      zero label is semantically exact.

### Phase 3 — No `math.isclose` refactors remain

After per-site review, no S1244 site in this checkout is a legitimate
tolerance-replacement candidate. The Phase 3 work is therefore: add `# NOSONAR`
+ a one-line rationale comment at each of the sites above, and confirm the
scanner no longer reports S1244 for those paths. **No `math.isclose` import is
added anywhere.**

### Resolves `dicom_window_level.py:229` inconsistency

The original `:229` `# NOSONAR` suppression was inconsistent with the unsuppressed
siblings at `:113`, `:174`, `:381`, `slice_display_lut.py:36`, `wl_preset_catalog.py:148`,
`window_level_preset_handler.py:42`. Phase 3a makes the disposition uniform:
all of them suppressed with the same DS-VR rationale comment.

## Explicitly out of scope

- The 114 MAJOR CODE_SMELL findings (e.g. `python:S107`, `python:S1854`,
  `python:S3358`). Track separately; do not mix into this fix branch.
- Re-running the scanner with `--with-coverage` is a verification step, not a
  code change.

## Verification (after each phase)

- [ ] `python -m pytest tests/ -q` green (focus: anonymizer, slice sync, window/level, volume).
- [ ] `ruff` and `basedpyright` clean for touched modules.
- [ ] `python scripts/git_hook_privacy_checks.py --staged` passes (privacy-relevant: Phase 1 touches de-identification).
- [ ] Re-run `python scripts/report_local_sonarqube_issues.py --output tmp/sonar-current-findings.md`
      and confirm the addressed rules no longer appear for the fixed paths.
- [ ] `python scripts/agent_smoke_harness.py` — marked **N/A** for this branch
      (no UX/loading/navigation/MPR/overlay/SR surfaces touched); include only if
      Phase 2b slice-sync or measurement-coordinator changes alter runtime
      behavior. Document the N/A decision in the PR description.
- [ ] `python scripts/check_repo_harness.py` — run before merge.
- [ ] `python scripts/check_architecture_boundaries.py` — marked **N/A** for this
      branch (no cross-domain imports introduced or removed); document the N/A
      decision in the PR description.

## Files changed on this branch

- `scripts/report_local_sonarqube_issues.py` — reporter now also fetches MAJOR findings.
- `tests/test_report_local_sonarqube_issues.py` — updated policy-class assertion.
- `dev-docs/plans/SONARQUBE_MAJOR_FINDINGS_REMEDIATION_PLAN_20260718.md` — this plan.
