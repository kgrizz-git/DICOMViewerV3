# Maintenance Log

**Last updated:** 2026-08-02

This file records development and repository-maintenance history that is useful to contributors and agents but is not necessarily user-facing release history.

Use this log for CI, static analysis, harness changes, dependency-verification passes, repo hygiene, doc-garden cleanup, and other maintainer workflow notes. Use [`../CHANGELOG.md`](../CHANGELOG.md) for user-visible product/release changes. Use [`TO_DO.md`](TO_DO.md) only for active backlog items and near-term follow-ups.

## 2026-08-02

- **Engineering documentation sync:** aligned top-level developer docs with the GDCM decoder productionization and launcher incomplete-venv fix. Updated `README.md` technology stack, `ARCHITECTURE.md` decoder domain, `SOURCE_LAYOUT.md` decoder modules, `DEVELOPER_SETUP.md` troubleshooting (venv + compressed DICOM), `HARNESS.md` decoder fixture smoke command, `BUILDING_EXECUTABLES.md` frozen-build decoder validation, and `CODE_DOCUMENTATION.md` / `dev-docs/README.md` index entries.

## 2026-07-30

- **Unused-symbol / correctness cleanup** on `chore/dead-branch-and-unused-cleanup`:
  basedpyright `reportUnusedImport` + `reportUnusedVariable` +
  `reportUnusedParameter` on `src/` went from **93 → 0** (dead imports/locals
  removed or `_`-prefixed; intentional re-exports and keyword-stable params
  kept with safe markers). Also removed the zoom-release dead pan branch,
  bypassed the OVERLAY empty-coordinates gate, clamped palette LUTs per
  channel, and zeroed flat `normalize_to_uint8` arrays. Overlay LSB no-NumPy
  bit-order was already fixed earlier (`annotation_overlay_bitmap.py`); closed
  the stale TO_DO item. See CHANGELOG `[Unreleased]` Fixed/Changed.

## 2026-07-28

- Landed three pylinac ACR CT features on `feature/pylinac-ct-cnr-batch-xlsx`
  (commits 39dcd7a, 20c8f82, 5a5d3ed), plus the `run.py` `sys.path` launcher
  fix folded into the same branch/PR/CI run. Plan:
  `dev-docs/plans/completed/PYLINAC_CT_CNR_BATCH_XLSX_PLAN.md`.
  - **F1 — CNR intermediates:** `_extract_low_contrast_cnr_details` in
    `src/qa/pylinac_acr_ct.py` harvests object ROI mean, background mean/σ, and
    module CNR from the live `low_contrast_module` (dict-valued `rois` /
    `background_rois`; `cnr()` is a method) into `metrics.low_contrast_cnr`.
    `results_data(as_dict=True)` now feeds a structured `raw_pylinac`, and
    `_jsonable` was hardened for non-`float64` numpy scalars.
  - **F3 — XLSX export:** `src/qa/qa_xlsx_export.build_qa_workbook`
    (Summary/Detail/Images, Qt-free, reuses `qa_export._flatten`); transient
    `QARequest.analyzed_image_out_path` / `QAResult.analyzed_image_path` drive
    `analyzer.save_analyzed_image()` inside the runner with facade-owned
    `TemporaryDirectory` lifecycle. Single-run `schema_version` bumped 1.1 → 1.3.
  - **F2 — batch CT:** `QACTBatchWorker` (serial, per-series error isolation,
    cooperative cancel, worker-owned image temp dir), `CTBatchResult`, selection
    and summary dialogs, and the `acr_ct_batch_requested` signal wiring.
  - F1 built with Opus; F3 and F2 implemented by Sonnet subagents in isolated
    worktrees (F3 first for the shared `build_qa_workbook` dependency, then F2),
    reviewed and re-linted before merge. Pre-merge live-phantom numeric value
    check for F1 (against a real CatPhan dataset) is still open.

## 2026-07-26

- Addressed verified CodeRabbit findings on the S3776 PR (RLE UID, cancel
  animation stop, FrameDatasetWrapper local overrides, first-slice guards,
  overlay recreate context, overlay bitmap LSB/pad, export docstring/sanitize,
  MPR assign disconnect). Skipped speculative nitpick refactors.
- Cleared basedpyright push-gate errors introduced by recent S3776 helper
  extractions: typed bare generics, overlay parser null guard, measurement
  `QPointF` casts, and `importlib` loaders for load-pipeline / ROI-export
  modules so import-cycle errors no longer block pre-push.
- Completed a Sonar `python:S3776` slice on overlay bitmap conversion: moved byte
  extraction, LSB-first unpack, coordinate mapping, OpenCV/scipy path extraction,
  and no-NumPy fallback into `src/tools/annotation_overlay_bitmap.py`;
  `AnnotationManager._convert_overlay_bitmap_to_graphics` now delegates to that
  module. Added `tests/tools/test_annotation_overlay_bitmap_sonar_slice.py`.
  Target finding was cognitive complexity ~85 (radon CCN 34 on the method before
  refactor).
- Completed a Sonar `python:S3776` slice on ROI TXT/CSV export: moved TXT
  area-line formatting, slice/series blocks, and CSV row builders / finalize
  logic into `roi_export_txt` and `roi_export_csv`; `write_txt` and `write_csv`
  in `roi_export_service` are thin wrappers. Added
  `tests/core/test_roi_export_txt_csv_sonar_slice.py`. Target findings were
  cognitive complexity 83 / 81 (radon CCN 26 / 31 on `write_txt` / `write_csv`
  before refactor).
- Completed a Sonar `python:S3776` slice on histogram series-frequency
  computation: moved dataset resolution, rescale parsing, and histogram
  accumulation helpers into `src/gui/dialogs/histogram_frequency.py`;
  `HistogramDialog._compute_series_global_frequency_max` now orchestrates only.
  Added `tests/gui/test_histogram_frequency_sonar_slice.py`. Target finding was
  cognitive complexity ~85 (radon CCN 39 on `_compute_series_global_frequency_max`).
- Completed a Sonar `python:S3776` slice on single-file DICOM loading: moved
  compression-label lookup, defer/multiframe messages, memory-estimate pre-load,
  slow-file timing assembly, and exception message builders into
  `dicom_loader_file`; `DICOMLoader.load_file` now orchestrates module-level
  read/annotate/multiframe helpers. Added
  `tests/core/test_dicom_loader_load_file_sonar_slice.py`. Target finding was
  cognitive complexity 88 (radon CCN 39 on `load_file`).
- Completed a Sonar `python:S3776` slice on first-slice (full replace) load:
  moved pre-reset, stale subwindow cleanup, PS/KO load, subwindow-0 display,
  navigator reveal/fit, and deferred paint side effects into
  `src/gui/file_series_first_slice_load.py`;
  `FileSeriesLoadingCoordinator.handle_load_first_slice` now orchestrates only.
  Added `tests/gui/test_file_series_first_slice_load_sonar_slice.py`. Target finding
  was cognitive complexity 87.
- Completed a Sonar `python:S3776` slice on series-transition window/level
  resolution: extracted new-series stored/fallback/cache helpers in
  `slice_window_level_resolver` so `resolve_window_level_for_series_transition`
  orchestrates only. Added
  `tests/core/test_slice_window_level_resolver_sonar_slice.py`. Target finding
  was cognitive complexity 89.
- Completed a Sonar `python:S3776` slice on measurement itemChange handlers:
  moved handle/group position, selection, geometry sync, and debug logging into
  `src/tools/measurement_item_change.py`; both `itemChange` methods now
  orchestrate that module. Added
  `tests/tools/test_measurement_item_change_sonar_slice.py`. Target findings
  were cognitive complexity 92 and 74.
- Ran a fresh local SonarQube analysis on `349ab6f` after the series-navigator
  list slice. CE task succeeded; `scripts/report_local_sonarqube_issues.py`
  reported **242** priority findings (BLOCKER/CRITICAL/MAJOR). Highest remaining
  open `python:S3776`: `measurement_items.itemChange` (92),
  `resolve_window_level_for_series_transition` (89), `dicom_loader.load_file` (88),
  `handle_load_first_slice` (87).
- Completed a Sonar `python:S3776` slice on series navigator list rebuild:
  moved series sorting, section-width, and display-label helpers into
  `series_navigator_model`; `SeriesNavigator.update_series_list` now
  orchestrates clear/append/schedule helpers. Added
  `tests/gui/test_series_navigator_list_update_sonar_slice.py`. Target finding
  was cognitive complexity 94.
- Completed a Sonar `python:S3776` slice on overlay corner text: lifted
  multiframe label, InstanceNumber/slice, thickness, and timing formatters out
  of `get_corner_text` in `overlay_text_builder`. Added
  `tests/gui/test_overlay_text_builder_sonar_slice.py`. Target finding was
  cognitive complexity 94.
- Completed a Sonar `python:S3776` slice on ROI XLSX export: moved workbook
  assembly, series/slice blocks, ROI stats/area/channel rows, and
  crosshair/measurement writers into `src/core/roi_export_xlsx.py`;
  `roi_export_service.write_xlsx` now orchestrates that module. Added
  `tests/core/test_roi_export_xlsx_sonar_slice.py`. Target finding was
  cognitive complexity 99.
- Completed a Sonar `python:S3776` slice on projection enabled handling:
  extracted state-apply, MPR/non-MPR refresh, and DEBUG_PROJECTION helpers in
  `projection_app_facade` so `on_projection_enabled_changed` orchestrates only.
  Covered by existing `tests/core/test_projection_app_facade.py`. Target finding
  was cognitive complexity 107.
- Completed a Sonar `python:S3776` slice on ROI statistics overlays: moved
  text formatting, font resolution, item ensure/flags, scene position, and
  visibility sync into `src/tools/roi_statistics_overlay.py`;
  `ROIManager.create_statistics_overlay` / position update now orchestrate
  those helpers. Added `tests/tools/test_roi_statistics_overlay_sonar_slice.py`.
  Target finding was cognitive complexity 122.
- Completed a Sonar `python:S3776` slice on subwindow layout signal wiring:
  extracted `_disconnect_ignore_missing` / tracked-slot pop helpers and
  fixed signal-pair tables so `connect_subwindow_signals` orchestrates only.
  Added `tests/core/test_subwindow_signal_wiring_sonar_slice.py`. Target finding
  was cognitive complexity 126.
- Completed a Sonar `python:S3776` slice on additive file load:
  moved eviction, PS/KO load, appended-series refresh, empty-pane auto-assign,
  navigator/fusion/status side effects into
  `src/gui/file_series_additive_load.py`;
  `FileSeriesLoadingCoordinator.handle_additive_load` now orchestrates only.
  Added `tests/gui/test_file_series_additive_load_sonar_slice.py`. Target finding
  was cognitive complexity 127.
- Completed a Sonar `python:S3776` slice on `FrameDatasetWrapper.__init__`:
  extracted nested functional-group helpers for plane geometry, pixel measures,
  rescale, and VOI LUT into focused functions in `multiframe_handler`. Added
  `tests/core/test_frame_dataset_wrapper_sonar_slice.py`. Target finding was
  cognitive complexity 133.
- Completed a Sonar `python:S3776` slice on overlay position updates: moved
  widget geometry sync, viewport corner anchors, max-width cache resolution,
  left/right item placement, and deferred repaint into
  `src/gui/overlay_position_updater.py`; `OverlayManager.update_overlay_positions`
  now orchestrates only. Added
  `tests/gui/test_overlay_position_updater_sonar_slice.py`. Target finding was
  cognitive complexity 142 on `update_overlay_positions`.
- Completed a Sonar `python:S3776` slice on the load pipeline: shared helpers
  for merge paths / empty-load errors / failed-file warnings / post-load
  status / progress UI; sync body split from outer exception wrapper; async
  implementation moved to `src/core/loading_pipeline_async.py` (re-exported
  from `loading_pipeline`). Added `tests/test_loading_pipeline_sonar_slice.py`.
  Fresh analysis: `run_load_pipeline_async` (was 146) cleared; no remaining
  `S3776` under `loading_pipeline*`; priority `S3776` count 253 → 251.
- Completed the non-constructor `python:S107` parameter-object sweep (8 sites:
  layout/load, render pipelines, cine + export request dataclasses) and fixed
  the two follow-on `python:S5806` builtin-shadow findings in
  `export_manager` (`format` → `export_format` locals). Documented the six
  remaining DI `__init__` constructors with `# NOSONAR(S107)` (wiring ctors;
  rule remains active for methods): `dialog_coordinator`, `export_dialog`,
  `histogram_dialog`, `keyboard_event_handler`, `roi_coordinator`,
  `slice_display_manager`. Fresh local analysis target: **0 MAJOR** from
  these S107 sites; CRITICAL volume is still dominated by deferred `S3776`.

## 2026-07-25

- **Superseded by the privacy-gated PR/push configuration below:** enabled the
  initial approved SonarQube Cloud CI analysis of `src/` only after pushes to
  `main`: `.github/workflows/sonarqube-cloud-main.yml` is pinned to the
  official scan action and uses only the repository `SONAR_TOKEN` secret.
  Root `sonar-project.properties` excludes tests, coverage, artifacts, local
  data, and generated/cache paths. The harness now permits only this exact
  main-only workflow; Automatic Analysis must remain disabled in SonarQube
  Cloud to prevent independent PR analysis.
- Completed the privacy structural-schema SonarQube slice: decomposed metric
  normalization and rendered-value revalidation, schema loading, validator
  parsing, and operation parsing into small fail-closed helpers. Added direct
  normalization and invalid-schema regression coverage. A fresh full-suite,
  coverage-backed local analysis cleared all five
  `utils/privacy/structural_schema.py` `S3776` findings; priority findings are
  now **280** (down from 285).
- Completed a targeted local SonarQube cleanup slice: made the RDSR privacy
  projection's `dataclasses.replace` type preservation explicit (`S5886`) and
  moved the lazy 3D-render eligibility import out of the subwindow wiring loop
  (`S1515`), with regression coverage for both. Documented four `S8572`
  suppressions where raw `logging.exception` would violate the PHI/PII sink
  gate; those paths retain structural/sanitized exception reporting. Fresh
  coverage-backed local analysis: **285** priority findings (down from 291).
- Approved a dormant, source-only SonarQube Cloud scope configuration for a
  future explicit CI workflow on `main`. Cloud analysis remains inactive until
  that workflow and its secret are separately enabled; PR, branch, test,
  coverage, artifact, and local-data uploads remain prohibited.

## 2026-07-24

- Local SonarQube freshness is now advisory-stale when a successful submission
  is older than 14 days or more than five commits behind `HEAD`. Submission
  records include their Git revision so the main pre-push reminder can detect
  code drift without contacting SonarQube.
- Every local pre-push now performs metadata-only Docker Hub/SonarSource checks
  for an updated local SonarQube server image and native scanner at most once
  every seven days. It records an ignored local result and never pulls,
  installs, or restarts anything.

## 2026-07-18

- Completed the fusion coordinator Sonar finish slice
  (`plans/SONARQUBE_FUSION_COORDINATOR_FINISH_SLICE_PLAN_20260718.md`): extracted
  helpers for `_finish_overlay_series_load`, `get_fused_image`, and
  `_update_spatial_alignment`. Extended
  `tests/gui/test_fusion_coordinator_sonar_slice.py`. Fresh analysis: **287**
  priority findings (down from 290); `fusion_coordinator` `S3776` → 0.
- Completed the fusion coordinator Sonar first slice
  (`plans/SONARQUBE_FUSION_COORDINATOR_SLICE_PLAN_20260718.md`): extracted
  helpers for `handle_fusion_enabled_changed`, `_update_base_display`,
  `sync_ui_from_handler_state`, `_update_resampling_status`, and
  `_auto_detect_fusion_candidates`. Added
  `tests/gui/test_fusion_coordinator_sonar_slice.py`. Fresh analysis: **290**
  priority findings (down from 295); five targeted `S3776` cleared (3 remaining
  in-file deferred: overlay load, fused image, spatial alignment).
- Completed the ROI coordinator Sonar finish slice
  (`plans/SONARQUBE_ROI_COORDINATOR_FINISH_SLICE_PLAN_20260718.md`): extracted
  helpers for `handle_roi_drawing_finished`, `handle_roi_delete_requested`,
  `delete_all_rois_current_slice`, and `handle_scene_selection_changed`. Added
  `tests/gui/test_roi_coordinator_sonar_finish_slice.py`. Fresh analysis:
  **295** priority findings (down from 299); `roi_coordinator` `S3776` → 0.
- Completed the MPR controller Sonar finish slice
  (`plans/SONARQUBE_MPR_CONTROLLER_FINISH_SLICE_PLAN_20260718.md`): extracted
  helpers for `prompt_save_mpr_as_dicom`, `attach_floating_mpr`,
  `_on_mpr_requested`, and `_reset_window_level_for_mpr`. Extended
  `tests/gui/test_mpr_controller_sonar_slice.py`. Fresh analysis: **299**
  priority findings (down from 303); `mpr_controller` `S3776` → 0.
- Completed the MPR controller Sonar slice
  (`plans/SONARQUBE_MPR_CONTROLLER_SLICE_PLAN_20260718.md`): extracted helpers
  for `display_mpr_slice`, `_activate_mpr`, `_tear_down_mpr_at_subwindow`,
  `_install_mpr_payload_at_subwindow`, and `_build_overlay_dataset`. Added
  `tests/gui/test_mpr_controller_sonar_slice.py`. Fresh analysis: **303**
  priority findings (down from 308); five targeted `S3776` cleared (`mpr_controller`
  `S3776` 9 → 4 remaining out-of-scope methods).
- Finished non-font `python:S1192` cleanup and added a file-scoped ignore for
  `S1192` on `src/utils/bundled_fonts.py` only
  (`tools/sonarqube/sonar-project.properties` multicriteria
  `bundled_fonts_s1192`) so the font catalog stays readable without demoting
  the rule globally. Fresh analysis: **308** priority findings (down from 347);
  `S1192` at 0 (including fonts ignore).
- Cleared all open `python:S108` empty-block findings and started
  `python:S1192` (duplicate string literals): extracted shared UI/status
  constants in dialogs/widgets/loading paths; left `src/utils/bundled_fonts.py`
  deferred as a font data table. Fresh analysis: **347** priority findings
  (down from 399); `S108` at 0; `S1192` remaining **39** (16 in
  `bundled_fonts`).
- Completed the view state manager Sonar slice
  (`plans/SONARQUBE_VIEW_STATE_MANAGER_SLICE_PLAN_20260718.md`): extracted
  helpers for `store_initial_view_state`, `reset_view`,
  `handle_window_changed`, `handle_rescale_toggle`, and
  `handle_viewport_resized`. Added
  `tests/gui/test_view_state_manager_sonar_slice.py`. Fresh analysis: **399**
  priority findings (down from 408); five targeted `S3776` cleared.
- Completed the Sonar MAJOR mechanical sweep
  (`plans/SONARQUBE_MAJOR_MECHANICAL_SWEEP_PLAN_20260718.md`): cleared all open
  `python:S125`, `python:S1066`, and `python:S1172` findings (commented-out
  code, collapsible ifs, unused parameters with signature-safe removals or
  `_ = param` retention). Fresh analysis: **408** priority findings (down from
  454); targeted three MAJOR rules at 0.
- Completed the slice display manager Sonar slice
  (`plans/SONARQUBE_SLICE_DISPLAY_MANAGER_SLICE_PLAN_20260718.md`): extracted
  helpers for `_render_base_image_pipeline`, `_sync_controls_and_metadata`,
  `_render_scene_overlays_annotations`, `display_rois_for_slice`, and
  `handle_series_navigation`. Added
  `tests/gui/test_slice_display_manager_sonar_slice.py`. Fresh analysis:
  **454** priority findings (down from 461); five targeted `S3776` cleared
  (`python:S3776` 282 → 277).
- Completed the ROI coordinator statistics-path Sonar slice
  (`plans/SONARQUBE_ROI_COORDINATOR_STATS_SLICE_PLAN_20260718.md`): extracted
  projection/spacing/ownership helpers for
  `_get_pixel_array_for_statistics`, `update_roi_statistics`, and
  `update_roi_statistics_overlays`; removed dead closure-debug code. Added
  `tests/gui/test_roi_coordinator_statistics.py`. Fresh analysis: **461**
  priority findings (down from 464); targeted stats-path `S3776` cleared.
- Completed the undo/redo annotation-command Sonar slice
  (`plans/SONARQUBE_UNDO_REDO_ANNOTATION_COMMANDS_SLICE_PLAN_20260718.md`):
  extracted add/remove helpers for `MeasurementCommand`,
  `TextAnnotationCommand`, `ArrowAnnotationCommand`, and `CrosshairCommand`.
  Added `tests/test_undo_redo_annotation_commands.py`. Fresh local analysis +
  scoped reporter: **464** active priority findings (down from 472);
  `undo_redo.py` targeted `S3776` findings cleared (293 → 285 overall).
- Completed the first CRITICAL code-smell remediation slice
  (`plans/SONARQUBE_CRITICAL_CODE_SMELL_FIRST_SLICE_PLAN_20260718.md`):
  - **S5727:** removed redundant `None` guards before
    `FusionCoordinator._update_spatial_alignment` cache writes; every branch
    already assigned `(scale, offset)` tuples. Added
    `tests/gui/test_fusion_coordinator_spatial_alignment.py`.
  - **S3776 (ROICommand only):** extracted add/remove/overlay-restore helpers in
    `utils.undo_redo.ROICommand` without changing undo semantics. Added
    `tests/test_undo_redo_roi_commands.py`.
  - Fresh local analysis + scoped reporter: **472** active priority findings
    (down from 476); remaining CRITICAL/MAJOR backlog stays in `TO_DO.md`.
- Widened the scoped local SonarQube reporter to include all open BLOCKER,
  CRITICAL, and MAJOR issues, regardless of type. The prior CRITICAL query
  filtered to BUG/VULNERABILITY and omitted the dashboard's CRITICAL
  CODE_SMELL findings; regression coverage now locks the all-types scope.
- Local SonarQube runner and scoped reporter now load simple `KEY=VALUE` (or
  `export KEY=VALUE`) entries from the ignored repository-root `.env` file.
  Explicit environment variables still take precedence, the file is parsed
  rather than executed, and token values are never printed. This lets the
  documented `.env` workflow work without a separate shell export.
- Remediated local SonarQube MAJOR findings on branch
  `fix/sonarqube-major-findings-20260718` (analysis
  `2026-07-18T17:12:01+0000` / revision `9484958196fcd183a88407f5f312d77bb521f8df`):
  - **S2245:** `deep_anonymizer` date-shift jitter now uses `secrets.randbelow`.
  - **S3923:** collapsed six identical if/else sites (annotation options colors,
    image-viewer pixel-array ambiguous branch, slice-sync plane lookup via the
    shared dataset→sorted mapper, measurement undo-batch tracking for angle and
    linear items).
  - **S1244:** documented `# NOSONAR(S1244)` suppressions for all 19 float-equality
    findings (DICOM DS-VR RescaleSlope/Intercept guards, VTK empty-scene bounds
    sentinels, flip/zoom/export/angle label sentinels); upgraded the bare
    `# NOSONAR` at `dicom_window_level.py:229` to rule-scoped form. No
    `math.isclose` refactors.
  - Deferred 114 MAJOR CODE_SMELL findings — tracked in `TO_DO.md`.
  - Plan: `plans/SONARQUBE_MAJOR_FINDINGS_REMEDIATION_PLAN_20260718.md`.


- Hardened local SonarQube endpoint handling: `SONAR_HOST_URL` now accepts
  only HTTP(S) loopback hosts, and the Docker-only override accepts only
  `host.docker.internal`. Added regression coverage for `file://`, remote,
  and credential-bearing URL rejection. The two validated `urllib` request
  sinks now have narrow Semgrep suppressions documenting this enforced
  boundary; the targeted security-audit scan returns zero findings.
- Added `scripts/report_local_sonarqube_issues.py`, an opt-in local reporter
  that queries severe SonarQube findings with `componentKeys`, requires every
  returned issue to belong to the requested component, rejects malformed or
  incomplete pagination, and keeps credentials out of command arguments and
  persisted reports. It can assert the latest analysis revision and writes
  detailed metadata only below ignored `tmp/`. Added mocked-HTTP regression
  tests, local-runner documentation, and the inventory entrypoint.
- Corrected a false DICOM Viewer triage report: its ten findings belonged to
  `weekend-digest-free-apis` and `spotibye`. A fresh local analysis processed
  at 2026-07-18 17:12:01 UTC for revision
  `9484958196fcd183a88407f5f312d77bb521f8df` returned zero component-scoped
  BLOCKER or CRITICAL BUG/VULNERABILITY findings. Focused tests (14), Ruff,
  basedpyright, full privacy-output check, security-tool inventory, and repo
  harness passed.

## 2026-07-16

- Added the canonical machine-readable security/privacy tool inventory with
  tested versions, installation scopes, network policies, hook/CI enforcement,
  model hashes, internal control entrypoints, and explicit prohibited external
  services. The repo harness and CI now validate its schema, required coverage,
  and referenced paths. Added a tracked, no-install `.envrc`, safe
  `.env.example`, and privacy-critical ignores/admission blocks for `.env`,
  `.direnv/`, `.scannerwork/`, `.sonar*`, and `.sonarqube*` local state. Direnv
  performs only a network-free requirements-hash check; the explicit
  `scripts/sync_dev_environment.py` command installs changed dependencies and
  stamps the active project venv after success.
- Installed and validated the isolated local PHI review environment
  (`.phi-tools`, approximately 1.7 GB): pinned PhiScan, Presidio plus the pinned English
  spaCy model, DICOM PHI scanner, EasyOCR/PyTorch with environment-local model
  weights, and system Tesseract/ExifTool. Fixed media/DICOM wrappers to resolve
  selected paths before entering protected temporary working directories and
  made the DICOM wrapper fail closed when OCR weights are missing. Added the
  clean private-repository recreation runbook after verifying the 672-commit
  `old-main` archive has no overlap with the 25 commits actually on GitHub. A
  dry-run clean-root export then drove two corrections: force-adding only the
  tracked archive so conservatively ignored packaged icons remain present, and
  allowing reviewed Gitleaks false positives to bind to an exact Git blob,
  rule, and line instead of the root commit identity.
- Added protected-path and conditional local-review enforcement: the blocking
  artifact gate now rejects force-added files under privacy-critical local data,
  screenshot, log, analysis, backup, and temporary roots and validates the
  staged `.gitignore` blob retains every required rule. Pre-commit now invokes
  advisory PhiScan/OCR/Presidio/DICOM wrappers only for matching staged index
  blobs, and successful `main` pre-push flows run local-only Hounddog before the
  existing SonarQube freshness reminder. Optional results remain advisory;
  artifact admission and human hash review remain blocking.

- **Local-first analysis policy:** Removed Codecov coverage upload/configuration
  and SonarQube Cloud repository configuration. CI retains a console-only
  coverage summary. External analysis/telemetry integrations are prohibited by
  the privacy guardrails; the local SonarQube Community Build runner remains
  opt-in.
- **Agent harness simplification:** Removed duplicate project-local general
  skills, specialist role agents, auto-orchestration state/run packets, and the
  test ledger. Retained only the DICOM Viewer-specific agent smoke skill in
  both supported skill locations.
- **Periodic local assurance:** Fixed pre-push ref input reuse so the main-only
  full scanner suite cannot be skipped after the metadata guard consumes
  stdin. Main updates now get a non-blocking reminder when the ignored local
  SonarQube Community Build record is missing or older than 30 days; the check
  never contacts SonarQube or requires a token.

## 2026-07-14

- **Optional local SonarQube Community Build runner:** Added `scripts/run_local_sonarqube.py` plus isolated `tools/sonarqube/sonar-project.properties` for opt-in local analysis. The runner uses `SONAR_TOKEN`, preflights the service, selects a native or Docker scanner, records the last successful submission in ignored `.sonar-local/last-analysis.json`, and offers opt-in pytest coverage. It is intentionally excluded from automatic hook execution and CI because a local scan may be slow. SonarQube Cloud was later removed under the 2026-07-16 local-first policy.

## 2026-07-11

- **Backlog history split:** `TO_DO.md` was converted back to an active-backlog-only checklist: removed the top `Changes:` narrative and removed fully completed `[x]` task rows. Completed user-visible changes belong in `CHANGELOG.md`; maintainer/process changes belong here; detailed implementation records belong in plans, info docs, or bug-investigation notes.

## 2026-06-16

- **Static typing cleanup:** Swept basedpyright back to **0 errors** in `src/` and `scripts/` after the refactor/PS3.15/nuclear work had regressed to 246 errors. Categories included `Tag` to `BaseTag` annotation fixes, `TYPE_CHECKING` app imports, type arguments, Qt builder-pattern directives, and defensive `None` guards. Full pytest at the time: **1008 passed / 17 skipped**.
- **Doc feature coverage tooling:** Added `scripts/check_doc_feature_coverage.py`, a report-only menu/`QAction` label to `user-docs/` coverage heuristic with `--fail-under` support, tests, and HARNESS documentation.
- **Changelog hygiene:** Consolidated duplicate `[Unreleased]` third-level headings in `CHANGELOG.md`; doc-garden duplicate count returned to 0.
- **User-doc coverage:** Added topic guides for de-identified export, measurements/annotations, keyboard shortcuts, multi-window layouts, the general Export dialog, and the DICOM Tag Viewer. Extended repo-harness doc-garden checks to report missing/stale `Last updated:` metadata on required user guides.

## 2026-06-04

- **UX maintenance sweep:** Updated W/L status-bar and preset access notes after status bar center readout changed to numeric W/L, right-pane `Presets...` moved beside `Use rescaled values`, and W/L presets were exposed from the View menu and Quick W/L dialog.
- **Workflow fixes tracked:** Recorded close-out for cut/paste same-slice positioning, ROI resize handle cleanup on delete/cut, large-file cancel-before-load, Edit -> Cut, canceled folder-load index skip/toast, and compact W/L preset labels. User-visible entries remain in `CHANGELOG.md`; implementation details remain in linked plans/tests.
