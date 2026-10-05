"""``SliceDisplayManager.projection_drawn`` says whether the last draw was a projection."""

from __future__ import annotations

from types import SimpleNamespace

from gui.slice_display_manager import SliceDisplayManager


def _manager(enabled: bool, result):
    manager = SliceDisplayManager.__new__(SliceDisplayManager)
    manager.projection_enabled = enabled
    manager._create_projection_image = lambda *a, **k: result  # type: ignore[method-assign]
    return manager


def _build(manager):
    return manager._try_build_projection_image(
        SimpleNamespace(), {}, "st", "se", 0, 40.0, 400.0, False, None, None, voi_from_dicom=True
    )


def test_a_drawn_projection_is_recorded() -> None:
    manager = _manager(True, "image")
    assert _build(manager) == "image"
    assert manager.projection_drawn is True


def test_a_failed_or_disabled_projection_is_not() -> None:
    failed = _manager(True, None)
    assert _build(failed) is None
    assert failed.projection_drawn is False
    disabled = _manager(False, "image")
    disabled.projection_drawn = True
    assert _build(disabled) is None
    assert disabled.projection_drawn is False


def test_an_exception_is_not_recorded_as_drawn() -> None:
    manager = _manager(True, None)

    def boom(*_a, **_k):
        raise RuntimeError("x")

    manager._create_projection_image = boom  # type: ignore[method-assign]
    assert _build(manager) is None
    assert manager.projection_drawn is False
