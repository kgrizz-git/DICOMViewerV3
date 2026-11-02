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
* ``requirements-docs`` (zensical + PyYAML, installed by the docs build, the
  offline-docs bundle, the launchers, and the action-pins job) is also compiled
  with ``-c requirements-dev.txt``. uv accepts a hashed constraints file, so
  the docs lock cannot drift from the versions the dev lock pins.
* uv keeps the pins already present in the output file, so recompiling an
  unchanged tree is a no-op. ``--upgrade`` deletes the old locks first.
* Resolving needs network access to PyPI.
* ``--untrusted-inputs`` is for the Dependabot recompile workflow, which runs
  with a write token on requirement files taken from a pull request. It rejects
  index, find-links, editable, path, and URL requirements before compiling, and
  compiles with ``--only-binary :all:`` and ``--no-config`` so resolving cannot
  build (run code from) an arbitrary source distribution. ``SDIST_ONLY`` lists
  the PyPI packages that ship no wheel and may still be built. The lock header
  keeps the normal command, so the output is byte-identical to a normal run.
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path

UV_VERSION = "0.13.5"
PYTHON_VERSION = "3.12"

# Order matters: the app lock constrains the others, and the dev lock also
# constrains the docs/tooling lock.
LOCK_STEMS = (
    "requirements",
    "requirements-dev",
    "requirements-build",
    "requirements-docs",
)
APP_LOCK = "requirements.txt"
DEV_LOCK = "requirements-dev.txt"
# Packages in the locks that publish only a source distribution. With
# --untrusted-inputs, these are the only ones uv may build to read metadata.
SDIST_ONLY = ("future",)
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


def compile_command(stem: str, uv: str = "uv", *, hardened: bool = False) -> list[str]:
    """Return the ``uv pip compile`` argv for one lock, with repo-relative paths.

    ``hardened`` adds the no-build flags used for untrusted inputs and keeps
    the normal command in the lock header.
    """
    command = [uv, "pip", "compile", input_name(stem), *COMMON_FLAGS]
    if hardened:
        command += ["--only-binary", ":all:"]
        for name in SDIST_ONLY:
            command += ["--no-binary", name]
        header = " ".join(compile_command(stem))
        command += ["--no-config", "--custom-compile-command", header]
    if stem != "requirements":
        command += ["-c", APP_LOCK]
    if stem == "requirements-docs":
        command += ["-c", DEV_LOCK]
    command += ["-o", output_name(stem)]
    return command


_INCLUDE = re.compile(r"^(?:-r|-c|--requirement|--constraint)(?:\s+|=)(\S+)$")
_HASH = re.compile(r"^--hash=sha256:[0-9a-f]{64}$")
_COMMENT = re.compile(r"(?:^|\s)#.*$")


def untrusted_input_problems(directory: Path) -> list[str]:
    """Return the lines in the requirement files that are unsafe to compile.

    Allowed: requirement specifiers by name, ``-r``/``-c`` of another
    requirement file in this set, and ``--hash=sha256:`` lines. Rejected:
    every other option (index URLs, find-links, editables, build settings),
    direct references (``name @ url``), URLs, and local paths.
    """
    allowed_files = {input_name(s) for s in LOCK_STEMS} | {
        output_name(s) for s in LOCK_STEMS
    }
    problems: list[str] = []
    for name in sorted(allowed_files):
        path = directory / name
        if not path.exists():
            continue
        for number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            line = _COMMENT.sub("", raw).strip().removesuffix("\\").strip()
            if not line:
                continue
            include = _INCLUDE.match(line)
            if include:
                if include.group(1) not in allowed_files:
                    problems.append(f"{name}:{number}: include outside the lock set")
                continue
            if _HASH.match(line):
                continue
            if (
                line.startswith(("-", ".", "/", "~", "\\"))
                or "@" in line
                or "://" in line
                or not re.match(r"^[A-Za-z0-9]", line)
            ):
                problems.append(f"{name}:{number}: not a plain requirement: {line}")
    return problems


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


def compile_all(
    directory: Path, *, uv: str = "uv", upgrade: bool = False, hardened: bool = False
) -> int:
    """Compile every lock inside ``directory``; return the first failing exit code."""
    for stem in LOCK_STEMS:
        if upgrade:
            (directory / output_name(stem)).unlink(missing_ok=True)
        print(f"Compiling {output_name(stem)} ...", flush=True)
        result = subprocess.run(
            compile_command(stem, uv, hardened=hardened), cwd=directory, check=False
        )
        if result.returncode != 0:
            print(f"uv pip compile failed for {input_name(stem)}.", file=sys.stderr)
            return result.returncode or 1
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").split("\n\n")[0])
    parser.add_argument(
        "--upgrade", action="store_true", help="Re-resolve to the newest versions."
    )
    parser.add_argument(
        "--untrusted-inputs",
        action="store_true",
        help="Reject unsafe requirement lines and compile without building sdists.",
    )
    args = parser.parse_args(argv)
    directory = Path(__file__).resolve().parent.parent
    if args.untrusted_inputs:
        problems = untrusted_input_problems(directory)
        if problems:
            print("Refusing to compile untrusted inputs:", file=sys.stderr)
            for problem in problems:
                print(f"  {problem}", file=sys.stderr)
            return 1
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
        directory, uv=uv, upgrade=args.upgrade, hardened=args.untrusted_inputs
    )


if __name__ == "__main__":
    raise SystemExit(main())
