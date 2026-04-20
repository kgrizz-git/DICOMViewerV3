# Documentation structure, completeness, and Quick Guide alignment

**Created:** 2026-04-20  
**Status:** In progress (Phases 1–4 partially implemented 2026-04-20)  
**Inputs:**

- [Documentation assessment — 2026-04-20](../../doc-assessments/doc-assessment-2026-04-20-002224.md) (findings + recommended architecture section)
- Existing user hub: [user-docs/USER_GUIDE.md](../../../user-docs/USER_GUIDE.md)
- In-app Quick Start: [resources/help/quick_start_guide.html](../../../resources/help/quick_start_guide.html)
- Doc URL wiring: [src/utils/doc_urls.py](../../../src/utils/doc_urls.py)

**Goal:** Separate **end-user** documentation (binary + from-source) from **developer** documentation; make docs **accurate**, **navigable**, and **discoverable**; align the bundled **Quick Guide** with the full hub and topic guides; close known **completeness** gaps (e.g. local study index, settings reference).

---

## Principles

1. **Code and UI strings are source of truth** for behavior; user docs describe what shipped.
2. **One primary place** for shortcuts and overlay semantics (avoid Quick Start vs hub drift).
3. **README** stays a short billboard; depth lives under `user-docs/` and `dev-docs/`.
4. **Plans** under `dev-docs/plans/` are not substitutes for user-facing guides—link with an “Advanced” label only when useful.

---

## Phase 1 — Information architecture (no large prose rewrites)

**Objective:** Clear entry points and indexes so audiences do not mix.

- [x] **README.md** — Add an explicit two-link pattern at the top of the “Documentation” area: **User documentation** → `user-docs/USER_GUIDE.md`; **Developer documentation** → `AGENTS.md` + `dev-docs/DEVELOPER_SETUP.md`. Keep binary vs source distinctions in short sub-bullets if both are supported publicly.
- [x] **USER_GUIDE.md hub** — Add a one-line orientation row: Quick Start (in-app) | This hub | Changelog | Issues (as applicable). Ensure the topics table remains the canonical map to MPR / QA / fusion docs.
- [x] **dev-docs/README.md** — Create a lightweight **developer index** (setup, releasing, security, plans, info/, assessments) with **no** end-user workflow content. Link it from `AGENTS.md` in one sentence if helpful.
- [x] **Optional: user-docs/README.md** — Only if GitHub folder browsing needs a landing page; otherwise skip to avoid duplication with `USER_GUIDE.md`.

**Verification:** A new reader can answer in 30 seconds: “Where do I read as a user?” vs “Where do I read as a contributor?”

---

## Phase 2 — Quick Guide (bundled HTML + parity with hub)

**Objective:** `quick_start_guide.html` hits all **major** features and shortcuts, then links to GitHub topic pages; wording matches the hub where topics overlap.

- [x] **Outline alignment** — Reconcile sections with the assessment’s Quick Guide TOC: opening data, layouts, W/L, privacy, overlays (**Space** / **Shift+Space** = same phrasing as [USER_GUIDE.md](../../../user-docs/USER_GUIDE.md)), tools (ROI / measure / annotations + key hints), MPR / fusion / QA (one short paragraph + link each), export & SR (menu paths), settings (high-level), shortcuts (compact table or top-N list + “full hub”).
- [x] **Placeholder links** — Confirm `{doc_*}` placeholders stay in sync with files listed in `QuickStartGuideDialog` / `doc_urls.py` when new topic MD files are added.
- [x] **Optional mirror** — Decide whether to add `user-docs/QUICK_GUIDE.md` (same outline as HTML for GitHub-only readers) **or** document in `dev-docs/RELEASING.md` that HTML and hub must both be updated when shortcuts/menus change (pick one maintenance strategy).

**Verification:** Spot-check 5 menu paths and 5 shortcuts against `src/` menu builders and keyboard handler; no contradiction between HTML and `USER_GUIDE.md` for overlay cycling.

---

## Phase 3 — Completeness: settings and local study index

**Objective:** User-visible settings and the **local study index** are documented for end users.

- [x] **Local study index** — Add a short subsection to `USER_GUIDE.md` (and optionally one README bullet): what it does, **Settings** location (“Local study index (encrypted)”), auto-add on open, DB path, privacy implications at a high level. Link to [LOCAL_STUDY_DATABASE_AND_INDEXING_PLAN.md](LOCAL_STUDY_DATABASE_AND_INDEXING_PLAN.md) as **background** only.
- [x] **Settings / configuration reference** — Add either:
  - **`user-docs/CONFIGURATION.md`** — Settings dialog groups in **UI order**, labels matching `settings_dialog.py` / related UI; defaults and effects in plain language; optional “config key” column for support, **or**
  - A major **“Settings reference”** section inside `USER_GUIDE.md` if you want a single file for users.
- [ ] **Cross-check** — Walk `src/utils/config/*` mixins and `settings_dialog.py` for groups not yet mentioned (incremental passes are OK; mark gaps with TODO comments in the plan checklist until closed).

**Verification:** Every **Settings** group name visible in the app has at least one sentence in user docs or an explicit “documented elsewhere” pointer.

---

## Phase 4 — Binary vs from-source and release-matched docs (maintainer policy)

**Objective:** Reduce confusion when `main` docs describe behavior newer than a frozen binary.

- [x] **dev-docs/RELEASING.md** (or **BUILDING_EXECUTABLES** companion) — Document a policy for `USER_DOCS_GITHUB_PREFIX` in [doc_urls.py](../../../src/utils/doc_urls.py): default **main** for living docs vs optional **tag/blob** URLs for release-specific doc sets when behavior diverges materially.
- [x] **User-facing note** — One sentence in `USER_GUIDE.md` (source/versioning section) that binaries may lag `main`; point to **CHANGELOG** and tagged releases.

**Verification:** A maintainer can answer: “Which URL should frozen build X ship in Help → Documentation?”

---

## Phase 5 — Quality gates (automation and cadence)

**Objective:** Catch link rot and force periodic review.

- [ ] **CI or local script** — Relative link check for `user-docs/*.md` (and key `dev-docs/` indexes you add). Optional: external URL check with allowlist.
- [ ] **Cadence** — Note in `RELEASING.md` or `AGENTS.md`: after each **minor** release (or large UI change), run [doc-assessment-template.md](../../templates-generalized/doc-assessment-template.md) → new timestamped file under `dev-docs/doc-assessments/`.

**Verification:** A deliberate broken relative link in a test branch fails the chosen check.

---

## Phase 6 — Developer doc boundaries (optional cleanup)

**Objective:** Keep `AGENTS.md` operational; avoid unbounded growth.

- [ ] If `AGENTS.md` exceeds comfort length, split **contributor / PR** prose into **`dev-docs/CONTRIBUTING.md`** and keep `AGENTS.md` focused on venv, commands, `src/` map, CI, agent rules.
- [ ] Ensure [CODE_DOCUMENTATION.md](../../CODE_DOCUMENTATION.md) continues to point to real help loaders and `resources/help/*.html` paths (regression guard after refactors).

**Verification:** New contributor path: README → AGENTS → dev-docs index → DEVELOPER_SETUP without hitting user-only tutorials.

---

## Dependencies and ordering

- Phases **1–2** can proceed in parallel with **3** (different files).
- **4** is mostly policy text; can land anytime after **1**.
- **5** depends on repo appetite for CI; lowest user-visible priority.
- **6** is optional until `AGENTS.md` grows unwieldy.

---

## Out of scope (track separately)

- Full **offline** doc bundle + `file://` policy — see `dev-docs/TO_DO.md` (Documentation → offline bundle item) and [BUILDING_EXECUTABLES.md](../../info/BUILDING_EXECUTABLES.md) when prioritized.
- Replacing the generic **“Conduct documentation audit”** TO_DO item: this plan **supersedes** ad-hoc audit intent for structure/completeness; keep a periodic re-assessment habit via Phase 5.

---

## Completion criteria (definition of done)

- [x] README clearly separates user vs developer entry points.
- [x] Quick Start HTML and `USER_GUIDE.md` agree on overlay / shortcut semantics for shared topics.
- [x] Local study index and settings surface documented for end users.
- [x] Maintainer policy recorded for doc URLs vs releases.
- [ ] Optional: link checker in CI; doc assessment run recorded after major doc pass.
