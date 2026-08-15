# DICOM Viewer V3

> A cross-platform desktop DICOM viewer for reviewing studies, measurements,
> reconstructions, exports, and selected automated QA workflows.

DICOM Viewer V3 runs on Windows, macOS, and Linux. It is designed for local
study review, with multi-window viewing, window/level controls, cine playback,
MPR, PET/SPECT fusion, ROI and measurement tools, annotations, metadata
inspection and editing, image/DICOM export, and optional ACR phantom QA through
pylinac.

**Release notes:** [CHANGELOG.md](CHANGELOG.md) · **User guide:**
[user-docs/USER_GUIDE.md](user-docs/USER_GUIDE.md) · **Developer docs:**
[dev-docs/README.md](dev-docs/README.md)

## Start here

### Use a packaged release

Download the appropriate release for your platform and follow the included
instructions. In the application, **Help → Quick Start Guide** gives a short
orientation; **Help → Documentation** opens the full user-guide hub.

### Run from a source checkout

1. Get the code:

   ```bash
   git clone https://github.com/kgrizz-git/DICOMViewerV3.git
   cd DICOMViewerV3
   ```

2. Use the launcher for your operating system, or create a virtual environment
   and run the application directly.

| Platform | Recommended launcher | What it does |
| --- | --- | --- |
| Windows | Double-click [`launch.bat`](launch.bat) | Creates a `venv` when needed, installs or refreshes dependencies, and starts the viewer. It can also use an existing `venv`, `.venv`, `env`, or `virtualenv`. |
| macOS | Double-click [`launch.command`](launch.command), or run `bash launch.command` | Creates and uses `venv`, offers dependency refresh, and starts the viewer. If macOS blocks a downloaded script, make it executable with `chmod +x launch.command` first. |
| Linux / any platform | Create and activate a virtual environment, install requirements, then run [`run.py`](run.py) | Uses the same startup wrapper as the launchers. |

For a manual Linux or macOS setup:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python run.py
```

For a manual Windows PowerShell setup:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python run.py
```

`run.py` starts `src/main.py` with the source directory on Python's import
path. From an activated environment, `python src/main.py` is also supported.

## Requirements

- Python 3.12 or later. Python 3.12 is the CI and recommended Windows version;
  imaging dependencies are more likely to have pre-built wheels.
- The Python packages listed in [requirements.txt](requirements.txt).
- A display environment supported by Qt/PySide6.

Very new Python releases can require native-extension builds. The launcher
scripts check the essential runtime imports after installation and report an
incomplete environment before starting the application.

## What is included

| Area | Capabilities |
| --- | --- |
| Viewing | Multi-pane layouts, window/level, slice navigation, cine, thumbnails, metadata, and configurable overlays. |
| Reconstruction | MPR and slab projections; optional VTK-based volume rendering. |
| Clinical tools | ROIs, distance and angle measurements, text/arrow annotations, and tag editing. |
| Fusion | PET/SPECT overlays on CT or MR, including opacity, alignment, resampling, and display controls. |
| Export | Images, screenshots, derived DICOM, tags, structured reports, and selected QA outputs. |
| QA | Optional ACR CT/MRI and nuclear-medicine workflows powered by the pinned pylinac dependency. |

The full dependency and decoder details are in
[requirements.txt](requirements.txt) and
[DICOM support analysis](dev-docs/info/DICOM_SUPPORT_ANALYSIS.md).

## Documentation

### For users

- [User guide hub](user-docs/USER_GUIDE.md)
- [Configuration](user-docs/CONFIGURATION.md)
- **Quick Start Guide** — available in the application through **Help → Quick
  Start Guide**.
- [Change log](CHANGELOG.md)

### For contributors

- [Contributing and CI](dev-docs/CONTRIBUTING.md)
- [Developer setup and troubleshooting](dev-docs/DEVELOPER_SETUP.md)
- [Test-suite guide](tests/README.md)
- [Architecture](ARCHITECTURE.md) and [source layout](dev-docs/SOURCE_LAYOUT.md)
- [Design system](DESIGN.md)
- [Security-tool guide](dev-docs/SECURITY_TOOLS_CLI_GUIDE.md)

## Project layout

```text
DICOMViewerV3/
├── src/        Application source
├── tests/      Automated tests and test-running guidance
├── user-docs/  User-facing guides
├── dev-docs/   Contributor documentation, plans, and investigations
├── resources/  Bundled help and Qt styling resources
├── scripts/    Verification, maintenance, and local tooling helpers
└── .github/    Continuous-integration workflows
```

## Contributing

Please begin with [CONTRIBUTING.md](dev-docs/CONTRIBUTING.md). It explains the
development environment, hooks, privacy safeguards, test and coverage gates,
and release process. Before changing the UI, also consult [DESIGN.md](DESIGN.md).

For repository automation and AI-assisted work, [AGENTS.md](AGENTS.md) is the
operational reference.
