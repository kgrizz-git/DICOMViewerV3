"""
Comprehensive unit tests for src/gui/cine_video_export.py.

Achieves 100% statement and branch coverage for cine_video_export module.
"""

import os
import shutil
import tempfile
import threading
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from PIL import Image
from pydicom.dataset import Dataset

from gui.cine_video_export import (
    CineFrameRequest,
    build_cine_export_frame_indices,
    clamp_int,
    cleanup_temp_frame_dir,
    describe_focused_cine_export_blocker,
    effective_fps_for_encoder,
    encode_cine_video_from_png_paths,
    ffmpeg_codec_and_params_for_cine_container,
    gif_frame_duration_milliseconds,
    rasterize_cine_export_frame,
    safe_remove_partial_output,
)


def test_clamp_int() -> None:
    """Test clamp_int function."""
    assert clamp_int(5, 0, 10) == 5
    assert clamp_int(-5, 0, 10) == 0
    assert clamp_int(15, 0, 10) == 10


def test_build_cine_export_frame_indices() -> None:
    """Test build_cine_export_frame_indices under various parameters."""
    # 1. Total slices <= 0
    assert build_cine_export_frame_indices(0, 0, 5, True) == []

    # 2. use_cine_loop_bounds = False
    assert build_cine_export_frame_indices(5, 1, 3, False) == [0, 1, 2, 3, 4]

    # 3. None loop bounds
    assert build_cine_export_frame_indices(5, None, None, True) == [0, 1, 2, 3, 4]

    # 4. Valid loop bounds
    assert build_cine_export_frame_indices(5, 1, 3, True) == [1, 2, 3]

    # 5. Inverted loop bounds (le < ls)
    assert build_cine_export_frame_indices(5, 3, 1, True) == [1, 2, 3]

    # 6. Out of range loop bounds
    assert build_cine_export_frame_indices(5, -2, 20, True) == [0, 1, 2, 3, 4]


def test_effective_fps_and_gif_duration() -> None:
    """Test effective_fps_for_encoder and gif_frame_duration_milliseconds."""
    assert effective_fps_for_encoder("MP4", -5.0) == 10.0
    assert effective_fps_for_encoder("MP4", 0.5) == 1.0
    assert effective_fps_for_encoder("MP4", 200.0) == 120.0
    assert effective_fps_for_encoder("MP4", 25.0) == 25.0

    # GIF frame duration calculation (10 FPS -> 100 ms)
    assert gif_frame_duration_milliseconds("GIF", 10.0) == 100.0


def test_ffmpeg_codec_and_params_for_cine_container() -> None:
    """Test container codec mappings and unsupported format exception."""
    assert ffmpeg_codec_and_params_for_cine_container("AVI") == (
        "mpeg4",
        ["-pix_fmt", "yuv420p"],
    )
    assert ffmpeg_codec_and_params_for_cine_container("mp4") == (
        "mpeg4",
        ["-pix_fmt", "yuv420p", "-movflags", "+faststart"],
    )
    assert ffmpeg_codec_and_params_for_cine_container("MPG") == (
        "mpeg2video",
        ["-f", "mpeg", "-pix_fmt", "yuv420p"],
    )

    with pytest.raises(ValueError, match="No FFmpeg codec mapping for format"):
        ffmpeg_codec_and_params_for_cine_container("MKV")


def _make_dummy_request(**kwargs) -> CineFrameRequest:
    """Helper to build a populated CineFrameRequest instance."""
    ds = Dataset()
    ds.SOPInstanceUID = "1.2.3"
    defaults = {
        "dataset": ds,
        "studies": {"study1": {"series1": [ds]}},
        "study_uid": "study1",
        "series_uid": "series1",
        "slice_index": 0,
        "total_slices": 10,
        "window_level_option": "default",
        "current_window_center": 40.0,
        "current_window_width": 400.0,
        "include_overlays": False,
        "use_rescaled_values": True,
        "roi_manager": None,
        "overlay_manager": None,
        "measurement_tool": None,
        "config_manager": None,
        "text_annotation_tool": None,
        "arrow_annotation_tool": None,
        "projection_enabled": False,
        "projection_type": "MIP",
        "projection_slice_count": 3,
        "export_scale": 1.0,
        "scale_annotations_with_image": False,
        "subwindow_annotation_managers": None,
    }
    defaults.update(kwargs)
    return CineFrameRequest(**defaults)


def test_rasterize_cine_export_frame() -> None:
    """Test rasterize_cine_export_frame with window/level, projections, scales, overlays, and image modes."""
    # 1. Image processor returns None
    req = _make_dummy_request()
    with patch(
        "gui.cine_video_export.DICOMProcessor.dataset_to_image", return_value=None
    ):
        assert rasterize_cine_export_frame(req) is None

    # 2. Standard image rendering with photometric processing and scale > 1.0
    img_l = Image.new("L", (100, 100), 128)
    req_scaled = _make_dummy_request(
        window_level_option="current",
        export_scale=2.0,
        include_overlays=True,
    )
    with (
        patch(
            "gui.cine_video_export.DICOMProcessor.dataset_to_image", return_value=img_l
        ),
        patch(
            "gui.cine_video_export._er.process_image_by_photometric_interpretation",
            return_value=img_l,
        ),
        patch(
            "gui.cine_video_export._er.render_overlays_and_rois",
            side_effect=lambda req: req.image,
        ),
    ):
        res = rasterize_cine_export_frame(req_scaled)
        assert res is not None
        assert res.size == (200, 200)
        assert res.mode == "RGB"

    # 3. Projection image rendering (is_projection_image = True)
    img_rgb = Image.new("RGB", (100, 100), (255, 0, 0))
    req_proj = _make_dummy_request(projection_enabled=True)
    with patch(
        "gui.cine_video_export._er.create_projection_for_export", return_value=img_rgb
    ):
        res_proj = rasterize_cine_export_frame(req_proj)
        assert res_proj is not None
        assert res_proj.mode == "RGB"

    # 4. Projection image rendering fallback when projection returns None
    with (
        patch(
            "gui.cine_video_export._er.create_projection_for_export", return_value=None
        ),
        patch(
            "gui.cine_video_export.DICOMProcessor.dataset_to_image",
            return_value=img_rgb,
        ),
        patch(
            "gui.cine_video_export._er.process_image_by_photometric_interpretation",
            return_value=img_rgb,
        ),
    ):
        res_fallback = rasterize_cine_export_frame(req_proj)
        assert res_fallback is not None

    # 5. RGBA image mode conversion to RGB
    img_rgba = Image.new("RGBA", (50, 50), (100, 100, 100, 255))
    req_rgba = _make_dummy_request()
    with (
        patch(
            "gui.cine_video_export.DICOMProcessor.dataset_to_image",
            return_value=img_rgba,
        ),
        patch(
            "gui.cine_video_export._er.process_image_by_photometric_interpretation",
            return_value=img_rgba,
        ),
    ):
        res_rgba = rasterize_cine_export_frame(req_rgba)
        assert res_rgba is not None
        assert res_rgba.mode == "RGB"


def test_encode_cine_video_from_png_paths() -> None:
    """Test encode_cine_video_from_png_paths for GIF, MP4/AVI/MPG, empty paths, 2D/3D arrays, and cancellation."""
    tmp = Path(tempfile.mkdtemp())
    try:
        p1 = tmp / "frame1.png"
        p2 = tmp / "frame2.png"
        p1.write_bytes(b"dummy")
        p2.write_bytes(b"dummy")

        # 1. Empty paths exception
        with pytest.raises(RuntimeError, match="No frames to encode"):
            encode_cine_video_from_png_paths([], "out.gif", "GIF", 10.0)

        # 2. Cancel event set before start
        cancel_evt = threading.Event()
        cancel_evt.set()
        with pytest.raises(RuntimeError, match="Export cancelled"):
            encode_cine_video_from_png_paths([p1], "out.gif", "GIF", 10.0, cancel_evt)

        # 3. GIF encoding with 2D and 3D (RGB) arrays
        mock_writer = MagicMock()
        arr_2d = np.zeros((10, 10), dtype=np.uint8)
        arr_3d = np.zeros((10, 10, 3), dtype=np.uint8)

        with (
            patch("gui.cine_video_export.imageio.get_writer", return_value=mock_writer),
            patch("gui.cine_video_export.imageio.imread", side_effect=[arr_2d, arr_3d]),
        ):
            encode_cine_video_from_png_paths([p1, p2], "out.gif", "GIF", 10.0)
            assert mock_writer.append_data.call_count == 2
            mock_writer.close.assert_called_once()

        # 4. GIF mid-loop cancellation (hits line 315)
        cancel_mid_gif = threading.Event()

        def side_effect_cancel_gif(*args, **kwargs):
            cancel_mid_gif.set()
            return arr_2d

        with (
            patch("gui.cine_video_export.imageio.get_writer", return_value=MagicMock()),
            patch(
                "gui.cine_video_export.imageio.imread",
                side_effect=side_effect_cancel_gif,
            ),
            pytest.raises(RuntimeError, match="Export cancelled"),
        ):
            encode_cine_video_from_png_paths(
                [p1, p2], "out.gif", "GIF", 10.0, cancel_mid_gif
            )

        # 5. MP4/AVI/MPG encoding with 2D and 3D arrays
        mock_writer_ffmpeg = MagicMock()
        with (
            patch(
                "gui.cine_video_export.imageio.get_writer",
                return_value=mock_writer_ffmpeg,
            ),
            patch("gui.cine_video_export.imageio.imread", side_effect=[arr_2d, arr_3d]),
        ):
            encode_cine_video_from_png_paths([p1, p2], "out.mp4", "MP4", 10.0)
            assert mock_writer_ffmpeg.append_data.call_count == 2
            mock_writer_ffmpeg.close.assert_called_once()

        # 6. MP4 mid-loop cancellation (hits line 337)
        cancel_mid_ff = threading.Event()

        def side_effect_cancel_ff(*args, **kwargs):
            cancel_mid_ff.set()
            return arr_2d

        with (
            patch("gui.cine_video_export.imageio.get_writer", return_value=MagicMock()),
            patch(
                "gui.cine_video_export.imageio.imread",
                side_effect=side_effect_cancel_ff,
            ),
            pytest.raises(RuntimeError, match="Export cancelled"),
        ):
            encode_cine_video_from_png_paths(
                [p1, p2], "out.mp4", "MP4", 10.0, cancel_mid_ff
            )

        # 7. Unsupported format exception
        with pytest.raises(RuntimeError, match="Unsupported video format: FLV"):
            encode_cine_video_from_png_paths([p1], "out.flv", "FLV", 10.0)

    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_safe_remove_partial_output_and_cleanup(tmp_path: Path) -> None:
    """Test safe_remove_partial_output and cleanup_temp_frame_dir."""
    tmp_file = str(tmp_path / "partial.out")
    Path(tmp_file).write_bytes(b"temp")

    safe_remove_partial_output(tmp_file)
    assert not os.path.exists(tmp_file)

    # Safe remove nonexistent file or permission error handling
    safe_remove_partial_output(tmp_file)

    with (
        patch("os.path.isfile", return_value=True),
        patch("os.remove", side_effect=OSError("Permission denied")),
    ):
        safe_remove_partial_output("error.file")

    # Cleanup temp dir
    tmp_dir = str(tmp_path / "frames")
    os.makedirs(tmp_dir)
    cleanup_temp_frame_dir(tmp_dir)
    assert not os.path.exists(tmp_dir)
    cleanup_temp_frame_dir(None)


def test_describe_focused_cine_export_blocker() -> None:
    """Test describe_focused_cine_export_blocker under various app states."""
    app = MagicMock()
    app.get_focused_subwindow_index.return_value = 0

    # 1. MPR view focused
    app.subwindow_data = {0: {"is_mpr": True}}
    assert "MPR view" in describe_focused_cine_export_blocker(app)

    # 2. Missing cine_player attribute
    app.subwindow_data = {
        0: {"is_mpr": False, "current_study_uid": "s1", "current_series_uid": "se1"}
    }
    app.cine_player = None
    assert "not available" in describe_focused_cine_export_blocker(app)

    # 3. Series is not cine-capable
    app.cine_player = MagicMock()
    app.cine_player.is_cine_capable.return_value = False
    assert "no multi-frame cine series" in describe_focused_cine_export_blocker(app)

    # 4. Series is cine-capable (no blocker)
    app.cine_player.is_cine_capable.return_value = True
    assert describe_focused_cine_export_blocker(app) is None


def test_inverted_loop_bounds_are_normalized_to_forward_order() -> None:
    """Cine export is forward-only and normalizes inverted bounds."""
    result = build_cine_export_frame_indices(5, 3, 1, True)
    assert result == [1, 2, 3]
    assert result != [3, 2, 1]


def test_encode_cine_video_forwards_rgba_writer_input() -> None:
    """The internal encoder forwards RGBA input; rasterization owns flattening."""
    tmp = Path(tempfile.mkdtemp())
    try:
        p1 = tmp / "rgba.png"
        p1.write_bytes(b"dummy")

        arr_rgba = np.zeros((10, 10, 4), dtype=np.uint8)
        mock_writer = MagicMock()

        with (
            patch("gui.cine_video_export.imageio.get_writer", return_value=mock_writer),
            patch("gui.cine_video_export.imageio.imread", return_value=arr_rgba),
        ):
            encode_cine_video_from_png_paths([p1], "out.mp4", "MP4", 10.0)

            passed_arr = mock_writer.append_data.call_args[0][0]
            assert passed_arr.shape == (10, 10, 4)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ---------------------------------------------------------------------------
# Integration tests (real imageio encoding, adopted from initial-commit suite)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "fmt,ext",
    [("GIF", ".gif"), ("AVI", ".avi"), ("MP4", ".mp4"), ("MPG", ".mpg")],
)
def test_encode_cine_video_small_integration(
    tmp_path: Path, fmt: str, ext: str
) -> None:
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
        assert size > 32


def test_avi_encode_requests_mpeg4_writer(tmp_path: Path) -> None:
    """Assert get_writer is called with correct codec/fps/ffmpeg_params for AVI."""
    pngs = []
    for i in range(2):
        p = tmp_path / f"a{i}.png"
        Image.fromarray(np.zeros((8, 8, 3), dtype=np.uint8), mode="RGB").save(p)
        pngs.append(p)
    out = tmp_path / "x.avi"
    mock_writer = MagicMock()
    with patch(
        "gui.cine_video_export.imageio.get_writer", return_value=mock_writer
    ) as gw:
        encode_cine_video_from_png_paths(
            pngs, str(out), "AVI", fps=12.0, cancel_event=None
        )
    kwargs = gw.call_args.kwargs
    assert kwargs.get("codec") == "mpeg4"
    assert kwargs.get("fps") == 12.0
    assert kwargs.get("ffmpeg_params") == ["-pix_fmt", "yuv420p"]
    mock_writer.append_data.assert_called()
    mock_writer.close.assert_called_once()


def test_mp4_encode_requests_mpeg4_faststart_writer(tmp_path: Path) -> None:
    """Assert get_writer is called with correct codec and +faststart for MP4."""
    pngs = []
    for i in range(2):
        p = tmp_path / f"m{i}.png"
        Image.fromarray(np.zeros((8, 8, 3), dtype=np.uint8), mode="RGB").save(p)
        pngs.append(p)
    out = tmp_path / "x.mp4"
    mock_writer = MagicMock()
    with patch(
        "gui.cine_video_export.imageio.get_writer", return_value=mock_writer
    ) as gw:
        encode_cine_video_from_png_paths(
            pngs, str(out), "MP4", fps=18.0, cancel_event=None
        )
    kwargs = gw.call_args.kwargs
    assert kwargs.get("codec") == "mpeg4"
    assert kwargs.get("ffmpeg_params") == [
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
    ]
    mock_writer.close.assert_called_once()


def test_mpg_encode_requests_mpeg2_ps_writer(tmp_path: Path) -> None:
    """Assert get_writer is called with mpeg2video codec for MPG."""
    pngs = []
    for i in range(2):
        p = tmp_path / f"b{i}.png"
        Image.fromarray(np.zeros((8, 8, 3), dtype=np.uint8), mode="RGB").save(p)
        pngs.append(p)
    out = tmp_path / "x.mpg"
    mock_writer = MagicMock()
    with patch(
        "gui.cine_video_export.imageio.get_writer", return_value=mock_writer
    ) as gw:
        encode_cine_video_from_png_paths(
            pngs, str(out), "MPG", fps=8.0, cancel_event=None
        )
    kwargs = gw.call_args.kwargs
    assert kwargs.get("codec") == "mpeg2video"
    assert kwargs.get("ffmpeg_params") == ["-f", "mpeg", "-pix_fmt", "yuv420p"]
    mock_writer.close.assert_called_once()


def test_gif_encode_passes_duration_kwarg_from_fps(tmp_path: Path) -> None:
    """Assert GIF get_writer receives duration in ms matching 1000/fps."""
    pngs = []
    for i in range(2):
        p = tmp_path / f"g{i}.png"
        Image.fromarray(np.zeros((8, 8, 3), dtype=np.uint8), mode="RGB").save(p)
        pngs.append(p)
    out = tmp_path / "x.gif"
    mock_writer = MagicMock()
    with patch(
        "gui.cine_video_export.imageio.get_writer", return_value=mock_writer
    ) as gw:
        encode_cine_video_from_png_paths(
            pngs, str(out), "GIF", fps=25.0, cancel_event=None
        )
    kwargs = gw.call_args.kwargs
    assert kwargs.get("duration") == pytest.approx(1000.0 / 25.0)
    mock_writer.close.assert_called_once()


def test_gif_frame_duration_ms_cross_validates_with_effective_fps() -> None:
    """gif_frame_duration_milliseconds * effective_fps_for_encoder should equal 1000 ms."""
    for req in (15.0, 0.0, 200.0):
        eff = effective_fps_for_encoder("GIF", req)
        d_ms = gif_frame_duration_milliseconds("GIF", req)
        assert abs((d_ms / 1000.0) * eff - 1.0) < 1e-9


def test_gif_file_frame_duration_metadata_scales_with_fps(tmp_path: Path) -> None:
    """Integration: Pillow per-frame duration in ms should be longer at lower FPS."""
    delays: dict[float, int] = {}
    for fps in (10.0, 40.0):
        pngs = []
        for i in range(3):
            p = tmp_path / f"h{fps}_{i}.png"
            Image.fromarray(np.zeros((10, 10, 3), dtype=np.uint8), mode="RGB").save(p)
            pngs.append(p)
        out = tmp_path / f"anim_{fps}.gif"
        encode_cine_video_from_png_paths(
            pngs, str(out), "GIF", fps=fps, cancel_event=None
        )
        with Image.open(out) as im:
            im.seek(0)
            delays[fps] = int(im.info.get("duration", 0))
    assert delays[10.0] > delays[40.0]
