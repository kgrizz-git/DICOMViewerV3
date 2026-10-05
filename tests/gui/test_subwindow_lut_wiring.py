# pyright: reportAttributeAccessIssue=false
"""The per-pane LUT callbacks ``subwindow_manager_factory`` installs on a viewer."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from pydicom.dataset import Dataset
from pydicom.sequence import Sequence

from core.lut_catalog import colormap_lut, linear_lut
from gui.subwindow_manager_factory import _wire_series_lut


def _voi_dataset(bits: int) -> Dataset:
    item = Dataset()
    item.LUTDescriptor = [2, 0, bits]
    item.LUTData = [0, 255]
    ds = Dataset()
    ds.Modality = "PT"
    ds.PhotometricInterpretation = "MONOCHROME2"
    ds.VOILUTSequence = Sequence([item])
    return ds


def _wired(qapp, dataset: Dataset | None, *, config=None, mpr_panes: dict[int, bool] | None = None):
    from gui.image_viewer import ImageViewer

    redrawn: list[tuple[int, bool]] = []
    mpr_panes = mpr_panes if mpr_panes is not None else {}
    view_state = SimpleNamespace(series_defaults={}, current_series_identifier="s1", image_viewer=None)
    managers = {
        "view_state_manager": view_state,
        "slice_display_manager": SimpleNamespace(current_dataset=dataset),
    }
    app = SimpleNamespace(
        subwindow_managers={0: managers, 1: {}},
        _redisplay_subwindow_slice=lambda i, preserve_view: redrawn.append((i, preserve_view)),
        config_manager=config,
        main_window=None,
        _mpr_controller=SimpleNamespace(is_mpr=lambda i: mpr_panes.get(i, False)),
    )
    viewer = ImageViewer()
    viewer.slice_display_for_test = managers["slice_display_manager"]
    _wire_series_lut(app, 0, managers, viewer)
    _ = qapp
    return viewer, view_state, redrawn


@pytest.mark.qt
def test_the_viewer_reports_modality_and_dicom_lut_state(qapp) -> None:
    viewer, view_state, redrawn = _wired(qapp, _voi_dataset(8))
    assert viewer.current_modality() == "PT"
    assert viewer.dicom_lut_state() == (True, False)
    viewer.set_dicom_lut(True)
    assert viewer.dicom_lut_state() == (True, True)
    assert viewer.dicom_lut_applied()
    assert view_state.series_defaults["s1"]["voi_from_dicom"] is True
    assert redrawn == [(0, True)]
    viewer.redisplay_all_panes()
    assert redrawn[1:] == [(0, True), (1, True)]


@pytest.mark.qt
def test_an_unsupported_voi_lut_is_not_offered(qapp) -> None:
    viewer, _view_state, _redrawn = _wired(qapp, _voi_dataset(9))
    assert viewer.dicom_lut_state() == (False, False)
    viewer2, _vs, _r = _wired(qapp, None)
    assert viewer2.dicom_lut_state() == (False, False)
    assert viewer2.current_modality() == ""


@pytest.mark.qt
def test_the_resolver_and_label_use_the_app_config(qapp) -> None:
    config = SimpleNamespace(
        get_show_lut_label=lambda: True,
        get_privacy_view=lambda: False,
        get_lut_defaults=lambda: {"PT": {"kind": "colormap", "name": "hot"}},
        load_custom_luts_document=lambda: None,
    )
    viewer, view_state, _redrawn = _wired(qapp, _voi_dataset(8), config=config)
    assert view_state.lut_default_resolver() == colormap_lut("hot")
    assert viewer.current_series_lut() == colormap_lut("hot")
    assert viewer.lut_pane_label.current_text() == "LUT: hot"
    plain, plain_state, _r = _wired(qapp, _voi_dataset(8))
    assert not hasattr(plain_state, "lut_default_resolver")
    assert plain.current_series_lut().name == linear_lut().name




@pytest.mark.qt
def test_a_drawn_projection_reports_dicom_as_not_applied(qapp) -> None:
    viewer, _view_state, _redrawn = _wired(qapp, _voi_dataset(8))
    viewer.set_dicom_lut(True)
    viewer.slice_display_for_test.projection_drawn = True
    # The menu still shows the choice; the label must not claim it applied.
    assert viewer.dicom_lut_state() == (True, True)
    assert not viewer.dicom_lut_applied()
    viewer.slice_display_for_test.projection_drawn = False
    assert viewer.dicom_lut_applied()



@pytest.mark.qt
def test_an_mpr_pane_reports_dicom_as_not_applied(qapp) -> None:
    mpr_panes = {0: True}
    viewer, _view_state, _redrawn = _wired(qapp, _voi_dataset(8), mpr_panes=mpr_panes)
    viewer.set_dicom_lut(True)
    assert viewer.dicom_lut_state() == (True, True)
    assert not viewer.dicom_lut_applied()
    mpr_panes[0] = False
    assert viewer.dicom_lut_applied()
