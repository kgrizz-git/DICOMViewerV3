"""
PyLinac subclasses used by DICOM Viewer V3 for ACR CT and ACR MRI Large.

1. **Relaxed image extent** — ``CatPhanBase._is_within_image_extent`` in stock
   pylinac only allows slice indices strictly between 1 and num_images-2, so
   auto-detection on slice 0, 1, or the last image always fails. The viewer
   always uses subclasses that accept any index in ``0 <= idx < num_images``.

2. **Optional physical scan extent tolerance** — when
   ``_scan_extent_tolerance_mm > 0``, z-coverage is checked with a widened
   range (same as before). When tolerance is 0, physical extent uses the
   stock CatPhanBase implementation (``super()``) so only image-extent
   behavior differs from upstream.

``ACRCTRelaxedExtent`` / ``ACRMRILargeRelaxedExtent`` remain as aliases of the
viewer classes for compatibility with older imports.
"""

from __future__ import annotations

from pylinac import ACRCT, ACRMRILarge

from qa.analysis_types import physical_scan_extent_passes_relaxed


class _RelaxedImageExtentMixin:
    """
    Accept origin / HU-localization on any in-range slice index.

    Stock pylinac requires ``1 < image_num < num_images - 1``; this mixin
    uses ``0 <= image_num < num_images`` so edge slices work for auto and
    manual ``origin_slice``.
    """

    def _is_within_image_extent(self, image_num: int) -> bool:
        n = int(image_num)
        n_img = int(self.num_images)
        if 0 <= n < n_img:
            return True
        raise ValueError(
            "The determined image number is out of range for the loaded stack "
            f"(index {n}, num_images {n_img})."
        )


class _RelaxedPhysicalScanExtentMixin:
    """
    Optional mm tolerance on DICOM z bounds vs module offsets.

    Set ``_scan_extent_tolerance_mm`` on the instance before ``analyze()``
    (done by the runner). When 0, delegate to stock CatPhanBase check.
    """

    _scan_extent_tolerance_mm: float = 0.0

    def _ensure_physical_scan_extent(self) -> bool:
        eps = float(getattr(self, "_scan_extent_tolerance_mm", 0.0) or 0.0)
        if eps <= 0:
            return super()._ensure_physical_scan_extent()

        from pylinac.core.image import z_position

        z_positions = [z_position(m) for m in self.dicom_stack.metadatas]
        min_scan_extent_slice = round(min(z_positions), 1)
        max_scan_extent_slice = round(max(z_positions), 1)
        min_config_extent_slice = round(min(self._module_offsets()), 1)
        max_config_extent_slice = round(max(self._module_offsets()), 1)
        return physical_scan_extent_passes_relaxed(
            min_scan_extent_slice,
            max_scan_extent_slice,
            min_config_extent_slice,
            max_config_extent_slice,
            eps,
        )


class ACRCTForViewer(
    _RelaxedImageExtentMixin,
    _RelaxedPhysicalScanExtentMixin,
    ACRCT,
):
    """ACR CT with viewer image-extent rule and optional scan-extent tolerance."""


class ACRMRILargeForViewer(
    _RelaxedImageExtentMixin,
    _RelaxedPhysicalScanExtentMixin,
    ACRMRILarge,
):
    """ACR MRI Large with viewer image-extent rule and optional scan-extent tolerance."""


ACRCTRelaxedExtent = ACRCTForViewer
ACRMRILargeRelaxedExtent = ACRMRILargeForViewer
