# Medium bug-hunt findings — fix plan (2026-11-04)

**Status:** Chunk 1 (CT batch result dialog slot wipe) already committed; chunk 2 (study-index relocate) implemented; remaining P2 items pending. Revised 2026-11-06 after a second review (cine fallback test, relocate test fakes, per-item preview slab).  
**Priority:** P2 (six items) plus optional P3 MPR hardening  
**Created:** 2026-11-06  
**Verified against:** `docs/track-medium-bug-hunt-findings-20261104` @ `2816eae` (same `src/` as `7016f3b`)  
**Tracks:** [`TO_DO.md`](../TO_DO.md) §Bugs / Correctness — “Medium findings from 2026-11-04 critical-bug hunt”  
**Investigation:** [`CRITICAL_BUG_HUNT_MEDIUM_FINDINGS_2026-11-04.md`](../bug-investigations/CRITICAL_BUG_HUNT_MEDIUM_FINDINGS_2026-11-04.md)

## Verdict

The six P2 items are real on this branch. One claim in the hunt note is narrower than written: cine export does **not** put `_MIP_Nslices` in the video filename. It does silently encode the source slice when a requested projection slab cannot be built. The three MPR notes are real code gaps with a narrow trigger; they stay optional and ship only in the same change if the P2 work is already green.

Nothing here met the critical bar in the original hunt, and this re-check did not find a crash, data-loss, or on-image wrong-patient path. Two items are local AppSec (spreadsheet formula bypass, Qt rich text). The relocate item is catalog integrity. The others are wrong dialog ownership, wrong contrast, or a misleading export.

**Semantic versioning:** each code fix is a patch. Do not bump `src/version.py` while `0.5.0` is still unreleased. Record the user-visible fixes under `[Unreleased]` / Fixed when they land, not in the plan-only commit.

## Confirmed defects

### 1. CT batch result dialog slot wipe — P2

`QAAppFacade.show_ct_batch_result_dialog` connects `on_destroyed` to a callback that always assigns `app._ct_batch_result_dialog = None`. The dialog sets `WA_DeleteOnClose` (`create_ct_batch_result_dialog`). `QObject.destroyed` can run after `close()` returns. A second batch closes dialog A, stores dialog B, then A's deferred destroy clears B's slot. Later batches no longer have the live dialog, so they cannot close it. Temp-dir cleanup is per worker closure and is fine; only the slot clear is wrong.

MRI already does this correctly in `gui.qa_mri_batch_flow._show_acr_mri_batch_summary`: `close()` the previous dialog, and clear the slot only when `app._mri_batch_result_dialog is dialog`. Cleanup of that dialog's worker still runs.

**Fix:** Match the MRI order and guard. Do not assign the slot to `None` unconditionally, including the assignment that currently runs immediately after `close()`.

### 2. Study-index relocate commits on any one file — P2

`StudyIndexStore.relocate_study_paths` rewrites every selected row when `any(os.path.isfile(...))` is true. Rows whose path is not under `old_root` still get `study_root_path` set to `new_root` while `file_path` stays on the old tree. `StudyIndexSearchDialog._relocate_and_reopen` then calls `_open_paths([new_root])`, which folder-rescans the chosen directory.

A partial move, or another folder that happens to contain one shared relative name, updates study A's catalog and opens folder B. Overlays re-parse DICOM, so this is not a wrong name burned into the image. It is a wrong catalog and a wrong folder open.

**Fix:**

- `iter_study_groups` and `get_file_paths_for_study` key a study by `(study_uid, study_root_path)`. Do not move only the in-prefix rows. If any row in the group has a `file_path` that is not under `old_root` on a path-component boundary, commit nothing and return 0. A partial rewrite would leave a second group at the old root and drop those instances from the relocated open. A root such as `ar` must not absorb `archive/`.
- Otherwise commit only when **every** rewritten path exists as a file. If any are missing, write nothing and return 0.
- Before commit, `dcmread(..., stop_before_pixels=True)` each new file. Require `SOPInstanceUID` to match that row and `StudyInstanceUID` to match `study_uid`. A same-relative-name tree from a different study must not commit. A missing UID, or `InvalidDicomError`, fails closed (return 0). Do not let the read exception surface as "Relocate failed".
- Keep the DICOM read out of `sqlcipher_store`. `index_folder_thread` already uses `pydicom.dcmread`. The header check belongs in the index service (or a helper next to it). `relocate_study_paths` today selects only `id, file_path`, so it cannot see `sop_instance_uid`. Add a store method that applies an already-checked list, for example `apply_study_path_updates(rows: list[tuple[str, str, int]])` writing `(file_path, study_root_path, id)` in one transaction. The service loads the SOP and study UID, checks the files, and calls that method only when every row passes. Header-only reads on the relocate click are enough. Do not move this onto a background indexer.
- After success, `StudyIndexSearchDialog._relocate_and_reopen` opens `get_file_paths_for_study(study_uid, new_root)`, not `[new_root]`. Sibling DICOM in the chosen directory stays out of this open. `_open_paths` is the dialog's `open_paths_callback`; do not change what a normal Study Index row open loads. `_MissingStudiesDialog._relocate_selected` does not open files; leave that.
- Both failure strings (search dialog ~line 720 and missing-studies dialog ~line 1120) become: "The index was not changed. Relocate only runs when every indexed file for this study is inside its current folder and the same file is found in the selected folder." Do not claim that files were found.

**Existing tests this fix must update** (they lock today's contract, including the `b"DICM"` stubs and the folder open):

- `tests/test_study_index_integrity_scan.py`: `_seed` and `test_relocate_preserves_similarly_prefixed_unrelated_paths` write `b"DICM"`, which `dcmread` rejects. Write a minimal synthetic dataset per file (`save_as`) whose `SOPInstanceUID` equals that row and whose `StudyInstanceUID` equals the study uid. No real patient data. `_seed` may keep the shared `sop_instance_uid` it already stores (`"{study_uid}.i"`); match that value, do not invent a uniqueness migration for the scan tests.
- `test_relocate_rewrites_paths_and_counts` still expects `n == 3` once those files are readable DICOM with matching UIDs.
- `test_relocate_preserves_similarly_prefixed_unrelated_paths` must expect `0`, with both rows still on the old root and the `archive/unrelated.dcm` path unchanged. Do not change it to `1`. Returning 1 would split the `(study_uid, study_root_path)` group.
- `tests/gui/test_study_index_open_relocate.py` `_FakeService` does not implement `get_file_paths_for_study`. Add it, return a non-empty path list, and change `test_relocate_reopens_new_folder` from `opened == [["/new/loc"]]` to that list.
- `tests/gui/test_study_index_search_dialog_coverage.py` `Service.get_file_paths_for_study` already returns `list(self.file_paths)`. Do not add another method. In `test_relocate_and_reopen_success_and_guards`, set `service.file_paths` to the paths that should open and assert `opened == [list(service.file_paths)]`. Point the `"No relocated files"` assertion at `"The index was not changed"`.

### 3. Fusion grayscale base re-stretch — P2

`FusionCoordinator.get_fused_image` takes the windowed PIL image (`np.array(base_image)`) and calls `create_fusion_image(..., base_wl=None)`. A mode-L PIL image is 2D `uint8`. `_fusion_float_base` divides by 255 only for 3-channel integer RGB. The 2D `base_wl is None` branch in `_base_display_rgb` min-max normalizes. A soft-tissue window whose samples do not already span 0 and 255 is stretched again when fusion turns on. The RGB path keeps dtype scale. Same patient, display only.

Do **not** delete min-max for every 2D base. `tests/test_fusion_processor.py::test_auto_normalize_when_base_is_non_uniform` locks the float32 contract: values `0, 50, 100, 150` become `0, 85, 170, 255` when `base_wl` is omitted. Wider integer dtypes used as raw samples (`test_non_float32_inputs` uses `int16`) stay on that path.

**Fix:** Treat 2D `uint8` as display-final, the array `np.array` produces from a mode-L PIL image. Divide it by 255, the same scale the integer RGB path uses, and do not min-max it. Decide that from the dtype **before** `_fusion_float_base` casts it to float32. An explicit `base_wl` still windows. Float and non-`uint8` integer bases keep today's min-max when `base_wl` is `None`.

### 4. Spreadsheet formula neutralization skips leading whitespace and controls — P2 (AppSec)

`neutralize_spreadsheet_value` returns early unless `value[:1]` is `=`, `+`, `-`, or `@`. A leading tab, CR, LF, space, or other leading whitespace/control leaves the trigger in place. Excel and LibreOffice still evaluate some of those cells. Study-index, SR, and ROI writers already call this helper for a bare trigger; the hole is in the helper, so every writer inherits it.

**Fix:** If a string has a formula trigger at the first character that is not Unicode whitespace and not a C0 control (`ord < 32`), prefix the **original** string with one apostrophe. Do not strip the leading characters (the stored text must survive). Non-strings stay unchanged. `" hello"` and `"\tHello"` stay unchanged.

Study-index import (`portability._restore_imported_text`) currently strips one leading apostrophe only when the next character is a trigger. `"\t=cmd"` would export as `"'\t=cmd"` and import would keep the apostrophe. Extend the restore so that, after the apostrophe, leading whitespace and C0 controls are skipped and a following trigger still strips **only** that apostrophe. Keep the existing collision: a value already stored as `'=` comes back without the apostrophe. Document the same collision for `'\\t=` (apostrophe, whitespace/control, trigger). No second neutralization rule.

### 5. Projection still-image name, and cine's silent single-slice fallback — P2

`export_filename` appends `_{TYPE}_{N}slices` whenever `projection_enabled` is true. `ExportManager.export_selected` chooses that name **before** `export_slice`. For PNG/JPG, `create_projection_for_export` returns `None` when the slab has fewer than two slices, and `export_slice` then writes the source slice to the projection path. The overwrite preview uses the same name. Anonymized DICOM already skips a slice that was not prebuilt. Do not weaken that fail-closed DICOM path.

Cine's save dialog names the file from `SeriesDescription` (`gui.actions.dialog_actions`). It does not add `_MIP_Nslices`. `rasterize_cine_export_frame` still substitutes the source slice when the projection returns `None`, so a projection cine can be a stack of ordinary slices.

**Fix:**

- Never write a projection token unless that slice's projection image was actually built. PNG/JPG fallback uses the single-slice filename (`projection_enabled=False` for that item). If a later build still returns `None`, write the single-slice name or fail the item. Do not leave a `_MIP_` file that holds one source slice.
- Preview (`get_export_paths_for_selection`): when `studies` is present, use the same slab test as `create_projection_for_export` for that item. Omit the projection token when the series has fewer than two slices, or when `end_slice - start_slice + 1 < 2` (the last slice of a longer series). Do not treat "series length ≥ 2" as enough. When `studies` is `None`, keep today's name. `tests/gui/test_export_manager_slice.py::test_get_export_paths_dicom_and_projection_suffix` locks `_MIP_4slices` for a one-item selection with no `studies` dict, and the method docstring already says a projection that fails to build may appear in the preview and not on disk. Do not change that test.
- DICOM projection stays fail-closed: no source-slice DICOM written under a projection series when the slab was not built.
- Cine: when projection is on and a frame's slab cannot be built, do not encode the source slice as that frame. `rasterize_cine_export_frame` returns `None` for that frame. The caller skips it and reports how many were skipped, or aborts before encode if none can be built. Leave the video filename as the series description.
- `tests/gui/test_cine_video_export.py` case "4. Projection image rendering fallback" currently asserts `rasterize_cine_export_frame(...) is not None` when `create_projection_for_export` returns `None`. Change that assertion to `None`. That is the one cine assertion this plan authorizes changing.

### 6. DICOM text in `QLabel` AutoText — P2 (AppSec)

`QLabel` defaults to `Qt.TextFormat.AutoText`. `mightBeRichText` treats a leading `<...>` as HTML, so a `StudyDescription` or overlay tag can change the label or trigger a resource lookup (`<img>`). This is local UI spoofing, not code execution.

Confirmed sinks:

- `gui.series_navigator_view.StudyLabel` — constructor and `set_text` use `StudyDescription` from `study_label_from_dataset` with no format set.
- `gui.overlay_manager.ViewportOverlayWidget` corner labels — `set_corner_text` calls `setText` with DICOM field text. `StudyDescription` is in the detailed field list.

`gui.lut_pane_label` already calls `setTextFormat(Qt.TextFormat.PlainText)`. The MPR banner string is app-generated (`"MPR – …"`), not a DICOM tag; leave it unless a later read shows a tag value in that string. Do not flip intentional `RichText` help labels in settings dialogs.

**Fix:** In `StudyLabel.__init__`, replace `QLabel(study_label_text, self)` with `QLabel(self)`, then `setTextFormat(Qt.TextFormat.PlainText)`, then `setText(study_label_text)`. The corner labels in `ViewportOverlayWidget` are already empty `QLabel(self)` widgets. Call `setTextFormat(PlainText)` on each one while they are created. Do not rebuild them. `set_text` and `set_corner_text` keep assigning text after that. The graphics overlay path (`overlay_items_factory.create_graphics_overlay_text_item`) already calls `document.setPlainText`. Leave it. Tooltips stay as they are. Do not convert them into labels.

## Optional P3 — MPR admission and sync

Ship these only after the P2 tests are green, in the same branch if the edits stay small. Do not block the P2 fixes on them.

1. **Empty source key.** `dataset_source_key` returns `("", "")` when the dataset list cannot be read. A readable dataset with no `StudyInstanceUID` returns `("", series_key)`, which is still an empty study UID. `_source_matches` requires equal study UIDs, so that build is not released by closing a study that has a real UID. On a normal study the key is populated. Hardening: do not admit `reserve_pane_build` when the study UID is empty; surface the existing admission status text. Do not drop sessions that legitimately belong to a study whose UID is non-empty.

2. **Slice sync reads the stale index after a failed linked redraw.** `mpr_view_links._write_members` stores `mpr_slice_index` before redraw. `display_mpr_slice` writes `current_slice_index` only when the image is applied. `SliceSyncCoordinator._get_slice_index` in `src/core/slice_sync_coordinator.py` reads only `current_slice_index`. For an MPR pane (`is_mpr` and `mpr_result`), return `mpr_slice_index` when it is an int, otherwise the current index. Native panes stay on `current_slice_index`.

3. **Registry reservations without a pane map entry.** `reserve_pane_build` stores the token in both `MprSessionRegistry` and `controller._build_reservations[pane]`. `release_closed_source_sessions` retires pane workers and discards sessions that already have views. It does not call `registry.close_study`. A pending build token with no pane entry survives. `registry.close_study` also discards sessions, so calling it from the pane path would double-discard and raise. Add a reservation-only UID sweep (the loop at the end of `_close_source`) and call that from study/series close. Sessions continue to go through the existing discard path exactly once.

## Decisions

- One plan, one implementation branch (this PR's branch until the fixes land). P2 items are independent enough to commit in logical slices, but they stay on this branch.
- No new user-guide page. Relocate's failure text is the only string change a user sees, and it replaces an inaccurate sentence. Formula apostrophes stay undocumented, matching the completed CSV plan. Projection filename and cine skip counts are behavior, not a new workflow; mention the cine skip in `[Unreleased]` only.
- No PHI fixtures. Tests use synthetic UIDs, tiny arrays, and `QLabel` strings. Do not add DICOM files, screenshots, or spreadsheets of real studies.
- `docs-impact: not needed` for the plan commit. Re-evaluate when the code fix changes the relocate message or cine skip behavior; a changelog line covers it if Help does not describe those paths today.

## Checklist

- [x] CT: `on_destroyed` clears `_ct_batch_result_dialog` only when it is that dialog. A replacement dialog stays referenced if the previous destroy runs late. Worker temp cleanup still runs for the dialog that closed.
- [x] Relocate: if any row is outside `old_root`, or any new file is missing, unreadable, or has a different SOP/Study UID, commit nothing and return 0. A fully in-prefix study with matching headers commits. Open passes the relocated file paths. Both dialogs use the new unchanged-index sentence. Existing relocate tests updated as in §2, not left red.
- [ ] Fusion: 2D `uint8` display base is `/255` with no min-max. Float min-max test still passes. Explicit `base_wl` unchanged.
- [ ] Formula helper: leading tab, CR, LF, space, and a C0 control before `=+-@` gain one apostrophe. Study-index CSV round-trips `\t=cmd` back to `\t=cmd`. Benign indented text is unchanged.
- [ ] PNG/JPG: a thin slab, including the last slice of a longer series, is not saved under `_MIP_` / `_AIP_` / `_MINIP_`. Preview uses that same per-item slab test when `studies` is present. Preview with `studies is None` still includes `_MIP_4slices` for the existing one-item DICOM test. DICOM projection still writes nothing for a slab that was not built.
- [ ] Cine: `rasterize_cine_export_frame` returns `None` when the requested projection slab was not built, and the named fallback assertion in `test_cine_video_export.py` expects `None`. The user is told when frames were skipped or when there is nothing to encode.
- [ ] Navigator study label and overlay corner labels are `PlainText` before the DICOM string is set. A `<b>…</b>` description is shown as characters.
- [ ] P3 (optional, same branch if small): reject empty-UID admission; MPR slice sync reads `mpr_slice_index`; close sweeps registry reservations that have no pane entry, without discarding a session twice.
- [ ] Changelog `[Unreleased]` / Fixed notes for the user-visible items, each marked patch, no version bump while `0.5.0` is unreleased.
- [ ] Focused tests below, then the full suite if a slice touches more than one domain.

## Tests

Run with the project venv. Do not construct a `QCoreApplication`; use the session `qapp` fixture.

| Area | Start with |
|------|------------|
| CT dialog slot | `tests/gui/test_qa_app_facade_guard_paths.py`, `tests/gui/test_qa_app_facade_round2.py` |
| Relocate | `tests/test_study_index_integrity_scan.py`, `tests/gui/test_study_index_open_relocate.py`, `tests/gui/test_study_index_search_dialog_coverage.py`, `tests/gui/test_study_index_missing_studies_dialog.py` |
| Fusion scale | `tests/test_fusion_processor.py` |
| Formula + CSV round-trip | `tests/test_spreadsheet_safety.py`, `tests/core/test_spreadsheet_safety_extended.py`, study-index portability tests |
| PNG name / preview / cine fallback | `tests/gui/test_export_manager_slice.py`, `tests/gui/test_export_projection_anonymized.py`, `tests/gui/test_cine_video_export.py` |
| PlainText labels | `tests/gui/test_lut_pane_label.py` as the pattern; add a navigator/overlay case beside existing navigator tests |
| P3 only | existing `tests/test_mpr_*.py`, `tests/gui/test_mpr_*.py`, `tests/core/test_mpr_*.py` |

Add tests that fail on today's code. Where this plan names an existing assertion, update it to the new contract. Do not loosen any other assertion to keep the old behavior.

## Out of scope

- Critical-bar work (none confirmed here).
- Rewriting fusion's float auto-normalize contract.
- Changing intentional `RichText` help copy.
- MPR feature work beyond the three hardening notes above.
