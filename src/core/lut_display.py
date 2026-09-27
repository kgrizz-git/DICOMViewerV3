"""
Display-stage LUT: net inversion, then the look-up table, then a PIL image.

Order is fixed: window/level or normalize has already produced a uint8 array.
This module applies ``P_inv`` (MONOCHROME1, then the user invert flag on that
2-D array) and then ``apply_lut_to_uint8``. It does not window and it does not
fold polarity into the LUT. A color LUT expands to RGB only after both
inversions. ``lut=None`` returns the inverted bytes unchanged.

Inputs:
    - uint8 display arrays, photometric interpretation, user-invert flag, LUT

Outputs:
    - uint8 ``(H, W)`` or ``(H, W, 3)`` arrays, and PIL images in mode L or RGB

Requirements:
    - numpy, Pillow
    - core.lut_engine.LookUpTable, apply_lut_to_uint8
    - core.photometric_polarity.apply_monochrome1_polarity
"""

from __future__ import annotations

from typing import Any

import numpy as np
from PIL import Image

from core.lut_engine import LookUpTable, apply_lut_to_uint8
from core.photometric_polarity import apply_monochrome1_polarity


def apply_user_invert_and_lut(
    polarized_uint8: np.ndarray,
    *,
    image_inverted: bool = False,
    lut: LookUpTable | None = None,
) -> np.ndarray:
    """User-invert a 2-D array that already had MONOCHROME1 applied, then the LUT.

    Call ``apply_monochrome1_polarity`` first and keep that call at the display
    site. Both inversions are ``255 - array`` on uint8, so they cancel when
    both flags are set. The LUT runs after that and may expand to RGB.
    A color array (``ndim != 2``) is returned unchanged: it is not a grayscale
    LUT input, and the viewer inverts that PIL image afterwards.
    """
    if polarized_uint8.ndim != 2:
        return polarized_uint8
    if image_inverted:
        polarized_uint8 = 255 - polarized_uint8.astype(np.uint8)
    return apply_lut_to_uint8(polarized_uint8, lut)


def finalize_uint8_display(
    display_uint8: np.ndarray,
    *,
    photometric_interpretation: str | None,
    image_inverted: bool = False,
    lut: LookUpTable | None = None,
) -> np.ndarray:
    """MONOCHROME1, then user invert, then the LUT. Prefer the two calls at sites that must stay greppable."""
    polarized = apply_monochrome1_polarity(display_uint8, photometric_interpretation)
    return apply_user_invert_and_lut(
        polarized,
        image_inverted=image_inverted,
        lut=lut,
    )


def pil_from_display_array(display: np.ndarray) -> Image.Image:
    """Build a mode ``L`` or ``RGB`` image from a finalized display array."""
    if display.ndim == 2:
        return Image.fromarray(np.ascontiguousarray(display), mode="L")
    if display.ndim == 3 and display.shape[2] == 3:
        return Image.fromarray(np.ascontiguousarray(display), mode="RGB")
    return Image.fromarray(np.ascontiguousarray(display))


def grayscale_export_kwargs(dataset: Any, image_inverted: bool, lut: LookUpTable | None) -> dict[str, Any]:
    """Kwargs for a grayscale export render. Color DICOM skips the LUT and the baked invert."""
    from core.dicom_color import is_color_image

    color, _photometric = is_color_image(dataset)
    if color:
        return {"image_inverted": False, "lut": None}
    return {"image_inverted": bool(image_inverted), "lut": lut}


def invert_color_export_image(image: Image.Image, dataset: Any, image_inverted: bool) -> Image.Image:
    """User-invert a color export after photometric conversion. Grayscale already inverted."""
    if not image_inverted:
        return image
    from core.dicom_color import is_color_image

    color, _photometric = is_color_image(dataset)
    if color and image.mode in ("L", "RGB"):
        from PIL import ImageOps

        return ImageOps.invert(image)
    return image


def rgb_preview_image(display: np.ndarray) -> Image.Image:
    """Return an RGB preview. Grayscale stays gray; a color LUT is already RGB."""
    if display.ndim == 2:
        return pil_from_display_array(display).convert("RGB")
    return pil_from_display_array(display)
