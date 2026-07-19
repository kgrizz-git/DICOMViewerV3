"""
Characterize SliceDisplayManager contracts targeted by the Sonar S3776 slice.

Covers base-image pipeline fallbacks, W/L control sync, scene overlay wiring,
ROI slice filtering/selection, and series navigation by SeriesNumber.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from PIL import Image

from gui.slice_display_manager import SliceDisplayManager


def _make_manager(**overrides) -> SliceDisplayManager:
    """Build a manager with MagicMock collaborators for unit tests."""
    scroll = MagicMock()
    scroll.value.return_value = 10
    image_viewer = MagicMock()
    image_viewer.scene = MagicMock()
    image_viewer.current_zoom = 1.25
    image_viewer.horizontalScrollBar.return_value = scroll
    image_viewer.verticalScrollBar.return_value = scroll

    view_state = MagicMock()
    view_state.series_defaults = {}
    view_state.get_series_pixel_range.return_value = (None, None)
    view_state.current_window_center = 40.0
    view_state.current_window_width = 400.0

    kwargs = {
        "dicom_processor": MagicMock(),
        "image_viewer": image_viewer,
        "metadata_panel": MagicMock(),
        "slice_navigator": MagicMock(),
        "window_level_controls": MagicMock(),
        "roi_manager": MagicMock(),
        "measurement_tool": MagicMock(),
        "overlay_manager": MagicMock(),
        "view_state_manager": view_state,
        "text_annotation_tool": MagicMock(),
        "arrow_annotation_tool": MagicMock(),
        "roi_list_panel": MagicMock(),
        "roi_statistics_panel": MagicMock(),
        "update_roi_statistics_overlays_callback": MagicMock(),
        "annotation_manager": MagicMock(),
        "dicom_organizer": MagicMock(),
        "fusion_coordinator": None,
        "open_structured_report_browser_callback": None,
        "display_rois_callback": None,
        "display_measurements_callback": None,
        "update_tag_viewer_callback": None,
    }
    kwargs.update(overrides)
    mgr = SliceDisplayManager(**kwargs)
    mgr.current_slice_index = 0
    return mgr


def _ds(
    *,
    study: str = "study-1",
    series: str = "series-1",
    modality: str = "CT",
    series_number: int | None = 1,
    rows: int = 64,
    cols: int = 64,
) -> SimpleNamespace:
    ns = SimpleNamespace(
        StudyInstanceUID=study,
        SeriesInstanceUID=series,
        Modality=modality,
        Rows=rows,
        Columns=cols,
    )
    if series_number is not None:
        ns.SeriesNumber = series_number
    return ns


@pytest.mark.qt
def test_projection_success_skips_dataset_to_image(qapp) -> None:
    proj = Image.new("L", (8, 8), 100)
    mgr = _make_manager()
    mgr.projection_enabled = True
    mgr._create_projection_image = MagicMock(return_value=proj)  # type: ignore[method-assign]
    mgr.dicom_processor.dataset_to_image.return_value = Image.new("L", (8, 8), 50)
    ds = _ds()

    mgr._render_base_image_pipeline(
        ds,
        {ds.StudyInstanceUID: {ds.SeriesInstanceUID: [ds]}},
        ds.StudyInstanceUID,
        ds.SeriesInstanceUID,
        0,
        40.0,
        400.0,
        True,
        1.0,
        0.0,
        True,
        False,
        "series-key",
        None,
    )

    mgr.dicom_processor.dataset_to_image.assert_not_called()
    mgr.image_viewer.set_image.assert_called_once()
    assert mgr.image_viewer.set_image.call_args.args[0] is proj


@pytest.mark.qt
def test_projection_none_falls_back_to_dataset_to_image(qapp) -> None:
    single = Image.new("L", (8, 8), 50)
    mgr = _make_manager()
    mgr.projection_enabled = True
    mgr._create_projection_image = MagicMock(return_value=None)  # type: ignore[method-assign]
    mgr.dicom_processor.dataset_to_image.return_value = single
    ds = _ds()

    mgr._render_base_image_pipeline(
        ds,
        {ds.StudyInstanceUID: {ds.SeriesInstanceUID: [ds]}},
        ds.StudyInstanceUID,
        ds.SeriesInstanceUID,
        0,
        40.0,
        400.0,
        True,
        1.0,
        0.0,
        True,
        False,
        "series-key",
        None,
    )

    mgr.dicom_processor.dataset_to_image.assert_called_once()
    assert mgr.image_viewer.set_image.call_args.args[0] is single


@pytest.mark.qt
def test_none_image_uses_placeholder_and_sr_bar(qapp) -> None:
    mgr = _make_manager()
    mgr.dicom_processor.dataset_to_image.return_value = None
    ds = _ds(modality="SR")

    mgr._render_base_image_pipeline(
        ds,
        {},
        "",
        "",
        0,
        None,
        None,
        False,
        None,
        None,
        False,
        True,
        "series-key",
        None,
    )

    mgr.image_viewer.set_no_pixel_placeholder_bar.assert_any_call(
        True, open_callback=None, show_open_button=False
    )
    mgr.image_viewer.fit_to_view.assert_called_once_with(center_image=True)


@pytest.mark.qt
def test_fusion_replaces_base_image_when_available(qapp) -> None:
    base = Image.new("L", (8, 8), 10)
    fused = Image.new("RGB", (8, 8), (1, 2, 3))
    fusion = MagicMock()
    fusion.get_fused_image.return_value = fused
    mgr = _make_manager(fusion_coordinator=fusion)
    mgr.dicom_processor.dataset_to_image.return_value = base
    ds = _ds()
    studies = {ds.StudyInstanceUID: {ds.SeriesInstanceUID: [ds]}}

    mgr._render_base_image_pipeline(
        ds,
        studies,
        ds.StudyInstanceUID,
        ds.SeriesInstanceUID,
        0,
        40.0,
        400.0,
        True,
        1.0,
        0.0,
        True,
        False,
        "series-key",
        None,
    )

    fusion.get_fused_image.assert_called_once()
    assert mgr.image_viewer.set_image.call_args.args[0] is fused


@pytest.mark.qt
def test_sync_new_series_sets_window_level_controls(qapp) -> None:
    mgr = _make_manager()
    mgr.dicom_processor.get_pixel_value_range.return_value = (-1000.0, 1000.0)
    ds = _ds()

    mgr._sync_controls_and_metadata(
        ds,
        update_metadata=True,
        update_controls=True,
        use_rescaled_values=True,
        is_new_study_series=True,
        is_same_series=False,
        window_center=40.0,
        window_width=400.0,
        rescale_type="HU",
        rescale_slope=1.0,
        rescale_intercept=0.0,
    )

    mgr.metadata_panel.set_dataset.assert_called_once_with(ds)
    mgr.window_level_controls.set_ranges.assert_called_once()
    mgr.window_level_controls.set_window_level.assert_called_once_with(
        40.0, 400.0, block_signals=True, unit="HU"
    )


@pytest.mark.qt
def test_sync_clamps_out_of_range_window_level(qapp) -> None:
    mgr = _make_manager()
    mgr.dicom_processor.get_pixel_value_range.return_value = (0.0, 100.0)
    mgr.view_state_manager.get_series_pixel_range.return_value = (0.0, 100.0)
    ds = _ds()

    mgr._sync_controls_and_metadata(
        ds,
        update_metadata=False,
        update_controls=True,
        use_rescaled_values=False,
        is_new_study_series=False,
        is_same_series=True,
        window_center=500.0,
        window_width=10.0,
        rescale_type=None,
        rescale_slope=1.0,
        rescale_intercept=0.0,
    )

    assert mgr.view_state_manager.current_window_center == 50.0
    assert mgr.view_state_manager.current_window_width == 100.0
    mgr.window_level_controls.set_window_level.assert_called()


@pytest.mark.qt
def test_overlay_passes_projection_meta_and_clears_on_new_series(qapp, monkeypatch) -> None:
    mgr = _make_manager()
    mgr.projection_enabled = True
    mgr.projection_slice_count = 2
    mgr.projection_type = "mip"
    ds0 = _ds()
    ds1 = _ds()
    ds0.SliceThickness = "2.5"
    ds1.SliceThickness = "2.5"
    studies = {ds0.StudyInstanceUID: {ds0.SeriesInstanceUID: [ds0, ds1]}}
    monkeypatch.setattr(
        "gui.slice_display_manager.get_slice_thickness",
        lambda d: float(getattr(d, "SliceThickness", 0) or 0) or None,
    )
    monkeypatch.setattr(
        "gui.slice_display_manager.get_pixel_spacing",
        lambda _d: (1.0, 1.0),
    )
    monkeypatch.setattr(
        "gui.slice_display_manager.get_composite_series_key",
        lambda d: d.SeriesInstanceUID,
    )
    monkeypatch.setattr(
        "gui.slice_display_manager.DICOMParser",
        lambda _ds: MagicMock(),
    )
    mgr.display_rois_for_slice = MagicMock()  # type: ignore[method-assign]
    mgr.display_measurements_for_slice = MagicMock()  # type: ignore[method-assign]
    mgr.display_text_annotations_for_slice = MagicMock()  # type: ignore[method-assign]
    mgr.display_arrow_annotations_for_slice = MagicMock()  # type: ignore[method-assign]
    mgr.annotation_manager.get_annotations_for_image.return_value = [{"id": 1}]

    mgr._render_scene_overlays_annotations(
        ds0,
        studies,
        ds0.StudyInstanceUID,
        ds0.SeriesInstanceUID,
        0,
        True,
    )

    kwargs = mgr.overlay_manager.create_overlay_items.call_args.kwargs
    assert kwargs["projection_enabled"] is True
    assert kwargs["projection_start_slice"] == 0
    assert kwargs["projection_end_slice"] == 1
    assert kwargs["projection_total_thickness"] == 5.0
    assert kwargs["projection_type"] == "mip"
    mgr.measurement_tool.clear_measurements_from_other_slices.assert_called_once()
    mgr.text_annotation_tool.clear_annotations.assert_called_once()
    mgr.arrow_annotation_tool.clear_arrows.assert_called_once()
    mgr.annotation_manager.create_presentation_state_items.assert_called_once()


@pytest.mark.qt
def test_display_rois_removes_foreign_and_clears_selection(qapp, monkeypatch) -> None:
    monkeypatch.setattr(
        "gui.slice_display_manager.get_composite_series_key",
        lambda d: d.SeriesInstanceUID,
    )
    scene = MagicMock()
    foreign_item = MagicMock()
    foreign_item.scene.return_value = scene
    current_item = MagicMock()
    current_item.scene.return_value = scene
    scene.items.return_value = [foreign_item, current_item]

    foreign_roi = MagicMock()
    foreign_roi.item = foreign_item
    foreign_roi.statistics_overlay_item = None
    current_roi = MagicMock()
    current_roi.item = current_item
    current_roi.statistics_overlay_item = None

    mgr = _make_manager()
    mgr.image_viewer.scene = scene
    mgr.current_slice_index = 0
    key_current = ("study-1", "series-1", 0)
    key_other = ("study-1", "series-1", 1)
    mgr.roi_manager.rois = {
        key_current: [current_roi],
        key_other: [foreign_roi],
    }
    mgr.roi_manager.get_rois_for_slice.return_value = [current_roi]
    mgr.roi_manager.find_roi_by_item.side_effect = lambda item: (
        foreign_roi if item is foreign_item else current_roi if item is current_item else None
    )
    mgr.roi_manager.get_selected_roi.return_value = foreign_roi
    ds = _ds()

    mgr.display_rois_for_slice(ds)

    scene.removeItem.assert_called_with(foreign_item)
    mgr.roi_list_panel.update_roi_list.assert_called_once_with("study-1", "series-1", 0)
    mgr.roi_manager.select_roi.assert_called_once_with(None)
    mgr.roi_list_panel.select_roi_in_list.assert_called_with(None)
    mgr.roi_statistics_panel.clear_statistics.assert_called_once()
    mgr.update_roi_statistics_overlays_callback.assert_called_once()


@pytest.mark.qt
def test_series_navigation_orders_by_series_number(qapp) -> None:
    s1 = _ds(series="uid-a", series_number=10)
    s2 = _ds(series="uid-b", series_number=20)
    s3 = _ds(series="uid-c", series_number=30)
    mgr = _make_manager()
    mgr.current_study_uid = "study-1"
    mgr.current_series_uid = "uid-b"
    mgr.current_studies = {
        "study-1": {
            "uid-a": [s1],
            "uid-b": [s2],
            "uid-c": [s3],
        }
    }

    next_uid, idx, ds = mgr.handle_series_navigation(1)
    assert next_uid == "uid-c"
    assert idx == 0
    assert ds is s3

    prev_uid, idx2, ds2 = mgr.handle_series_navigation(-1)
    assert prev_uid == "uid-a"
    assert idx2 == 0
    assert ds2 is s1


@pytest.mark.qt
def test_series_navigation_single_series_and_end_clamp(qapp) -> None:
    only = _ds(series="uid-only", series_number=1)
    mgr = _make_manager()
    mgr.current_study_uid = "study-1"
    mgr.current_series_uid = "uid-only"
    mgr.current_studies = {"study-1": {"uid-only": [only]}}
    assert mgr.handle_series_navigation(1) == (None, None, None)

    s1 = _ds(series="uid-a", series_number=1)
    s2 = _ds(series="uid-b", series_number=2)
    mgr.current_series_uid = "uid-a"
    mgr.current_studies = {"study-1": {"uid-a": [s1], "uid-b": [s2]}}
    assert mgr.handle_series_navigation(-1) == (None, None, None)

    mgr.current_series_uid = "uid-b"
    assert mgr.handle_series_navigation(1) == (None, None, None)
