#!/usr/bin/env python3
"""Regenerate the hashed, universal requirements locks from the ``.in`` files.

``requirements*.in`` hold the human-edited floors and comments.
``requirements*.txt`` are the compiled, hash-pinned locks that CI, the frozen
builds, and ``pip-audit`` install and scan. Edit a ``.in`` file, then run::

    python scripts/compile_requirements.py            # keep existing pins
    python scripts/compile_requirements.py --upgrade  # re-resolve to newest

Design notes:

* The compiler is ``uv pip compile`` at the exact version in ``UV_VERSION``. It
  must match the ``uv==...`` pin in ``.github/workflows/ci.yml`` and
  ``requirements-dev.in`` (a unit test enforces this), so local runs and CI
  produce byte-identical output.
* ``--universal`` plus ``--python-version 3.12`` is what makes one lock valid on
  win32, darwin, and linux. uv resolves every platform at once and keeps
  environment markers (for example ``colorama ; sys_platform == 'win32'``).
  ``pip-compile`` only resolves for the host, so a Linux lock would drop the
  Windows and macOS only packages and fail ``--require-hashes`` installs there.
* ``requirements-dev`` and ``requirements-build`` are compiled with
  ``-c requirements.txt`` so every file agrees on the application versions.
* uv keeps the pins already present in the output file, so recompiling an
  unchanged tree is a no-op. ``--upgrade`` deletes the old locks first.
* Resolving needs network access to PyPI.
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path

UV_VERSION = "0.13.4"
PYTHON_VERSION = "3.12"

# Order matters: the app lock is the constraint for the other two.
LOCK_STEMS = ("requirements", "requirements-dev", "requirements-build")
APP_LOCK = "requirements.txt"
COMMON_FLAGS = (
    "--universal",
    "--python-version",
    PYTHON_VERSION,
    "--generate-hashes",
    "--strip-extras",
)


def input_name(stem: str) -> str:
    """Return the ``.in`` file name for a lock stem."""
    return f"{stem}.in"


def output_name(stem: str) -> str:
    """Return the compiled ``.txt`` file name for a lock stem."""
    return f"{stem}.txt"


def compile_command(stem: str, uv: str = "uv") -> list[str]:
    """Return the ``uv pip compile`` argv for one lock, with repo-relative paths."""
    command = [uv, "pip", "compile", input_name(stem), *COMMON_FLAGS]
    if stem != "requirements":
        command += ["-c", APP_LOCK]
    command += ["-o", output_name(stem)]
    return command


def parse_uv_version(output: str) -> str | None:
    """Extract ``X.Y.Z`` from ``uv --version`` output, or None."""
    match = re.search(r"\buv (\d+\.\d+\.\d+)", output)
    return match.group(1) if match else None


def uv_version_ok(output: str) -> bool:
    """Return whether ``uv --version`` output reports the pinned version."""
    return parse_uv_version(output) == UV_VERSION


def installed_uv_version(uv: str = "uv") -> str | None:
    """Return the installed uv version, or None when uv is missing or unusable."""
    try:
        result = subprocess.run(
            [uv, "--version"], capture_output=True, text=True, check=False
        )
    except OSError:
        return None
    return parse_uv_version(result.stdout)


def compile_all(directory: Path, *, uv: str = "uv", upgrade: bool = False) -> int:
    """Compile all three locks inside ``directory``; return the first failing exit code."""
    for stem in LOCK_STEMS:
        if upgrade:
            (directory / output_name(stem)).unlink(missing_ok=True)
        print(f"Compiling {output_name(stem)} ...", flush=True)
        result = subprocess.run(compile_command(stem, uv), cwd=directory, check=False)
        if result.returncode != 0:
            print(f"uv pip compile failed for {input_name(stem)}.", file=sys.stderr)
            return result.returncode or 1
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").split("\n\n")[0])
    parser.add_argument(
        "--upgrade", action="store_true", help="Re-resolve to the newest versions."
    )
    args = parser.parse_args(argv)
    uv = shutil.which("uv") or "uv"
    found = installed_uv_version(uv)
    if found != UV_VERSION:
        print(
            f"Need uv=={UV_VERSION} (found {found or 'none'}). "
            f'Install it with: python -m pip install "uv=={UV_VERSION}"',
            file=sys.stderr,
        )
        return 1
    return compile_all(
        Path(__file__).resolve().parent.parent, uv=uv, upgrade=args.upgrade
    )


if __name__ == "__main__":
    raise SystemExit(main())
