# Tests — DICOM Viewer V3

Run tests from the **project root** with the virtual environment activated (see [AGENTS.md](../AGENTS.md) and [dev-docs/DEVELOPER_SETUP.md](../dev-docs/DEVELOPER_SETUP.md)).

## Quick run

```bash
python tests/run_tests.py
```

This sets `PYTHONPATH` to `src`, runs **pytest** if installed, otherwise **unittest**.

For how to select and write unit, Qt/PySide6, and pylinac tests, see
[test-writing guidance](../dev-docs/info/TESTING_GUIDANCE.md).

### Pytest (optional)

```bash
pip install -r requirements-dev.txt
```

`pytest.ini` sets `-n auto`, so **pytest-xdist is required** — `pip install
pytest` alone will fail with `unrecognized arguments: -n`. Installing
`requirements-dev.txt` is the supported path. Add `-n 0` to any command below
to disable parallelism for single-test iteration.

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

## Focused test selection

Start with the smallest test family that owns the changed behavior, then add
the cross-cutting test named below when applicable. These are local feedback
commands, not a substitute for the full suite after a cross-domain change.

| Change area | Command |
|---|---|
| Core helper or controller | `python -m pytest tests/core -q` |
| Qt widget, dialog, or coordinator | `python -m pytest tests/gui -q` |
| Config persistence | `python -m pytest tests/config -q` |
| QA/pylinac package | `python -m pytest tests/qa tests/test_pylinac_*.py tests/test_qa_*.py -q` |
| Main-window wiring | `python -m pytest tests/test_main_signal_wiring.py tests/test_main_signals_view.py -q` |
| Loading or parsing | `python -m pytest tests/test_dicom_loader.py tests/test_dicom_parser.py tests/core/test_dicom_loader_*.py -q` |
| MPR | `python -m pytest tests/test_mpr_*.py tests/core/test_mpr_*.py tests/gui/test_mpr_*.py -q` |
| Privacy | `python -m pytest tests/test_privacy_*.py tests/core/test_privacy_controller.py tests/gui/test_privacy_storage_settings.py -q` |
| Harness/documentation mechanics | `python -m pytest tests/test_repo_harness.py tests/test_agent_smoke_harness.py -q` |

When shell glob expansion is unavailable, name the relevant test files
explicitly. For a change-area map and manual-smoke routing, see
[`dev-docs/HARNESS.md`](../dev-docs/HARNESS.md#change-routing-and-focused-verification).

## CI

GitHub Actions workflows under `.github/workflows/` run the test and quality checks configured for this repository. The **`pytest`** job runs the full suite with coverage and **`--cov-fail-under=65`**. Local `pre-push` does **not** re-run the full suite (too slow); use the command below before a risky merge if you want the same check locally:

```bash
PYTHONPATH=src python -m pytest tests --cov=src --cov-fail-under=65
```

**`user-docs-links`** runs `scripts/check_user_docs_links.py` (same assertion as `tests/test_user_docs_links.py`).
