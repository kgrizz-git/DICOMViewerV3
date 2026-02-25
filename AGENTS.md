# Agent instructions – DICOM Viewer V3

Guidance for AI agents and developers working in this repository.

## Virtual environment (venv)

**Always activate the venv in the `venv` directory before running tests or application code.**

- **Windows (Command Prompt):** `venv\Scripts\activate`
- **Windows (PowerShell):** `.\venv\Scripts\Activate.ps1`
- **macOS / Linux:** `source venv/bin/activate`

From project root, after activation:

- Run the app: `python src/main.py`
- Run tests: `python tests/run_tests.py` or `python -m pytest tests/ -v`

If no venv exists, create one: `python -m venv venv`, activate it, then `pip install -r requirements.txt`.

## Other conventions

- See `.cursor/rules` and user rules for backup-before-modify, testing, and commit guidelines.
- Project layout: `src/` (application), `tests/` (tests), `dev-docs/` (plans, assessments).

## View and display options

- **Image Smoothing**: User-configurable option in the **View** menu and in the **image viewer context menu** (right-click on image). When enabled, the image uses smooth scaling when idle after zoom/pan; during zoom/pan it uses fast scaling for responsiveness. Default is **off** (no enhancement). Setting is persisted in config.
