# Documentation triage ledger

**Last updated:** 2026-09-06  
**Status:** Living, current-state register. Git history preserves decision
history; do not delete a resolved row without recording the replacement or why
the signal ceased to apply.

## Purpose and rules

This ledger turns documentation gaps into explicit decisions rather than an
undifferentiated coverage percentage. It covers signals from the feature
coverage report, a documentation assessment, release review, PR review, or a
manual user/developer documentation audit. It is not a claim that the list is
an exhaustive inventory of application behavior.

Every row must have a source signal, an inventory ID from
[`DOCUMENTATION_INVENTORY.md`](DOCUMENTATION_INVENTORY.md), a disposition, a
rationale, and—unless it is resolved in the same change—a repository-relative
follow-up link. `pending-triage` is allowed only until the next relevant
assessment; it is not a resolution.

| Disposition | Meaning |
| --- | --- |
| `pending-triage` | Signal recorded but not yet evaluated against code/UI and canonical docs. |
| `document` | Add or materially correct the named canonical documentation. |
| `intentionally-omit` | User-facing documentation is unnecessary; rationale must say why. |
| `duplicate` | Existing canonical documentation covers the behavior; add its exact path/section and improve discovery only if needed. |
| `obsolete` | The signal no longer represents shipped behavior; cite the code/removal evidence. |
| `deferred` | Work is warranted but intentionally scheduled later; a bounded repository-relative follow-up is mandatory. |

When a decision changes, update the row with the new disposition, rationale,
and review date in the resolving PR. Git history is the decision trail. An
assessment must list the triage IDs it sampled or changed.

## Feature-coverage decisions (Phase 1 — 2026-09-05)

Source: `python scripts/check_doc_feature_coverage.py` at revision `b5dc73a`,
with dispositions from
[`doc-assessment-2026-09-05-111057.md`](doc-assessments/doc-assessment-2026-09-05-111057.md).
The script remains a lower-bound heuristic. `document` follow-ups for TRIAGE-001–036
listed below were applied on branch `docs/documentation-phase1-accuracy-audit`
(commits from 2026-09-05 Phase 1 first slice + Muse review fixes). Keep the row
for history; do not reopen unless the shipped text drifts again.

| ID | Signal / source | Inventory ID | Disposition | Required decision evidence / likely destination | Follow-up | Last reviewed |
| --- | --- | --- | --- | --- | --- | --- |
| TRIAGE-001 | Clear Cine Bounds — `src/gui/cine_controls_widget.py:335` | DOC-05 | document | Right-click frame slider clears loop start/end; not in user-docs. | [USER_GUIDE_LAYOUTS.md — Slice & cine](../user-docs/USER_GUIDE_LAYOUTS.md#slice--cine-navigation) | 2026-09-05 |
| TRIAGE-002 | Decrease Font Size — `src/gui/main_window_menu_builder.py:417` | DOC-16 | duplicate | Covered by overlay font shortcuts and Overlay Settings. | [USER_GUIDE_SHORTCUTS.md](../user-docs/USER_GUIDE_SHORTCUTS.md); [CONFIGURATION.md — Overlay Settings](../user-docs/CONFIGURATION.md#view--overlay-settings) | 2026-09-05 |
| TRIAGE-003 | Direction Labels Color — `src/gui/main_window_menu_builder.py:463` | DOC-04 | duplicate | Alternate entry for Overlay Settings direction-label color. | [CONFIGURATION.md — Overlay Settings](../user-docs/CONFIGURATION.md#view--overlay-settings) | 2026-09-05 |
| TRIAGE-004 | Disclaimer — `src/gui/main_window_menu_builder.py:721` | DOC-12 | document | Help → Disclaimer safety text not in user-docs. | [USER_GUIDE.md](../user-docs/USER_GUIDE.md) — Safety / disclaimer | 2026-09-05 |
| TRIAGE-005 | Edit Recent List — `src/gui/main_window_menu_builder.py:103` | DOC-05 | document | File → Edit Recent List… workflow undocumented. | [USER_GUIDE.md](../user-docs/USER_GUIDE.md) — Recent files | 2026-09-05 |
| TRIAGE-006 | Enable Slice Sync — `src/gui/main_window_menu_builder.py:523` | DOC-05 | document | View → Slice Sync master toggle needs layouts coverage. | [USER_GUIDE_LAYOUTS.md](../user-docs/USER_GUIDE_LAYOUTS.md) — Linked navigation | 2026-09-05 |
| TRIAGE-007 | Enable/Disable — `src/gui/main_window_menu_builder.py:542` | DOC-05 | document | Master toggle for **Show Slice Location Lines** (not slice sync). | [USER_GUIDE_LAYOUTS.md](../user-docs/USER_GUIDE_LAYOUTS.md) — Slice Location Lines | 2026-09-05 |
| TRIAGE-008 | Exit — `src/gui/main_window_menu_builder.py:174` | DOC-02 | intentionally-omit | Standard File → Exit; quit shortcut already documented. | — | 2026-09-05 |
| TRIAGE-009 | Export Customizations — `src/gui/main_window_menu_builder.py:146` | DOC-04 | document | File → Export Customizations… path/scope incomplete in docs. | [CONFIGURATION.md](../user-docs/CONFIGURATION.md) — Import & export customizations | 2026-09-05 |
| TRIAGE-010 | Export Tag Presets — `src/gui/main_window_menu_builder.py:156` | DOC-17 | document | File → Export Tag Presets… bulk JSON export. | [USER_GUIDE_EXPORT.md](../user-docs/USER_GUIDE_EXPORT.md#dicom-tag-export-dialog) | 2026-09-05 |
| TRIAGE-011 | Import Customizations — `src/gui/main_window_menu_builder.py:150` | DOC-04 | document | File → Import Customizations… merge/apply behavior. | [CONFIGURATION.md](../user-docs/CONFIGURATION.md) — Import & export customizations | 2026-09-05 |
| TRIAGE-012 | Import Tag Presets — `src/gui/main_window_menu_builder.py:160` | DOC-17 | document | File → Import Tag Presets… merge; skips name conflicts. | [USER_GUIDE_EXPORT.md](../user-docs/USER_GUIDE_EXPORT.md#dicom-tag-export-dialog) | 2026-09-05 |
| TRIAGE-013 | Increase Font Size — `src/gui/main_window_menu_builder.py:429` | DOC-16 | duplicate | Same as TRIAGE-002. | [USER_GUIDE_SHORTCUTS.md](../user-docs/USER_GUIDE_SHORTCUTS.md) | 2026-09-05 |
| TRIAGE-014 | Magnify — `src/gui/main_window_toolbar_builder.py:379` | DOC-06 | duplicate | Magnify / **G** already in annotations + shortcuts. | [USER_GUIDE_ANNOTATIONS.md](../user-docs/USER_GUIDE_ANNOTATIONS.md); [USER_GUIDE_SHORTCUTS.md](../user-docs/USER_GUIDE_SHORTCUTS.md) | 2026-09-05 |
| TRIAGE-015 | Manage Sync Groups — `src/gui/main_window_menu_builder.py:533` | DOC-05 | document | Slice Sync → Manage Sync Groups… dialog. | [USER_GUIDE_LAYOUTS.md](../user-docs/USER_GUIDE_LAYOUTS.md) — Linked navigation | 2026-09-05 |
| TRIAGE-016 | Move Down — `src/gui/dialogs/edit_recent_list_dialog.py:297` | DOC-05 | duplicate | Subordinate to TRIAGE-005. | [USER_GUIDE.md](../user-docs/USER_GUIDE.md) — Recent files | 2026-09-05 |
| TRIAGE-017 | Move Up — `src/gui/dialogs/edit_recent_list_dialog.py:290` | DOC-05 | duplicate | Subordinate to TRIAGE-005. | [USER_GUIDE.md](../user-docs/USER_GUIDE.md) — Recent files | 2026-09-05 |
| TRIAGE-018 | No recent files — `src/gui/main_window_recent_files_manager.py:94` | DOC-05 | intentionally-omit | Empty-state UI text only. | — | 2026-09-05 |
| TRIAGE-019 | Only Show For Same Group — `src/gui/main_window_menu_builder.py:555` | DOC-05 | document | Slice-location line filter by sync group. | [USER_GUIDE_LAYOUTS.md](../user-docs/USER_GUIDE_LAYOUTS.md) — Slice Location Lines | 2026-09-05 |
| TRIAGE-020 | Remove This Item — `src/gui/dialogs/edit_recent_list_dialog.py:283` | DOC-05 | duplicate | Subordinate to TRIAGE-005. | [USER_GUIDE.md](../user-docs/USER_GUIDE.md) — Recent files | 2026-09-05 |
| TRIAGE-021 | Rotate 180° — `src/gui/main_window_menu_builder.py:382` | DOC-16 | document | View → Orientation → Rotate 180° (menu-only). | [USER_GUIDE_SHORTCUTS.md](../user-docs/USER_GUIDE_SHORTCUTS.md) — View & display | 2026-09-05 |
| TRIAGE-022 | Scale Markers Color — `src/gui/main_window_menu_builder.py:453` | DOC-04 | duplicate | Alternate Overlay Settings entry. | [CONFIGURATION.md — Overlay Settings](../user-docs/CONFIGURATION.md#view--overlay-settings) | 2026-09-05 |
| TRIAGE-023 | Set Cine End — `src/gui/cine_controls_widget.py:327` | DOC-05 | document | Right-click frame slider set end; with 001/024. | [USER_GUIDE_LAYOUTS.md — Slice & cine](../user-docs/USER_GUIDE_LAYOUTS.md#slice--cine-navigation) | 2026-09-05 |
| TRIAGE-024 | Set Cine Start — `src/gui/cine_controls_widget.py:321` | DOC-05 | document | Right-click frame slider set start; with 001/023. | [USER_GUIDE_LAYOUTS.md — Slice & cine](../user-docs/USER_GUIDE_LAYOUTS.md#slice--cine-navigation) | 2026-09-05 |
| TRIAGE-025 | Show Direction Labels — `src/gui/main_window_menu_builder.py:457` | DOC-04 | duplicate | Covered by Overlay Settings / MPR tips. | [CONFIGURATION.md — Overlay Settings](../user-docs/CONFIGURATION.md#view--overlay-settings) | 2026-09-05 |
| TRIAGE-026 | Show Instances Separately — `src/gui/main_window_menu_builder.py:350` | DOC-05 | document | Multi-frame per-instance navigator expansion. | [USER_GUIDE_LAYOUTS.md](../user-docs/USER_GUIDE_LAYOUTS.md) — Series navigator | 2026-09-05 |
| TRIAGE-027 | Show Only For Focused Window — `src/gui/main_window_menu_builder.py:568` | DOC-05 | document | Slice-location lines from focused window only. | [USER_GUIDE_LAYOUTS.md](../user-docs/USER_GUIDE_LAYOUTS.md) — Slice Location Lines | 2026-09-05 |
| TRIAGE-028 | Show Scale Markers — `src/gui/main_window_menu_builder.py:447` | DOC-04 | duplicate | Covered by Overlay Settings. | [CONFIGURATION.md — Overlay Settings](../user-docs/CONFIGURATION.md#view--overlay-settings) | 2026-09-05 |
| TRIAGE-029 | Show Slab Boundaries (Begin/End) Instead of Centre — `src/gui/main_window_menu_builder.py:584` | DOC-05 | document | Centre vs ±½-thickness boundary lines; align CONFIGURATION wording. | [USER_GUIDE_LAYOUTS.md](../user-docs/USER_GUIDE_LAYOUTS.md); [CONFIGURATION.md](../user-docs/CONFIGURATION.md#view--overlay-settings) | 2026-09-05 |
| TRIAGE-030 | Show Slice/Frame Count on Navigator Thumbnails — `src/gui/main_window_menu_builder.py:326` | DOC-05 | document | Navigator thumbnail instance/frame badges. | [USER_GUIDE_LAYOUTS.md](../user-docs/USER_GUIDE_LAYOUTS.md) — Series navigator | 2026-09-05 |
| TRIAGE-031 | Show Window Assignment Thumbnail — `src/gui/main_window_menu_builder.py:339` | DOC-05 | document | Clickable window-slot map on navigator. | [USER_GUIDE_LAYOUTS.md](../user-docs/USER_GUIDE_LAYOUTS.md) — Series navigator | 2026-09-05 |
| TRIAGE-032 | Show/Hide Left Pane — `src/gui/main_window_menu_builder.py:307` | DOC-05 | document | View → Show/Hide Left Pane (persisted). | [USER_GUIDE_LAYOUTS.md](../user-docs/USER_GUIDE_LAYOUTS.md) — Side panes | 2026-09-05 |
| TRIAGE-033 | Show/Hide Right Pane — `src/gui/main_window_menu_builder.py:313` | DOC-05 | document | View → Show/Hide Right Pane (persisted). | [USER_GUIDE_LAYOUTS.md](../user-docs/USER_GUIDE_LAYOUTS.md) — Side panes | 2026-09-05 |
| TRIAGE-034 | Show/Hide Series Navigator — `src/gui/main_window_menu_builder.py:320` | DOC-05 | duplicate | Covered via **N** and layouts/shortcuts guides. | [USER_GUIDE_LAYOUTS.md](../user-docs/USER_GUIDE_LAYOUTS.md) — Series navigator | 2026-09-05 |

## Assessment and release debt

Add non-feature gaps here with the same fields when an assessment finds stale
claims, mirror drift, missing docstrings, broken support paths, or a required
assessment was waived. A `deferred` row must be revisited at the next relevant
assessment and cannot be silently carried forward.

TRIAGE-037 and TRIAGE-038 are the ledger's first `deferred` rows. Both record
audit scope that was previously deferred in prose only, which is exactly the
silent carry-forward this section forbids.

| ID | Signal / source | Inventory ID | Disposition | Required decision evidence / likely destination | Follow-up | Last reviewed |
| --- | --- | --- | --- | --- | --- | --- |
| TRIAGE-035 | Quick Start HTML omits 3-pane layouts / Magnify **G** / wrong shortcuts pointer | DOC-03 | document | Align `resources/help/quick_start_guide.html` with layouts + shortcuts guides. | [quick_start_guide.html](../resources/help/quick_start_guide.html); [doc-assessment-2026-09-05-111057.md](doc-assessments/doc-assessment-2026-09-05-111057.md) | 2026-09-05 |
| TRIAGE-036 | CONFIGURATION “Slice Position Lines” vs UI “Show Slice Location Lines” | DOC-04 | document | Rename/align terminology in CONFIGURATION Overlay Settings. | [CONFIGURATION.md](../user-docs/CONFIGURATION.md#view--overlay-settings) | 2026-09-05 |
| TRIAGE-037 | DOC-11 marked `Assessed` on evidence of code inspection only; the row's own recipe (exercise every Help action, verify resolved URL/offline path and anchor) was not executed | DOC-11 | deferred | **Narrowed 2026-09-06:** link-target resolution is now machine-verified by `tests/test_doc_urls_resolve.py` (every `user_doc_url()` filename exists under `user-docs/`; every Quick Start `{doc_*}` placeholder is substituted). What remains deferred is only launching the app and exercising each Help action in the running UI. | [DOCUMENTATION_WORKFLOW_AND_FRESHNESS_PLAN.md — Phase 2](plans/DOCUMENTATION_WORKFLOW_AND_FRESHNESS_PLAN.md#phase-2--complete-the-accuracy-audit) | 2026-09-06 |
| TRIAGE-038 | **Narrowed 2026-09-06:** slices 2b and 2c are complete, so 7 of the original 15 rows are now assessed. The 8 rows still at `Baseline` are exactly slice 2a, the user-facing set that needs a running UI: DOC-01, 06, 07, 08, 09, 10, 18, 19 | DOC-01, DOC-06, DOC-07, DOC-08, DOC-09, DOC-10, DOC-18, DOC-19 | deferred | Phase 1 audited a first slice by design, but no phase or trigger was assigned to clear the remainder, so the rows had no owner. Slices 2b and 2c landed in [`doc-assessment-2026-09-06-234253.md`](doc-assessments/doc-assessment-2026-09-06-234253.md). Slice 2a is all that remains: those rows require exercising fusion, MPR, 3D, annotations, anonymization, export, and pylinac QA in the running application. | [DOCUMENTATION_WORKFLOW_AND_FRESHNESS_PLAN.md — Phase 2](plans/DOCUMENTATION_WORKFLOW_AND_FRESHNESS_PLAN.md#phase-2--complete-the-accuracy-audit) | 2026-09-06 |
| TRIAGE-039 | `CHANGELOG.md` ends with five comparison links to tags `v0.1.0`, `v0.1.1`, `v0.1.2`, `v0.4.0` that do not exist; the repository has zero Git tags locally and on the remote, so every one 404s on GitHub | DOC-15 | deferred | Verified 2026-09-06: `git tag \| wc -l` → 0 and `git ls-remote --tags origin \| wc -l` → 0, while [`RELEASING.md`](RELEASING.md) steps 5–6 instruct annotated tagging. The documented release process has never been completed. Fixing this means either creating retroactive tags or removing the links — a release-policy decision for the maintainer, not a documentation edit. Same missing release boundary that blocks the release-assessment trigger. | [DOCUMENTATION_WORKFLOW_AND_FRESHNESS_PLAN.md — Enforcement gaps to build](plans/DOCUMENTATION_WORKFLOW_AND_FRESHNESS_PLAN.md#enforcement-gaps-to-build) (release-assessment assertion, blocked on tagging) | 2026-09-06 |
