# Documentation triage ledger

**Last updated:** 2026-09-04  
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

## Open feature-coverage baseline (2026-09-04)

Source: `python scripts/check_doc_feature_coverage.py` at revision `316552e`.
The script is a lower-bound heuristic: it extracts literal `QAction` labels and
does not certify behavior, shortcuts, non-QAction UI, or documentation
accuracy. All rows below are deliberately `pending-triage` until reviewed.

| ID | Signal / source | Inventory ID | Disposition | Required decision evidence / likely destination | Follow-up | Last reviewed |
| --- | --- | --- | --- | --- | --- | --- |
| TRIAGE-001 | Clear Cine Bounds — `src/gui/cine_controls_widget.py:335` | DOC-07 | pending-triage | Check cine bounds behavior and MPR/cine guide coverage. | [TO_DO Documentation](TO_DO.md#documentation) | 2026-09-04 |
| TRIAGE-002 | Decrease Font Size — `src/gui/main_window_menu_builder.py:417` | DOC-05 | pending-triage | Check visible scope, shortcut, persistence, and navigation/shortcuts docs. | [TO_DO Documentation](TO_DO.md#documentation) | 2026-09-04 |
| TRIAGE-003 | Direction Labels Color — `src/gui/main_window_menu_builder.py:463` | DOC-04 | pending-triage | Check setting name/default/persistence and configuration reference. | [TO_DO Documentation](TO_DO.md#documentation) | 2026-09-04 |
| TRIAGE-004 | Disclaimer — `src/gui/main_window_menu_builder.py:721` | DOC-12 | pending-triage | Check dialog content, route, and safety/support guidance. | [TO_DO Documentation](TO_DO.md#documentation) | 2026-09-04 |
| TRIAGE-005 | Edit Recent List — `src/gui/main_window_menu_builder.py:103` | DOC-05 | pending-triage | Check workflow and guide-hub discovery. | [TO_DO Documentation](TO_DO.md#documentation) | 2026-09-04 |
| TRIAGE-006 | Enable Slice Sync — `src/gui/main_window_menu_builder.py:523` | DOC-07 | pending-triage | Check MPR/sync behavior, scope, and labels. | [TO_DO Documentation](TO_DO.md#documentation) | 2026-09-04 |
| TRIAGE-007 | Enable/Disable — `src/gui/main_window_menu_builder.py:542` | DOC-07 | pending-triage | Identify controlled feature before deciding canonical destination. | [TO_DO Documentation](TO_DO.md#documentation) | 2026-09-04 |
| TRIAGE-008 | Exit — `src/gui/main_window_menu_builder.py:174` | DOC-02 | pending-triage | Decide whether standard application exit needs user-guide mention. | [TO_DO Documentation](TO_DO.md#documentation) | 2026-09-04 |
| TRIAGE-009 | Export Customizations — `src/gui/main_window_menu_builder.py:146` | DOC-04 | pending-triage | Check configuration export format, destination, and errors. | [TO_DO Documentation](TO_DO.md#documentation) | 2026-09-04 |
| TRIAGE-010 | Export Tag Presets — `src/gui/main_window_menu_builder.py:156` | DOC-10 | pending-triage | Check tag-preset export behavior and tag guide coverage. | [TO_DO Documentation](TO_DO.md#documentation) | 2026-09-04 |
| TRIAGE-011 | Import Customizations — `src/gui/main_window_menu_builder.py:150` | DOC-04 | pending-triage | Check configuration import merge/overwrite behavior and errors. | [TO_DO Documentation](TO_DO.md#documentation) | 2026-09-04 |
| TRIAGE-012 | Import Tag Presets — `src/gui/main_window_menu_builder.py:160` | DOC-10 | pending-triage | Check tag-preset import behavior and tag guide coverage. | [TO_DO Documentation](TO_DO.md#documentation) | 2026-09-04 |
| TRIAGE-013 | Increase Font Size — `src/gui/main_window_menu_builder.py:429` | DOC-05 | pending-triage | Check visible scope, shortcut, persistence, and navigation/shortcuts docs. | [TO_DO Documentation](TO_DO.md#documentation) | 2026-09-04 |
| TRIAGE-014 | Magnify — `src/gui/main_window_toolbar_builder.py:379` | DOC-02 | pending-triage | Check tool behavior and guide/Quick Start coverage. | [TO_DO Documentation](TO_DO.md#documentation) | 2026-09-04 |
| TRIAGE-015 | Manage Sync Groups — `src/gui/main_window_menu_builder.py:533` | DOC-07 | pending-triage | Check sync-group workflow and MPR guide coverage. | [TO_DO Documentation](TO_DO.md#documentation) | 2026-09-04 |
| TRIAGE-016 | Move Down — `src/gui/dialogs/edit_recent_list_dialog.py:297` | DOC-05 | pending-triage | Check recent-list workflow; may be subordinate to TRIAGE-005. | [TO_DO Documentation](TO_DO.md#documentation) | 2026-09-04 |
| TRIAGE-017 | Move Up — `src/gui/dialogs/edit_recent_list_dialog.py:290` | DOC-05 | pending-triage | Check recent-list workflow; may be subordinate to TRIAGE-005. | [TO_DO Documentation](TO_DO.md#documentation) | 2026-09-04 |
| TRIAGE-018 | No recent files — `src/gui/main_window_recent_files_manager.py:94` | DOC-05 | pending-triage | Determine whether empty-state text warrants user documentation. | [TO_DO Documentation](TO_DO.md#documentation) | 2026-09-04 |
| TRIAGE-019 | Only Show For Same Group — `src/gui/main_window_menu_builder.py:555` | DOC-07 | pending-triage | Check sync visibility semantics and MPR guide coverage. | [TO_DO Documentation](TO_DO.md#documentation) | 2026-09-04 |
| TRIAGE-020 | Remove This Item — `src/gui/dialogs/edit_recent_list_dialog.py:283` | DOC-05 | pending-triage | Check recent-list workflow; may be subordinate to TRIAGE-005. | [TO_DO Documentation](TO_DO.md#documentation) | 2026-09-04 |
| TRIAGE-021 | Rotate 180° — `src/gui/main_window_menu_builder.py:382` | DOC-02 | pending-triage | Check image-navigation behavior and guide coverage. | [TO_DO Documentation](TO_DO.md#documentation) | 2026-09-04 |
| TRIAGE-022 | Scale Markers Color — `src/gui/main_window_menu_builder.py:453` | DOC-04 | pending-triage | Check setting name/default/persistence and configuration reference. | [TO_DO Documentation](TO_DO.md#documentation) | 2026-09-04 |
| TRIAGE-023 | Set Cine End — `src/gui/cine_controls_widget.py:327` | DOC-07 | pending-triage | Check cine bounds behavior and MPR/cine guide coverage. | [TO_DO Documentation](TO_DO.md#documentation) | 2026-09-04 |
| TRIAGE-024 | Set Cine Start — `src/gui/cine_controls_widget.py:321` | DOC-07 | pending-triage | Check cine bounds behavior and MPR/cine guide coverage. | [TO_DO Documentation](TO_DO.md#documentation) | 2026-09-04 |
| TRIAGE-025 | Show Direction Labels — `src/gui/main_window_menu_builder.py:457` | DOC-04 | pending-triage | Check setting name/default/persistence and configuration reference. | [TO_DO Documentation](TO_DO.md#documentation) | 2026-09-04 |
| TRIAGE-026 | Show Instances Separately — `src/gui/main_window_menu_builder.py:350` | DOC-05 | pending-triage | Check navigation behavior and relevant guide coverage. | [TO_DO Documentation](TO_DO.md#documentation) | 2026-09-04 |
| TRIAGE-027 | Show Only For Focused Window — `src/gui/main_window_menu_builder.py:568` | DOC-07 | pending-triage | Check sync visibility semantics and MPR guide coverage. | [TO_DO Documentation](TO_DO.md#documentation) | 2026-09-04 |
| TRIAGE-028 | Show Scale Markers — `src/gui/main_window_menu_builder.py:447` | DOC-04 | pending-triage | Check setting name/default/persistence and configuration reference. | [TO_DO Documentation](TO_DO.md#documentation) | 2026-09-04 |
| TRIAGE-029 | Show Slab Boundaries (Begin/End) Instead of Centre — `src/gui/main_window_menu_builder.py:584` | DOC-07 | pending-triage | Check MPR projection behavior and terminology. | [TO_DO Documentation](TO_DO.md#documentation) | 2026-09-04 |
| TRIAGE-030 | Show Slice/Frame Count on Navigator Thumbnails — `src/gui/main_window_menu_builder.py:326` | DOC-05 | pending-triage | Check setting scope/default/persistence and navigation guide coverage. | [TO_DO Documentation](TO_DO.md#documentation) | 2026-09-04 |
| TRIAGE-031 | Show Window Assignment Thumbnail — `src/gui/main_window_menu_builder.py:339` | DOC-05 | pending-triage | Check navigation/layout behavior and guide coverage. | [TO_DO Documentation](TO_DO.md#documentation) | 2026-09-04 |
| TRIAGE-032 | Show/Hide Left Pane — `src/gui/main_window_menu_builder.py:307` | DOC-05 | pending-triage | Check pane behavior, menu/shortcut label, and layout guide coverage. | [TO_DO Documentation](TO_DO.md#documentation) | 2026-09-04 |
| TRIAGE-033 | Show/Hide Right Pane — `src/gui/main_window_menu_builder.py:313` | DOC-05 | pending-triage | Check pane behavior, menu/shortcut label, and layout guide coverage. | [TO_DO Documentation](TO_DO.md#documentation) | 2026-09-04 |
| TRIAGE-034 | Show/Hide Series Navigator — `src/gui/main_window_menu_builder.py:320` | DOC-05 | pending-triage | Check pane behavior, menu/shortcut label, and layout guide coverage. | [TO_DO Documentation](TO_DO.md#documentation) | 2026-09-04 |

## Assessment and release debt

Add non-feature gaps here with the same fields when an assessment finds stale
claims, mirror drift, missing docstrings, broken support paths, or a required
assessment was waived. A `deferred` row must be revisited at the next relevant
assessment and cannot be silently carried forward.
