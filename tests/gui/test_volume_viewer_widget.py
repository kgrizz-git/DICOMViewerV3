from __future__ import annotations

import sys
import types
from typing import ClassVar

import pytest
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QLabel, QWidget

from core.volume_3d_user_presets import snapshot_current_settings
from core.volume_renderer import (
    BACKGROUND_COLORS,
    BLEND_MODES,
    BUILTIN_PRESETS,
    QUALITY_MODES,
    RENDER_METHODS,
)
from gui.volume_viewer_widget import VolumeViewerWidget


class _FakeTransferFunctionEditorWidget(QWidget):
    points_changed = Signal(list)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.points = []

    def set_points(self, points) -> None:
        self.points = list(points)


class _FakeCamera:
    def __init__(self) -> None:
        self.azimuth_calls: list[float] = []

    def Azimuth(self, value: float) -> None:
        self.azimuth_calls.append(value)

    def GetPosition(self):
        return (1.0, 2.0, 3.0)

    def GetFocalPoint(self):
        return (0.0, 0.0, 0.0)

    def GetClippingRange(self):
        return (0.1, 1000.0)


class _FakeInput:
    def __init__(self, dims=(256, 256, 600)) -> None:
        self._dims = dims

    def GetDimensions(self):
        return self._dims


class _FakeMapper:
    def __init__(self, dims=(256, 256, 600)) -> None:
        self._input = _FakeInput(dims)

    def GetClassName(self):
        return "vtkSmartVolumeMapper"

    def GetLastUsedRenderMode(self):
        return 2

    def GetInput(self):
        return self._input


class _FakeVolumeProperty:
    def GetShade(self):
        return 1

    def GetAmbient(self):
        return 0.3

    def GetDiffuse(self):
        return 0.7

    def GetSpecular(self):
        return 0.2


class _FakeVolume:
    def __init__(self, dims=(256, 256, 600)) -> None:
        self._mapper = _FakeMapper(dims)
        self._property = _FakeVolumeProperty()

    def GetMapper(self):
        return self._mapper

    def GetBounds(self):
        return (0, 1, 0, 1, 0, 1)

    def GetVisibility(self):
        return True

    def GetProperty(self):
        return self._property


class _FakeVolumes:
    def __init__(self, volume=None) -> None:
        self._volume = volume or _FakeVolume()

    def InitTraversal(self) -> None:
        pass

    def GetNextVolume(self):
        return self._volume

    def GetNumberOfItems(self):
        return 1


class _FakeScene:
    def __init__(self) -> None:
        self.camera = _FakeCamera()
        self.volumes = _FakeVolumes()
        self.reset_clipping_calls = 0
        self.reset_camera_calls = 0

    def GetActiveCamera(self):
        return self.camera

    def GetVolumes(self):
        return self.volumes

    def ResetCameraClippingRange(self) -> None:
        self.reset_clipping_calls += 1

    def ResetCamera(self) -> None:
        self.reset_camera_calls += 1

    def ComputeVisiblePropBounds(self):
        return (0.0, 10.0, 0.0, 20.0, 0.0, 30.0)


class _FakeStyle:
    def __init__(self) -> None:
        self.observers: list[str] = []

    def AddObserver(self, event_name: str, callback) -> None:
        self.observers.append(event_name)

    def GetClassName(self):
        return "FakeInteractorStyle"


class _FakeIren:
    def __init__(self) -> None:
        self.style = _FakeStyle()
        self.observers: list[str] = []
        self.key = ""

    def GetInteractorStyle(self):
        return self.style

    def AddObserver(self, event_name: str, callback) -> None:
        self.observers.append(event_name)

    def GetKeySym(self):
        return self.key


class _FakeRenderWindow:
    def __init__(self) -> None:
        self.render_count = 0
        self.iren = _FakeIren()

    def GetInteractor(self):
        return self.iren

    def Render(self) -> None:
        self.render_count += 1

    def GetSize(self):
        return (640, 480)


class _FakeInteractor:
    def __init__(self, render_window: _FakeRenderWindow) -> None:
        self.render_window = render_window
        self.initialized = False
        self.finalized = False

    def GetRenderWindow(self):
        return self.render_window

    def Initialize(self) -> None:
        self.initialized = True

    def Finalize(self) -> None:
        self.finalized = True

    def width(self) -> int:
        return 320

    def height(self) -> int:
        return 240


class _FakeConfig:
    def __init__(self, user_presets=None) -> None:
        self.store = {}
        self.saved = False
        self.user_presets = list(user_presets or [])

    def get(self, key):
        return self.store.get(key)

    def set(self, key, value) -> None:
        self.store[key] = value

    def save_config(self) -> None:
        self.saved = True

    def get_volume_3d_user_presets(self):
        return list(self.user_presets)

    def set_volume_3d_user_presets(self, presets) -> None:
        self.user_presets = list(presets)


class _FakeRenderer:
    def __init__(self, *, ssao_available=True) -> None:
        self.ssao_available = ssao_available
        self.scene = _FakeScene()
        self.background_calls: list[tuple[float, float, float]] = []
        self.quality_modes: list[str] = []
        self.views: list[str] = []
        self.render_methods: list[str] = []
        self.interactive_quality: list[bool] = []
        self.blend_modes: list[str] = []
        self.cropping_planes = None
        self.cleared_cropping = 0
        self.custom_points = None
        self.cleanup_called = False
        self.reset_camera_calls = 0
        self.check_gpu_fallback_calls = 0
        self.global_opacity = None
        self.window_level = None
        self.threshold = None
        self.response = None
        self.smoothing = None
        self.ssao_enabled = None
        self.gradient_enabled = None
        self.gradient_strength = None
        self.interpolation = None
        self.lighting = None
        self.preset = None
        self._mapper = types.SimpleNamespace(GetSampleDistance=lambda: 0.8)

    def get_renderer(self):
        return self.scene

    def is_ssao_available(self) -> bool:
        return self.ssao_available

    def set_background(self, r, g, b) -> None:
        self.background_calls.append((r, g, b))

    def set_preset(self, preset) -> None:
        self.preset = preset

    def set_global_opacity(self, value) -> None:
        self.global_opacity = value

    def set_window_level(self, window, level) -> None:
        self.window_level = (window, level)

    def reset_window_level(self):
        return (123.0, -45.0)

    def set_threshold(self, value) -> None:
        self.threshold = value

    def reset_camera(self) -> None:
        self.reset_camera_calls += 1

    def set_view(self, name: str) -> None:
        self.views.append(name)

    def set_quality_mode(self, name: str) -> None:
        self.quality_modes.append(name)

    def set_render_method(self, method: str) -> None:
        self.render_methods.append(method)

    def set_interactive_quality(self, enabled: bool) -> None:
        self.interactive_quality.append(enabled)

    def check_gpu_fallback(self, render_window) -> None:
        self.check_gpu_fallback_calls += 1

    def set_custom_opacity_points(self, points) -> None:
        self.custom_points = points

    def set_lighting(self, *params) -> None:
        self.lighting = params

    def set_blend_mode(self, mode: str) -> None:
        self.blend_modes.append(mode)

    def set_display_smoothing(self, value: float) -> None:
        self.smoothing = value

    def set_ssao_enabled(self, enabled: bool) -> None:
        self.ssao_enabled = enabled

    def set_gradient_opacity_enabled(self, enabled: bool) -> None:
        self.gradient_enabled = enabled

    def set_gradient_opacity_strength(self, value: float) -> None:
        self.gradient_strength = value

    def set_interpolation(self, enabled: bool) -> None:
        self.interpolation = enabled

    def clear_cropping(self) -> None:
        self.cleared_cropping += 1

    def set_cropping(self, plane_list) -> None:
        self.cropping_planes = list(plane_list)

    def cleanup(self) -> None:
        self.cleanup_called = True

    def set_opacity_response(self, gamma: float) -> None:
        self.response = gamma


class _FakeMessageBox:
    warnings: ClassVar[list[tuple]] = []
    infos: ClassVar[list[tuple]] = []
    questions: ClassVar[list[tuple]] = []
    next_question_answer = None
    StandardButton = types.SimpleNamespace(Yes=1, No=2)

    @classmethod
    def warning(cls, *args):
        cls.warnings.append(args)
        return None

    @classmethod
    def information(cls, *args):
        cls.infos.append(args)
        return None

    @classmethod
    def question(cls, *args):
        cls.questions.append(args)
        return cls.next_question_answer


class _FakeInputDialog:
    next_value = ("", False)

    @classmethod
    def getText(cls, *args, **kwargs):
        return cls.next_value


class _FakePlanes:
    def __init__(self) -> None:
        self._planes = ["p0", "p1", "p2"]

    def GetNumberOfPlanes(self):
        return len(self._planes)

    def GetPlane(self, index: int):
        return self._planes[index]


class _FakeBoxRepresentation:
    def __init__(self) -> None:
        self.place_factor = None
        self.bounds = None

    def SetPlaceFactor(self, value: float) -> None:
        self.place_factor = value

    def PlaceWidget(self, bounds) -> None:
        self.bounds = list(bounds)

    def GetPlanes(self, planes) -> None:
        planes._planes = ["a", "b", "c", "d"]


class _FakeBoxWidget2:
    def __init__(self) -> None:
        self.rep = None
        self.interactor = None
        self.observers: list[str] = []
        self.on_count = 0
        self.off_count = 0

    def SetRepresentation(self, rep) -> None:
        self.rep = rep

    def SetInteractor(self, interactor) -> None:
        self.interactor = interactor

    def AddObserver(self, event_name: str, callback) -> None:
        self.observers.append(event_name)

    def On(self) -> None:
        self.on_count += 1

    def Off(self) -> None:
        self.off_count += 1

    def GetRepresentation(self):
        return self.rep


class _UpdateTrackingWidget(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.update_calls = 0

    def update(self) -> None:
        self.update_calls += 1
        super().update()


def _install_fake_tf_editor(monkeypatch) -> None:
    module = types.ModuleType("gui.transfer_function_editor_widget")
    module.TransferFunctionEditorWidget = _FakeTransferFunctionEditorWidget
    monkeypatch.setitem(sys.modules, "gui.transfer_function_editor_widget", module)


def _make_widget(monkeypatch, qapp, *, renderer=None, config=None) -> VolumeViewerWidget:
    monkeypatch.setattr(VolumeViewerWidget, "_setup_ui", lambda self: None)
    widget = VolumeViewerWidget(
        renderer or _FakeRenderer(),
        config_manager=config,
    )
    widget._viewport_container = _UpdateTrackingWidget()
    widget._overlay_label = QLabel(widget._viewport_container)
    return widget


def _install_dialog_stubs(monkeypatch) -> None:
    _FakeMessageBox.warnings = []
    _FakeMessageBox.infos = []
    _FakeMessageBox.questions = []
    _FakeMessageBox.next_question_answer = None
    _FakeInputDialog.next_value = ("", False)
    monkeypatch.setattr("gui.volume_viewer_widget.QMessageBox", _FakeMessageBox)
    monkeypatch.setattr("gui.volume_viewer_widget.QInputDialog", _FakeInputDialog)


@pytest.mark.qt
def test_build_controls_creates_expected_widgets(monkeypatch, qapp) -> None:
    _install_fake_tf_editor(monkeypatch)
    renderer = _FakeRenderer(ssao_available=False)
    widget = _make_widget(monkeypatch, qapp, renderer=renderer)

    scroll = widget._build_controls()
    widget._refresh_preset_combo(select_index=0)

    assert scroll.widget() is not None
    assert widget._preset_combo.count() > len(BUILTIN_PRESETS)
    assert widget._render_method_combo.count() == len(RENDER_METHODS)
    assert widget._blend_mode_combo.count() == len(BLEND_MODES)
    assert widget._background_combo.count() == len(BACKGROUND_COLORS)
    assert widget._detail_slider.maximum() == len(QUALITY_MODES) - 1
    assert widget._advanced_group.isVisible() is False
    assert widget._ssao_cb.isEnabled() is False


@pytest.mark.qt
def test_initialize_and_deferred_init_cover_setup_paths(monkeypatch, qapp) -> None:
    _install_fake_tf_editor(monkeypatch)
    renderer = _FakeRenderer()
    widget = _make_widget(monkeypatch, qapp, renderer=renderer)
    widget._build_controls()
    render_window = _FakeRenderWindow()
    interactor = _FakeInteractor(render_window)
    widget._interactor = interactor
    widget._vtk_render_window = render_window

    widget.initialize("MR", rescale_applied=True)
    widget._deferred_vtk_init()

    assert widget._current_modality == "MR"
    assert widget._scalar_domain_label.text()
    assert renderer.background_calls
    assert interactor.initialized is True
    assert "StartInteractionEvent" in render_window.iren.style.observers
    assert "EndInteractionEvent" in render_window.iren.style.observers
    assert "KeyPressEvent" in render_window.iren.observers
    assert renderer.reset_camera_calls == 1
    assert renderer.check_gpu_fallback_calls == 1
    assert render_window.render_count >= 1
    assert widget._initialized is True


@pytest.mark.qt
def test_preset_combo_mapping_and_last_preset_persistence(monkeypatch, qapp) -> None:
    _install_fake_tf_editor(monkeypatch)
    config = _FakeConfig()
    widget = _make_widget(monkeypatch, qapp, renderer=_FakeRenderer(), config=config)
    widget._build_controls()
    widget._user_presets = [
        snapshot_current_settings(
            name="Saved One",
            base_preset=BUILTIN_PRESETS[0].name,
            opacity=80.0,
            window=2000.0,
            level=0.0,
            threshold=0,
            background="Black",
            quality="Normal",
        )
    ]

    widget._refresh_preset_combo(select_index=len(BUILTIN_PRESETS))

    assert widget._current_logical_index() == len(BUILTIN_PRESETS)
    assert widget._is_user_preset_logical(widget._current_logical_index()) is True
    assert widget._current_base_preset_name() == BUILTIN_PRESETS[0].name

    widget._current_modality = "CT"
    widget._save_last_preset(BUILTIN_PRESETS[1].name)

    assert config.saved is True
    assert config.store[widget._LAST_PRESET_CONFIG_KEY]["CT"] == BUILTIN_PRESETS[1].name
    assert widget._load_last_preset_index() == 1


@pytest.mark.qt
def test_apply_control_values_and_user_preset_update_renderer(monkeypatch, qapp) -> None:
    _install_fake_tf_editor(monkeypatch)
    renderer = _FakeRenderer()
    widget = _make_widget(monkeypatch, qapp, renderer=renderer)
    widget._build_controls()
    widget._refresh_preset_combo(select_index=0)

    widget._apply_control_values(opacity=150.0, window=222.4, level=-55.5, threshold=999)

    assert widget._threshold_label.text() == "+500"
    assert renderer.global_opacity is not None
    assert renderer.window_level == (222.4, -55.5)
    assert renderer.threshold == 500.0

    record = snapshot_current_settings(
        name="Saved Two",
        base_preset=BUILTIN_PRESETS[0].name,
        opacity=42.0,
        window=321.0,
        level=-12.0,
        threshold=-25,
        background=BACKGROUND_COLORS[1][0],
        quality=QUALITY_MODES[2][0],
    )
    widget._apply_user_preset(record)

    assert renderer.preset is BUILTIN_PRESETS[0]
    assert renderer.background_calls[-1] == BACKGROUND_COLORS[1][1]
    assert widget._detail_auto_cb.isChecked() is False
    assert widget._detail_slider.value() == 2
    assert renderer.quality_modes[-1] == QUALITY_MODES[2][0]


@pytest.mark.qt
def test_overlay_text_keypress_status_and_cleanup(monkeypatch, qapp) -> None:
    _install_fake_tf_editor(monkeypatch)
    renderer = _FakeRenderer()
    widget = _make_widget(monkeypatch, qapp, renderer=renderer)
    widget._build_controls()
    widget._refresh_preset_combo(select_index=0)

    widget._overlay_text_prev = "Line1\nLine2\nLine3\nLine4"
    widget._detail_slider.setValue(1)
    widget._blend_mode_combo.setCurrentIndex(0)
    widget._update_overlay_text()

    assert widget._overlay_label.text()
    assert widget._viewport_container.update_calls >= 1
    assert "Mapper:" in widget._render_status_label.text() or widget._render_status_label.text() == ""

    render_window = _FakeRenderWindow()
    interactor = _FakeInteractor(render_window)
    widget._interactor = interactor
    widget._vtk_render_window = render_window
    widget._initialized = True

    render_window.iren.key = "r"
    widget._on_key_press()
    render_window.iren.key = "plus"
    widget._opacity_spin.setValue(95.0)
    start_opacity = widget._opacity_spin.value()
    widget._on_key_press()
    render_window.iren.key = "a"
    widget._on_key_press()
    assert widget._auto_rotate_btn.isChecked() is True
    render_window.iren.key = "bracketright"
    old_index = widget._preset_combo.currentIndex()
    widget._on_key_press()

    widget._on_toggle_advanced()
    widget._update_render_status()
    widget._on_interaction_start()
    widget._on_interaction_end()
    widget._on_render_method_changed(1)
    widget._render()
    widget.cleanup()

    assert renderer.views[-1] == "Anterior"
    assert widget._opacity_spin.value() == start_opacity + 5.0
    assert widget._auto_rotate_btn.isChecked() is False
    assert widget._preset_combo.currentIndex() >= old_index
    assert widget._advanced_group.isHidden() is False
    assert "Mapper:" in widget._render_status_label.text()
    assert renderer.interactive_quality[-2:] == [True, False]
    assert renderer.render_methods[-1] == RENDER_METHODS[1]
    assert renderer.cleanup_called is True
    assert interactor.finalized is True


@pytest.mark.qt
def test_save_preset_flow_and_validation(monkeypatch, qapp) -> None:
    _install_fake_tf_editor(monkeypatch)
    _install_dialog_stubs(monkeypatch)
    config = _FakeConfig()
    widget = _make_widget(monkeypatch, qapp, renderer=_FakeRenderer(), config=config)
    widget._build_controls()
    widget._refresh_preset_combo(select_index=0)

    no_config_widget = _make_widget(monkeypatch, qapp, renderer=_FakeRenderer(), config=None)
    no_config_widget._build_controls()
    no_config_widget._refresh_preset_combo(select_index=0)
    no_config_widget._on_save_preset()
    assert any("not available" in call[2] for call in _FakeMessageBox.warnings)

    _FakeMessageBox.warnings = []
    monkeypatch.setattr(widget, "_current_base_preset_name", lambda: "bogus")
    widget._on_save_preset()
    assert any("Could not determine the base transfer function" in call[2] for call in _FakeMessageBox.warnings)

    monkeypatch.setattr(widget, "_current_base_preset_name", lambda: BUILTIN_PRESETS[0].name)
    _FakeMessageBox.warnings = []
    _FakeInputDialog.next_value = (BUILTIN_PRESETS[0].name, True)
    widget._on_save_preset()
    assert any("reserved for a built-in preset" in call[2] for call in _FakeMessageBox.warnings)

    _FakeInputDialog.next_value = ("My Saved Preset", True)
    widget._user_presets = [
        snapshot_current_settings(
            name="My Saved Preset",
            base_preset=BUILTIN_PRESETS[0].name,
            opacity=60.0,
            window=100.0,
            level=0.0,
            threshold=0,
            background="Black",
            quality="Normal",
        )
    ]
    _FakeMessageBox.next_question_answer = object()
    widget._on_save_preset()
    assert _FakeMessageBox.questions
    assert len(config.user_presets) == 0

    _FakeMessageBox.infos = []
    _FakeMessageBox.next_question_answer = _FakeMessageBox.StandardButton.Yes
    widget._opacity_spin.setValue(44.0)
    widget._window_spin.setValue(222.0)
    widget._level_spin.setValue(-11.0)
    widget._threshold_slider.setValue(12)
    widget._background_combo.setCurrentIndex(1)
    widget._detail_slider.setValue(2)
    widget._on_save_preset()

    assert len(config.user_presets) == 1
    saved = config.user_presets[0]
    assert saved["name"] == "My Saved Preset"
    assert saved["background"] == BACKGROUND_COLORS[1][0]
    assert saved["quality"] == QUALITY_MODES[2][0]
    assert any("saved successfully" in call[2] for call in _FakeMessageBox.infos)
    assert widget._preset_combo.currentIndex() >= len(BUILTIN_PRESETS)


@pytest.mark.qt
def test_misc_control_handlers_and_crop_box_paths(monkeypatch, qapp) -> None:
    _install_fake_tf_editor(monkeypatch)
    _install_dialog_stubs(monkeypatch)
    renderer = _FakeRenderer()
    widget = _make_widget(monkeypatch, qapp, renderer=renderer)
    widget._build_controls()
    widget._refresh_preset_combo(select_index=0)
    render_window = _FakeRenderWindow()
    interactor = _FakeInteractor(render_window)
    widget._interactor = interactor
    widget._vtk_render_window = render_window
    widget._initialized = True

    monkeypatch.setattr("gui.volume_viewer_widget.QDesktopServices.openUrl", lambda url: False)
    widget._on_open_documentation()
    assert any("Could not open the documentation link" in call[2] for call in _FakeMessageBox.warnings)

    widget._on_response_changed(25)
    widget._on_background_changed(1)
    widget._on_window_slider_changed(321)
    widget._on_window_spin_changed(444.0)
    widget._on_level_slider_changed(-12)
    widget._on_level_spin_changed(55.0)
    widget._on_reset_window_level()
    widget._on_threshold_changed(-14)
    widget._on_reset_camera()
    widget._on_set_view("Left")
    widget._on_auto_rotate_toggled(True)
    widget._auto_rotate_step()
    widget._on_tf_points_changed([(1, 0.1), (2, 0.9)])
    widget._on_lighting_changed(2)
    widget._on_overlay_toggled(Qt.CheckState.Unchecked.value)
    widget._on_blend_mode_changed(1)
    widget._on_smoothing_changed(1.2)
    widget._on_ssao_changed(Qt.CheckState.Checked.value)
    widget._on_gradient_opacity_changed(Qt.CheckState.Checked.value)
    widget._on_go_strength_changed(75)
    widget._on_interpolation_changed(Qt.CheckState.Checked.value)
    widget._on_detail_auto_changed(Qt.CheckState.Checked.value)
    widget._on_detail_changed(0)

    fake_vtk = types.SimpleNamespace(
        vtkBoxWidget2=_FakeBoxWidget2,
        vtkBoxRepresentation=_FakeBoxRepresentation,
        vtkPlanes=_FakePlanes,
    )
    monkeypatch.setattr("gui.volume_viewer_widget.vtk_mod", fake_vtk)
    widget._on_crop_toggled(Qt.CheckState.Checked.value)
    widget._on_crop_box_changed()
    widget._on_crop_toggled(Qt.CheckState.Unchecked.value)
    widget._on_reset_crop()

    assert renderer.response is not None
    assert renderer.background_calls[-1] == BACKGROUND_COLORS[1][1]
    assert renderer.window_level[0] in {321.0, 444.0}
    assert renderer.window_level[1] == 55.0
    assert widget._threshold_label.text() == "-14"
    assert renderer.reset_camera_calls >= 1
    assert renderer.views[-1] == "Left"
    assert render_window.render_count >= 2
    assert renderer.custom_points == [(1.0, 0.1), (2.0, 0.9)]
    assert renderer.lighting == widget._LIGHTING_PRESETS[2]
    assert widget._overlay_label.isVisible() is False
    assert renderer.blend_modes[-1] == BLEND_MODES[1][0]
    assert renderer.smoothing == 1.2
    assert renderer.ssao_enabled is True
    assert renderer.gradient_enabled is True
    assert renderer.gradient_strength == 0.75
    assert renderer.interpolation is False
    assert renderer.quality_modes
    assert renderer.cropping_planes == ["a", "b", "c", "d"]
    assert renderer.cleared_cropping >= 1
