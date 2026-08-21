# DICOM Viewer V3

DICOM Viewer V3 is a cross-platform desktop application for reviewing medical
imaging studies locally on Windows, macOS, and Linux. Open studies from files
or folders, review them with multi-window viewing and clinical measurement
tools, and export images or derived DICOM — all on your own machine. It is not
a PACS server or archive.

<!-- Hero screenshot: intentionally not included yet. Screenshots are
     human-captured and pass PHI review before being committed and added to
     security/approved-media-sha256.json. Insert one primary image (optional
     second) directly below this line once approved. -->

## Get the app

Download a packaged release for your platform from the
[releases page](https://github.com/kgrizz-git/DICOMViewerV3/releases) and run
the installer or bundle. Inside the app, **Help → Quick Start Guide** gives a
short orientation and **Help → Documentation** opens the full user guide.

## What you can do

| Area | Capabilities |
| --- | --- |
| Viewing | Multi-pane layouts, window/level presets, slice navigation, cine playback, series navigator, configurable overlays. |
| Reconstruction | MPR and slab projections; optional volume rendering. |
| Clinical tools | ROIs, distance/angle measurements, text and arrow annotations, metadata inspection and tag editing. |
| Fusion | PET/SPECT overlays on CT or MR with opacity, alignment, and display controls. |
| Export | Images, screenshots, cine video, derived DICOM, tags, and structured reports. |
| QA (optional) | ACR CT/MRI and nuclear-medicine phantom workflows. |

Studies opened locally are indexed into an encrypted local study database so
you can find and reopen them quickly.

## Documentation for users

- [User guide](user-docs/USER_GUIDE.md)
- [Configuration](user-docs/CONFIGURATION.md)
- [Change log](CHANGELOG.md)

## Run from source

Clone the repository, then double-click [`launch.bat`](launch.bat) (Windows) or
run `bash launch.command` (macOS/Linux). The launcher creates a virtual
environment if needed, installs dependencies, and starts the viewer.

Prefer a manual setup, hit a launcher problem, or want tests and tooling? See
[dev-docs/DEVELOPER_SETUP.md](dev-docs/DEVELOPER_SETUP.md).

## Contributing and project layout

Contributions start with [dev-docs/CONTRIBUTING.md](dev-docs/CONTRIBUTING.md);
architecture lives in [ARCHITECTURE.md](ARCHITECTURE.md), and the full
developer documentation index is [dev-docs/README.md](dev-docs/README.md).
Source is under `src/`, user guides under `user-docs/`, contributor docs and
plans under `dev-docs/`.
