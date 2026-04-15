"""
Tests for cine video export helpers and imageio encoding (small synthetic frames).

Uses ``tmp_path`` only; output files are capped to a few KiB.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from core.cine_video_export import (
    build_cine_export_frame_indices,
    encode_cine_video_from_png_paths,
)


def test_build_cine_export_frame_indices_full_range() -> None:
    assert build_cine_export_frame_indices(5, 1, 3, False) == [0, 1, 2, 3, 4]


def test_build_cine_export_frame_indices_loop_bounds() -> None:
    assert build_cine_export_frame_indices(10, 2, 5, True) == [2, 3, 4, 5]
    assert build_cine_export_frame_indices(5, 9, 0, True) == [0, 1, 2, 3, 4]


def test_build_cine_export_frame_indices_empty_total() -> None:
    assert build_cine_export_frame_indices(0, 0, 0, True) == []


@pytest.mark.parametrize("fmt,ext", [("GIF", ".gif"), ("AVI", ".avi"), ("MPG", ".mpg")])
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
