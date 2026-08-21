#!/bin/bash
# DICOM Viewer V3 Launcher
# Double-click this file on macOS to open in Terminal, or run: bash launch.command
#
# Virtual environment resolution (first match wins): .venv, venv, env, virtualenv.
# If none exist, create/setup targets .venv.
# Keep this candidate list in sync with launch.bat (enforced by check_repo_harness.py).

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

resolve_venv() {
    # Always returns 0 so a future `set -e` cannot abort at startup when no env exists.
    local candidate
    for candidate in .venv venv env virtualenv; do
        # Prefer a regular file (existence), matching launch.bat's python.exe check.
        if [[ -f "$SCRIPT_DIR/$candidate/bin/python" ]]; then
            VENV="$SCRIPT_DIR/$candidate"
            VENV_PY="$VENV/bin/python"
            return 0
        fi
    done
    VENV="$SCRIPT_DIR/.venv"
    VENV_PY="$VENV/bin/python"
    return 0
}

resolve_venv

install_requirements() {
    echo ""
    echo "Installing requirements into:"
    echo "  $VENV_PY"
    echo "This can take several minutes. Do not close this window."
    # Always use the venv interpreter explicitly instead of relying on activate + bare pip.
    "$VENV_PY" -m pip install --upgrade pip || {
        echo "ERROR: Failed to upgrade pip inside the virtual environment."
        return 1
    }
    "$VENV_PY" -m pip install -r "$SCRIPT_DIR/requirements.txt" || {
        echo "ERROR: Failed to install requirements into the virtual environment."
        echo "The venv folder may exist but be incomplete. Choose option 2"
        echo "(Reinstall / update requirements) after fixing the error, or delete"
        echo "the venv and create it again."
        return 1
    }
    # Canary imports: enough of the app stack that a half-finished pip install still fails.
    "$VENV_PY" -c "import pydicom, PySide6, numpy, PIL" || {
        echo "ERROR: Requirements appeared to install, but required packages are still missing."
        echo "Try option 2 (Reinstall / update requirements) or delete and recreate the venv."
        return 1
    }
    echo "Requirements installed successfully."
    return 0
}

run_activated() {
    echo ""
    echo "Starting DICOM Viewer..."
    if ! "$VENV_PY" "$SCRIPT_DIR/run.py"; then
        echo ""
        echo "DICOM Viewer exited with an error."
        read -rp "Press Enter to close..."
        exit 1
    fi
    exit 0
}

run_sys() {
    echo ""
    echo "Starting DICOM Viewer (system Python)..."
    if ! python3 "$SCRIPT_DIR/run.py"; then
        echo ""
        echo "DICOM Viewer exited with an error."
        echo "If you see ModuleNotFoundError, install requirements for this Python:"
        echo "  python3 -m pip install -r \"$SCRIPT_DIR/requirements.txt\""
        read -rp "Press Enter to close..."
        exit 1
    fi
    exit 0
}

setup_and_run() {
    echo ""
    echo "Creating virtual environment..."
    python3 -m venv "$VENV" || {
        echo "ERROR: Failed to create virtual environment."
        exit 1
    }
    if [[ ! -f "$VENV_PY" ]]; then
        echo "ERROR: Virtual environment was created but python is missing:"
        echo "  $VENV_PY"
        exit 1
    fi
    install_requirements || exit 1
    run_activated
}

reinstall() {
    if [[ ! -f "$VENV_PY" ]]; then
        echo "ERROR: Virtual environment python not found:"
        echo "  $VENV_PY"
        exit 1
    fi
    echo ""
    echo "Updating requirements..."
    install_requirements || exit 1
    run_activated
}

run_with_check() {
    if [[ ! -f "$VENV_PY" ]]; then
        echo "ERROR: Virtual environment python not found:"
        echo "  $VENV_PY"
        exit 1
    fi
    # Recover from a half-created venv (folder exists, packages never installed).
    if ! "$VENV_PY" -c "import pydicom, PySide6, numpy, PIL" >/dev/null 2>&1; then
        echo ""
        echo "Virtual environment is incomplete (required packages missing)."
        echo "Installing requirements before starting..."
        install_requirements || exit 1
    fi
    # shellcheck disable=SC1091
    source "$VENV/bin/activate"
    run_activated
}

delete_venv() {
    local target="$VENV"
    echo ""
    read -rp "Delete the virtual environment? This cannot be undone. (y/n): " confirm
    if [[ ! "$confirm" =~ ^[Yy]$ ]]; then
        return 0
    fi
    echo "Deleting virtual environment..."
    echo "  $target"
    rm -rf "$target"
    if [[ -e "$target" ]]; then
        echo "ERROR: Could not delete the virtual environment (files may be in use)."
        echo "Close the app and any terminals using that Python, then try again."
        echo "  $target"
        read -rp "Press Enter to continue..."
        return 1
    fi
    echo "Virtual environment deleted."
    resolve_venv
    return 0
}

menu_loop() {
    local choice
    while true; do
        echo ""
        echo "==============================="
        echo "  DICOM Viewer V3 Launcher"
        echo "==============================="
        echo ""

        if [[ -f "$VENV_PY" ]]; then
            echo "Virtual environment: FOUND"
            echo "  $VENV"
            echo ""
            echo "  1  Run DICOM Viewer"
            echo "  2  Reinstall / update requirements"
            echo "  3  Delete virtual environment"
            echo "  4  Exit"
            echo ""
            read -rp "Choose [1-4]: " choice
            case "$choice" in
                1) run_with_check ;;
                2) reinstall ;;
                3) delete_venv ;;
                4) exit 0 ;;
                *) continue ;;
            esac
        else
            echo "Virtual environment: NOT FOUND"
            echo ""
            echo "What is a venv? A separate folder of Python packages used only by this app."
            echo "It avoids mixing versions with other Python programs on your PC and makes"
            echo "updates or cleanup simpler. Using one is recommended, not required."
            echo "You can run with system Python instead (option 2 below) if you prefer."
            echo ""
            echo "  1  Create venv, install requirements, then run"
            echo "  2  Run using system Python (no venv)"
            echo "  3  Exit"
            echo ""
            read -rp "Choose [1-3]: " choice
            case "$choice" in
                1) setup_and_run ;;
                2) run_sys ;;
                3) exit 0 ;;
                *) continue ;;
            esac
        fi
    done
}

menu_loop
