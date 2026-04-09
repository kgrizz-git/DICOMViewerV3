"""
Optional pylinac subclasses that relax CatPhanBase._ensure_physical_scan_extent.

Used when the viewer requests a small tolerance (mm) on DICOM z bounds so
near-miss acquisitions can still analyze without mutating phantom offset
constants. Default analysis path uses stock ACRMRILarge / ACRCT classes.
"""

from __future__ import annotations

from pylinac import ACRCT, ACRMRILarge

from qa.analysis_types import physical_scan_extent_passes_relaxed


class _RelaxedPhysicalScanExtentMixin:
    """
    Override extent check. Set ``_scan_extent_tolerance_mm`` on the instance
    before calling ``analyze()`` (done by the runner).
    """

    _scan_extent_tolerance_mm: float = 0.0

    def _ensure_physical_scan_extent(self) -> bool:
        from pylinac.core.image import z_position

        z_positions = [z_position(m) for m in self.dicom_stack.metadatas]
        min_scan_extent_slice = round(min(z_positions), 1)
        max_scan_extent_slice = round(max(z_positions), 1)
        min_config_extent_slice = round(min(self._module_offsets()), 1)
        max_config_extent_slice = round(max(self._module_offsets()), 1)
        eps = float(getattr(self, "_scan_extent_tolerance_mm", 0.0) or 0.0)
        return physical_scan_extent_passes_relaxed(
            min_scan_extent_slice,
            max_scan_extent_slice,
            min_config_extent_slice,
            max_config_extent_slice,
            eps,
        )


class ACRMRILargeRelaxedExtent(_RelaxedPhysicalScanExtentMixin, ACRMRILarge):
    """ACR MRI Large with relaxed scan-extent gate (subclass, not a fork)."""


class ACRCTRelaxedExtent(_RelaxedPhysicalScanExtentMixin, ACRCT):
    """ACR CT with relaxed scan-extent gate (subclass, not a fork)."""
