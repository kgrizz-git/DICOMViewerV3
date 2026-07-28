"""Launcher for DICOM Viewer V3. Run this from the project root directory."""
import runpy
import sys
from pathlib import Path

src_dir = Path(__file__).parent / "src"
# runpy.run_path() on a plain .py file does not add the script's directory to
# sys.path, so main.py's top-level imports (core, gui, ...) would fail. Running
# src/main.py directly works only because Python auto-inserts src/ there.
sys.path.insert(0, str(src_dir))

main_py = src_dir / "main.py"
sys.argv[0] = str(main_py)
runpy.run_path(sys.argv[0], run_name="__main__")
