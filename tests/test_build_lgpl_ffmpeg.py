"""Unit tests for scripts/build_lgpl_ffmpeg.py audit and digest helpers."""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.build_lgpl_ffmpeg import (
    FFMPEG_TARBALL_SHA256,
    FFMPEG_TARBALL_URL,
    FfmpegAuditError,
    TarballDigestError,
    audit_ffmpeg_outputs,
    configure_command,
    find_forbidden_enable_flags,
    pyinstaller_binary_entry,
    pyinstaller_data_entry,
    stage_built_ffmpeg,
    verify_tarball_sha256,
)

_GOOD_CONFIG = (
    "--prefix=/usr/local --disable-gpl --disable-nonfree --disable-debug"
)


def _version_block(configuration: str) -> str:
    return (
        "ffmpeg version 7.1.5 Copyright (c) 2000-2025 the FFmpeg developers\n"
        f"configuration: {configuration}\n"
    )


def _encoders_block(*names: str) -> str:
    lines = ["Encoders:"]
    for name in names:
        lines.append(f" V..... {name:<16} description")
    return "\n".join(lines) + "\n"


def _muxers_block(*names: str) -> str:
    lines = ["File muxers:"]
    for name in names:
        lines.append(f" E..... {name:<16} description")
    return "\n".join(lines) + "\n"


def _passing_outputs(configuration: str = _GOOD_CONFIG) -> tuple[str, str, str]:
    return (
        _version_block(configuration),
        _encoders_block("mpeg4", "mpeg2video"),
        _muxers_block("mpeg"),
    )


@pytest.mark.parametrize(
    "flag",
    [
        "--enable-gpl",
        "--enable-nonfree",
        "--enable-libx264",
        "--enable-libx265",
        "--enable-postproc",
    ],
)
def test_forbidden_enable_flags_fail_audit(flag: str) -> None:
    version, encoders, muxers = _passing_outputs(
        f"--disable-debug {flag} --prefix=/tmp"
    )
    with pytest.raises(FfmpegAuditError, match="Forbidden configure flags"):
        audit_ffmpeg_outputs(version, encoders, muxers)


@pytest.mark.parametrize(
    "flag",
    [
        "--disable-gpl",
        "--disable-libx264",
        "--disable-postproc",
    ],
)
def test_disable_flags_do_not_fail_audit(flag: str) -> None:
    configuration = f"{_GOOD_CONFIG} {flag}"
    version, encoders, muxers = _passing_outputs(configuration)
    audit_ffmpeg_outputs(version, encoders, muxers)
    assert flag not in find_forbidden_enable_flags(configuration)


def test_missing_mpeg4_encoder_fails() -> None:
    version, _, muxers = _passing_outputs()
    encoders = _encoders_block("mpeg2video")
    with pytest.raises(FfmpegAuditError, match="Missing required encoders"):
        audit_ffmpeg_outputs(version, encoders, muxers)


def test_missing_mpeg2video_encoder_fails() -> None:
    version, _, muxers = _passing_outputs()
    encoders = _encoders_block("mpeg4")
    with pytest.raises(FfmpegAuditError, match="Missing required encoders"):
        audit_ffmpeg_outputs(version, encoders, muxers)


def test_missing_mpeg_muxer_fails() -> None:
    version, encoders, _ = _passing_outputs()
    muxers = _muxers_block("mp4")
    with pytest.raises(FfmpegAuditError, match="Missing required muxers"):
        audit_ffmpeg_outputs(version, encoders, muxers)


def test_verify_tarball_sha256_rejects_mismatch(tmp_path: Path) -> None:
    blob = tmp_path / "ffmpeg-7.1.5.tar.xz"
    blob.write_bytes(b"not a real tarball")
    with pytest.raises(TarballDigestError, match="SHA-256 mismatch"):
        verify_tarball_sha256(blob)


def test_verify_tarball_sha256_accepts_matching_digest(tmp_path: Path) -> None:
    blob = tmp_path / "ffmpeg-7.1.5.tar.xz"
    blob.write_bytes(b"fixture bytes for digest test")
    import hashlib

    digest = hashlib.sha256(blob.read_bytes()).hexdigest()
    verify_tarball_sha256(blob, expected_sha256=digest)


def test_pinned_digest_constant_is_lowercase_hex() -> None:
    assert len(FFMPEG_TARBALL_SHA256) == 64
    assert FFMPEG_TARBALL_SHA256.lower() == FFMPEG_TARBALL_SHA256


def test_pyinstaller_data_entry_is_dest_source_data(tmp_path: Path) -> None:
    """COLLECT unpacks 3-tuples. A (source, dest) pair crashes normalize_toc."""
    source = tmp_path / "ffmpeg"
    source.write_bytes(b"fake-ffmpeg")
    entry = pyinstaller_data_entry(source, "ffmpeg/ffmpeg")
    assert entry == ("ffmpeg/ffmpeg", str(source.resolve()), "DATA")
    binary = pyinstaller_binary_entry(source, "ffmpeg/ffmpeg")
    assert binary == ("ffmpeg/ffmpeg", str(source.resolve()), "BINARY")


def test_configure_command_uses_shell_on_windows(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("scripts.build_lgpl_ffmpeg.os.name", "nt")
    command = configure_command()
    assert command[0] == "sh"
    assert command[1] == "configure"
    assert "--disable-gpl" in command
    assert "--disable-autodetect" in command


def test_configure_command_is_direct_on_posix(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("scripts.build_lgpl_ffmpeg.os.name", "posix")
    command = configure_command()
    assert command[0] == "./configure"
    assert "--disable-gpl" in command
    assert "--disable-autodetect" in command


def test_stage_replaces_stale_lgplv3_notice(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A later build without --enable-version3 must not keep COPYING.LGPLv3."""
    monkeypatch.setattr("scripts.build_lgpl_ffmpeg.repo_root", lambda: tmp_path)
    source = tmp_path / "src"
    source.mkdir()
    (source / "COPYING.LGPLv2.1").write_text("lgpl-2.1\n", encoding="utf-8")
    (source / "COPYING.LGPLv3").write_text("lgpl-3\n", encoding="utf-8")
    built = tmp_path / "ffmpeg"
    built.write_bytes(b"fake-ffmpeg")

    stage_built_ffmpeg(built, source, "--enable-version3 --disable-gpl")
    stage = tmp_path / "build" / "ffmpeg-lgpl"
    assert (stage / "COPYING.LGPLv3").is_file()

    stage_built_ffmpeg(built, source, "--disable-gpl --disable-nonfree")
    assert (stage / "COPYING.LGPLv2.1").is_file()
    assert (stage / "ffmpeg").is_file()
    assert not (stage / "COPYING.LGPLv3").exists()


def test_urlopen_uses_the_pinned_tarball_url_literal() -> None:
    """The download call must pass the pinned URL as a literal, not a name.

    Semgrep's dynamic-urllib rule ignores a call only when ``urlopen`` has a
    single string-literal argument. ``timeout=`` and ``nosemgrep`` both still
    produce a SARIF result that GitHub code scanning alerts on.
    """
    source = Path("scripts/build_lgpl_ffmpeg.py").read_text(encoding="utf-8")
    assert f'urllib.request.urlopen("{FFMPEG_TARBALL_URL}")' in source
