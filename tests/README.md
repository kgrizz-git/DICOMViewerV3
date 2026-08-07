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
| Root tests | `tests/test_*.py` | Cross-cutting integration, privacy, harness, workflow, and legacy tests that span multiple source packages. |
| Config mixins | `tests/config/` | Display, layout, ROI, paths, … |
| Core | `tests/core/` | Tests mirroring `src/core/`, including DICOM parsing, pixels, rescale, loading, and subwindow behavior. |
| GUI | `tests/gui/` | Tests mirroring `src/gui/` dialogs, widgets, and coordinators. |
| Metadata | `tests/metadata/` | Tests mirroring `src/metadata/`. |
| QA | `tests/qa/` | Tests mirroring `src/qa/`. |
| ROI | `tests/roi/` | Tests mirroring `src/roi/`. |
| Scripts | `tests/scripts/` | Repository-script tests. |
| Smoke | `tests/smoke/` | Regression / resource presence |
| Tools | `tests/tools/` | Tests mirroring `src/tools/`. |
| Utils | `tests/utils/` | Tests mirroring `src/utils/`. |

Most tests **do not require DICOM files** on disk; they use synthetic data or mocks.

## CI

GitHub Actions workflows under `.github/workflows/` run the test and quality checks configured for this repository. The **`pytest`** job runs the full suite with coverage and **`--cov-fail-under=65`**. Local `pre-push` does **not** re-run the full suite (too slow); use the command below before a risky merge if you want the same check locally:

```bash
PYTHONPATH=src pytest tests --cov=src --cov-fail-under=65
```

**`user-docs-links`** runs `scripts/check_user_docs_links.py` (same assertion as `tests/test_user_docs_links.py`).
