"""Unit tests for scripts/build_lgpl_ffmpeg.py audit and digest helpers."""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.build_lgpl_ffmpeg import (
    FFMPEG_TARBALL_SHA256,
    FfmpegAuditError,
    TarballDigestError,
    audit_ffmpeg_outputs,
    find_forbidden_enable_flags,
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
