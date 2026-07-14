# Plan: PyInstaller macOS `.app` bundle size reduction — **completed (primary delivery)**

**Status:** Moved to `dev-docs/plans/completed/` on 2026-04-09. Core spec, CI, docs, and automated import audit are in place. Optional follow-ups (Qt plugin narrowing, hooks, retention tuning) remain below.

## Goal and success criteria (met for shipped scope)

- **Measure** the macOS `dist/DICOMViewerV3.app` bundle in CI via **`du`** (drill-down under `Contents/`, `MacOS/`, `Frameworks/`).
- Apply **safe** PyInstaller `excludes` (matplotlib non-Qt backends + file writers; **darwin + `PYINSTALLER_MACOS_SLIM`** large PySide6 trims — **default off**) without breaking histogram (**`backend_qtagg`**), DICOM codecs, or Qt UI.
- **UPX off on macOS** for codesign/notarization compatibility.
- CI uploads **`dist/`** + AppImage only — **no** PyInstaller **`build/`** artifacts (saves GB-hours; debug locally).

## Automated guard (post-plan)

- **`scripts/pyinstaller_exclude_lists.py`** — single source for matplotlib backend/writer excludes, PIL/Tk-related excludes, and macOS-only PySide6 module excludes; **`DICOMViewerV3.spec`** imports these tuples.
- **`tests/test_pyinstaller_exclude_audit.py`** — AST scan of **`src/`** and **`tests/`**: fails if any excluded `matplotlib.backends.*` or trimmed **`PySide6.*`** module is imported. Run with normal pytest / CI test job.
- **Does not catch:** dynamic imports (`importlib`, `__import__`), string-driven `matplotlib.use(...)`, or third-party wheels (e.g. pylinac) importing excluded Qt — **macOS smoke** on `.app` still recommended after dependency upgrades.

### If we stopped excluding — how much bigger? (macOS PySide6 list only)

**Scope:** **`MACOS_PYSIDE6_MODULE_EXCLUDES`** applies **only on macOS**. **Matplotlib** and **PIL/Tk** excludes apply on **Windows/Linux/macOS** (see **`scripts/pyinstaller_exclude_lists.py`**).

**Reality:** PyInstaller only bundles what analysis pulls. If nothing in the graph imports WebEngine (etc.), removing excludes might add **~0 MB**. If analysis **would** ship those Qt subsystems, **not** excluding them often adds **on the order of ~200–500 MB** to the `.app` (disk, uncompressed), with **Qt WebEngine** usually the dominant chunk (**~150–350 MB** typical order of magnitude). Smaller modules (Multimedia, 3D, Charts, QML, Pdf, Sql, serial, …) add **tens of MB** each in rough terms.

**Definitive check:** Same commit, two macOS builds: **`PYINSTALLER_MACOS_SLIM`** unset vs **`=1`**; compare **`du -sh dist/DICOMViewerV3.app`**. See **`dev-docs/info/PYINSTALLER_BUNDLE_SIZE_AND_BASELINES.md`** for a breakdown table and maintainer baseline template.

## Update (post-plan): `PYINSTALLER_MACOS_SLIM` + CI

- **`DICOMViewerV3.spec`:** macOS PySide6 submodule list applies only when **`PYINSTALLER_MACOS_SLIM`** is truthy; CI matrix macOS job keeps slim **off**; optional **`workflow_dispatch`** job produces **`DICOMViewerV3-macOS-slim`**.

## Maintainer decisions (recorded)

1. **Apple Developer ID / notarization:** Not enrolled yet; **plan to** use **Developer ID Application** for distribution outside the Mac App Store. Until then, local `.app` testing is fine; keep **`USE_UPX = not IS_DARWIN`** and follow **`dev-docs/info/CODE_SIGNING_AND_NOTARIZATION.md`** when certificates exist.
2. **Upload `build/` from CI:** **No** — workflow does **not** upload PyInstaller **`build/`** (no failed-job exception). Reproduce PyInstaller analysis problems on a dev machine.
3. **Baseline size table:** **`dev-docs/info/PYINSTALLER_BUNDLE_SIZE_AND_BASELINES.md`** — per-OS **`du`** / PowerShell commands, CI log pointers, and an empty table to fill after releases.

## Context and links

| Path | Notes |
|------|--------|
| [`DICOMViewerV3.spec`](../../../DICOMViewerV3.spec) | `IS_DARWIN` / `USE_UPX`; **`PYINSTALLER_MACOS_SLIM`** gates macOS PySide6 excludes; `hiddenimports` include **`matplotlib.backends.backend_qtagg`**. |
| [`scripts/pyinstaller_exclude_lists.py`](../../../scripts/pyinstaller_exclude_lists.py) | Shared exclude lists. |
| [`tests/test_pyinstaller_exclude_audit.py`](../../../tests/test_pyinstaller_exclude_audit.py) | Import audit tests. |
| [`dev-docs/info/PYINSTALLER_BUNDLE_SIZE_AND_BASELINES.md`](../info/PYINSTALLER_BUNDLE_SIZE_AND_BASELINES.md) | Size estimates, per-OS measurement, baseline table. |
| [`dev-docs/info/BUILDING_EXECUTABLES.md`](../info/BUILDING_EXECUTABLES.md) | Build steps, spec overview. |
| [`dev-docs/info/CODE_SIGNING_AND_NOTARIZATION.md`](../info/CODE_SIGNING_AND_NOTARIZATION.md) | macOS signing / notarization. |
| [`dev-docs/info/GITHUB_ACTIONS_STORAGE_AND_BILLING.md`](../info/GITHUB_ACTIONS_STORAGE_AND_BILLING.md) | Artifact GB-hours. |
| [`.github/workflows/build.yml`](../../../.github/workflows/build.yml) | Matrix build; size logging; **dist/** + AppImage artifacts only. |

## Phase checklist (delivered vs follow-up)

### Phase 1 — Measure and baseline

- [x] CI **`du`** on macOS `.app` and drill-down (`Contents/*`, `MacOS/*`, `Frameworks/*`).
- [x] **Optional (2026-04-09 coder):** `scripts/report-macos-bundle-size.sh` + CI **top 10** under `Frameworks/` and `Resources/` (`sort -hr | head -10`); copy-paste **`du`** commands in `BUILDING_EXECUTABLES.md` and **`PYINSTALLER_BUNDLE_SIZE_AND_BASELINES.md`**.
- [ ] **Optional:** Maintainer fills baseline rows in **`dev-docs/info/PYINSTALLER_BUNDLE_SIZE_AND_BASELINES.md`** after the next tagged build.

### Phase 2 — Safe PyInstaller levers

- [x] Shared exclude lists + darwin-only PySide6 trims (verified no matching imports in `src/` / `tests/`).
- [x] Matplotlib: **`backend_qtagg`** in hiddenimports; excluded other backends and pdf/svg/ps/pgf/cairo writers (no `savefig` to those formats in `src/`).
- [x] PIL/Tk: explicit **`PIL_TK_RELATED_EXCLUDES`** + audit test.
- [ ] **Follow-up:** Narrow Qt **plugins** only with `du` evidence + feature tests.

### Phase 3 — UPX on macOS

- [x] `USE_UPX = not IS_DARWIN`; documented in `BUILDING_EXECUTABLES.md`.

### Phase 4 — Hooks / `collect_submodules`

- [ ] **Follow-up:** Optional experiments only after measured need.

### Phase 5 — CI artifacts

- [x] Upload: **`dist/`** + AppImage only; **no** `build/` upload (removed optional **`workflow_dispatch`** input).
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

---

**Plan closed for primary objectives;** track optional items in [`dev-docs/FUTURE_WORK_DETAIL_NOTES.md`](../FUTURE_WORK_DETAIL_NOTES.md) or a new issue if needed.

### Coder follow-up (2026-04-09)

- Extended **`Analysis.excludes`** test-package list (`pylinac.tests`, `imageio.tests`, `pandas.tests`) and macOS **`PySide6`** trims (**`QtPdf`**, **`QtPdfWidgets`**, **`QtVirtualKeyboard`**) plus **`matplotlib.backends.backend_qtcairo`** in **`scripts/pyinstaller_exclude_lists.py`**; re-ran **`tests/test_pyinstaller_exclude_audit.py`** and a full **`PyInstaller`** spec build on Windows where venv exists.

### Maintainer follow-up (2026-04-09)

- Documented **order-of-magnitude** “if macOS PySide6 excludes removed” in **`dev-docs/info/PYINSTALLER_BUNDLE_SIZE_AND_BASELINES.md`**; added baseline table + per-OS measurement; recorded **no `build/` CI upload**, **Developer ID planned**, baseline doc location. Removed optional **`build/`** artifact step from **`.github/workflows/build.yml`**.
