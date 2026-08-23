"""Legacy ``QVTKRenderWindowInteractor`` surface, kept behind an escape hatch.

This is the pre-2026-08 rendering path.  It renders from inside ``paintEvent``,
which deadlocks the GUI thread on native macOS (see
``dev-docs/plans/3D_VIEWER_MACOS_NATIVE_RENDERING_PLAN.md``), so it is **not**
the default and must never be used there.

It exists for the opposite direction of risk: the 3D viewer was historically
verified only on Windows under Parallels, so the offscreen surface is the newer,
less-proven path *on those platforms*.  If a Windows / Parallels regression
turns up in the field, this restores the old behaviour without a rebuild::

    DICOMVIEWER_3D_LEGACY_INTERACTOR=1

It presents the same API as :class:`~gui.volume.render_surface.VolumeRenderSurface`
so the viewer widget does not need to know which surface it has.

Planned for removal once the offscreen surface has shipped one clean release —
tracked in ``dev-docs/TO_DO.md``.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import QSizePolicy, QVBoxLayout, QWidget


class LegacyInteractorSurface(QWidget):
    """Adapter exposing the render-surface API over the old VTK Qt interactor."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        import vtkmodules.all as vtk_mod
        from vtkmodules.qt.QVTKRenderWindowInteractor import (
            QVTKRenderWindowInteractor,
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._widget: Any = QVTKRenderWindowInteractor(self)
        layout.addWidget(self._widget)

        self._render_window: Any = self._widget.GetRenderWindow()
        self._widget.SetInteractorStyle(vtk_mod.vtkInteractorStyleTrackballCamera())
        self._initialized = False
        self._cleaned_up = False

    # ------------------------------------------------------------------
    # Render-surface API
    # ------------------------------------------------------------------

    @property
    def render_window(self) -> Any:
        return self._render_window

    @property
    def interactor(self) -> Any:
        """Return the VTK interactor (not the Qt widget)."""
        if self._render_window is None:
            return None
        return self._render_window.GetInteractor()

    def add_renderer(self, renderer: Any) -> None:
        self._render_window.AddRenderer(renderer)

    def render_frame(self) -> None:
        if self._cleaned_up or self._render_window is None:
            return
        self._render_window.Render()

    def showEvent(self, event: Any) -> None:
        """Initialise the native interactor once the widget is realised."""
        super().showEvent(event)
        if not self._initialized and not self._cleaned_up:
            self._initialized = True
            self._widget.Initialize()

    def cleanup(self) -> None:
        if self._cleaned_up:
            return
        self._cleaned_up = True
        if self._widget is not None:
            try:
                self._widget.Finalize()
            except Exception:
                pass
            self._widget = None
        self._render_window = None
