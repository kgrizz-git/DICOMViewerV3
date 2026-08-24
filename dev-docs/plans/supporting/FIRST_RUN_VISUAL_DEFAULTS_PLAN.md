# First-run visual defaults plan

**Status:** Complete
**Last updated:** 2026-08-24
**Related:** [active backlog](../TO_DO.md), [design specification](../../DESIGN.md), [README polish plan](../README_END_USER_POLISH_PLAN.md)

## Goal

Make a new installation more legible and immediately discoverable without
changing an existing user's chosen appearance. Pair that preference-only work
with splitter handles that are reliably targetable and a concise README
showcase of the approved synthetic-demo workflows.

## Scope

1. Fresh visual defaults: larger overlay/annotation text, medium-weight
   overlay type, scale markers and orientation labels on, red scale markers,
   violet accent, and icon-plus-label toolbar buttons.
2. Preserve values already stored in an existing configuration. The
   configuration loader overlays stored JSON onto defaults, so changing default
   values is sufficient: a previously saved value wins; a missing key gets the
   fresh default. Do not add an eager startup rewrite or reset preferences.
3. Make the Qt splitter's actual hit target 8 px (not merely its stylesheet
   appearance), while retaining a 1 px resting hairline and a visible hover
   affordance.
4. Add at most two human-approved, hash-pinned screenshots to the README:
   one multi-pane/MPR workflow and one 3D workflow.

## Verification

- Config tests cover fresh defaults, stored legacy values, and absent-key
  fallbacks.
- Qt tests cover the main splitter's actual 8 px handle width and scale-marker
  geometry.
- Run the focused UI/config tests, privacy gates, user-doc link checker,
  repository harness, agent smoke harness, and full pytest.
- Before tracking either image: perform the human-reviewed media check, add
  the final exact hashes to `security/approved-media-sha256.json`, and run the
  artifact gate. Do not use a local path or an unreviewed capture.

## Completion

Completed 2026-08-24. The overlapping first-run-default, scale-marker,
splitter, and 1280 px toolbar-fit items have been removed from `TO_DO.md`;
the broader UX and documentation backlog remains open.
