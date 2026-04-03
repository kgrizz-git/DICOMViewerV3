# Tests — DICOM Viewer V3

Run tests from the **project root** with the virtual environment activated (see [AGENTS.md](../AGENTS.md) and [dev-docs/DEVELOPER_SETUP.md](../dev-docs/DEVELOPER_SETUP.md)).

## Quick run

```bash
python tests/run_tests.py
```

This sets `PYTHONPATH` to `src`, runs **pytest** if installed, otherwise **unittest**.

### Pytest (optional)

```bash
pip install pytest
```

**Windows (PowerShell):**

```powershell
$env:PYTHONPATH = "src"; python -m pytest tests -v --tb=short
```

**macOS / Linux:**

```bash
PYTHONPATH=src python -m pytest tests -v --tb=short
```

### Unittest only

**Windows (PowerShell):**

```powershell
$env:PYTHONPATH = "src"; python -m unittest discover -s tests -p "test_*.py" -v
```

Or:

```bash
python tests/run_tests.py --unittest
```

## Layout

| Area | Path | Notes |
|------|------|--------|
| Root tests | `tests/test_*.py` | Parser, loader, export, MPR, pylinac extent, etc. |
| Config mixins | `tests/config/` | Display, layout, ROI, paths, … |
| Metadata | `tests/metadata/` | Metadata controller |
| ROI | `tests/roi/` | ROI / measurement controller |
| Core | `tests/core/` | Subwindow ROI focus, loading progress |
| Smoke | `tests/smoke/` | Regression / resource presence |

Most tests **do not require DICOM files** on disk; they use synthetic data or mocks.

## CI

GitHub Actions workflows under `.github/workflows/` run the test and quality checks configured for this repository.
