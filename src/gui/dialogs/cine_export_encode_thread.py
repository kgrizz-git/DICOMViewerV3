"""
Background thread for cine video encoding (imageio / FFmpeg).

Reads temporary PNG frames written on the main thread and streams them into
GIF / AVI / MPG. Subprocesses are owned by imageio-ffmpeg (**no** ``shell=True``).

Inputs:
    - Ordered PNG paths, output path, format, FPS, optional ``threading.Event`` cancel flag.

Outputs:
    - Emits ``succeeded`` or ``failed(str)``; partial output file should be removed by caller on cancel/error.

Requirements:
    - PySide6 ``QThread``; ``core.cine_video_export.encode_cine_video_from_png_paths``.
"""

from __future__ import annotations

import threading
from pathlib import Path
from typing import List, Optional, Sequence

from PySide6.QtCore import QThread, Signal

from core.cine_video_export import encode_cine_video_from_png_paths


class CineVideoEncodeThread(QThread):
    """Encode PNG frame files to GIF / AVI / MPG in a worker thread."""

    succeeded = Signal()
    failed = Signal(str)

    def __init__(
        self,
        png_paths: Sequence[Path],
        output_path: str,
        video_format: str,
        fps: float,
        cancel_event: threading.Event,
    ) -> None:
        super().__init__()
        self._paths: List[Path] = [Path(p) for p in png_paths]
        self._output_path = output_path
        self._video_format = video_format
        self._fps = fps
        self._cancel_event = cancel_event

    def run(self) -> None:  # type: ignore[override]
        try:
            encode_cine_video_from_png_paths(
                self._paths,
                self._output_path,
                self._video_format,
                self._fps,
                self._cancel_event,
            )
        except Exception as exc:  # noqa: BLE001 — surface to UI
            self.failed.emit(str(exc))
            return
        if self._cancel_event.is_set():
            self.failed.emit("Export cancelled.")
            return
        self.succeeded.emit()
