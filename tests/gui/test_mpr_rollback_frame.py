"""Real Qt rollback after an install has already painted replacement pixels."""

from unittest.mock import patch

import pytest
from mpr_lifecycle_harness import _make_controller, _make_result, _seed_mpr_pane
from PIL import Image

from gui.image_viewer import ImageViewer


@pytest.mark.parametrize("occupied_mpr", [False, True])
def test_late_install_failure_restores_last_good_frame(qapp, occupied_mpr):
    ctrl, app = _make_controller()
    viewer = ImageViewer()
    app.multi_window_layout.get_subwindow(0).image_viewer = viewer
    old = Image.new("L", (4, 4), color=31)
    viewer.set_display_final_image(old, preserve_view=False, image_inverted=True)
    if occupied_mpr:
        _seed_mpr_pane(app, 0, _make_result())
    else:
        app.subwindow_data[0] = {"current_dataset": "original", "custom": "keep"}
    before = dict(app.subwindow_data[0])
    manager = app.subwindow_managers[0]["view_state_manager"]
    manager.current_dataset = "original-context"
    payload = {"mpr_result": _make_result(), "mpr_slice_index": 1}

    def paint_replacement(*_args):
        viewer.set_display_final_image(
            Image.new("L", (4, 4), color=219),
            preserve_view=False, image_inverted=False,
        )
        manager.current_dataset = "replacement-context"

    with (
        patch.object(ctrl, "display_mpr_slice", side_effect=paint_replacement),
        patch.object(ctrl, "_apply_mpr_banner", side_effect=RuntimeError("late failure")),
        patch.object(ctrl, "_fit_image_viewer_after_mpr"),
    ):
        assert ctrl._install_mpr_payload_at_subwindow(0, payload) is False
    assert app.subwindow_data[0] == before
    assert viewer.original_image.getpixel((0, 0)) == 31
    assert viewer.image_item.pixmap().toImage().pixelColor(0, 0).red() == 31
    assert manager.current_dataset == "original-context"
    viewer.close()
