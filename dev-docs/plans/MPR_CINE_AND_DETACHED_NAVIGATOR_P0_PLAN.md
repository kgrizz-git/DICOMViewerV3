# P0 plan: MPR cine depth + detached MPR navigator / drag

**Created:** 2026-04-20  
**Tracks:** [`dev-docs/TO_DO.md`](../TO_DO.md) — Bugs lines 42–43 (MPR cine range; Clear Window + detached MPR drag).

## Context

- **Cine on MPR:** `CinePlayer._advance_frame` used DICOM slice-grouping while the slice navigator reported `MprResult.n_slices`, so playback stopped at the base series depth.
- **Detached MPR:** `update_mpr_navigator_thumbnail` cleared navigator key `-1` on every attached MPR refresh; `attach_floating_mpr` cleared `_detached_mpr_payload` before a confirmed install.

## Code touchpoints

- [`src/gui/cine_player.py`](../../src/gui/cine_player.py) — linear cine flag; `_advance_frame`; `start_playback` capability gate.
- [`src/core/cine_app_facade.py`](../../src/core/cine_app_facade.py) — MPR-aware `is_cine_capable`, frame UI, sync linear flag.
- [`src/core/mpr_navigator_thumbnail.py`](../../src/core/mpr_navigator_thumbnail.py) — stop clearing `-1` on attached thumbnail updates.
- [`src/core/mpr_controller.py`](../../src/core/mpr_controller.py) — transactional `attach_floating_mpr`; `_install_mpr_payload_at_subwindow` returns success; emit `mpr_activated` only on success; clear `-1` after successful attach.

---

## Master checklist

- [x] Investigation / root cause documented (this file + inline behavior)
- [x] Cine: MPR uses linear advancement for full `n_slices`; play enabled when `n_slices > 1`
- [x] Detached MPR: navigator `-1` preserved; attach clears payload only after successful install; `mpr_activated` only on success
- [x] Manual QA (developer): cine through MPR stack; Clear Window → drag reassignment; second MPR + detached coexistence
- [x] CHANGELOG + `dev-docs/TO_DO.md` lines 42–43 marked complete with link here

## Completion protocol

Mark each item `[x]` only when fully verified. If blocked, add a short note under the item (do not rename the goal).
