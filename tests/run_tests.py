"""
Test runner script for DICOM Viewer V3.

Ensures src is on PYTHONPATH and runs pytest (or unittest if pytest not installed).
Run from project root:
  python tests/run_tests.py
  python tests/run_tests.py --unittest   # force unittest instead of pytest
With venv activated from project root:
  .venv\\Scripts\\activate   (Windows)
  source .venv/bin/activate   (Linux/macOS)
  python tests/run_tests.py
"""

import os
import sys
import subprocess

def main():
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    src_dir = os.path.join(project_root, "src")
    tests_dir = os.path.join(project_root, "tests")

    if src_dir not in sys.path:
        sys.path.insert(0, src_dir)

    os.chdir(project_root)
    env = os.environ.copy()
    env["PYTHONPATH"] = src_dir + os.pathsep + env.get("PYTHONPATH", "")

    use_unittest = "--unittest" in sys.argv
    if use_unittest:
        sys.argv.remove("--unittest")

    if use_unittest:
        return subprocess.call(
            [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py", "-v"],
            env=env,
            cwd=project_root,
        )
    try:
        import pytest
        return subprocess.call(
            [sys.executable, "-m", "pytest", "tests", "-v", "--tb=short"] + [a for a in sys.argv[1:] if a != "--unittest"],
            env=env,
            cwd=project_root,
        )
    except ImportError:
        print("pytest not installed; falling back to unittest. Install with: pip install pytest")
        return subprocess.call(
            [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py", "-v"],
            env=env,
            cwd=project_root,
        )

if __name__ == "__main__":
    sys.exit(main())
