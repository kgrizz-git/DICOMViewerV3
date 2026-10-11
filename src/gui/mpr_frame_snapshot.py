"""Retain and restore a pane's last-good pixels without re-running rendering."""

from dataclasses import dataclass
from typing import Any, cast

from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QGraphicsPixmapItem, QGraphicsView


@dataclass
class FrameSnapshot:
    """Image reference and implicitly shared Qt pixmap plus viewport geometry."""

    original: Any
    pixmap: Any = None
    transform: Any = None
    scene_rect: Any = None
    scroll: tuple[int, int] = (0, 0)
    attributes: dict[str, Any] | None = None


def capture_frame(viewer: Any) -> FrameSnapshot | None:
    """Capture a real Qt frame, or a duck-typed image used by offline tests."""
    if viewer is None:
        return None
    saved = FrameSnapshot(getattr(viewer, "original_image", None))
    if not isinstance(viewer, QGraphicsView):
        return saved
    viewer = cast(Any, viewer)  # ImageViewer adds attributes to QGraphicsView.
    item = getattr(viewer, "image_item", None)
    saved.pixmap = QPixmap(item.pixmap()) if isinstance(item, QGraphicsPixmapItem) else QPixmap()
    saved.transform = viewer.transform()
    saved.scene_rect = viewer.sceneRect()
    saved.scroll = (viewer.horizontalScrollBar().value(), viewer.verticalScrollBar().value())
    saved.attributes = {name: getattr(viewer, name) for name in (
        "zoom_factor", "base_fit_scale", "image_inverted",
    ) if hasattr(viewer, name)}
    return saved


def restore_frame(viewer: Any, saved: FrameSnapshot | None) -> bool:
    """Restore pixels directly; Qt rollback does not call any image renderer."""
    if viewer is None or saved is None:
        return False
    if not isinstance(viewer, QGraphicsView):
        if saved.original is not None:
            viewer.set_display_final_image(
                saved.original, preserve_view=True,
                image_inverted=bool(getattr(viewer, "image_inverted", False)),
            )
        viewer.original_image = saved.original
        return True
    viewer = cast(Any, viewer)  # ImageViewer owns its scene and image item.
    item = getattr(viewer, "image_item", None)
    if isinstance(item, QGraphicsPixmapItem):
        viewer.scene.removeItem(item)
    viewer.image_item = None
    if saved.pixmap is not None and not saved.pixmap.isNull():
        viewer.image_item = QGraphicsPixmapItem(saved.pixmap)
        viewer.scene.addItem(viewer.image_item)
    viewer.original_image = saved.original
    for name, value in (saved.attributes or {}).items():
        setattr(viewer, name, value)
    viewer.setSceneRect(saved.scene_rect)
    viewer.setTransform(saved.transform)
    viewer.horizontalScrollBar().setValue(saved.scroll[0])
    viewer.verticalScrollBar().setValue(saved.scroll[1])
    viewer.viewport().update()
    return True
