# README end-user polish plan

**Date:** 2026-08-20  
**Status:** Draft — not started  
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
2. **Hero screenshot(s)** — one primary product image near the top (optional second for a key workflow). Keep the caption short; do not turn the README into a gallery.
3. **Get the app** — packaged release first (download + Help → Quick Start / Documentation). One or two sentences only.
4. **What you can do** — compact capability list or small table (viewing, tools, export, optional QA). No dependency deep-dives.
5. **Docs for users** — links to user guide, configuration, changelog.
6. **Run from source** (later / secondary) — short “for developers and contributors” section: launcher table, link to `DEVELOPER_SETUP` / `CONTRIBUTING` for Python/venv detail instead of duplicating long install blocks.
7. **Contributing / project layout** — brief, at the bottom; point to `dev-docs/` rather than restating architecture.

## Screenshots (human-owned)

Agents can wire Markdown and folder layout, but **capture, visual PHI review, and approved-media admission are human steps**. Do not invent or commit clinical-looking bitmaps without that review.

Suggested set (keep small):

| Asset | Purpose |
| --- | --- |
| Main viewer (1×1 or 2×2) | Primary README hero — study open, overlays readable, no clutter |
| Optional: MPR or fusion | One secondary image only if it earns its place |

Rules:

- Use **wholly synthetic / approved demo** studies only. Never real patient pixels or burned-in identifiers.
- Prefer a dark or light theme that matches current UI; crop chrome that adds noise.
- Draft locally under gitignored `resources/screenshots-ignored/` (or `tmp/`) until review is done.
- Before committing tracked images (e.g. under `resources/` or `docs/media/`), follow [`PHI_PII_REPOSITORY_GUARDRAILS.md`](../PHI_PII_REPOSITORY_GUARDRAILS.md): human visual review (+ OCR if useful), then update [`security/approved-media-sha256.json`](../../security/approved-media-sha256.json). A clean advisory scanner is not permission to update the manifest.
- Cap at **1–2** images in the README so the page stays short.

Checklist additions for screenshots:

- [ ] Capture candidate PNG(s) locally (owner: human); keep drafts out of git until reviewed.
- [ ] Confirm no PHI / PII / local paths / identifiable anatomy context in pixels or window chrome.
- [ ] Choose final path + filenames; embed only after manifest update.
- [ ] Add short alt text / captions in the README.

## Non-goals

- Expanding the README into a second user guide.
- Moving or rewriting the full user-docs tree in this pass.
- Changing launcher behavior (handled separately: prefer `.venv`).
- Marketing fluff, badges walls, or long technology-stack essays upfront.
- A large screenshot gallery or animated media in v1 of this polish.

## Principles

- End-user path first; contributor path second.
- Prefer links over paste-heavy install recipes in the README.
- One job per section; avoid repeating the same “how to run” in three places.
- Keep total length comparable to or shorter than today after polish.
- Preserve accurate facts (Python recommendation, launcher names, doc paths) when they move or shrink.

## Checklist

- [ ] Inventory current README sections and mark each as keep-upfront / move-later / link-out / drop-as-redundant.
- [ ] Draft a lean top half (product → packaged use → capabilities → user docs).
- [ ] Collapse source-run guidance: keep launcher names and one “see developer setup” link; trim duplicated bash/PowerShell blocks or move them fully to `DEVELOPER_SETUP.md` if already covered there.
- [ ] Confirm `DEVELOPER_SETUP.md` (or `CONTRIBUTING.md`) already holds the detailed install path before removing detail from the README.
- [ ] Soften or relocate Requirements / project-layout / tech pointers so they do not interrupt the user path.
- [ ] Place hero screenshot slot(s) in the draft layout (images may land in a follow-up commit after human capture/review).
- [ ] Update any cross-links that assume the old section order (`AGENTS`, `dev-docs/README`, assessments) only if they cite README anchors or wording that changes.
- [ ] Run `python scripts/check_user_docs_links.py` after edits (covers
      `user-docs/`, root `README.md`, and `dev-docs/README.md`).
- [ ] Changelog entry (docs-only; patch note) when the rewrite lands.

## Success criteria

- A clinician or local user can answer “what is this?” and “how do I open it?” without reading venv or repo-layout sections.
- A contributor still finds setup and architecture within one click from the README footer.
- The file does not grow; prefer a net reduction of upfront noise.

## Out of scope for the launcher PR

This plan is documentation follow-up. Do not block the `.venv` launcher alignment PR on completing this rewrite.
