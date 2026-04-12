"""
Helpers for QGraphicsView transforms when zoom is composed with rotation and flip.

``transform().m11()`` is unreliable as a zoom scalar after 90°/270° rotation (m11 may
be ~0) or when horizontal flip makes m11 negative. ``ImageViewer`` keeps
``current_zoom`` as the authoritative positive scale; other views fall back to the
Euclidean norm of the 2×2 linear part of the transform.

Used when converting between viewport pixels and scene units for
``ItemIgnoresTransformations`` overlays (ROI stats, measurements, crosshairs,
corner metadata).
"""
from __future__ import annotations

import math
from typing import Any


def graphics_view_uniform_zoom(view: Any) -> float:
    """
    Return a positive uniform scale factor suitable for viewport ↔ scene pixel math.

    Scene delta ≈ viewport_pixels * (1 / return_value) for uniform zoom+rotate+flip
    composed as in ``ImageViewerViewMixin._apply_view_transform``.
    """
    z = getattr(view, "current_zoom", None)
    if isinstance(z, (int, float)) and z > 0:
        return float(z)
    t = view.transform()
    m11, m12 = float(t.m11()), float(t.m12())
    mag = math.hypot(m11, m12)
    if mag > 1e-9:
        return mag
    m21, m22 = float(t.m21()), float(t.m22())
    mag = math.hypot(m21, m22)
    return mag if mag > 1e-9 else 1.0
