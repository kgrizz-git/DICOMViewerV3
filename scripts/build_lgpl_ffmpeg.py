#!/usr/bin/env python3
"""Build and audit a static LGPL FFmpeg CLI for frozen DICOM Viewer releases.

Downloads one pinned official FFmpeg 7.1.x source tarball, verifies its
SHA-256 digest, configures and compiles a static ``ffmpeg`` executable with
the repository's LGPL configure line, stages the binary plus license texts
under ``build/ffmpeg-lgpl/``, and audits ``ffmpeg -version`` / ``-encoders`` /
``-muxers`` so GPL flags and missing cine codecs are caught at build time.

Implements Phase 2 of ``dev-docs/plans/supporting/FFMPEG_REPLACEMENT_PLAN.md``
(Decisions 2–4). This script does **not** replace the ``imageio-ffmpeg`` wheel
at dev time; it produces the binary PyInstaller will bundle in a later phase.

**Windows:** run the ``build`` subcommand on ``windows-latest`` inside an
MSYS2 **mingw64** shell with a typical autotools toolchain (``gcc``, ``make``,
``nasm``/``yasm`` as needed). Native CPython starts ``configure`` through
``sh`` because Windows cannot execute that extensionless script directly.
There is no third-party prebuilt binary fallback.

Design notes
------------
- Stdlib only (``urllib``, ``hashlib``, ``lzma``, ``tarfile``, ``subprocess``).
  Compiling still requires the platform C toolchain on the host.
- Network fetch and compile run only for the explicit ``build`` subcommand;
  ``--help`` and ``audit`` never download or compile.
- Tarball digest is checked **before** ``./configure``; a mismatch aborts the
  build without touching the source tree configure step.
- GPL detection uses **whole** configure flags (token equality), so
  ``--disable-gpl`` does not trip the ``--enable-gpl`` rule.

Inputs
------
- ``build``: network access to ``https://ffmpeg.org/releases/`` for the pinned
  tarball; writable ``tmp/`` (download cache) and ``build/ffmpeg-lgpl/`` (stage).
- ``audit``: captured stdout from ``ffmpeg -version``, ``ffmpeg -hide_banner
  -encoders``, and ``ffmpeg -hide_banner -muxers`` (files or in-memory strings
  for unit tests).

Outputs
-------
- ``build/ffmpeg-lgpl/ffmpeg`` or ``build/ffmpeg-lgpl/ffmpeg.exe``
- ``build/ffmpeg-lgpl/COPYING.LGPLv2.1`` (always, from the extracted source)
- ``build/ffmpeg-lgpl/COPYING.LGPLv3`` when the built configuration includes
  ``--enable-version3``
- ``build/ffmpeg-lgpl/ffmpeg-lgpl-build-manifest.txt`` (version, SHA-256,
  configure line)

Requirements
------------
- Python 3.10+ (matches the rest of the repository).
- For ``build``: POSIX ``make`` and a compiler; MSYS2 mingw64 on Windows CI.

Usage (from repository root)::

    python scripts/build_lgpl_ffmpeg.py --help
    python scripts/build_lgpl_ffmpeg.py audit \\
        --version-file path/to/version.txt \\
        --encoders-file path/to/encoders.txt \\
        --muxers-file path/to/muxers.txt
    python scripts/build_lgpl_ffmpeg.py build
    python scripts/build_lgpl_ffmpeg.py build --tarball /path/to/ffmpeg-7.1.5.tar.xz

Exit code: 0 on success, 1 on audit/build/digest failure, 2 on usage errors.
"""

from __future__ import annotations

import argparse
import hashlib
import logging
import os
import shutil
import socket
import subprocess
import sys
import tarfile
import urllib.error
import urllib.request
from pathlib import Path

LOGGER = logging.getLogger("build_lgpl_ffmpeg")

# Latest 7.1.x on https://ffmpeg.org/releases/ as of implementation (2026-10-17).
# Upstream publishes PGP ``.asc`` signatures but no ``.tar.xz.sha256`` sidecar for
# recent releases; digest verified by downloading the official tarball to ``tmp/``
# and matching Debian ``ffmpeg_7.1.5.orig.tar.xz`` / Homebrew ``ffmpeg@7`` metadata.
FFMPEG_VERSION = "7.1.5"
FFMPEG_TARBALL_BASENAME = f"ffmpeg-{FFMPEG_VERSION}.tar.xz"
FFMPEG_TARBALL_URL = f"https://ffmpeg.org/releases/{FFMPEG_TARBALL_BASENAME}"
FFMPEG_TARBALL_SHA256 = (
    "de668509caf9e35e3cd162473441fdb29538c6d96ed080292b3cf9e6fc5d558f"
)

CONFIGURE_ARGS: tuple[str, ...] = (
    "--disable-gpl",
    "--disable-nonfree",
    "--disable-autodetect",
    "--disable-ffplay",
    "--disable-ffprobe",
    "--disable-doc",
    "--disable-debug",
)
CONFIGURE_LINE = "./configure " + " ".join(CONFIGURE_ARGS)

FORBIDDEN_WHOLE_FLAGS: frozenset[str] = frozenset(
    {
        "--enable-gpl",
        "--enable-nonfree",
        "--enable-libx264",
        "--enable-libx265",
        "--enable-postproc",
    }
)

REQUIRED_ENCODERS: frozenset[str] = frozenset({"mpeg4", "mpeg2video"})
REQUIRED_MUXERS: frozenset[str] = frozenset({"mpeg"})

VERSION_CONFIGURATION_PREFIX = "configuration:"


class FfmpegLgplError(Exception):
    """Base error for digest, audit, or build failures."""


class TarballDigestError(FfmpegLgplError):
    """Raised when a tarball SHA-256 does not match the pinned digest."""


class FfmpegAuditError(FfmpegLgplError):
    """Raised when ``ffmpeg`` output fails the LGPL / codec audit."""


def repo_root() -> Path:
    """Return the repository root (parent of ``scripts/``)."""
    return Path(__file__).resolve().parents[1]


def compute_file_sha256(path: Path) -> str:
    """Return the lowercase hex SHA-256 digest of ``path``."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_tarball_sha256(
    tarball_path: Path,
    expected_sha256: str | None = None,
) -> None:
    """Fail if ``tarball_path`` digest differs from the pinned (or supplied) value."""
    expected = (expected_sha256 or FFMPEG_TARBALL_SHA256).lower()
    actual = compute_file_sha256(tarball_path).lower()
    if actual != expected:
        raise TarballDigestError(
            f"Tarball SHA-256 mismatch for {tarball_path.name}: "
            f"expected {expected}, got {actual}"
        )


def extract_configuration_line(version_stdout: str) -> str:
    """Return the configure flag string from ``ffmpeg -version`` output."""
    for line in version_stdout.splitlines():
        stripped = line.strip()
        if stripped.lower().startswith(VERSION_CONFIGURATION_PREFIX):
            return stripped[len(VERSION_CONFIGURATION_PREFIX) :].strip()
    raise FfmpegAuditError(
        "ffmpeg -version output has no configuration: line"
    )


def configuration_tokens(configuration_line: str) -> list[str]:
    """Split a configuration line into argv-style tokens."""
    return configuration_line.split()


def find_forbidden_enable_flags(configuration_line: str) -> list[str]:
    """Return forbidden whole flags present on the configuration line."""
    tokens = configuration_tokens(configuration_line)
    return sorted(flag for flag in tokens if flag in FORBIDDEN_WHOLE_FLAGS)


def _listing_codec_names(tool_output: str, candidates: frozenset[str]) -> set[str]:
    """Match FFmpeg encoder/muxer listing lines (name is typically the second field)."""
    found: set[str] = set()
    for line in tool_output.splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[1] in candidates:
            found.add(parts[1])
    return found


def missing_required_encoders(encoders_stdout: str) -> list[str]:
    """Return required encoder names absent from ``ffmpeg -encoders`` output."""
    present = _listing_codec_names(encoders_stdout, REQUIRED_ENCODERS)
    return sorted(REQUIRED_ENCODERS - present)


def missing_required_muxers(muxers_stdout: str) -> list[str]:
    """Return required muxer names absent from ``ffmpeg -muxers`` output."""
    present = _listing_codec_names(muxers_stdout, REQUIRED_MUXERS)
    return sorted(REQUIRED_MUXERS - present)


def audit_ffmpeg_outputs(
    version_stdout: str,
    encoders_stdout: str,
    muxers_stdout: str,
) -> str:
    """Validate captured FFmpeg CLI output; return the configuration line on success.

    Raises :class:`FfmpegAuditError` when a forbidden flag or required codec is missing.
    """
    configuration_line = extract_configuration_line(version_stdout)

    forbidden = find_forbidden_enable_flags(configuration_line)
    if forbidden:
        raise FfmpegAuditError(
            "Forbidden configure flags in ffmpeg -version: "
            + ", ".join(forbidden)
        )

    missing_enc = missing_required_encoders(encoders_stdout)
    if missing_enc:
        raise FfmpegAuditError(
            "Missing required encoders in ffmpeg -encoders: "
            + ", ".join(missing_enc)
        )

    missing_mux = missing_required_muxers(muxers_stdout)
    if missing_mux:
        raise FfmpegAuditError(
            "Missing required muxers in ffmpeg -muxers: "
            + ", ".join(missing_mux)
        )

    return configuration_line


def configuration_uses_lgplv3(configuration_line: str) -> bool:
    """True when the built binary was configured with ``--enable-version3``."""
    return "--enable-version3" in configuration_tokens(configuration_line)


def write_build_manifest(
    stage_dir: Path,
    configuration_line: str,
) -> Path:
    """Write version, digest, and configure line beside the staged binary."""
    manifest_path = stage_dir / "ffmpeg-lgpl-build-manifest.txt"
    body = (
        f"ffmpeg_version={FFMPEG_VERSION}\n"
        f"tarball={FFMPEG_TARBALL_BASENAME}\n"
        f"tarball_url={FFMPEG_TARBALL_URL}\n"
        f"tarball_sha256={FFMPEG_TARBALL_SHA256}\n"
        f"configure_line={CONFIGURE_LINE}\n"
        f"built_configuration={configuration_line}\n"
    )
    manifest_path.write_text(body, encoding="utf-8")
    return manifest_path


def download_tarball(destination: Path) -> None:
    """Download the pinned official tarball to ``destination``.

    Semgrep's dynamic-urllib rule treats ``urlopen`` as safe only when its only
    argument is a string literal. A ``timeout=`` keyword or a ``nosemgrep``
    comment still leaves a SARIF result, and GitHub code scanning alerts on it.
    The 600 second limit is the process socket default for this call only.
    """
    # Keep this literal identical to ``FFMPEG_TARBALL_URL`` (version + basename).
    pinned_url = "https://ffmpeg.org/releases/ffmpeg-7.1.5.tar.xz"
    if pinned_url != FFMPEG_TARBALL_URL:
        raise FfmpegLgplError(
            "Download URL literal does not match FFMPEG_TARBALL_URL"
        )
    LOGGER.info("Downloading %s", pinned_url)
    destination.parent.mkdir(parents=True, exist_ok=True)
    previous_timeout = socket.getdefaulttimeout()
    socket.setdefaulttimeout(600)
    try:
        with (
            urllib.request.urlopen("https://ffmpeg.org/releases/ffmpeg-7.1.5.tar.xz") as response,
            destination.open("wb") as handle,
        ):
            shutil.copyfileobj(response, handle)
    except urllib.error.URLError as exc:
        raise FfmpegLgplError(f"Failed to download {FFMPEG_TARBALL_URL}: {exc}") from exc
    finally:
        socket.setdefaulttimeout(previous_timeout)


def extract_tarball(tarball_path: Path, destination_dir: Path) -> Path:
    """Extract the FFmpeg source tree and return its root directory."""
    destination_dir.mkdir(parents=True, exist_ok=True)
    with tarfile.open(tarball_path, mode="r:xz") as archive:
        # "data" rejects path traversal and special files in a downloaded archive.
        archive.extractall(path=destination_dir, filter="data")
    source_root = destination_dir / f"ffmpeg-{FFMPEG_VERSION}"
    if not source_root.is_dir():
        raise FfmpegLgplError(
            f"Expected extracted directory {source_root} after unpacking"
        )
    return source_root


def ffmpeg_exe_name() -> str:
    return "ffmpeg.exe" if os.name == "nt" else "ffmpeg"


def pyinstaller_data_entry(source: Path, dest_name: str) -> tuple[str, str, str]:
    """Return a post-Analysis ``a.datas`` entry ``(dest_name, source, "DATA")``.

    ``COLLECT`` passes that list to ``normalize_toc``, which unpacks 3-tuples.
    A hook-style ``(source, dest_dir)`` pair aborts the freeze.
    """
    return (dest_name.replace("\\", "/"), str(source.resolve()), "DATA")


def configure_command() -> list[str]:
    """Return the argv that runs the FFmpeg ``configure`` script.

    On Windows the CI interpreter is native CPython, even inside an MSYS2
    shell. ``CreateProcess`` cannot execute the extensionless POSIX script,
    so the script is started through ``sh.exe``. ``make`` is a native
    executable and stays a direct argv.
    """
    if os.name == "nt":
        return ["sh", "configure", *CONFIGURE_ARGS]
    return ["./configure", *CONFIGURE_ARGS]


def _run_checked(
    command: list[str],
    *,
    cwd: Path,
    env: dict[str, str] | None = None,
) -> None:
    """Run ``command`` and raise :class:`FfmpegLgplError` instead of a traceback."""
    try:
        subprocess.run(command, cwd=cwd, env=env, check=True)
    except subprocess.CalledProcessError as exc:
        raise FfmpegLgplError(
            f"Command failed with exit {exc.returncode}: {command[0]}"
        ) from exc
    except OSError as exc:
        raise FfmpegLgplError(f"Command failed to start: {command[0]}: {exc}") from exc


def run_configure_and_build(source_root: Path) -> Path:
    """Run ``configure`` and ``make`` in ``source_root``; return built ``ffmpeg`` path."""
    env = os.environ.copy()
    configure_cmd = configure_command()
    LOGGER.info("Running %s in %s", CONFIGURE_LINE, source_root)
    _run_checked(configure_cmd, cwd=source_root, env=env)
    try:
        cpu_count = os.cpu_count() or 1
    except NotImplementedError:
        cpu_count = 1
    LOGGER.info("Running make -j%s in %s", cpu_count, source_root)
    _run_checked(["make", f"-j{cpu_count}"], cwd=source_root)
    built = source_root / ffmpeg_exe_name()
    if not built.is_file():
        raise FfmpegLgplError(f"Build did not produce {built}")
    return built


def capture_ffmpeg_tool_output(ffmpeg_path: Path, args: list[str]) -> str:
    """Run ``ffmpeg_path`` with ``args`` and return decoded stdout."""
    try:
        completed = subprocess.run(
            [str(ffmpeg_path), *args],
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as exc:
        raise FfmpegLgplError(
            f"ffmpeg {' '.join(args)} failed with exit {exc.returncode}"
        ) from exc
    return completed.stdout


def stage_built_ffmpeg(
    built_ffmpeg: Path,
    source_root: Path,
    configuration_line: str,
) -> Path:
    """Replace ``build/ffmpeg-lgpl/`` with this build's executable, licenses, and manifest.

    The directory is removed first so a previous ``COPYING.LGPLv3`` cannot
    remain after a build whose configuration lacks ``--enable-version3``.
    """
    stage_dir = repo_root() / "build" / "ffmpeg-lgpl"
    if stage_dir.exists():
        shutil.rmtree(stage_dir)
    stage_dir.mkdir(parents=True)

    staged_exe = stage_dir / ffmpeg_exe_name()
    shutil.copy2(built_ffmpeg, staged_exe)
    if os.name != "nt":
        staged_exe.chmod(staged_exe.stat().st_mode | 0o111)

    lgpl21 = source_root / "COPYING.LGPLv2.1"
    if not lgpl21.is_file():
        raise FfmpegLgplError(f"Missing {lgpl21} in FFmpeg source tree")
    shutil.copy2(lgpl21, stage_dir / "COPYING.LGPLv2.1")

    if configuration_uses_lgplv3(configuration_line):
        lgpl3 = source_root / "COPYING.LGPLv3"
        if not lgpl3.is_file():
            raise FfmpegLgplError(
                "Configuration includes --enable-version3 but COPYING.LGPLv3 is missing"
            )
        shutil.copy2(lgpl3, stage_dir / "COPYING.LGPLv3")

    write_build_manifest(stage_dir, configuration_line)
    return staged_exe


def run_build(tarball_path: Path | None) -> int:
    """Download (optional), verify digest, compile, audit, and stage FFmpeg."""
    root = repo_root()
    cache_dir = root / "tmp" / "ffmpeg-lgpl-src"
    work_dir = root / "build" / "ffmpeg-lgpl-work"

    if tarball_path is None:
        tarball_path = cache_dir / FFMPEG_TARBALL_BASENAME
        if not tarball_path.is_file():
            download_tarball(tarball_path)

    verify_tarball_sha256(tarball_path)

    if work_dir.exists():
        shutil.rmtree(work_dir)
    source_root = extract_tarball(tarball_path, work_dir)

    built_ffmpeg = run_configure_and_build(source_root)

    version_stdout = capture_ffmpeg_tool_output(built_ffmpeg, ["-version"])
    encoders_stdout = capture_ffmpeg_tool_output(
        built_ffmpeg, ["-hide_banner", "-encoders"]
    )
    muxers_stdout = capture_ffmpeg_tool_output(
        built_ffmpeg, ["-hide_banner", "-muxers"]
    )
    configuration_line = audit_ffmpeg_outputs(
        version_stdout, encoders_stdout, muxers_stdout
    )

    staged = stage_built_ffmpeg(built_ffmpeg, source_root, configuration_line)
    LOGGER.info("Staged LGPL ffmpeg at %s", staged)
    return 0


def run_audit(
    version_text: str,
    encoders_text: str,
    muxers_text: str,
) -> int:
    """Audit captured FFmpeg stdout without compiling."""
    audit_ffmpeg_outputs(version_text, encoders_text, muxers_text)
    LOGGER.info("FFmpeg audit passed")
    return 0


def _read_text_file(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build or audit a pinned LGPL FFmpeg CLI for release bundles.",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Log informational messages to stderr",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    audit_parser = subparsers.add_parser(
        "audit",
        help="Audit captured ffmpeg -version / -encoders / -muxers (no network, no compile)",
    )
    audit_parser.add_argument(
        "--audit-only",
        action="store_true",
        help="Alias for the audit subcommand (ignored; present for CI/doc symmetry)",
    )
    audit_parser.add_argument(
        "--version-file",
        type=Path,
        required=True,
        help="File containing stdout of ffmpeg -version",
    )
    audit_parser.add_argument(
        "--encoders-file",
        type=Path,
        required=True,
        help="File containing stdout of ffmpeg -hide_banner -encoders",
    )
    audit_parser.add_argument(
        "--muxers-file",
        type=Path,
        required=True,
        help="File containing stdout of ffmpeg -hide_banner -muxers",
    )

    build_parser = subparsers.add_parser(
        "build",
        help="Download, digest-check, configure, compile, audit, and stage ffmpeg",
    )
    build_parser.add_argument(
        "--tarball",
        type=Path,
        default=None,
        help=(
            "Use an existing ffmpeg tarball path instead of downloading to tmp/ "
            f"(digest must still match {FFMPEG_TARBALL_SHA256})"
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s: %(message)s",
        stream=sys.stderr,
    )
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    if not args.verbose:
        LOGGER.setLevel(logging.WARNING)

    try:
        if args.command == "audit":
            return run_audit(
                _read_text_file(args.version_file),
                _read_text_file(args.encoders_file),
                _read_text_file(args.muxers_file),
            )
        if args.command == "build":
            return run_build(args.tarball)
    except FfmpegLgplError as exc:
        LOGGER.error("%s", exc)
        return 1
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
