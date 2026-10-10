"""
Characterization tests for the MPR-navigation and tag-editing mixin bodies.

Covers detached MPR sessions and thumbnail clicks (``MPRNavigationMixin``) and
the tag edit/undo/redo refresh fan-out across the metadata panel and the tag
viewer dialog (``TagEditingMixin``).
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

from main_mixin_delegation_support import _stub_for

# --- MPRNavigationMixin: detached sessions and thumbnails ---------------------------


def test_on_mpr_thumbnail_clicked_focuses_an_unfocused_pane() -> None:
    """Clicking a navigator thumbnail focuses the pane that hosts the MPR."""
    subwindow = MagicMock(name="subwindow")
    subwindow.is_focused = False
    layout = MagicMock()
    layout.get_subwindow.return_value = subwindow
    stub = _stub_for("MPRNavigationMixin", multi_window_layout=layout)

    stub._on_mpr_thumbnail_clicked(2)

    layout.get_subwindow.assert_called_once_with(2)
    subwindow.set_focused.assert_called_once_with(True)


def test_on_mpr_thumbnail_clicked_ignores_the_detached_session() -> None:
    """The detached MPR has no pane, so a click on it must not touch the layout."""
    layout = MagicMock()
    stub = _stub_for("MPRNavigationMixin", multi_window_layout=layout)

    stub._on_mpr_thumbnail_clicked(-1)

    layout.get_subwindow.assert_not_called()


def test_on_mpr_thumbnail_clicked_does_not_refocus_the_focused_pane() -> None:
    """Re-focusing an already-focused pane would steal/reset its widget state."""
    subwindow = MagicMock(name="subwindow")
    subwindow.is_focused = True
    layout = MagicMock()
    layout.get_subwindow.return_value = subwindow
    stub = _stub_for("MPRNavigationMixin", multi_window_layout=layout)

    stub._on_mpr_thumbnail_clicked(1)

    subwindow.set_focused.assert_not_called()


def test_on_mpr_thumbnail_clicked_swallows_a_layout_failure() -> None:
    """A disappearing pane during teardown must not propagate out of the Qt slot."""
    layout = MagicMock()
    layout.get_subwindow.side_effect = RuntimeError("pane destroyed")
    stub = _stub_for("MPRNavigationMixin", multi_window_layout=layout)

    stub._on_mpr_thumbnail_clicked(1)


def test_on_mpr_assign_requested_attaches_the_exact_detached_view() -> None:
    """A negative source is -view_id: it attaches that exact view, never "the" floating one."""
    controller = MagicMock()
    stub = _stub_for("MPRNavigationMixin", _mpr_controller=controller)

    stub._on_mpr_assign_requested(-7, 2)

    controller.attach_detached_view.assert_called_once_with(7, 2)
    controller.relocate_mpr_subwindow.assert_not_called()


def test_on_mpr_assign_requested_relocates_an_attached_mpr() -> None:
    """Dropping an attached MPR onto another pane moves it rather than re-attaching."""
    controller = MagicMock()
    stub = _stub_for("MPRNavigationMixin", _mpr_controller=controller)

    stub._on_mpr_assign_requested(0, 3)

    controller.relocate_mpr_subwindow.assert_called_once_with(0, 3)
    controller.attach_detached_view.assert_not_called()


def test_on_mpr_clear_from_navigator_thumbnail_discards_only_that_detached_view() -> None:
    """Clearing a detached tile discards that exact view and removes only its tile."""
    controller = MagicMock()
    navigator = MagicMock()
    stub = _stub_for(
        "MPRNavigationMixin", _mpr_controller=controller, series_navigator=navigator
    )

    stub._on_mpr_clear_from_navigator_thumbnail(-4)

    controller.discard_detached_view.assert_called_once_with(4)
    navigator.clear_mpr_thumbnail.assert_called_once_with(-4)
    controller.clear_mpr.assert_not_called()


def test_on_mpr_clear_from_navigator_thumbnail_clears_an_attached_pane() -> None:
    """An attached pane is only cleared when it really is showing an MPR."""
    controller = MagicMock()
    controller.is_mpr.return_value = True
    stub = _stub_for("MPRNavigationMixin", _mpr_controller=controller)

    stub._on_mpr_clear_from_navigator_thumbnail(1)

    controller.clear_mpr.assert_called_once_with(1)


def test_on_mpr_clear_from_navigator_thumbnail_ignores_a_native_pane() -> None:
    """Clearing the MPR action on a native series must not clear anything."""
    controller = MagicMock()
    controller.is_mpr.return_value = False
    stub = _stub_for("MPRNavigationMixin", _mpr_controller=controller)

    stub._on_mpr_clear_from_navigator_thumbnail(1)

    controller.clear_mpr.assert_not_called()


def test_get_subwindow_mpr_output_pixel_spacing_returns_the_mpr_spacing() -> None:
    """The MPR output spacing is read from the pane's cached MPR result."""
    result = MagicMock(output_spacing_mm=(0.5, 0.5))
    stub = _stub_for(
        "MPRNavigationMixin", subwindow_data={0: {"is_mpr": True, "mpr_result": result}}
    )

    assert stub._get_subwindow_mpr_output_pixel_spacing(0) == (0.5, 0.5)


def test_get_subwindow_mpr_output_pixel_spacing_is_none_for_a_native_pane() -> None:
    """A native pane has no MPR output grid."""
    stub = _stub_for("MPRNavigationMixin", subwindow_data={0: {"is_mpr": False}})

    assert stub._get_subwindow_mpr_output_pixel_spacing(0) is None


def test_get_subwindow_mpr_output_pixel_spacing_is_none_without_a_result() -> None:
    """An MPR pane mid-build has no result object yet."""
    stub = _stub_for("MPRNavigationMixin", subwindow_data={0: {"is_mpr": True, "mpr_result": None}})

    assert stub._get_subwindow_mpr_output_pixel_spacing(0) is None


def test_get_subwindow_mpr_output_pixel_spacing_swallows_a_failing_result() -> None:
    """A raising ``output_spacing_mm`` must degrade to None, not break the MPR toolbar."""
    class _Exploding:
        @property
        def output_spacing_mm(self) -> Any:
            raise RuntimeError("boom")

    stub = _stub_for(
        "MPRNavigationMixin", subwindow_data={0: {"is_mpr": True, "mpr_result": _Exploding()}}
    )

    assert stub._get_subwindow_mpr_output_pixel_spacing(0) is None


# --- TagEditingMixin: tag edit / undo / redo fan-out ---------------------------------


def _tag_panel_stub() -> MagicMock:
    panel = MagicMock(name="metadata_panel")
    panel.search_edit.text.return_value = "Patient"
    panel.parser._tag_cache = MagicMock(name="panel_tag_cache")
    panel._cached_tags = {"a": 1}
    return panel


def _tag_viewer_stub() -> MagicMock:
    dialog = MagicMock(name="tag_viewer_dialog")
    dialog.search_edit.text.return_value = "Modality"
    dialog.parser._tag_cache = MagicMock(name="viewer_tag_cache")
    dialog._cached_tags = {"b": 2}
    return dialog


def _tag_edit_stub(*, dialog: MagicMock | None, undo: bool = False) -> Any:
    controller = MagicMock(name="metadata_controller")
    if undo:
        controller.undo_tag_edit.return_value = True
        controller.redo_tag_edit.return_value = True
    panel = _tag_panel_stub()
    coordinator = MagicMock(name="dialog_coordinator")
    coordinator.tag_viewer_dialog = dialog
    stub = _stub_for(
        "TagEditingMixin",
        metadata_controller=controller,
        metadata_panel=panel,
        dialog_coordinator=coordinator,
        current_dataset=object(),
    )
    stub._update_undo_redo_state = MagicMock()
    return stub, controller, panel, coordinator


def test_on_tag_edited_refreshes_panel_and_open_viewer() -> None:
    """A tag edit must refresh the metadata panel and invalidate the viewer dialog's cache."""
    dialog = _tag_viewer_stub()
    stub, controller, panel, _coordinator = _tag_edit_stub(dialog=dialog)

    stub._on_tag_edited("(0010,0010)", "NEW")

    # The panel refresh goes through its controller using the panel's own search text.
    controller.refresh_panel_tags.assert_called_once_with("Patient")
    # The viewer dialog caches its own parsed tags, so its cache is dropped in place.
    assert dialog._cached_tags is None
    dialog.parser._tag_cache.clear.assert_called_once_with()
    dialog._populate_tags.assert_called_once_with("Modality")
    stub._update_undo_redo_state.assert_called_once_with()
    # The metadata panel is refreshed through its controller, not by clearing its
    # own cache here - that asymmetry is deliberate (see ``_refresh_tag_ui``).
    panel.parser._tag_cache.clear.assert_not_called()


def test_on_tag_edited_skips_the_viewer_when_it_is_closed() -> None:
    """With no tag-viewer dialog open the panel still refreshes and nothing raises."""
    stub, controller, _panel, _coordinator = _tag_edit_stub(dialog=None)

    stub._on_tag_edited("(0010,0010)", "NEW")

    # The edit must not be swallowed just because the optional viewer is closed.
    controller.refresh_panel_tags.assert_called_once_with("Patient")
    stub._update_undo_redo_state.assert_called_once_with()


def test_undo_tag_edit_refreshes_both_surfaces() -> None:
    """A successful undo re-reads the dataset and refreshes undo/redo enablement."""
    dialog = _tag_viewer_stub()
    stub, controller, _panel, _coordinator = _tag_edit_stub(dialog=dialog, undo=True)

    stub._undo_tag_edit()

    controller.undo_tag_edit.assert_called_once_with(stub.current_dataset)
    controller.refresh_panel_tags.assert_called_once_with()
    dialog._populate_tags.assert_called_once_with("Modality")
    stub._update_undo_redo_state.assert_called_once_with()


def test_undo_tag_edit_skips_refresh_when_the_undo_failed() -> None:
    """A refused undo must not clear caches or repopulate the panel."""
    dialog = _tag_viewer_stub()
    stub, controller, _panel, _coordinator = _tag_edit_stub(dialog=dialog)
    controller.undo_tag_edit.return_value = False

    stub._undo_tag_edit()

    controller.refresh_panel_tags.assert_not_called()
    dialog._populate_tags.assert_not_called()
    stub._update_undo_redo_state.assert_not_called()


def test_redo_tag_edit_refreshes_both_surfaces() -> None:
    """Redo mirrors undo: the same refreshes, gated on ``redo_tag_edit`` returning True."""
    dialog = _tag_viewer_stub()
    stub, controller, _panel, _coordinator = _tag_edit_stub(dialog=dialog, undo=True)

    stub._redo_tag_edit()

    controller.redo_tag_edit.assert_called_once_with(stub.current_dataset)
    controller.refresh_panel_tags.assert_called_once_with()
    dialog._populate_tags.assert_called_once_with("Modality")
    stub._update_undo_redo_state.assert_called_once_with()


def test_redo_tag_edit_skips_refresh_when_the_redo_failed() -> None:
    """A refused redo must leave the UI untouched."""
    dialog = _tag_viewer_stub()
    stub, controller, _panel, _coordinator = _tag_edit_stub(dialog=dialog)
    controller.redo_tag_edit.return_value = False

    stub._redo_tag_edit()

    controller.refresh_panel_tags.assert_not_called()
    stub._update_undo_redo_state.assert_not_called()


def test_refresh_tag_ui_populates_the_panel_only_when_it_holds_a_dataset() -> None:
    """The metadata panel with no dataset has nothing to re-read."""
    dialog = _tag_viewer_stub()
    panel = _tag_panel_stub()
    panel.dataset = None
    coordinator = MagicMock(name="dialog_coordinator")
    coordinator.tag_viewer_dialog = dialog
    stub = _stub_for("TagEditingMixin", metadata_panel=panel, dialog_coordinator=coordinator)

    stub._refresh_tag_ui()

    panel._populate_tags.assert_not_called()
    dialog._populate_tags.assert_called_once_with("Modality")


def test_refresh_tag_ui_clears_both_caches_when_a_dataset_is_loaded() -> None:
    """After a tag change both surfaces must drop their parser caches."""
    dialog = _tag_viewer_stub()
    stub, _controller, panel, _coordinator = _tag_edit_stub(dialog=dialog)
    panel.dataset = object()

    stub._refresh_tag_ui()

    assert panel._cached_tags is None
    panel.parser._tag_cache.clear.assert_called_once_with()
    panel._populate_tags.assert_called_once_with("Patient")
    assert dialog._cached_tags is None
    dialog.parser._tag_cache.clear.assert_called_once_with()
    dialog._populate_tags.assert_called_once_with("Modality")
