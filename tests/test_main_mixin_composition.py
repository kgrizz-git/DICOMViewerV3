"""
Phase 2 mixin composition tests for DICOMViewerApp.

Verifies plain-mixin inheritance, QObject-first MRO, no mixin __init__, and zero
method-name collisions across mixin classes before method extraction begins.
"""

from __future__ import annotations

import pytest
from main_test_helpers import instantiate_app
from PySide6.QtCore import QObject

import main as main_module
from main_app_display_settings import DisplayProjectionMixin, SettingsLayoutMixin
from main_app_initialization import InitializationMixin
from main_app_subwindow_management import MPRNavigationMixin, SubwindowManagementMixin
from main_app_tag_roi import ROIWorkflowMixin, TagEditingMixin
from main_app_ui_and_files import FileOperationsMixin, UIHandlersMixin

ALL_MIXINS: tuple[type, ...] = (
    InitializationMixin,
    SubwindowManagementMixin,
    MPRNavigationMixin,
    UIHandlersMixin,
    FileOperationsMixin,
    DisplayProjectionMixin,
    SettingsLayoutMixin,
    TagEditingMixin,
    ROIWorkflowMixin,
)


def _user_defined_names(cls: type) -> set[str]:
    """Return non-dunder names defined directly on ``cls`` (not inherited)."""
    return {name for name in cls.__dict__ if not (name.startswith("__") and name.endswith("__"))}


def test_dicom_viewer_app_inherits_qobject_and_all_mixins() -> None:
    app_cls = main_module.DICOMViewerApp
    assert issubclass(app_cls, QObject)
    for mixin in ALL_MIXINS:
        assert issubclass(app_cls, mixin)


def test_qobject_is_first_base_and_mro_entry() -> None:
    app_cls = main_module.DICOMViewerApp
    assert app_cls.__bases__[0] is QObject
    assert app_cls.__mro__[1] is QObject


def test_no_mixin_defines_init() -> None:
    for mixin in ALL_MIXINS:
        assert "__init__" not in mixin.__dict__


def test_zero_method_name_collisions_across_mixins() -> None:
    mixin_names = [_user_defined_names(mixin) for mixin in ALL_MIXINS]
    for i, names_a in enumerate(mixin_names):
        for j, names_b in enumerate(mixin_names):
            if i >= j:
                continue
            overlap = names_a & names_b
            assert overlap == set(), f"Mixin collision: {overlap}"


def test_dicom_viewer_app_body_does_not_shadow_mixin_methods() -> None:
    """DICOMViewerApp's own class dict must not redefine mixin-owned methods."""
    app_names = _user_defined_names(main_module.DICOMViewerApp)
    for mixin in ALL_MIXINS:
        overlap = app_names & _user_defined_names(mixin)
        assert overlap == set(), f"DICOMViewerApp shadows {mixin.__name__}: {overlap}"


def test_initialization_mixin_method_resolves_on_app() -> None:
    """Phase 3: init orchestration lives on InitializationMixin, not DICOMViewerApp body."""
    assert (
        main_module.DICOMViewerApp._init_core_managers
        is InitializationMixin._init_core_managers
    )


def test_subwindow_management_mixin_method_resolves_on_app() -> None:
    """Phase 4: subwindow lifecycle lives on SubwindowManagementMixin, not DICOMViewerApp body."""
    assert (
        main_module.DICOMViewerApp._build_managers_for_subwindow
        is SubwindowManagementMixin._build_managers_for_subwindow
    )


def test_mpr_navigation_mixin_method_resolves_on_app() -> None:
    """Phase 4: MPR navigation lives on MPRNavigationMixin, not DICOMViewerApp body."""
    assert (
        main_module.DICOMViewerApp._update_mpr_navigator_thumbnail
        is MPRNavigationMixin._update_mpr_navigator_thumbnail
    )


def test_ui_handlers_mixin_method_resolves_on_app() -> None:
    """Phase 5: UI handlers live on UIHandlersMixin, not DICOMViewerApp body."""
    assert (
        main_module.DICOMViewerApp._on_undo_requested
        is UIHandlersMixin._on_undo_requested
    )


def test_file_operations_mixin_method_resolves_on_app() -> None:
    """Phase 5: file operations live on FileOperationsMixin, not DICOMViewerApp body."""
    assert main_module.DICOMViewerApp._open_files is FileOperationsMixin._open_files


def test_display_projection_mixin_method_resolves_on_app() -> None:
    """Phase 5: display/projection live on DisplayProjectionMixin, not DICOMViewerApp body."""
    assert (
        main_module.DICOMViewerApp._display_slice
        is DisplayProjectionMixin._display_slice
    )


def test_settings_layout_mixin_method_resolves_on_app() -> None:
    """Phase 5: settings/layout live on SettingsLayoutMixin, not DICOMViewerApp body."""
    assert (
        main_module.DICOMViewerApp._on_layout_changed
        is SettingsLayoutMixin._on_layout_changed
    )


def test_tag_editing_mixin_method_resolves_on_app() -> None:
    """Phase 5: tag editing lives on TagEditingMixin, not DICOMViewerApp body."""
    assert (
        main_module.DICOMViewerApp._on_tag_edited
        is TagEditingMixin._on_tag_edited
    )


def test_roi_workflow_mixin_method_resolves_on_app() -> None:
    """Phase 5: ROI workflow lives on ROIWorkflowMixin, not DICOMViewerApp body."""
    assert (
        main_module.DICOMViewerApp._keyboard_delete_roi
        is ROIWorkflowMixin._keyboard_delete_roi
    )


@pytest.mark.qt
def test_dicom_viewer_app_init_still_constructs(tmp_path) -> None:
    app = instantiate_app(tmp_path)
    assert isinstance(app, main_module.DICOMViewerApp)
    assert isinstance(app, QObject)


@pytest.mark.qt
def test_startup_perf_log_path_does_not_crash(tmp_path, monkeypatch) -> None:
    """``DICOM_PERF_LOG=1`` / ``PERF_LOG`` must not NameError during app construction."""
    monkeypatch.setattr(main_module, "PERF_LOG", True)
    app = instantiate_app(tmp_path)
    assert isinstance(app, main_module.DICOMViewerApp)
    # Explicit helper path (also called from InitializationMixin post-init).
    app._log_startup_perf()
