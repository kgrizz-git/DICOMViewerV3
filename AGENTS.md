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
- **Multi-window layout**: 1x1 shows the **focused** view only; 1x2/2x1 show the focused view and the next view (in that order). Double-click on a pane (on image/background) expands it to 1x1; double-click again in 1x1 reverts to the last layout (or 2x2). **Swap** in the context menu (right-click → Swap) reorders view positions in 2x2 without moving data; swap is only active in 2x2.
