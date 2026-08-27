"""Regression tests for classifying blank first frames in the 3D renderer."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

import core.volume_renderer as volume_renderer
from core.volume_render_quality import GpuFallbackOutcome
from core.volume_renderer import PRESET_CT_BONE, VolumeRenderer, vtk_available

pytestmark = pytest.mark.skipif(not vtk_available, reason="VTK not installed")


class _RenderWindow:
    def __init__(self) -> None:
        self.render_calls = 0

    def Render(self) -> None:
        self.render_calls += 1


def _blank_readback_vtk():
    """Return a narrow VTK-module stand-in with a confirmed black RGB frame."""
    from vtkmodules.vtkCommonCore import vtkUnsignedCharArray

    scalars = vtkUnsignedCharArray()
    scalars.SetNumberOfComponents(3)
    scalars.SetNumberOfTuples(4)
    scalars.Fill(0)

    image = SimpleNamespace(
        GetDimensions=lambda: (2, 2, 1),
        GetPointData=lambda: SimpleNamespace(GetScalars=lambda: scalars),
    )

    class _WindowToImageFilter:
        def __init__(self) -> None:
            readback_calls.append(None)

        def SetInput(self, _window) -> None:
            pass

        def SetInputBufferTypeToRGB(self) -> None:
            pass

        def Update(self) -> None:
            pass

        def GetOutput(self):
            return image

    readback_calls: list[None] = []
    return SimpleNamespace(
        vtkWindowToImageFilter=_WindowToImageFilter,
        readback_calls=readback_calls,
    )


def _renderer_with_occupancy(occupancy: list[tuple[float, float, int]]) -> VolumeRenderer:
    renderer = VolumeRenderer()
    renderer.set_preset(PRESET_CT_BONE)
    renderer._scalar_occupancy = occupancy
    return renderer


def test_expected_blank_frame_keeps_gpu_path_and_does_not_latch(monkeypatch) -> None:
    """Water/air occupancy under CT Bone is not a GPU rendering failure."""
    renderer = _renderer_with_occupancy([(-1000.0, 120.0, 1_000)])
    window = _RenderWindow()
    monkeypatch.setattr(volume_renderer, "vtk_mod", _blank_readback_vtk())
    try:
        outcome = renderer.check_gpu_fallback(window, probe_quality="Fast")

        assert outcome is GpuFallbackOutcome.EXPECTED_BLANK
        assert renderer._gpu_fallback_done is False
        assert window.render_calls == 0
    finally:
        renderer.cleanup()


def test_expected_blank_probe_waits_for_a_transfer_function_change(monkeypatch) -> None:
    """An unchanged expected blank must not read back RGB every render."""
    renderer = _renderer_with_occupancy([(-1000.0, 120.0, 1_000)])
    window = _RenderWindow()
    fake_vtk = _blank_readback_vtk()
    monkeypatch.setattr(volume_renderer, "vtk_mod", fake_vtk)
    try:
        assert renderer.check_gpu_fallback(window) is GpuFallbackOutcome.EXPECTED_BLANK
        assert renderer.check_gpu_fallback(window) is GpuFallbackOutcome.EXPECTED_BLANK
        assert len(fake_vtk.readback_calls) == 1

        # Opacity changes the effective transfer function, so the next render
        # gets exactly one new probe without latching EXPECTED_BLANK forever.
        renderer.set_global_opacity(0.5)
        assert renderer.check_gpu_fallback(window) is GpuFallbackOutcome.EXPECTED_BLANK
        assert len(fake_vtk.readback_calls) == 2
    finally:
        renderer.cleanup()


def test_visible_content_with_black_gpu_frame_still_falls_back(monkeypatch) -> None:
    """Sparse bone-density content must preserve the real GPU fallback path."""
    renderer = _renderer_with_occupancy([(0.0, 0.0, 1_000), (3000.0, 3000.0, 3)])
    window = _RenderWindow()
    monkeypatch.setattr(volume_renderer, "vtk_mod", _blank_readback_vtk())
    try:
        outcome = renderer.check_gpu_fallback(window, probe_quality="Fast")

        assert outcome is GpuFallbackOutcome.FELL_BACK
        assert renderer._gpu_fallback_done is True
        assert window.render_calls == 1
        assert renderer._mapper.GetRequestedRenderMode() == 1
    finally:
        renderer.cleanup()
