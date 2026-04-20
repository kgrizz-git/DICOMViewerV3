"""
Tests for cine video export helpers and imageio encoding (small synthetic frames).

Uses ``tmp_path`` only; output files are capped to a few KiB. FFmpeg writer
arguments are asserted via mocks where golden video blobs would be fragile.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from PIL import Image

from core.cine_video_export import (
    build_cine_export_frame_indices,
    effective_fps_for_encoder,
    encode_cine_video_from_png_paths,
    ffmpeg_codec_and_params_for_cine_container,
    gif_frame_duration_milliseconds,
)


def test_build_cine_export_frame_indices_full_range() -> None:
    assert build_cine_export_frame_indices(5, 1, 3, False) == [0, 1, 2, 3, 4]


def test_build_cine_export_frame_indices_loop_bounds() -> None:
    assert build_cine_export_frame_indices(10, 2, 5, True) == [2, 3, 4, 5]
    assert build_cine_export_frame_indices(5, 9, 0, True) == [0, 1, 2, 3, 4]


def test_build_cine_export_frame_indices_empty_total() -> None:
    assert build_cine_export_frame_indices(0, 0, 0, True) == []


def test_effective_fps_clamps_and_zero_defaults() -> None:
    assert effective_fps_for_encoder("GIF", 200.0) == 120.0
    assert effective_fps_for_encoder("AVI", 0.5) == 1.0
    assert effective_fps_for_encoder("GIF", 0.0) == 10.0
    assert effective_fps_for_encoder("GIF", -3.0) == 10.0


def test_gif_frame_duration_ms_matches_effective_fps() -> None:
    """GIF Pillow writer ``duration`` is in ms → ms * (fps/1000) should equal 1 s per frame cycle."""
    for req in (15.0, 0.0, 200.0):
        eff = effective_fps_for_encoder("GIF", req)
        d_ms = gif_frame_duration_milliseconds("GIF", req)
        assert abs((d_ms / 1000.0) * eff - 1.0) < 1e-9


def test_ffmpeg_codec_mappings() -> None:
    assert ffmpeg_codec_and_params_for_cine_container("avi") == (
        "mpeg4",
        ["-pix_fmt", "yuv420p"],
    )
    c4, p4 = ffmpeg_codec_and_params_for_cine_container("MP4")
    assert c4 == "mpeg4"
    assert "-pix_fmt" in p4 and "yuv420p" in p4
    assert "+faststart" in "".join(p4)
    c, p = ffmpeg_codec_and_params_for_cine_container("MPG")
    assert c == "mpeg2video"
    assert "-f" in p and "mpeg" in p
    assert "yuv420p" in p


def test_ffmpeg_codec_mapping_rejects_gif() -> None:
    with pytest.raises(ValueError):
        ffmpeg_codec_and_params_for_cine_container("GIF")


@pytest.mark.parametrize(
    "fmt,ext",
    [("GIF", ".gif"), ("AVI", ".avi"), ("MP4", ".mp4"), ("MPG", ".mpg")],
)
def test_encode_cine_video_from_png_paths_small(tmp_path: Path, fmt: str, ext: str) -> None:
    """Write 4 tiny PNGs and encode; assert non-empty output under size cap."""
    pngs = []
    for i in range(4):
        p = tmp_path / f"f{i:04d}.png"
        arr = np.zeros((12, 14, 3), dtype=np.uint8) + (i + 1) * 40
        Image.fromarray(arr, mode="RGB").save(p)
        pngs.append(p)
    out = tmp_path / f"out{ext}"
    encode_cine_video_from_png_paths(pngs, str(out), fmt, fps=10.0, cancel_event=None)
    assert out.is_file()
    size = out.stat().st_size
    assert size > 0
    assert size < 512 * 1024
    if fmt == "GIF":
        with open(out, "rb") as fh:
            assert fh.read(6) in (b"GIF87a", b"GIF89a")
    elif fmt == "AVI":
        with open(out, "rb") as fh:
            assert fh.read(4) == b"RIFF"
    elif fmt == "MPG":
        # MPEG-PS magic is not guaranteed at offset 0 across muxers; size gate above is the main assertion.
        assert size > 32


def test_avi_encode_requests_mpeg4_writer(tmp_path: Path) -> None:
    pngs = []
    for i in range(2):
        p = tmp_path / f"a{i}.png"
        Image.fromarray(np.zeros((8, 8, 3), dtype=np.uint8), mode="RGB").save(p)
        pngs.append(p)
    out = tmp_path / "x.avi"
    mock_writer = MagicMock()
    with patch("core.cine_video_export.imageio.get_writer", return_value=mock_writer) as gw:
        encode_cine_video_from_png_paths(pngs, str(out), "AVI", fps=12.0, cancel_event=None)
    kwargs = gw.call_args.kwargs
    assert kwargs.get("codec") == "mpeg4"
    assert kwargs.get("fps") == 12.0
    assert kwargs.get("ffmpeg_params") == ["-pix_fmt", "yuv420p"]
    mock_writer.append_data.assert_called()
    mock_writer.close.assert_called_once()


def test_mp4_encode_requests_mpeg4_faststart_writer(tmp_path: Path) -> None:
    pngs = []
    for i in range(2):
        p = tmp_path / f"m{i}.png"
        Image.fromarray(np.zeros((8, 8, 3), dtype=np.uint8), mode="RGB").save(p)
        pngs.append(p)
    out = tmp_path / "x.mp4"
    mock_writer = MagicMock()
    with patch("core.cine_video_export.imageio.get_writer", return_value=mock_writer) as gw:
        encode_cine_video_from_png_paths(pngs, str(out), "MP4", fps=18.0, cancel_event=None)
    kwargs = gw.call_args.kwargs
    assert kwargs.get("codec") == "mpeg4"
    assert kwargs.get("ffmpeg_params") == ["-pix_fmt", "yuv420p", "-movflags", "+faststart"]
    mock_writer.close.assert_called_once()


def test_mpg_encode_requests_mpeg2_ps_writer(tmp_path: Path) -> None:
    pngs = []
    for i in range(2):
        p = tmp_path / f"b{i}.png"
        Image.fromarray(np.zeros((8, 8, 3), dtype=np.uint8), mode="RGB").save(p)
        pngs.append(p)
    out = tmp_path / "x.mpg"
    mock_writer = MagicMock()
    with patch("core.cine_video_export.imageio.get_writer", return_value=mock_writer) as gw:
        encode_cine_video_from_png_paths(pngs, str(out), "MPG", fps=8.0, cancel_event=None)
    kwargs = gw.call_args.kwargs
    assert kwargs.get("codec") == "mpeg2video"
    assert kwargs.get("ffmpeg_params") == ["-f", "mpeg", "-pix_fmt", "yuv420p"]
    mock_writer.close.assert_called_once()


def test_gif_encode_passes_duration_from_fps(tmp_path: Path) -> None:
    pngs = []
    for i in range(2):
        p = tmp_path / f"g{i}.png"
        Image.fromarray(np.zeros((8, 8, 3), dtype=np.uint8), mode="RGB").save(p)
        pngs.append(p)
    out = tmp_path / "x.gif"
    mock_writer = MagicMock()
    with patch("core.cine_video_export.imageio.get_writer", return_value=mock_writer) as gw:
        encode_cine_video_from_png_paths(pngs, str(out), "GIF", fps=25.0, cancel_event=None)
    kwargs = gw.call_args.kwargs
    assert kwargs.get("duration") == pytest.approx(1000.0 / 25.0)
    mock_writer.close.assert_called_once()


def test_gif_file_frame_duration_metadata_scales_with_fps(tmp_path: Path) -> None:
    """Integration: Pillow reads per-frame ``duration`` in ms; slower FPS → longer delay."""
    delays: dict[float, int] = {}
    for fps in (10.0, 40.0):
        pngs = []
        for i in range(3):
            p = tmp_path / f"h{fps}_{i}.png"
            Image.fromarray(np.zeros((10, 10, 3), dtype=np.uint8), mode="RGB").save(p)
            pngs.append(p)
        out = tmp_path / f"anim_{fps}.gif"
        encode_cine_video_from_png_paths(pngs, str(out), "GIF", fps=fps, cancel_event=None)
        with Image.open(out) as im:
            im.seek(0)
            delays[fps] = int(im.info.get("duration", 0))
    assert delays[10.0] > delays[40.0]
