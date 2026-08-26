# README end-user polish plan

**Date:** 2026-08-20  
**Status:** Complete (follow-up gallery expansion 2026-08-25; fusion/slab shots still open in TO_DO)
**Last updated:** 2026-08-25
**Priority:** P3 (docs / first impression)  
**Branch suggestion:** `docs/readme-end-user-polish`  
**Related:** [`README.md`](../../README.md), [`user-docs/USER_GUIDE.md`](../../user-docs/USER_GUIDE.md), [`dev-docs/CONTRIBUTING.md`](../CONTRIBUTING.md), [`AGENTS.md`](../../AGENTS.md)

## Goal

Rewrite the top of [`README.md`](../../README.md) so a non-developer visitor understands what the app is and how to get started within about one screen. Keep it short. Put developer and contributor material later, or link out.

## Problem

The current README opens with a solid product blurb, then mixes packaged-release use, source launchers, venv commands, Python version notes, feature tables, project layout, and contributing pointers in one dense flow. Source-run details appear before many readers need them. Technical setup is useful, but it competes with the end-user path.

## Target shape (keep short)

Aim for roughly this order and length:

1. **Title + one short paragraph** — what it is, platforms, who it is for (local study review; not a PACS server pitch).
2. **Hero screenshot** — one primary product image near the top, constrained display width, short caption.
3. **Get the app** — packaged release first (download + Help → Quick Start / Documentation). One or two sentences only.
4. **What you can do** — compact capability list or small table (viewing, tools, export, optional QA). No dependency deep-dives.
5. **Feature gallery** (optional follow-up) — a small, captioned set of additional screenshots so distinct workflows are visible without turning the README into a second user guide. Prefer HTML width constraints over full-bleed assets.
6. **Docs for users** — links to user guide, configuration, changelog.
7. **Run from source** (later / secondary) — short “for developers and contributors” section: launcher names, link to `DEVELOPER_SETUP` / `CONTRIBUTING` for Python/venv detail instead of duplicating long install blocks.
8. **Contributing / project layout** — brief, at the bottom; point to `dev-docs/` rather than restating architecture.

> **Superseded (v1 polish, 2026-08-20):** the original draft capped README images at
> **1–2** and treated a multi-image gallery as a non-goal. That guidance applied
> to the first end-user rewrite only.

## Screenshots (human-owned)

Agents can wire Markdown and folder layout, but **capture, visual PHI review, and approved-media admission are human steps**. Do not invent or commit clinical-looking bitmaps without that review.

### Shipped set (2026-08-24 / 2026-08-25)

| Asset | Purpose |
| --- | --- |
| `mpr-roi-workspace.png` | Hero — multi-pane ROI / MPR / cine / tag sidebar |
| `three-dimensional-volume-rendering.png` | Optional 3D volume rendering |
| `annotation-customization.png` | ROI / measurement / annotation appearance settings |
| `pixel-histogram.png` | Pixel-value histogram with viewer chrome |
| `dicom-tag-editor.png` | Tag viewer / editor dialog |
| `export-dicom-tags.png` | Tag export dialog |
| `automated-qa-menu.png` | Automated ACR CT / MRI / NM QC (pylinac) menu |

Seven approved screenshots total (one hero + six gallery tiles), resized for
display and hash-pinned under `resources/readme-screenshots/`.

### Still open

- Fusion and slab / intensity-projection (AIP, MIP, MinIP) screenshots — tracked
  in [`TO_DO.md`](../TO_DO.md) (**README feature screenshots — fusion and
  slab/MIP**). Text already mentions those capabilities; images are the gap.

Rules (still in force):

- Use **wholly synthetic / QC-phantom studies** only. Never real patient pixels,
  real clinical studies, or burned-in identifiers. After human visual PHI
  review, record the approved asset hash in
  [`security/approved-media-sha256.json`](../../security/approved-media-sha256.json).
- Prefer a dark or light theme that matches current UI; crop chrome that adds noise.
- Draft locally under gitignored `resources/screenshots-ignored/` (or `tmp/`) until review is done.
- Before committing tracked images (e.g. under `resources/` or `docs/media/`), follow [`PHI_PII_REPOSITORY_GUARDRAILS.md`](../PHI_PII_REPOSITORY_GUARDRAILS.md): human visual review (+ OCR if useful), then update the approved-media manifest. A clean advisory scanner is not permission to update the manifest.
- Keep the gallery curated: each image must earn a distinct feature story;
  constrain display width; do not dump every candidate from a capture folder.

Checklist additions for screenshots:

- [x] Capture candidate PNG(s) locally (owner: human); keep drafts out of git until reviewed.
- [x] Confirm no PHI / PII / local paths / identifiable anatomy context in pixels or window chrome.
- [x] Choose final path + filenames; embed only after manifest update.
- [x] Add short alt text / captions in the README.
- [x] **2026-08-25 gallery expansion:** seven constrained-width screenshots in
      README (hero + feature gallery); hashes in approved-media manifest.
- [ ] Fusion + slab/MIP gallery shots (see TO_DO).

## Non-goals

- Expanding the README into a second user guide.
- Moving or rewriting the full user-docs tree in this pass.
- Changing launcher behavior (handled separately: prefer `.venv`).
- Marketing fluff, badges walls, or long technology-stack essays upfront.
- Animated media, or an unbounded screenshot dump.
- ~~A large screenshot gallery in v1 of this polish~~ — **superseded 2026-08-25**
  by the shipped seven-image hero + feature gallery (still curated, not open-ended).

## Principles

- End-user path first; contributor path second.
- Prefer links over paste-heavy install recipes in the README.
- One job per section; avoid repeating the same “how to run” in three places.
- Keep total length comparable to or shorter than today after polish.
- Preserve accurate facts (Python recommendation, launcher names, doc paths) when they move or shrink.

## Checklist

- [x] Inventory current README sections and mark each as keep-upfront / move-later / link-out / drop-as-redundant.
- [x] Draft a lean top half (product → packaged use → capabilities → user docs).
- [x] Collapse source-run guidance: keep launcher names and one “see developer setup” link; trim duplicated bash/PowerShell blocks or move them fully to `DEVELOPER_SETUP.md` if already covered there.
- [x] Confirm `DEVELOPER_SETUP.md` (or `CONTRIBUTING.md`) already holds the detailed install path before removing detail from the README.
- [x] Soften or relocate Requirements / project-layout / tech pointers so they do not interrupt the user path.
- [x] Place hero screenshot slot(s) in the draft layout (images may land in a follow-up commit after human capture/review).
- [x] Update any cross-links that assume the old section order (`AGENTS`, `dev-docs/README`, assessments) only if they cite README anchors or wording that changes.
- [x] Run `python scripts/check_user_docs_links.py` after edits (covers
      `user-docs/`, root `README.md`, and `dev-docs/README.md`).
- [x] Changelog entry (docs-only; patch note) when the rewrite lands.
- [x] **Human-reviewed screenshots:** initial synthetic multi-pane/MPR and 3D
      workflows (2026-08-24), then seven-image hero + feature gallery
      (2026-08-25); hashes in `security/approved-media-sha256.json` with
      concise alt text/captions. Fusion/slab shots remain open in TO_DO.

## Success criteria

- A clinician or local user can answer “what is this?” and “how do I open it?” without reading venv or repo-layout sections.
- A contributor still finds setup and architecture within one click from the README footer.
- The file does not grow; prefer a net reduction of upfront noise.

## Out of scope for the launcher PR

This plan is documentation follow-up. Do not block the `.venv` launcher alignment PR on completing this rewrite.
