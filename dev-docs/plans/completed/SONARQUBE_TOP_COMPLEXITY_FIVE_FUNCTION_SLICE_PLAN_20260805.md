# Plan: Local SonarQube Top-Complexity Five-Function Slice

**Last updated:** 2026-08-05
**Status:** Implemented
**Branch:** `refactor/sonar-top-complexity-rendering-export`
**Scope:** One behavior-preserving PR; five `python:S3776` findings in four
production files.

## Goal

Close the five selected, highest-ranked local SonarQube cognitive-complexity
findings through small private-helper extractions. Preserve existing tag
export, presentation-state annotation, graphics-overlay, and DICOM tag-edit
behavior exactly; do not add features, change UI copy, or change public APIs.

## Outcome

Implemented as one behavior-preserving branch with characterization and
refactor commits kept separate. The final local analysis at source revision
`9a08fcd4b6930343a771fce5c6c63429c254e08d` reported **238** active
BLOCKER/CRITICAL/MAJOR findings, down from 243. All five selected
`python:S3776` findings are absent: both tag-export methods,
`create_presentation_state_items`, `create_overlay_items`, and `_create_ui`.

The report retains seven pre-existing `S3776` findings in the four touched
files; those methods were explicitly out of scope. A first final scan exposed
an `S107` parameter-count warning in a newly extracted graphics helper. The
helper now accepts a private `OverlayTextContext`, and the final report has no
new `S107` finding.

## Baseline and selection

The latest local SonarQube analysis was submitted 2026-08-05 at revision
`6cc6888366b47d513905cc8ad053a4215c72d88f`, with coverage. The scoped local
report returned 243 active BLOCKER/CRITICAL/MAJOR findings. `main` is one
commit later (`4e7f694`), but none of the selected production files changed
between the scan revision and the branch point.

Each selected finding is `python:S3776`, which asks for a cognitive complexity
of 15 or less. Their pre-refactor scores total 364:

| File | Method | Sonar complexity | Why selected |
|---|---|---:|---|
| `src/core/tag_export_writer.py` | `write_excel_file` | 78 | Highest individual open finding. |
| `src/tools/annotation_manager.py` | `create_presentation_state_items` | 77 | Tied second-highest finding; the annotation file has the highest aggregate remaining complexity (231). |
| `src/gui/overlay_manager.py` | `create_overlay_items` | 77 | The other tied second-highest finding; explicitly included after scope expansion. |
| `src/gui/dialogs/tag_edit_dialog.py` | `_create_ui` | 74 | Next-highest open finding. |
| `src/core/tag_export_writer.py` | `_write_tag_export_sheet_rows` | 58 | The second high-complexity function in the highest-ranked export module; clearing both makes its file-level row pipeline coherent. |

The initial two-file / three-function request could not include both tied
77-point methods: they are in different files. This expanded, single-PR scope
therefore contains four files and five functions rather than silently dropping
one of the tied findings.

## Guardrails

- Keep public callable names, signatures, return values, widget behavior, and
  existing error handling unchanged.
- Keep helpers private and in their existing modules. Do not introduce a new
  cross-domain module or any new dependency edge.
- Do not alter DICOM tag values, privacy rules, persistence, or formula
  neutralization behavior as part of a complexity refactor.
- Use only synthetic values in tests and reports. Do not add DICOM files,
  screenshots, spreadsheets, archives, or other binary assets.
- Do not opportunistically repair unrelated findings, including the remaining
  `annotation_manager`, `overlay_manager`, and `tag_edit_dialog` S3776 issues.
- Keep logging semantics intact; do not add ungated debug prints.

## Stream A — tag-export row pipeline

### Target methods

- `write_excel_file()` — 78
- `_write_tag_export_sheet_rows()` — 58

### Refactor shape

Extract format-neutral, private helpers inside `tag_export_writer.py` for:

1. resolving a selected series' constant/varying tag partitions;
2. formatting a parsed tag into its canonical tag-number, name, and display
   value cells;
3. producing constant-tag rows, including the optional missing-selected-tag
   row;
4. producing per-instance varying-tag rows, including bounds checks and the
   optional missing-selected-tag row;
5. rendering those rows to the XLSX worksheet versus a `SafeCsvWriter`; and
6. XLSX header/style, per-series heading, column widths, and workbook save.

The two target methods must become thin orchestration/rendering entry points.
Do not create a single replacement helper that retains the same nested
branching; split it until each new helper is independently understandable and
below the Sonar threshold.

### Contracts to preserve

- One worksheet per selected study, with the existing sanitized title and
  column widths; CSV/TXT remain one file per study with existing filenames.
- Constant tags are emitted once as `All`; varying tags are emitted once per
  selected instance; out-of-range instance indexes are skipped.
- Values that are lists retain their comma-joined display representation;
  nested selected tags retain their canonical tag number.
- `include_private`, `include_sequences`, and
  `include_missing_selected_tags` retain their current behavior for every
  output format.
- XLSX uses `neutralize_spreadsheet_value`; CSV/TXT keep using `SafeCsvWriter`
  so formula-like cells remain inert.
- Existing header text, blank rows, series headers, font styling, and writer
  ordering remain unchanged.

### Tests

Extend `tests/test_tag_export_writer.py` with table-driven inputs covering
constant, varying, missing, list-valued, nested, and out-of-range rows across
XLSX/CSV/TXT. Keep the existing formula-neutralization tests and add only
synthetic values. Keep `tests/test_tag_export_controller.py` and
`tests/smoke/test_export_smoke.py` green.

## Stream B — presentation-state graphics items

### Target method

- `AnnotationManager.create_presentation_state_items()` — 77

### Refactor shape

Keep the public method as the one place that owns the outer try/except,
coordinate transformation, and returned-item collection. Extract private
helpers for rendering individual TEXT, POLYLINE, CIRCLE, ELLIPSE, POINT, and
OVERLAY annotations, plus a shared private registration helper that appends a
successfully added item to both the scene tracking and the returned list.

The overlay helper may return more than one item so bitmap-first rendering and
the existing path fallback remain expressible without a hidden control-flow
change. Do not move the broad exception boundary inside the per-annotation
loop: today a malformed annotation stops further rendering and returns any
previously created items, and that behavior is part of this no-change slice.

### Contracts to preserve

- Coordinate transformation happens before type-specific rendering; an
  `OVERLAY` with empty coordinates remains eligible for bitmap/path rendering.
- Invalid colors still fall back to yellow; all added items retain current pen,
  brush, z-value (200), and visibility settings.
- Existing bounds rules are exact, including circle-radius and ellipse margins.
- TEXT/POLYLINE/CIRCLE/ELLIPSE/POINT minimum-coordinate requirements remain
  unchanged.
- OVERLAY keeps bitmap-first rendering, only falls back to paths when bitmap
  creation fails, and retains the existing path arguments and scene tracking.

### Tests

Extend `tests/test_annotation_manager.py` to independently assert item type,
scene membership, and manager membership for each rendering branch, invalid or
out-of-bounds input, overlay with no coordinates, bitmap success, and bitmap
fallback. Keep `tests/tools/test_annotation_overlay_bitmap_sonar_slice.py`
and `tests/gui/test_slice_display_manager_sonar_slice.py` green.

## Stream C — graphics-scene metadata overlays

### Target method

- `OverlayManager.create_overlay_items()` — 77

### Refactor shape

Extract private helpers for recording the current overlay context, resolving a
view and graphics-scene dimensions, calculating four corner anchors, rendering
right-aligned lines, and rendering each left-aligned multiline item. The public
method remains responsible for choosing widget versus graphics-item overlays,
clearing prior graphics items, visibility gating, and returning
`self.overlay_items`.

### Contracts to preserve

- Store the parser, scene, slice/stack, projection, and multiframe context
  before selecting either rendering path.
- The widget-overlay branch delegates with exactly the existing argument set
  and returns before graphics-item cleanup.
- The graphics path clears existing items and corner mappings before honoring
  hidden-state early return.
- Retain scene-rect, largest-item, and `800 × 600` dimension fallbacks.
- Retain existing viewport-to-scene coordinate mapping, uniform zoom handling,
  margins, four-corner ordering, and the current lower-right anchor calculation
  verbatim.
- Retain right-aligned line filtering/order, temporary width measurement,
  `corner_max_width_map` updates, per-line bottom stacking, and left-aligned
  multiline bottom adjustment.
- Forward privacy, projection, multiframe, and stack-position inputs to
  `get_corner_text()` unchanged.

### Tests

Add focused graphics-path cases under `tests/gui/test_overlay_manager_slice.py`
for widget delegation, hidden cleanup, scene/no-view fallback, view-mapped
corners, right-aligned line order and cached width, left-aligned bottom
anchoring, and context forwarding. Keep
`tests/gui/test_overlay_position_updater_sonar_slice.py`,
`tests/test_keyboard_overlay_shortcuts.py`, and
`tests/test_export_rendering_overlays.py` green.

## Stream D — tag-edit dialog construction

### Target method

- `TagEditDialog._create_ui()` — 74

### Refactor shape

Extract private builders for the tag-information section, input-widget
selection, numeric input configuration/current-value initialization, and
button-box construction/wiring. `_create_ui()` remains the ordered layout
orchestrator and continues setting `self.value_input` before validation setup.

### Contracts to preserve

- Read-only VRs show the existing readonly `QLineEdit`, message, style, and
  disabled OK button.
- Float VRs use a six-decimal `QDoubleSpinBox` with the same bounds.
- Signed integer VRs retain their `QSpinBox` bounds and current-value fallback.
- `UL` keeps the `QLineEdit` path needed for values beyond Qt's signed 32-bit
  spinbox maximum, including its zero fallback.
- List values retain first-value numeric initialization and comma-joined string
  display; scalar and empty values retain their current conversions/fallbacks.
- The existing dialog order, labels, modal result, and OK/Cancel signal wiring
  remain unchanged.

### Tests

Extend `tests/gui/test_tag_edit_dialog.py` for read-only, float, bounded
integer, large `UL`, list-valued numeric/string, and malformed current-value
branches. Keep `tests/test_tag_viewer_dialog.py`, `tests/test_metadata_panel.py`,
and `tests/test_nested_tag_roundtrip.py` green so nested edits remain path
addressed and privacy safeguards remain intact.

## Commit and PR plan

Keep the branch as one focused PR with small, reviewable, independently green
commits:

1. `docs: add Sonar top-complexity remediation plan`
2. `test: characterize tag export writer contracts`
3. `refactor: share tag export row generation`
4. `test: characterize presentation-state item rendering`
5. `refactor: simplify presentation-state item rendering`
6. `test: characterize graphics overlay rendering`
7. `refactor: simplify graphics overlay rendering`
8. `test: characterize tag edit dialog UI variants`
9. `refactor: simplify tag edit dialog UI construction`
10. `docs: record Sonar complexity remediation`

Do not combine characterization and refactor commits. Each refactor commit
must pass the tests introduced immediately before it. The final documentation
commit updates this plan to **Implemented**, records the final scan revision
and result in `dev-docs/MAINTENANCE_LOG.md`, and adds this plan to the static
analysis references in `dev-docs/TO_DO.md`. Do not update `CHANGELOG.md`: this
is an internal behavior-preserving refactor.

## Verification and acceptance criteria

Run the relevant focused suites after each stream, then run the complete final
gate with the project virtual environment active:

1. `python -m pytest tests/test_tag_export_writer.py tests/test_tag_export_controller.py tests/smoke/test_export_smoke.py -v`
2. `python -m pytest tests/test_annotation_manager.py tests/tools/test_annotation_overlay_bitmap_sonar_slice.py tests/gui/test_slice_display_manager_sonar_slice.py -v`
3. `python -m pytest tests/gui/test_overlay_manager_slice.py tests/gui/test_overlay_position_updater_sonar_slice.py tests/test_keyboard_overlay_shortcuts.py tests/test_export_rendering_overlays.py -v`
4. `python -m pytest tests/gui/test_tag_edit_dialog.py tests/test_tag_viewer_dialog.py tests/test_metadata_panel.py tests/test_nested_tag_roundtrip.py -v`
5. `python -m pytest tests/ -v`
6. `python scripts/check_architecture_boundaries.py`
7. `python scripts/check_repo_harness.py`
8. `python scripts/agent_smoke_harness.py`
9. `python scripts/git_hook_privacy_checks.py --staged`

Before the final Sonar analysis, manually smoke the changed UI paths using
synthetic or already-approved non-PHI data only: tag export to CSV/TXT/XLSX,
presentation-state/overlay display while zooming and panning, and string/
numeric tag-edit dialogs. Do not paste displayed tag values into the PR or
reports.

Finally, run a fresh local analysis with coverage and report the result against
the checked-out revision:

```sh
python scripts/run_local_sonarqube.py --with-coverage
python scripts/report_local_sonarqube_issues.py \
  --expected-revision "$(git rev-parse HEAD)"
```

The PR is complete only when all five selected S3776 findings are absent from
the scoped report, all verification gates pass, and the final documentation
records the actual remaining finding total without treating unrelated backlog
as a failure of this scoped pass.

## Verification outcome

- The combined affected test suite passed: **175 tests plus 3 subtests**.
- The full `tests/` suite completed successfully (3,633 collected tests).
- `check_architecture_boundaries.py`, `check_repo_harness.py`,
  `agent_smoke_harness.py --write-report`, the harness smoke-test suite, and
  the staged privacy check passed. Each local commit's repository hooks also
  passed.
- `python src/main.py` launched without a traceback. The required interactive
  manual smoke could not be completed because the PySide application window
  was not exposed to the available Computer Use environment; that visual check
  remains for a local desktop session with approved non-PHI data.
- A final local SonarQube report was obtained against
  `9a08fcd4b6930343a771fce5c6c63429c254e08d`; it contains 238 priority
  findings and no selected target location.

## Explicitly out of scope

- All non-selected S3776 findings, including `dicom_organizer`,
  `subwindow_lifecycle_controller`, `roi_manager`, `image_viewer_input`, and
  the remaining methods in the four selected files.
- MAJOR rules, duplicate strings, formatting-only cleanup, dependency changes,
  Sonar quality-profile changes, and a new complexity CI gate.
- Functional changes to tag export formats, presentation-state/overlay
  rendering, tag editing, DICOM persistence, privacy policy, or UI design.
