# DICOM Viewer V3

Cross-platform DICOM viewer for **Windows**, **macOS**, and **Linux**.

## Overview

View DICOM studies with **multi-window layouts**, **window/level**, **cine**, **MPR**, **image fusion** (PET/SPECT on CT/MR), **ROIs**, **measurements**, **annotations**, **metadata** viewing and editing, **export**, and optional **ACR phantom QA** (pylinac). See **[CHANGELOG.md](CHANGELOG.md)** for release notes.

## Documentation

- **In the app:** **Help → Quick Start Guide** — short onboarding, **table of contents**, and links that open full guides in your **browser** (GitHub).
- **Help → Documentation** — opens the **[user guide hub](user-docs/USER_GUIDE.md)** in your browser.
- **In this repo:** Topic guides under **[user-docs/](user-docs/)** (MPR, pylinac QA, image fusion, etc.).

## Requirements

- **Python 3.9+**. On **Windows**, **Python 3.11 or 3.12** is recommended so dependencies such as **pyjpegls** install from pre-built wheels. Very new versions (e.g. **3.14+**) may require building native extensions. Details: **[requirements.txt](requirements.txt)** and **[AGENTS.md](AGENTS.md)**.

## Technology stack (summary)

- **GUI:** PySide6 · **DICOM:** pydicom · **Arrays / imaging:** NumPy, Pillow · **Histogram:** matplotlib · **Tag export (Excel / CSV / UTF-8 text):** openpyxl (`*.xlsx`); CSV and tab-separated `*.txt` use the standard library · **Fusion 3D resampling:** SimpleITK · **ACR QA:** **pylinac 3.42.0** (exact pin), scipy, scikit-image · **Compare PDF merge:** pypdf · **Cine export (GIF/AVI/MPG):** imageio + imageio-ffmpeg (ships a **FFmpeg** build — **LGPL/GPL** components; review license implications for **redistributed** / **frozen** bundles)  
- **Optional (compressed DICOM):** pylibjpeg, pyjpegls, pylibjpeg-libjpeg — see `requirements.txt`.

## Project structure

```
DICOMViewerV3/
├── src/              # Application source
├── tests/            # Test suite — see tests/README.md
├── user-docs/        # User-facing Markdown guides (hub: USER_GUIDE.md)
├── dev-docs/         # Developer docs, plans, releasing, research
├── resources/        # Bundled help HTML, Qt styles (themes)
├── scripts/          # Helper scripts (e.g. TruffleHog install)
└── .github/          # CI workflows
```

## Installation

### Get the code

- **ZIP:** [GitHub — DICOMViewerV3](https://github.com/kgrizz-git/DICOMViewerV3) → **Code** → **Download ZIP** → extract.  
- **Git:** `git clone https://github.com/kgrizz-git/DICOMViewerV3.git` then `cd DICOMViewerV3`.

### Dependencies

From the **project root** (folder containing `requirements.txt` and `src/`):

```bash
pip install -r requirements.txt
```

Using a **virtual environment** is recommended (`python -m venv .venv`, then activate — see **[AGENTS.md](AGENTS.md)**). On Windows, **`launch.bat`** picks the first existing env among `venv`, `.venv`, `env`, and `virtualenv`.

### Run the application

```bash
python src/main.py
```

or:

```bash
python -m src.main
```

## Contributing / development

- **[AGENTS.md](AGENTS.md)** — venv, commands, `src/` layout, CI notes.  
- **[tests/README.md](tests/README.md)** — running tests.  
- **[dev-docs/DEVELOPER_SETUP.md](dev-docs/DEVELOPER_SETUP.md)** — troubleshooting installs and paths.

Optional contributor tooling: `requirements-dev.txt` and **[dev-docs/SECURITY_TOOLS_CLI_GUIDE.md](dev-docs/SECURITY_TOOLS_CLI_GUIDE.md)**.
