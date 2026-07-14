#!/bin/bash
# DICOM Viewer V3 Launcher
# Double-click this file on macOS to open in Terminal, or run: bash launch.command

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="$SCRIPT_DIR/venv"

run_activated() {
    echo ""
    echo "Starting DICOM Viewer..."
    python "$SCRIPT_DIR/run.py"
    exit 0
}

run_sys() {
    echo ""
    echo "Starting DICOM Viewer (system Python)..."
    python3 "$SCRIPT_DIR/run.py"
    exit 0
}

setup_and_run() {
    echo ""
    echo "Creating virtual environment..."
    python3 -m venv "$VENV" || { echo "ERROR: Failed to create virtual environment."; exit 1; }
    # shellcheck disable=SC1091
    source "$VENV/bin/activate"
    echo "Installing requirements..."
    pip install -r "$SCRIPT_DIR/requirements.txt" || { echo "ERROR: Failed to install requirements."; exit 1; }
    run_activated
}

reinstall() {
    # shellcheck disable=SC1091
    source "$VENV/bin/activate"
    echo ""
    echo "Updating requirements..."
    pip install -r "$SCRIPT_DIR/requirements.txt" || { echo "ERROR: Failed to install requirements."; exit 1; }
    run_activated
}

delete_venv() {
    echo ""
    read -rp "Delete the virtual environment? This cannot be undone. (y/n): " confirm
    if [[ "$confirm" =~ ^[Yy]$ ]]; then
        rm -rf "$VENV"
        echo "Virtual environment deleted."
    fi
    echo ""
    show_menu
}

show_menu() {
    echo ""
    echo "==============================="
    echo "  DICOM Viewer V3 Launcher"
    echo "==============================="
    echo ""

    if [ -f "$VENV/bin/activate" ]; then
        echo "Virtual environment: FOUND"
        echo ""
        echo "  1  Run DICOM Viewer"
        echo "  2  Reinstall / update requirements"
        echo "  3  Delete virtual environment"
        echo "  4  Exit"
        echo ""
        read -rp "Choose [1-4]: " choice
        case "$choice" in
            1) source "$VENV/bin/activate" && run_activated ;;
            2) reinstall ;;
            3) delete_venv ;;
            4) exit 0 ;;
            *) show_menu ;;
        esac
    else
        echo "Virtual environment: NOT FOUND"
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
            *) show_menu ;;
        esac
    fi
}

show_menu
