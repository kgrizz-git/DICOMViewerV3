# PyInstaller bundle size — baselines and per-OS measurement

This note supports reproducible **size tracking** for **Windows**, **macOS**, and **Linux** outputs from `DICOMViewerV3.spec`, and explains how rough **“what if we did not exclude X?”** estimates work.

## Single flag: `PYINSTALLER_MACOS_SLIM` (where it is set)

**One environment variable** turns macOS **PySide6 submodule excludes** on or off. It is defined and read in **`DICOMViewerV3.spec`** (not in GitHub’s UI by name — CI passes it into the process environment).

| Where | How slim is controlled |
|-------|-------------------------|
| **Local macOS shell** | Export or prefix: `PYINSTALLER_MACOS_SLIM=1 pyinstaller DICOMViewerV3.spec --clean --noconfirm`. Omit or use `0` / `false` for **off** (default). |
| **GitHub Actions — main matrix** | **`.github/workflows/build.yml`** sets **`PYINSTALLER_MACOS_SLIM`** to **`false`** (string) on the **macOS** matrix row and empty on Windows/Linux → **slim off** for **tag pushes** and default manual runs. |
| **GitHub Actions — optional second job** | Manual **Run workflow** only: checkbox **Also run a second macOS build with PYINSTALLER_MACOS_SLIM=1** → job **`macOS slim (PYINSTALLER_MACOS_SLIM=1)`** runs with **`PYINSTALLER_MACOS_SLIM=true`** → artifact **`DICOMViewerV3-macOS-slim`**. **Unchecked** → that job is **skipped** (no extra macOS slim build). |

**Disabling slim on GitHub:** Do **not** check the optional checkbox; tag-triggered builds never use slim. There is no separate “disable” beyond leaving slim **off** (default).

**Matplotlib** and **PIL/Tk-related** excludes in **`scripts/pyinstaller_exclude_lists.py`** still apply on **all** platforms regardless of **`PYINSTALLER_MACOS_SLIM`**.

## When are large PySide6 modules excluded on macOS?

**`MACOS_PYSIDE6_MODULE_EXCLUDES`** is applied only when **`sys.platform == "darwin"`** and **`PYINSTALLER_MACOS_SLIM`** is truthy (`1`, `true`, `yes`, `on`). Otherwise those names are **not** added to **`Analysis.excludes`**.

## Order-of-magnitude: macOS PySide6 trims (`MACOS_PYSIDE6_MODULE_EXCLUDES`)

PyInstaller only ships what its dependency analysis **collects**. If the app never imports a module, excludes may change **little or nothing**. If analysis **would** pull in optional Qt wheels (or a dependency starts importing them), **not** excluding can add a **large** amount on disk.

Very rough **upper-bound** intuition if those Qt subsystems **did** get bundled on macOS (Qt 6 / PySide6 era, uncompressed on disk):

| Area | Typical magnitude (order of magnitude) |
|------|----------------------------------------|
| **Qt WebEngine** (Core + Widgets + Quick) | Often **~150–350 MB** — usually the largest single chunk |
| **Qt Multimedia** (+ widgets) | **~15–50 MB** |
| **Qt 3D** (several modules) | **~25–80 MB** |
| **Qt Charts / DataVisualization** | **~10–35 MB** |
| **Qt Quick / QML / QuickWidgets** | **~15–60 MB** (more if combined with WebEngineQuick) |
| **Qt Pdf / PdfWidgets**, **VirtualKeyboard** | **~10–40 MB** |
| **Sql, Serial*, Bluetooth, Nfc, Positioning, Location** | **~5–25 MB** combined |

**Combined ballpark** if everything in **`MACOS_PYSIDE6_MODULE_EXCLUDES`** were actually present in the `.app`: often **~200–500 MB** extra vs a lean QtWidgets-focused bundle — **high variance** by PySide6 version, PyInstaller version, and whether WebEngine is pulled in at all.

**Authoritative method:** On a Mac, build twice from the same commit: **`PYINSTALLER_MACOS_SLIM`** unset vs **`PYINSTALLER_MACOS_SLIM=1`**; compare **`du -sh dist/DICOMViewerV3.app`**. In CI, run **Build Executables** manually with the **macOS slim** checkbox enabled and compare **`du`** in the **`DICOMViewerV3-macOS`** vs **`DICOMViewerV3-macOS-slim`** job logs.

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
- **macOS (default matrix job, slim off):** `dist/DICOMViewerV3.app` plus drill-downs under `Contents/`, `MacOS/`, `Frameworks/`, and top-N under `Frameworks/` / `Resources/`
- **macOS slim (optional job):** same paths; log section labeled **`macOS SLIM (PYINSTALLER_MACOS_SLIM=1)`**
- **Linux:** `dist/DICOMViewerV3` folder and main binary

Open the job log for each matrix leg (and the slim job if you ran it) to record numbers into the table below.

## Baseline size table (maintainer-maintained)

Fill in after tagged builds or manual workflow runs. Use **git tag or SHA**, **runner image** if known (e.g. `macos-14`), and **PySide6 / PyInstaller** versions from the build log or `pip freeze`.

| Date | Git ref | OS | Output measured | Size | PySide6 | PyInstaller | Notes |
|------|---------|----|-----------------|------|---------|-------------|-------|
| | | Windows | `dist/DICOMViewerV3/` folder | | | | |
| | | macOS | `dist/DICOMViewerV3.app` | | | | |
| | | Linux | `dist/DICOMViewerV3/` or AppImage | | | | |

## Related docs

- **`dev-docs/info/BUILDING_EXECUTABLES.md`** — build steps and spec overview  
- **`dev-docs/info/GITHUB_ACTIONS_STORAGE_AND_BILLING.md`** — artifact GB-hours  
- **`dev-docs/info/CODE_SIGNING_AND_NOTARIZATION.md`** — macOS signing / notarization (plan for **Developer ID** when distributing outside the Mac App Store)  
- **`dev-docs/plans/completed/pyinstaller-bundle-size-macos-2026-04-09.md`** — original size-reduction plan  
