"""
Overlay bitmap → graphics primitive helpers for annotation overlays.

Extracted from ``AnnotationManager._convert_overlay_bitmap_to_graphics`` to clear
Sonar ``python:S3776`` (cognitive complexity) while preserving DICOM LSB-first bit
unpacking, coordinate mapping, and OpenCV/scipy path extraction fallbacks.

Inputs:
    - Overlay bitmap payload (bytes, pydicom DataElement, list/tuple, etc.)
    - Column/row dimensions and image-space origin offsets

Outputs:
    - ``coordinates``: list of ``(x, y)`` pixel centers
    - ``paths``: list of polylines for connected components / contours

Requirements:
    - NumPy (primary path); optional OpenCV or scipy.ndimage for paths
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from utils.log_sanitizer import sanitized_format_exc


def extract_overlay_bytes(overlay_data: Any) -> tuple[bytes | None, bool]:
    """
    Normalize overlay payload to raw bytes.

    Returns:
        ``(bytes, conversion_failed)``. When ``conversion_failed`` is True the
        caller should return an empty result. ``bytes`` may be empty when the
        payload is valid but carries no byte buffer (list/tuple path).
    """
    if hasattr(overlay_data, "value"):
        return overlay_data.value, False
    if isinstance(overlay_data, (bytes, bytearray)):
        return bytes(overlay_data), False
    try:
        return bytes(overlay_data), False
    except Exception:
        return None, True


def overlay_bitmap_from_bytes(
    overlay_bytes: bytes,
    cols: int,
    rows: int,
    np: Any,
) -> Any | None:
    """Unpack LSB-first DICOM overlay bytes into a ``(rows, cols)`` uint8 bitmap."""
    num_bits = cols * rows
    num_bytes = (num_bits + 7) // 8

    if len(overlay_bytes) < num_bytes:
        num_bytes = len(overlay_bytes)
        num_bits = num_bytes * 8
        if num_bits > cols * rows:
            num_bits = cols * rows

    # DICOM overlay data uses LSB-first bit order per DICOM standard Part 5, Chapter 8
    bit_array = np.unpackbits(
        np.frombuffer(overlay_bytes[:num_bytes], dtype=np.uint8),
        bitorder="little",
    )
    if len(bit_array) >= num_bits:
        return bit_array[:num_bits].reshape((rows, cols))
    return None


def overlay_bitmap_from_non_bytes(
    overlay_data: Any,
    cols: int,
    rows: int,
    np: Any,
) -> Any | None:
    """Build a bitmap from list/tuple or other array-like overlay payload."""
    if isinstance(overlay_data, (list, tuple)):
        bitmap = np.array(overlay_data, dtype=np.uint8)
        if bitmap.size == cols * rows:
            return bitmap.reshape((rows, cols))
        return None
    try:
        bitmap = np.array(overlay_data, dtype=np.uint8)
        if bitmap.size == cols * rows:
            return bitmap.reshape((rows, cols))
        return None
    except Exception:
        return None


def resolve_overlay_numpy_bitmap(
    overlay_data: Any,
    cols: int,
    rows: int,
    np: Any,
) -> Any | None:
    """Resolve overlay payload to a numpy bitmap, or None when conversion fails."""
    overlay_bytes, conversion_failed = extract_overlay_bytes(overlay_data)
    if conversion_failed:
        return None
    if overlay_bytes:
        return overlay_bitmap_from_bytes(overlay_bytes, cols, rows, np)
    return overlay_bitmap_from_non_bytes(overlay_data, cols, rows, np)


def overlay_pixel_to_image_coords(
    row: int,
    col: int,
    origin_x: float,
    origin_y: float,
) -> tuple[float, float]:
    """Map bitmap row/column indices to image-space coordinates."""
    return float(col) + origin_x, float(row) + origin_y


def overlay_coordinates_from_bitmap(
    bitmap: Any,
    origin_x: float,
    origin_y: float,
    np: Any,
) -> list[tuple[float, float]]:
    """Collect image coordinates for every set pixel in the bitmap."""
    set_pixels = np.argwhere(bitmap > 0)
    if len(set_pixels) == 0:
        return []
    coordinates: list[tuple[float, float]] = []
    for pixel in set_pixels:
        row, col = pixel[0], pixel[1]
        coordinates.append(overlay_pixel_to_image_coords(row, col, origin_x, origin_y))
    return coordinates


def overlay_paths_from_opencv(
    bitmap: Any,
    origin_x: float,
    origin_y: float,
    np: Any,
    cv2: Any,
) -> list[list[tuple[float, float]]]:
    """Extract closed contour paths via OpenCV ``findContours`` / ``approxPolyDP``."""
    paths: list[list[tuple[float, float]]] = []
    contours, _ = cv2.findContours(
        (bitmap > 0).astype(np.uint8) * 255,
        cv2.RETR_EXTERNAL,
        cv2.CHAIN_APPROX_SIMPLE,
    )
    for contour in contours:
        if len(contour) < 3:
            continue
        simplified = cv2.approxPolyDP(contour, 0.5, closed=True)
        path_coords: list[tuple[float, float]] = []
        for point in simplified:
            col = point[0][0]
            row = point[0][1]
            path_coords.append(overlay_pixel_to_image_coords(row, col, origin_x, origin_y))
        if len(path_coords) >= 2:
            paths.append(path_coords)
    return paths


def overlay_paths_from_scipy(
    bitmap: Any,
    origin_x: float,
    origin_y: float,
    np: Any,
    ndimage: Any,
) -> list[list[tuple[float, float]]]:
    """Extract component boundary paths via scipy connected-components labeling."""
    paths: list[list[tuple[float, float]]] = []
    labeled, num_features = ndimage.label(bitmap > 0)
    for label_id in range(1, num_features + 1):
        component_pixels = np.argwhere(labeled == label_id)
        if len(component_pixels) < 3:
            continue
        component_pixels = component_pixels[
            np.lexsort((component_pixels[:, 1], component_pixels[:, 0]))
        ]
        if len(component_pixels) > 100:
            step = max(1, len(component_pixels) // 100)
            component_pixels = component_pixels[::step]
        path_coords: list[tuple[float, float]] = []
        for pixel in component_pixels:
            row, col = pixel[0], pixel[1]
            path_coords.append(overlay_pixel_to_image_coords(row, col, origin_x, origin_y))
        if len(path_coords) >= 2:
            paths.append(path_coords)
    return paths


def overlay_paths_from_bitmap(
    bitmap: Any,
    origin_x: float,
    origin_y: float,
    np: Any,
    log_debug: Callable[[str], None] | None = None,
    import_module: Callable[[str], Any] | None = None,
) -> list[list[tuple[float, float]]]:
    """Try OpenCV contour extraction, then scipy labeling; return [] when unavailable."""
    if import_module is None:
        import importlib

        import_module = importlib.import_module
    try:
        try:
            cv2 = import_module("cv2")
            return overlay_paths_from_opencv(bitmap, origin_x, origin_y, np, cv2)
        except ImportError:
            ndimage = import_module("scipy.ndimage")
            return overlay_paths_from_scipy(bitmap, origin_x, origin_y, np, ndimage)
    except ImportError:
        return []
    except Exception:
        if log_debug is not None:
            log_debug(sanitized_format_exc())
        return []


def overlay_coordinates_no_numpy(
    overlay_data: Any,
    cols: int,
    rows: int,
    origin_x: float,
    origin_y: float,
) -> list[tuple[float, float]]:
    """Byte-by-byte fallback when NumPy is unavailable (MSB-first within each byte)."""
    coordinates: list[tuple[float, float]] = []
    if isinstance(overlay_data, bytes):
        byte_idx = 0
        bit_idx = 0
        for row in range(rows):
            for col in range(cols):
                if byte_idx < len(overlay_data):
                    byte_val = overlay_data[byte_idx]
                    bit_val = (byte_val >> (7 - bit_idx)) & 1
                    if bit_val:
                        coordinates.append(
                            overlay_pixel_to_image_coords(row, col, origin_x, origin_y)
                        )
                    bit_idx += 1
                    if bit_idx >= 8:
                        bit_idx = 0
                        byte_idx += 1
    return coordinates


def convert_overlay_bitmap_to_graphics(
    overlay_data: Any,
    cols: int,
    rows: int,
    origin_x: float,
    origin_y: float,
    log_debug: Callable[[str], None] | None = None,
    import_module: Callable[[str], Any] | None = None,
) -> dict[str, Any]:
    """
    Convert overlay bitmap data to graphics primitives.

    Returns a dict with ``coordinates`` (point list) and ``paths`` (polyline list).
    """
    coordinates: list[tuple[float, float]] = []
    paths: list[list[tuple[float, float]]] = []
    try:
        import numpy as np

        bitmap = resolve_overlay_numpy_bitmap(overlay_data, cols, rows, np)
        if bitmap is None:
            return {"coordinates": [], "paths": []}

        set_pixels = np.argwhere(bitmap > 0)
        if len(set_pixels) == 0:
            return {"coordinates": [], "paths": []}

        coordinates = overlay_coordinates_from_bitmap(bitmap, origin_x, origin_y, np)
        paths = overlay_paths_from_bitmap(
            bitmap,
            origin_x,
            origin_y,
            np,
            log_debug=log_debug,
            import_module=import_module,
        )
    except ImportError:
        coordinates = overlay_coordinates_no_numpy(
            overlay_data, cols, rows, origin_x, origin_y
        )
    except Exception:
        if log_debug is not None:
            log_debug(sanitized_format_exc())

    return {"coordinates": coordinates, "paths": paths}
