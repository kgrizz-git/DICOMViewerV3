# Plan: PyInstaller macOS `.app` bundle size reduction — **completed (primary delivery)**

**Status:** Moved to `dev-docs/plans/completed/` on 2026-04-09. Core spec, CI, docs, and automated import audit are in place. Optional follow-ups (baseline `du` table, Qt plugin narrowing, hooks, retention tuning) remain below.

## Goal and success criteria (met for shipped scope)

- **Measure** the macOS `dist/DICOMViewerV3.app` bundle in CI via **`du`** (drill-down under `Contents/`, `MacOS/`, `Frameworks/`).
- Apply **safe** PyInstaller `excludes` (matplotlib non-Qt backends + file writers; **darwin-only** large PySide6 trims) without breaking histogram (**`backend_qtagg`**), DICOM codecs, or Qt UI.
- **UPX off on macOS** for codesign/notarization compatibility.
- Default CI artifacts exclude huge **`build/`** unless **workflow_dispatch** opts in.

## Automated guard (post-plan)

- **`scripts/pyinstaller_exclude_lists.py`** — single source for matplotlib backend/writer excludes and macOS PySide6 module excludes; **`DICOMViewerV3.spec`** imports these tuples.
- **`tests/test_pyinstaller_exclude_audit.py`** — AST scan of **`src/`** and **`tests/`**: fails if any excluded `matplotlib.backends.*` or trimmed **`PySide6.*`** module is imported. Run with normal pytest / CI test job.
- **Does not catch:** dynamic imports (`importlib`, `__import__`), string-driven `matplotlib.use(...)`, or third-party wheels (e.g. pylinac) importing excluded Qt — **macOS smoke** on `.app` still recommended after dependency upgrades.

## Context and links

| Path | Notes |
|------|--------|
| [`DICOMViewerV3.spec`](../../../DICOMViewerV3.spec) | `IS_DARWIN` / `USE_UPX`; excludes from `pyinstaller_exclude_lists`; `hiddenimports` include **`matplotlib.backends.backend_qtagg`**. |
| [`scripts/pyinstaller_exclude_lists.py`](../../../scripts/pyinstaller_exclude_lists.py) | Shared exclude lists. |
| [`tests/test_pyinstaller_exclude_audit.py`](../../../tests/test_pyinstaller_exclude_audit.py) | Import audit tests. |
| [`dev-docs/info/BUILDING_EXECUTABLES.md`](../info/BUILDING_EXECUTABLES.md) | Build steps, spec overview, optional `build/` upload. |
| [`dev-docs/info/CODE_SIGNING_AND_NOTARIZATION.md`](../info/CODE_SIGNING_AND_NOTARIZATION.md) | macOS signing / notarization. |
| [`dev-docs/info/GITHUB_ACTIONS_STORAGE_AND_BILLING.md`](../info/GITHUB_ACTIONS_STORAGE_AND_BILLING.md) | Artifact GB-hours. |
| [`.github/workflows/build.yml`](../../../.github/workflows/build.yml) | Matrix build; size logging; gated `build/` artifact. |

## Phase checklist (delivered vs follow-up)

### Phase 1 — Measure and baseline

- [x] CI **`du`** on macOS `.app` and drill-down (`Contents/*`, `MacOS/*`, `Frameworks/*`).
- [x] **Optional (2026-04-09 coder):** `scripts/report-macos-bundle-size.sh` + CI **top 10** under `Frameworks/` and `Resources/` (`sort -hr | head -10`); copy-paste **`du`** commands in `BUILDING_EXECUTABLES.md`.
- [ ] **Optional:** Maintainer records a baseline row (date, ref, `du -sh` total) in release notes or `BUILDING_EXECUTABLES.md`.

### Phase 2 — Safe PyInstaller levers

- [x] Shared exclude lists + darwin-only PySide6 trims (verified no matching imports in `src/` / `tests/`).
- [x] Matplotlib: **`backend_qtagg`** in hiddenimports; excluded other backends and pdf/svg/ps/pgf/cairo writers (no `savefig` to those formats in `src/`).
- [x] PIL/Tk: no Tk hiddenimports; explicit **`PIL_TK_RELATED_EXCLUDES`** (`PIL.ImageTk`, `PIL._tkinter_finder`) + audit test (`grep` / AST: no tk in `src/` or `tests/`).
- [ ] **Follow-up:** Narrow Qt **plugins** only with `du` evidence + feature tests.

### Phase 3 — UPX on macOS

- [x] `USE_UPX = not IS_DARWIN`; documented in `BUILDING_EXECUTABLES.md`.

### Phase 4 — Hooks / `collect_submodules`

- [ ] **Follow-up:** Optional experiments only after measured need.

### Phase 5 — CI artifacts

- [x] Default upload: `dist/` + AppImage; **`build/`** only when **workflow_dispatch** `upload_build_folder`.
- [ ] **Follow-up:** Revisit **`retention-days: 90`** vs billing doc if needed.

## Import audit summary (manual verification 2026-04-09)

- **Histogram:** `src/tools/histogram_widget.py` uses **`matplotlib.backends.backend_qtagg`** only (`FigureCanvasQTAgg`).
- **Matplotlib PDF/SVG/etc.:** No `savefig`, no `backend_pdf` / `backend_svg` imports in `src/`; QA PDFs use **pylinac** / **pypdf**, not matplotlib writers.
- **Excluded PySide6:** No matches in `src/` or `tests/` for WebEngine, Multimedia, Sql, Charts, 3D, Quick/QML, etc.
- **Tk / PIL.ImageTk:** Not used in `src/`.

## Risks (unchanged)

| Risk | Mitigation |
|------|------------|
| Aggressive `excludes` | Import audit test + macOS smoke after upgrades. |
| Third-party imports excluded Qt | Manual `.app` smoke; watch pylinac/PySide upgrades. |
| Dynamic matplotlib backend | Avoid `matplotlib.use('pdf')` etc. without removing excludes. |

## Questions for user (non-blocking for closure)

1. Notarized macOS every release? (Affects how strict to stay on UPX/packing.)
2. Upload **`build/`** automatically on **failed** jobs only?
3. Long-term home for **baseline size** table?

---

**Plan closed for primary objectives;** track optional items in [`dev-docs/FUTURE_WORK_DETAIL_NOTES.md`](../FUTURE_WORK_DETAIL_NOTES.md) or a new issue if needed.

### Coder follow-up (2026-04-09)

- Extended **`Analysis.excludes`** test-package list (`pylinac.tests`, `imageio.tests`, `pandas.tests`) and macOS **`PySide6`** trims (**`QtPdf`**, **`QtPdfWidgets`**, **`QtVirtualKeyboard`**) plus **`matplotlib.backends.backend_qtcairo`** in **`scripts/pyinstaller_exclude_lists.py`**; re-ran **`tests/test_pyinstaller_exclude_audit.py`** and a full **`PyInstaller`** spec build on Windows where venv exists.
