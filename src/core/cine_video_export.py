"""
Cine video export — frame index math, per-frame rasterization, and imageio encoding.

Builds deterministic frame lists from cine loop bounds, renders each frame with the
same LUT / photometric / projection / overlay path as :class:`core.export_manager.ExportManager`
PNG export (no ``grab()``), then writes **GIF** / **AVI** / **MP4** / **MPG** via **imageio** +
**imageio-ffmpeg** (FFmpeg subprocess with **no** ``shell=True``).

**Codecs (Windows 11 Media Player):** **GIF** uses imageio’s Pillow-backed writer; per-frame
delay is **milliseconds** (:func:`gif_frame_duration_milliseconds`) per the Pillow plugin API.
**AVI** and **MP4** use **MPEG-4 Part 2** (``mpeg4``) with **YUV 4:2:0** — not motion-JPEG /
PNG-in-AVI (**MPNG**). **MP4** adds ``-movflags +faststart`` so metadata is front-loaded for
players that stream from disk. Microsoft documents in-the-box **Media Player** support for
``.mp4`` with **MPEG-4** video; **``.mpg`` is treated as MPEG-1/2** in that matrix and
typically needs the free **MPEG-2 Video Extension** from the Store, so **MPG** here uses
canonical **MPEG-2** in a program stream (FFmpeg ``mpeg2video``) for standards-minded
archives and apps that have the extension — use **MP4** or **AVI** on stock Windows 11 if
you need playback without installing that add-on. This module does **not** write **H.264**
(**libx264** / AVC) by default (patent and redistribution policy vary; see **AGENTS.md** /
**CHANGELOG**).

Inputs:
    - ``Dataset`` per frame, ``studies`` map, window/level, optional ROI/overlay managers.

Outputs:
    - Video files on disk; optional temporary PNG frames (caller cleans up).

Requirements:
    - Pillow, numpy, pydicom, **imageio**, **imageio-ffmpeg**; ``core.dicom_processor``,
      ``core.export_rendering``.
"""

from __future__ import annotations

import os
import shutil
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple, cast

import imageio.v2 as imageio
import numpy as np
from PIL import Image
from pydicom.dataset import Dataset

from core import export_rendering as _er
from core.dicom_processor import DICOMProcessor


def clamp_int(value: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, value))


def build_cine_export_frame_indices(
    total_slices: int,
    loop_start_frame: Optional[int],
    loop_end_frame: Optional[int],
    use_cine_loop_bounds: bool,
) -> List[int]:
    """
    Return inclusive frame indices to export in order.

    If ``use_cine_loop_bounds`` is False, exports ``0 .. total_slices - 1``.
    If True, uses ``loop_start_frame`` / ``loop_end_frame`` (same semantics as
    :class:`gui.cine_player.CinePlayer`), clamped to the valid range.
    """
    if total_slices <= 0:
        return []
    last = total_slices - 1
    if not use_cine_loop_bounds:
        return list(range(total_slices))
    ls = int(loop_start_frame) if loop_start_frame is not None else 0
    le = int(loop_end_frame) if loop_end_frame is not None else last
    ls = clamp_int(ls, 0, last)
    le = clamp_int(le, 0, last)
    if le < ls:
        ls, le = le, ls
    return list(range(ls, le + 1))


def effective_fps_for_encoder(video_format: str, requested_fps: float) -> float:
    """Clamp FPS to a sane range for FFmpeg / GIF writers."""
    fps = float(requested_fps)
    if fps <= 0:
        fps = 10.0
    return float(max(1.0, min(fps, 120.0)))


def gif_frame_duration_milliseconds(video_format: str, requested_fps: float) -> float:
    """
    Per-frame display duration (**milliseconds**) for GIF export.

    ImageIO routes GIF writes through the **Pillow** v3 plugin, whose ``duration`` argument
    is in **ms** (see imageio ``pillow.py`` — passing seconds is interpreted as sub‑1 ms
    delays and many viewers clamp all frames to the same minimum interval).

    Uses the same FPS clamp as :func:`effective_fps_for_encoder` so the dialog /
    :class:`CineVideoEncodeThread` FPS matches GIF metadata.
    """
    eff = effective_fps_for_encoder(video_format, requested_fps)
    return 1000.0 / max(eff, 1e-6)


def ffmpeg_codec_and_params_for_cine_container(video_format: str) -> Tuple[str, List[str]]:
    """
    Return ``(codec, ffmpeg_params)`` for FFmpeg-backed cine containers.

    ``video_format`` is ``\"AVI\"``, ``\"MP4\"``, or ``\"MPG\"`` (case-insensitive).
    GIF is not handled here — callers use the dedicated GIF writer.

    Raises:
        ValueError: if the format is not AVI, MP4, or MPG.
    """
    fmt = str(video_format).strip().upper()
    if fmt == "AVI":
        # MPEG-4 Part 2 in AVI — broadly supported on Windows vs. PNG/MJPEG-in-AVI (MPNG).
        return ("mpeg4", ["-pix_fmt", "yuv420p"])
    if fmt == "MP4":
        # MPEG-4 Part 2 in MP4 — matches Windows 11 Media Player “MPEG-4” in-box path for .mp4.
        return ("mpeg4", ["-pix_fmt", "yuv420p", "-movflags", "+faststart"])
    if fmt == "MPG":
        # MPEG-2 in MPEG program stream — conventional .mpg. Windows 11 Media Player lists
        # .mpg under MPEG-1/2 and commonly requires the Store **MPEG-2 Video Extension**;
        # putting MPEG-4 video in .mpg still fails there, so prefer **MP4**/**AVI** for MPEG-4.
        return ("mpeg2video", ["-f", "mpeg", "-pix_fmt", "yuv420p"])
    raise ValueError(f"No FFmpeg codec mapping for format: {video_format!r}")


def rasterize_cine_export_frame(
    dataset: Dataset,
    studies: Dict[str, Dict[str, List[Dataset]]],
    study_uid: str,
    series_uid: str,
    slice_index: int,
    total_slices: int,
    window_level_option: str,
    current_window_center: Optional[float],
    current_window_width: Optional[float],
    include_overlays: bool,
    use_rescaled_values: bool,
    roi_manager: Any,
    overlay_manager: Any,
    measurement_tool: Any,
    config_manager: Any,
    text_annotation_tool: Any,
    arrow_annotation_tool: Any,
    projection_enabled: bool,
    projection_type: str,
    projection_slice_count: int,
    export_scale: float = 1.0,
    scale_annotations_with_image: bool = False,
    subwindow_annotation_managers: Optional[List[Dict[str, Any]]] = None,
) -> Optional[Image.Image]:
    """
    Rasterize one frame like PNG export (window/level, photometric, projection, overlays).

    Must be called from the **Qt main thread** when overlays reference live managers.
    """
    window_center = None
    window_width = None
    if (
        window_level_option == "current"
        and current_window_center is not None
        and current_window_width is not None
    ):
        window_center = current_window_center
        window_width = current_window_width

    is_projection_image = False
    if projection_enabled and studies and study_uid and series_uid and slice_index is not None:
        image = _er.create_projection_for_export(
            dataset,
            studies,
            study_uid,
            series_uid,
            slice_index,
            projection_type,
            projection_slice_count,
            window_center,
            window_width,
            use_rescaled_values,
        )
        if image is None:
            image = DICOMProcessor.dataset_to_image(
                dataset,
                window_center=window_center,
                window_width=window_width,
                apply_rescale=use_rescaled_values,
            )
        else:
            is_projection_image = True
    else:
        image = DICOMProcessor.dataset_to_image(
            dataset,
            window_center=window_center,
            window_width=window_width,
            apply_rescale=use_rescaled_values,
        )

    if image is None:
        return None

    if not is_projection_image:
        image = _er.process_image_by_photometric_interpretation(image, dataset)

    effective_scale = _er.effective_scale_for_image(image.width, image.height, export_scale)
    if effective_scale > 1.0:
        new_width = int(image.width * effective_scale)
        new_height = int(image.height * effective_scale)
        image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)

    if include_overlays:
        image = _er.render_overlays_and_rois(
            image,
            dataset,
            roi_manager,
            overlay_manager,
            measurement_tool,
            config_manager,
            text_annotation_tool,
            arrow_annotation_tool,
            study_uid,
            series_uid,
            slice_index,
            total_slices,
            coordinate_scale=effective_scale,
            export_scale=effective_scale,
            scale_annotations_with_image=scale_annotations_with_image,
            projection_enabled=projection_enabled,
            projection_type=projection_type,
            projection_slice_count=projection_slice_count,
            studies=studies,
            subwindow_annotation_managers=subwindow_annotation_managers,
        )
    if image.mode not in ("RGB", "RGBA"):
        image = image.convert("RGB")
    elif image.mode == "RGBA":
        rgb = Image.new("RGB", image.size, (255, 255, 255))
        rgb.paste(image, mask=image.split()[3])
        image = rgb
    return image


def encode_cine_video_from_png_paths(
    png_paths: Sequence[Path],
    output_path: str,
    video_format: str,
    fps: float,
    cancel_event: Optional[threading.Event] = None,
) -> None:
    """
    Stream-encoded video: read each PNG and append to an imageio writer.

    Runs safely in a **background thread** (no Qt objects). Uses imageio's FFmpeg
    plugin (imageio-ffmpeg); subprocesses are created **without** ``shell=True``.

    Raises:
        RuntimeError: on missing inputs, cancel, or writer failures.
    """
    paths = [Path(p) for p in png_paths]
    if not paths:
        raise RuntimeError("No frames to encode.")
    fmt = video_format.upper()
    eff_fps = effective_fps_for_encoder(fmt, fps)

    if cancel_event and cancel_event.is_set():
        raise RuntimeError("Export cancelled.")

    if fmt == "GIF":
        duration_ms = gif_frame_duration_milliseconds(fmt, fps)
        writer = imageio.get_writer(
            output_path,
            format=cast(Any, "GIF"),
            mode="I",
            duration=duration_ms,
            loop=0,
        )
        try:
            for i, p in enumerate(paths):
                if cancel_event and cancel_event.is_set():
                    raise RuntimeError("Export cancelled.")
                arr = imageio.imread(str(p))
                if arr.ndim == 2:
                    arr = np.stack([arr] * 3, axis=-1)
                writer.append_data(arr)
        finally:
            writer.close()

    elif fmt in ("AVI", "MP4", "MPG"):
        vid_codec, vid_extra = ffmpeg_codec_and_params_for_cine_container(fmt)
        writer = imageio.get_writer(
            output_path,
            format=cast(Any, "FFMPEG"),
            mode="I",
            fps=eff_fps,
            codec=vid_codec,
            ffmpeg_params=vid_extra,
            ffmpeg_log_level="error",
        )
        try:
            for p in paths:
                if cancel_event and cancel_event.is_set():
                    raise RuntimeError("Export cancelled.")
                arr = imageio.imread(str(p))
                if arr.ndim == 2:
                    arr = np.stack([arr] * 3, axis=-1)
                writer.append_data(arr)
        finally:
            writer.close()
    else:
        raise RuntimeError(f"Unsupported video format: {video_format}")


def safe_remove_partial_output(path: str) -> None:
    """Delete a partially written file if it exists."""
    try:
        if os.path.isfile(path):
            os.remove(path)
    except OSError:
        pass


def cleanup_temp_frame_dir(temp_dir: Optional[str]) -> None:
    if temp_dir and os.path.isdir(temp_dir):
        shutil.rmtree(temp_dir, ignore_errors=True)


def describe_focused_cine_export_blocker(app: Any) -> Optional[str]:
    """
    If cine export should be disabled, return a short user-facing reason; else ``None``.

    Mirrors **Save MPR as DICOM** gating: wrong mode or non-cine-capable series.
    """
    idx = int(app.get_focused_subwindow_index())
    data = app.subwindow_data.get(idx, {})
    if bool(data.get("is_mpr")):
        return (
            "The focused window is an MPR view.\n"
            "Focus a multi-frame 2D series and try again."
        )
    study_uid = str(data.get("current_study_uid") or "")
    series_uid = str(data.get("current_series_uid") or "")
    studies = getattr(app, "current_studies", None)
    if not getattr(app, "cine_player", None):
        return "Cine export is not available."
    if not app.cine_player.is_cine_capable(studies, study_uid, series_uid):
        return (
            "The focused window has no multi-frame cine series to export.\n"
            "Load a series with multiple frames or slices first."
        )
    return None
