"""Memory-lifetime tests for the 3D volume-renderer input path."""

from __future__ import annotations

import gc
import weakref

import numpy as np
import pytest

from core.volume_renderer import (
    PRESET_CT_BONE,
    VolumeData,
    VolumeRenderer,
    vtk_available,
)

pytestmark = pytest.mark.skipif(not vtk_available, reason="VTK not installed")


def test_shallow_vtk_input_keeps_backing_array_alive_after_volume_data_is_dropped() -> None:
    """The renderer must own NumPy scalars borrowed by ``numpy_to_vtk``.

    ``deep=False`` avoids one full float32 allocation, but VTK otherwise only
    holds a raw pointer.  Rendering after every caller-owned reference is
    dropped proves the renderer's strong backing reference prevents a
    use-after-free.
    """
    from vtkmodules.util import numpy_support

    from core.volume_renderer import vtk_mod

    array = np.full((8, 16, 16), 300.0, dtype=np.float32)
    volume_data = VolumeData(
        array=array,
        spacing=(1.0, 1.0, 1.0),
        origin=(0.0, 0.0, 0.0),
        direction=(1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0),
    )
    renderer = VolumeRenderer()
    try:
        renderer.attach_volume(volume_data)
        renderer.set_preset(PRESET_CT_BONE)
        backing_ref = weakref.ref(renderer._vtk_numpy_backing)

        del volume_data
        del array
        gc.collect()

        backing = renderer._vtk_numpy_backing
        assert backing is not None
        assert backing_ref() is backing
        vtk_scalars = renderer._vtk_image.GetPointData().GetScalars()
        np.testing.assert_array_equal(numpy_support.vtk_to_numpy(vtk_scalars), backing)

        # Force a non-GUI VTK pipeline to consume the borrowed scalars after
        # callers dropped their references.  A real render is covered by the
        # manual 3D smoke: a standalone vtkRenderWindow is unsafe in this
        # macOS test runner and can crash before renderer code is exercised.
        accumulator = vtk_mod.vtkImageAccumulate()
        accumulator.SetInputData(renderer._vtk_image)
        accumulator.Update()
        assert accumulator.GetVoxelCount() == backing.size
    finally:
        renderer.cleanup()
