"""Target and temporary sample-distance operations shared by volume renderers."""

from __future__ import annotations


class VolumeRendererQualityMixin:
    """Keep selected static quality separate from transient preview quality."""

    def set_quality_mode(self, mode_name: str, *, apply: bool = True) -> None:
        """Set the target detail, optionally applying it immediately."""
        for name, dist in self.QUALITY_MODES:
            if name == mode_name:
                self._quality_sample_distance = dist
                if apply:
                    self._mapper.SetSampleDistance(dist)
                    self._mapper.Modified()
                return
        self._log_unknown_quality(mode_name)

    def set_temporary_quality(self, mode_name: str) -> bool:
        """Apply a sample distance without changing the selected target detail."""
        for name, dist in self.QUALITY_MODES:
            if name == mode_name:
                self._mapper.SetSampleDistance(dist)
                self._mapper.Modified()
                return True
        self._log_unknown_quality(mode_name)
        return False

    def restore_target_quality(self) -> None:
        """Reapply selected static detail after a temporary override."""
        self._mapper.SetSampleDistance(self._quality_sample_distance)
        self._mapper.Modified()
