# Documentation improvement plan

**Plan ID / timestamp**: 2026-04-03-200500  
**Status**: Draft for implementation  
**Inputs**: [Documentation assessment](../doc-assessments/doc-assessment-2026-04-03-111903.md), [TO_DO.md § Documentation](../TO_DO.md#documentation) (lines 111–116), product goal: **in-app Quick Start with TOC and links**, **slimmer README** (no developer/test depth), **browser-accessible fuller docs**.

---

## 1. Goals

1. **End users** can open **Help** and get a **short Quick Start** with a clear **table of contents**, **in-document section links**, and **links that open fuller documentation in the system browser** (not only scrolling inside the dialog).
2. **README** stays **installer / first-run oriented**: what the app is, how to install, how to launch, where to get help, pointer to changelog/releases — **not** a duplicate of the full feature list or developer workflows.
3. **Developers / contributors** get tests, layout, CI, and deep technical notes in **`dev-docs/`** and/or **`tests/`**, cross-linked from **AGENTS.md** and optionally a single “contributor index.”
4. Close gaps called out in **TO_DO**: documentation audit cadence, Help/Documentation structure, **pylinac / automated QA** user-facing doc, **MPR** user-facing doc.

---

## 2. Current state (summary)

| Asset | Role today | Gap vs target |
|--------|------------|----------------|
| `README.md` | Very long feature list + install + **Running tests** + troubleshooting | Should shrink; tests/dev content belongs elsewhere; [assessment] wrong `docs/`/`data/` tree; stale test file list; duplicate Image Inversion bullet |
| `resources/help/quick_start_guide.html` | Large in-dialog guide with **TOC** and section `id`s; dialog has **Prev/Next section** and **Table of Contents** button | Too long for “quick start”; **no `http(s)` / file opens in browser** (`QTextBrowser` has external links disabled) |
| `src/gui/dialogs/quick_start_guide_dialog.py` | Loads HTML, theme tokens, search, section nav | Docstring still says content is in `_get_guide_content()` as body — wrong; should say **`resources/help/quick_start_guide.html`** ([assessment]) |
| `dev-docs/CODE_DOCUMENTATION.md` | Index of where help lives | **Out of date** for Quick Start path ([assessment]) |
| `dev-docs/info/PYLINAC_INTEGRATION_OVERVIEW.md` | Strong **developer** integration doc | Not framed as end-user “Tools → ACR…” workflow; TO_DO asks for explicit QA tool documentation |
| `dev-docs/plans/*` (e.g. MPR plans) | Implementation / roadmap | Not consolidated as **user** “how to use MPR” |
| `user-docs/IMAGE_FUSION_TECHNICAL_DOCUMENTATION.md` + `resources/help/fusion_technical_doc.html` | Fusion deep dive (md + in-app HTML) | Good pattern to mirror for other topics |

---

## 3. Recommended information architecture

### 3.1 Layers

| Layer | Audience | Format / delivery |
|-------|----------|-------------------|
| **A. Quick Start** | All users | **Short** `resources/help/quick_start_guide.html` — TOC + anchors + “More in browser” links |
| **B. User guide (full)** | Users who want depth | **Markdown in repo** under `user-docs/` (versioned with releases), e.g. `user-docs/USER_GUIDE.md` (hub) + topic files (`USER_GUIDE_MPR.md`, `USER_GUIDE_QA_PYLINAC.md`, …). Optional later: static HTML export or GitHub Pages. |
| **C. Developer / contributor** | Contributors, CI | `AGENTS.md` + `dev-docs/` + `tests/README.md` |

### 3.2 “Open in browser” strategy (phased)

**Phase 1 (low ceremony)**  
- Add **stable `https://` links** from Quick Start to **GitHub-rendered** `user-docs/*.md` on the default public repo (`README.md` already references `https://github.com/kgrizz-git/DICOMViewerV3`).  
- In `quick_start_guide_dialog.py`, enable **external** link handling for `http`/`https` only (keep fragment navigation for in-document anchors).

**Phase 2 (offline / packaged builds)**  
- For PyInstaller/AppImage builds, either:  
  - bundle a **generated HTML** tree under `resources/help/docs/` and open `file:///...` via `QUrl.fromLocalFile`, or  
  - ship the same GitHub URLs if network is acceptable.  
- Decision recorded in `dev-docs/info/BUILDING_EXECUTABLES.md` when implemented.

**Phase 3 (optional)**  
- Sphinx / MkDocs / Read the Docs if multi-version published docs become a requirement (TO_DO explicitly mentioned these). Defer until Phase 1–2 traffic and maintenance cost are understood.

---

## 4. README restructuring (target outline)

**Keep (short)**  
- Title, one-paragraph overview  
- Requirements (Python version summary + link to `requirements.txt` / AGENTS for detail)  
- Install: venv + `pip install -r requirements.txt`  
- Run: `python src/main.py` (and `launch.bat` on Windows one-liner)  
- **Help**: “Use **Help → Quick Start Guide** in the app; full topics: `user-docs/` (links)”  
- Link to **CHANGELOG**, **License** (when finalized), **Contributing** → AGENTS + dev-docs  

**Move out**  
- **Running tests** → `tests/README.md` (new or expanded) + one line in README: “See `tests/README.md` and `AGENTS.md`.”  
- **Long troubleshooting for Python dev environment** → `dev-docs/DEVELOPER_SETUP.md` (new) or subsection of AGENTS  
- **Exhaustive feature list** → trim to **high-level bullets** + “See User Guide / Quick Start / CHANGELOG for details”  

**Fix (from assessment)**  
- **Project structure** diagram: real folders (`src/`, `tests/`, `dev-docs/`, `user-docs/`, `resources/`, `scripts/`, `.github/`, …) — no fictional `docs/` / `data/` unless you add them  
- Remove **duplicate** Image Inversion bullet if still present  
- Do **not** maintain a partial list of test modules in README — point to `tests/`

---

## 5. Quick Start HTML (content + UX)

1. **Shorten** `quick_start_guide.html`: onboarding-only sections (open files, layouts, navigate slices/series, W/L basics, privacy, where to find Tools, link out for ROI/MPR/QA/fusion/export).  
2. **Preserve** `<h2 id="table-of-contents">` and TOC `<ul>` pattern — `_extract_toc_sections()` in `quick_start_guide_dialog.py` depends on it.  
3. **Add** a top “**Full documentation (browser)**” list with `https://github.com/.../blob/.../user-docs/...` links (use **main** branch or tag strategy documented in plan completion notes).  
4. **Implement** browser open for external URLs in the dialog (see §6).  
5. Optional: second Help menu item **“User Guide (browser)”** opening `USER_GUIDE.md` on GitHub (single entry point).

---

## 6. Application / UI changes

| Change | Rationale |
|--------|-----------|
| **Help → Documentation** (new) or rename/clarify existing items | TO_DO: complete Help entry; opens browser hub or local index |
| **`QuickStartGuideDialog`**: allow `http`/`https` in `_on_anchor_clicked` or via `QTextBrowser.setOpenExternalLinks(True)` with a filter | User requirement: click link → browser |
| **`main_window_menu_builder.py`**: wire new action(s) | Menu surface |
| **`dialog_coordinator.py`**: method to open documentation URL(s) | Keeps wiring out of `main.py` |
| **Security**: only allow `http`/`https` (and later vetted `file:` for bundled docs) | Avoid unexpected scheme handlers |

Reuse patterns from any existing “open URL” flows in the app (About, pylinac doc links) for consistency.

---

## 7. New / expanded documentation files (content)

| File | Purpose |
|------|---------|
| `user-docs/USER_GUIDE.md` | **Hub**: TOC linking to topic docs; how to use Help; version note |
| `user-docs/USER_GUIDE_MPR.md` | End-user MPR: how to open, navigate, limitations; link to `dev-docs/plans/SLICE_SYNC_AND_MPR_PLAN.md` only as “implementation detail” if needed |
| `user-docs/USER_GUIDE_QA_PYLINAC.md` | End-user: Tools → ACR CT / ACR MRI, inputs, JSON/PDF, compare mode, scan-extent tolerance — distill from `PYLINAC_INTEGRATION_OVERVIEW.md` |
| `tests/README.md` | How to run tests (`run_tests.py`, pytest, `PYTHONPATH`), layout of suites, no DICOM requirement where true |
| `dev-docs/DEVELOPER_SETUP.md` (optional) | Troubleshooting pip/venv/Windows wheels; Parallels path note — moved from README |

**Pylinac**: Keep `dev-docs/info/PYLINAC_INTEGRATION_OVERVIEW.md` as **source of truth for integration**; USER_GUIDE_QA is the **task-oriented** subset. Avoid duplicating long technical tables in both — link between them.

---

## 8. Documentation audit (recurring)

- Run [doc-assessment template](../templates-generalized/doc-assessment-template.md) **after** each release or major feature (MPR, QA, export).  
- Track in **TO_DO** or release checklist: “Quick Start + USER_GUIDE hub links still valid.”

---

## 9. Phased implementation checklist

### Phase A — Structure and README (high value, low risk)

- [ ] Add `tests/README.md` with test-running instructions (migrate text from README).  
- [ ] Slim `README.md` per §4; fix project tree; remove duplicate bullet; drop enumerated test list.  
- [ ] Add `user-docs/USER_GUIDE.md` hub (can start as stubs linking to existing `IMAGE_FUSION_TECHNICAL_DOCUMENTATION.md`).  
- [ ] Update `AGENTS.md` to point to `tests/README.md` and `user-docs/` hub if not already obvious.

### Phase B — In-app Quick Start + browser links

- [ ] Shorten `resources/help/quick_start_guide.html`; ensure TOC + ids; add “Full documentation” external links.  
- [ ] Update `quick_start_guide_dialog.py` for external HTTP(S) links + fix module docstring maintenance note.  
- [ ] Add **Help → Documentation** (or equivalent) in `main_window_menu_builder.py` + `dialog_coordinator.py`.  
- [ ] Update `dev-docs/CODE_DOCUMENTATION.md` Quick Start section to match HTML + dialog behavior.

### Phase C — TO_DO topics

- [ ] Author `user-docs/USER_GUIDE_QA_PYLINAC.md` (and link from hub + Quick Start).  
- [ ] Author `user-docs/USER_GUIDE_MPR.md` (and link from hub + Quick Start).  
- [ ] Optional: `dev-docs/DEVELOPER_SETUP.md` for moved README troubleshooting.

### Phase D — Packaged builds (when needed)

- [ ] Document and implement offline doc bundle + `file://` policy in `BUILDING_EXECUTABLES.md` / installer notes.

---

## 10. Files expected to be touched (implementation)

**User / repo docs**  
- `README.md`  
- `CHANGELOG.md` (user-visible doc reorg when shipped)  
- `user-docs/USER_GUIDE.md` (**new**)  
- `user-docs/USER_GUIDE_MPR.md` (**new**)  
- `user-docs/USER_GUIDE_QA_PYLINAC.md` (**new**)  
- `tests/README.md` (**new** or **expand**)  
- `dev-docs/DEVELOPER_SETUP.md` (**new**, optional)  
- `dev-docs/CODE_DOCUMENTATION.md`  
- `dev-docs/TO_DO.md` (check off or link to this plan when phases complete)  
- `AGENTS.md` (cross-links only if needed)

**Bundled help**  
- `resources/help/quick_start_guide.html`  
- Optionally later: `resources/help/docs/**` (Phase D static HTML)

**Application code**  
- `src/gui/dialogs/quick_start_guide_dialog.py`  
- `src/gui/dialog_coordinator.py`  
- `src/gui/main_window_menu_builder.py`  
- `src/core/app_signal_wiring.py` (if new signals to `main` or coordinator)  
- `src/main.py` (only if a thin delegate is required; prefer coordinator)

**Tests**  
- `tests/smoke/test_refactor_regression.py` (if paths or menu strings asserted)  
- New/updated tests for “external link opens” only if you add testable seams (optional)

**Existing reference docs (edit lightly)**  
- `dev-docs/info/PYLINAC_INTEGRATION_OVERVIEW.md` (add pointer to `user-docs/USER_GUIDE_QA_PYLINAC.md` at top)  
- `user-docs/IMAGE_FUSION_TECHNICAL_DOCUMENTATION.md` (link to `USER_GUIDE.md` hub)

---

## 11. Acceptance criteria

1. **Help → Quick Start** shows a **TOC** with working **in-page** section navigation (existing behavior preserved or improved).  
2. At least one **https** link in Quick Start opens the **system default browser** to the **user-docs** hub or a topic page.  
3. **README** does not contain the full “Running tests” section body — it points to **`tests/README.md`** (and AGENTS).  
4. **README** project structure matches the repository.  
5. **`CODE_DOCUMENTATION.md`** correctly states that Quick Start body is maintained in **`resources/help/quick_start_guide.html`**.  
6. **`USER_GUIDE_QA_PYLINAC.md`** and **`USER_GUIDE_MPR.md`** exist and are linked from the hub and Quick Start.  
7. Documentation audit (template) re-run records fewer README/HTML index mismatches.

---

## 12. Risks and mitigations

| Risk | Mitigation |
|------|------------|
| GitHub URLs break for forks/private remotes | Prefer relative “open repo root” doc or configurable docs base URL in config (future); Phase 1 can document “upstream links” |
| QTextBrowser HTML vs browser rendering differ | Keep Quick Start HTML simple; put complex tables in `user-docs` Markdown on GitHub |
| Duplicate maintenance (HTML + Markdown) | Quick Start = short; single source of depth = `user-docs`; changelog entry when user-visible behavior changes |

---

## 13. References

- [doc-assessment-2026-04-03-111903.md](../doc-assessments/doc-assessment-2026-04-03-111903.md)  
- [TO_DO.md — Documentation](../TO_DO.md#documentation)  
- [PYLINAC_INTEGRATION_OVERVIEW.md](../info/PYLINAC_INTEGRATION_OVERVIEW.md)  
- [BUILDING_EXECUTABLES.md](../info/BUILDING_EXECUTABLES.md) (packaged doc strategy)
