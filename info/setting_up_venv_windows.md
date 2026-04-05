# Setting up a Python virtual environment on Windows

This document shows quick commands and helper scripts to create, activate, and use a virtual environment for this project on Windows.

**Note: this may not be the best way to do this. May want to verify/update.**

Prerequisites
- Python 3 installed and on PATH (or available via the `py` launcher).
- `requirements.txt` present at repository root (this repo already includes one).

Quick commands

Check Python and pip:

```powershell
# If you have the "py" launcher available:
py --version
py -3 -m pip --version

# If the "py" launcher is not available, use the `python` command:
python --version
python -m pip --version
```

Create a venv in the project root (creates folder `env`):

```powershell
# Preferred (when available):
py -3 -m venv env

# Or, if `py` is not present on your system:
python -m venv env
```

Activate the environment
- PowerShell:

```powershell
.\env\Scripts\Activate.ps1
```

If PowerShell blocks activation, allow it for the current user:

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

- Command Prompt (cmd.exe):

```cmd
env\Scripts\activate.bat
```

- Git Bash / WSL (note Windows path):

```bash
source env/Scripts/activate
```

Install project dependencies

```powershell
pip install --upgrade pip
pip install -r requirements.txt
```

Save installed packages

```powershell
pip freeze > requirements.txt
```

Deactivate and remove

```powershell
deactivate
rd /s /q env
```

Helper scripts
- `scripts/setup_venv.ps1` — creates venv and installs `requirements.txt`.
- `scripts/setup_venv.bat` — same for cmd.exe.

Run the PowerShell helper (uses `python` and works with the Microsoft Store alias):

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\setup_venv.ps1
```

VS Code integration
-------------------

Place workspace settings in a `.vscode` folder at the repository root so they apply when the project is opened in VS Code. Example file: `.vscode/settings.json`.

Example `settings.json` (paste into `.vscode/settings.json`):

```json
{
    "python.defaultInterpreterPath": "${workspaceFolder}/env/Scripts/python.exe",
    "python.terminal.activateEnvironment": true,
    "python.analysis.extraPaths": ["${workspaceFolder}/src"],
    "python.envFile": "${workspaceFolder}/.env"
}
```

- **`python.defaultInterpreterPath`**: pins the workspace to the project's venv interpreter.
- **`python.terminal.activateEnvironment`**: auto-activates the venv for integrated terminals.
- **`python.analysis.extraPaths`**: adds `src` so the language server resolves local packages.
- **`python.envFile`**: points to a `.env` file (optional) for `PYTHONPATH` or environment variables.

Optional `.env` to add at repository root (makes `src` available to the analysis/debugger):

```text
PYTHONPATH=${workspaceFolder}/src
```

After adding the settings, restart VS Code or re-open the folder and use Command Palette -> `Python: Select Interpreter` to confirm the selected interpreter is `${workspaceFolder}/env/Scripts/python.exe`.

Notes
- Using `py -3` ensures Python 3 is used when `python` isn't on PATH.
- If you prefer `pipenv` or `virtualenv`, see the bottom of this repo's README.

- If the `py` launcher isn't available on your system, substitute `python` for `py -3` in the examples above (e.g. `python -m venv env`).


--------------------------------
Scripts\setup_venv.ps1

#!/usr/bin/env pwsh
# Minimal robust PowerShell helper: use `python` to create venv and install requirements.
# This script assumes `python` is callable in this shell (works with Microsoft Store alias).

Write-Host "Creating virtual environment using 'python -m venv env'..."
try {
    python -m venv env
} catch {
    Write-Error "Failed to run 'python -m venv env'. Ensure 'python' is on PATH and callable."
    exit 1
}

if (-not (Test-Path .\env\Scripts\python.exe)) {
    Write-Error "Virtual environment not found at .\env\Scripts\python.exe after creation. Aborting."
    exit 1
}

Write-Host "Upgrading pip inside venv..."
try {
    .\env\Scripts\python.exe -m pip install --upgrade pip
} catch {
    Write-Error "Failed to upgrade pip inside venv: $_"
}

if (Test-Path requirements.txt) {
    Write-Host "Installing dependencies from requirements.txt..."
    try {
        .\env\Scripts\python.exe -m pip install -r requirements.txt
    } catch {
        Write-Error "Failed to install requirements: $_"
    }
} else {
    Write-Host "No requirements.txt found; skipping dependency install." -ForegroundColor Yellow
}

Write-Host "Done. To activate the virtual environment run:`n  PowerShell: .\env\Scripts\Activate.ps1`n  CMD: env\Scripts\activate.bat" -ForegroundColor Green