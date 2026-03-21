"""Launcher for DICOM Viewer V3. Run this from the project root directory."""
import runpy
import sys
from pathlib import Path

sys.argv[0] = str(Path(__file__).parent / "src" / "main.py")
runpy.run_path(sys.argv[0], run_name="__main__")
