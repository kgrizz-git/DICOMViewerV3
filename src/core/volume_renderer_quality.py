"""Target and temporary sample-distance operations shared by volume renderers."""

from __future__ import annotations

from typing import Any, Protocol, cast


class _QualityRenderer(Protocol):
    """Collaborators supplied by a concrete volume renderer."""

    QUALITY_MODES: list[tuple[str, float]]
    _mapper: Any
    _quality_sample_distance: float

    def _log_unknown_quality(self, mode_name: str) -> None:
        """Log an invalid quality name."""


class VolumeRendererQualityMixin:
    """Keep selected static quality separate from transient preview quality."""

    def _quality_renderer(self) -> _QualityRenderer:
        """Return the concrete renderer's quality interface for type checking."""
        return cast(_QualityRenderer, cast(object, self))

    def set_quality_mode(self, mode_name: str, *, apply: bool = True) -> None:
        """Set the target detail, optionally applying it immediately."""
        renderer = self._quality_renderer()
        for name, dist in renderer.QUALITY_MODES:
            if name == mode_name:
                renderer._quality_sample_distance = dist
                if apply:
                    renderer._mapper.SetSampleDistance(dist)
                    renderer._mapper.Modified()
                return
        renderer._log_unknown_quality(mode_name)

    def set_temporary_quality(self, mode_name: str) -> bool:
        """Apply a sample distance without changing the selected target detail."""
        renderer = self._quality_renderer()
        for name, dist in renderer.QUALITY_MODES:
            if name == mode_name:
                renderer._mapper.SetSampleDistance(dist)
                renderer._mapper.Modified()
                return True
        renderer._log_unknown_quality(mode_name)
        return False

    def restore_target_quality(self) -> None:
        """Reapply selected static detail after a temporary override."""
        renderer = self._quality_renderer()
        renderer._mapper.SetSampleDistance(renderer._quality_sample_distance)
        renderer._mapper.Modified()
