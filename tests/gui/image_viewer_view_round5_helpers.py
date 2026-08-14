"""Shared synthetic image/viewer builders for split image-viewer coverage tests."""

from __future__ import annotations

from PIL import Image

from gui.image_viewer import ImageViewer


def create_viewer(qapp, *, w: int = 400, h: int = 300) -> ImageViewer:
    """Create a visible offscreen viewer with a predictable viewport size."""
    viewer = ImageViewer()
    viewer.resize(w, h)
    viewer.show()
    return viewer


def create_image(
    mode: str = "L", size: tuple[int, int] = (64, 64), fill: int = 128
) -> Image.Image:
    """Create a small in-memory image in the requested grayscale or RGB mode."""
    if mode == "L":
        return Image.new("L", size, fill)
    return Image.new("RGB", size, (fill, fill, fill))
