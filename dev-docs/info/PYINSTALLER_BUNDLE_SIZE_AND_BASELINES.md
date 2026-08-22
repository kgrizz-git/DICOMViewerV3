# PyInstaller bundle size — baselines and per-OS measurement

**Last updated:** 2026-08-22

This note supports reproducible **size tracking** for **Windows**, **macOS**, and **Linux** outputs from `DICOMViewerV3.spec`, and explains how rough **“what if we did not exclude X?”** estimates work.

## macOS PySide6 slim flag — measured 0 MB (retired 2026-08-22, D1)

The historical **`PYINSTALLER_MACOS_SLIM`** flag gated macOS **PySide6 submodule excludes** (`MACOS_PYSIDE6_MODULE_EXCLUDES`: WebEngine, 3D, Quick, Multimedia, QtPdf, etc.). It was **retired (D1)** after a same-commit local A/B on macOS (arm64, 2026-08-21):

- `du -sk`: **1,178,268 KB for both** `DICOMViewerV3_standard.app` (`PYINSTALLER_MACOS_SLIM` unset) and `DICOMViewerV3_slim.app` (`=1`) — byte-identical, **0 MB saved**. The PyInstaller analysis logs differ only by hook ordering.
- Environment: **PyInstaller 6.22.2**, pyinstaller-hooks-contrib **2026.6**, **PySide6 6.11.2**, **Python 3.12.10**.
- **Why zero:** the app imports only QtCore/QtGui/QtWidgets/QtOpenGL + the matplotlib `qtagg` path; modern PyInstaller traces the import graph, so the excluded modules were never collected in either build. The earlier “200–500 MB” upper-bound estimates were conditional on analysis pulling them in — falsified for this dependency graph.
- **Conditionality:** this is a property of the *current* dependency graph. A future **pylinac/PySide6 bump** that starts importing an excluded module reverses it. Post-D1, detection relies on a human reading the `du` logs against the baseline table below — there is no automated CI tripwire.

**Authoritative method (now a one-shot measure, no flag):** On a Mac, build **`pyinstaller DICOMViewerV3.spec --clean --noconfirm`** and run **`du -sh dist/DICOMViewerV3.app`**; compare against the baseline row below after dependency upgrades. The earlier CI “macOS slim” checkbox job no longer exists.

**Matplotlib** and **PIL/Tk-related** excludes in **`scripts/pyinstaller_exclude_lists.py`** still apply on **all** platforms.

## Matplotlib / PIL excludes (all OSes)

Dropping **`MATPLOTLIB_BACKEND_AND_WRITER_EXCLUDES`** or **`PIL_TK_RELATED_EXCLUDES`** usually changes size by **smaller** amounts than WebEngine — often on the order of **~5–40 MB** total depending on what PyInstaller was already pulling, unless a path forces in Tk or a heavy backend. Again, an A/B `du` on your target OS is definitive.

## Per-OS: how to measure (local)

Run from the **project root** after `pyinstaller DICOMViewerV3.spec --clean --noconfirm` (with the venv activated; see **`AGENTS.md`**).

### Windows (PowerShell)

```powershell
Get-ChildItem -Recurse dist\DICOMViewerV3 | Measure-Object -Property Length -Sum
# Folder size (approximate):
(Get-ChildItem -Recurse dist\DICOMViewerV3 | Measure-Object -Property Length -Sum).Sum / 1MB
```

Or use Explorer **Properties** on `dist\DICOMViewerV3`.

### macOS (bash)

```bash
du -sh dist/DICOMViewerV3.app
du -sh dist/DICOMViewerV3.app/Contents/* | sort -h
```

See also **`scripts/report-macos-bundle-size.sh`** if present.

### Linux (one-folder layout)

```bash
du -sh dist/DICOMViewerV3
du -sh dist/DICOMViewerV3/* | sort -h
```

For **AppImage**, measure the `.AppImage` file:

```bash
ls -lh DICOMViewerV3-*-x86_64.AppImage
```

## CI estimates (each OS)

The **Build Executables** workflow (`.github/workflows/build.yml`) runs **`Log distribution sizes`** with **`du -sh`** on:

- **Windows:** `dist/DICOMViewerV3` and `DICOMViewerV3.exe`
- **macOS (matrix job):** `dist/DICOMViewerV3.app` plus drill-downs under `Contents/`, `MacOS/`, `Frameworks/`, and top-N under `Frameworks/` / `Resources/`
- **Linux:** `dist/DICOMViewerV3` folder and main binary

Open the job log for each matrix leg to record numbers into the table below. (The former macOS slim checkbox job no longer exists — the slim flag was retired 2026-08-22 after measuring 0 MB saved.)

## Baseline size table (maintainer-maintained)

Fill in after tagged builds or manual workflow runs. Use **git tag or SHA**, **runner image** if known (e.g. `macos-14`), and **PySide6 / PyInstaller** versions from the build log or `pip freeze`.

| Date | Git ref | OS | Output measured | Size | PySide6 | PyInstaller | Notes |
|------|---------|----|-----------------|------|---------|-------------|-------|
| 2026-08-21 | same commit (A/B, `tmp/build_test.sh`) | macOS | `dist/DICOMViewerV3.app` (standard) | 1,178,268 KB (du -sk) | 6.11.2 | 6.22.2 | Standard build (`PYINSTALLER_MACOS_SLIM` unset); Python 3.12.10; hooks-contrib 2026.6. |
| 2026-08-21 | same commit (A/B, `tmp/build_test.sh`) | macOS | `dist/DICOMViewerV3.app` (slim) | 1,178,268 KB (du -sk) | 6.11.2 | 6.22.2 | Slim build (`PYINSTALLER_MACOS_SLIM=1`) — **0 MB saved** vs standard; byte-identical. Flag retired 2026-08-22 (D1). |
| | | Windows | `dist/DICOMViewerV3/` folder | | | | Not measured in the 2026-08-21 A/B; record after next tagged/Windows build. |
| | | Linux | `dist/DICOMViewerV3/` or AppImage | | | | Not measured in the 2026-08-21 A/B; record after next tagged/Linux build. |

## Related docs

- **`dev-docs/info/BUILDING_EXECUTABLES.md`** — build steps and spec overview  
- **`dev-docs/info/GITHUB_ACTIONS_STORAGE_AND_BILLING.md`** — artifact GB-hours  
- **`dev-docs/info/CODE_SIGNING_AND_NOTARIZATION.md`** — macOS signing / notarization (plan for **Developer ID** when distributing outside the Mac App Store)  
- **`dev-docs/plans/completed/pyinstaller-bundle-size-macos-2026-04-09.md`** — original size-reduction plan  
