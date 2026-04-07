# One-off generator: split src/gui/image_viewer.py into view / input / context_menu mixins.
# Run from repository root: python dev-docs/plans/_generate_image_viewer_phase3_split.py

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src" / "gui" / "image_viewer.py"


def lines_1based(path: Path) -> list[str]:
    return path.read_text(encoding="utf-8").splitlines(keepends=True)


def slice_lines(lines: list[str], start: int, end: int) -> str:
    """1-based inclusive line numbers."""
    return "".join(lines[start - 1 : end])


def self_to_viewer(block: str) -> str:
    return re.sub(r"\bself\b", "viewer", block)


def strip_common_indent(block: str, spaces_to_remove: int) -> str:
    out: list[str] = []
    for line in block.splitlines(True):
        if line.strip() == "":
            out.append("\n" if line.endswith("\n") else "")
            continue
        n = 0
        while n < len(line) and line[n] == " ":
            n += 1
        if n >= spaces_to_remove:
            out.append(line[spaces_to_remove:])
        else:
            out.append(line.lstrip())
    return "".join(out)


def main() -> None:
    lines = lines_1based(SRC)

    view_header = '''"""
Image viewer — view / scene / pixmap / zoom / overlays (Phase 3 split).

Mixin used by `gui.image_viewer.ImageViewer` together with input and context-menu helpers.

Requirements: PySide6, PIL, numpy.
"""
from __future__ import annotations

from PySide6.QtWidgets import QGraphicsView, QGraphicsPixmapItem, QApplication
from PySide6.QtCore import Qt, QRectF, QRect, QPointF, QPoint, QTimer
from PySide6.QtGui import QPixmap, QImage, QPainter, QColor, QTransform, QPen
from PIL import Image
from utils.bundled_fonts import make_qfont
from utils.debug_flags import DEBUG_MAGNIFIER, DEBUG_AGENT_LOG
import numpy as np
import os
from typing import Optional, Callable, Any, List, Tuple, Dict, Union, TYPE_CHECKING

if TYPE_CHECKING:
    from tools.roi_manager import ROIItem


class ImageViewerViewMixin:
    """Display, scaling, smoothing, scale/direction overlays, pixel readout helpers."""

'''

    view_body = slice_lines(lines, 327, 1221) + slice_lines(lines, 2827, 3356)
    (ROOT / "src" / "gui" / "image_viewer_view.py").write_text(
        view_header + view_body, encoding="utf-8"
    )

    # Right-press menu body was indented +8 vs function body (inside elif under mousePress)
    press_raw = slice_lines(lines, 1800, 1975)
    press_body = strip_common_indent(self_to_viewer(press_raw), 8)

    # Lambdas must call viewer._toggle_statistic (method on ImageViewer)
    press_body = press_body.replace("viewer._toggle_statistic", "viewer._toggle_statistic")

    release_raw = slice_lines(lines, 2209, 2654)
    release_body = strip_common_indent(self_to_viewer(release_raw), 16)

    cm_text = '''"""
Image viewer context menus (Phase 3 split).

QMenu construction for ROI / annotation / image background.

Requirements: PySide6; `viewer` is the ImageViewer instance.
"""
from __future__ import annotations

import sys
from typing import Any

from PySide6.QtWidgets import QMenu, QApplication
from PySide6.QtCore import Qt, QPointF
from PySide6.QtGui import QActionGroup


def toggle_roi_statistic(viewer: Any, roi: Any, stat_name: str, checked: bool) -> None:
    """Toggle a statistic in the ROI's visible_statistics set and notify coordinators."""
    if checked:
        roi.visible_statistics.add(stat_name)
    else:
        roi.visible_statistics.discard(stat_name)
    viewer.roi_statistics_selection_changed.emit(roi, roi.visible_statistics)


def handle_mouse_press_right_button(viewer: Any, event: Any) -> bool:
    """
    ROI / measurement / annotation context menus on right press.
    Returns True if the event was fully handled (caller should return without super).
    """
''' + press_body + '''

def show_image_background_context_menu_on_right_release(viewer: Any, event: Any) -> None:
    """After short right-click release on image: scene pick + full image context menu."""
''' + release_body

    (ROOT / "src" / "gui" / "image_viewer_context_menu.py").write_text(cm_text, encoding="utf-8")

    input_part_a = slice_lines(lines, 1223, 1797)
    right_delegate = """        elif event.button() == Qt.MouseButton.RightButton:
            from gui.image_viewer_context_menu import handle_mouse_press_right_button
            if handle_mouse_press_right_button(self, event):
                return

"""
    after_press = """        super().mousePressEvent(event)

"""
    toggle_method = """    def _toggle_statistic(self, roi, stat_name: str, checked: bool) -> None:
        from gui.image_viewer_context_menu import toggle_roi_statistic
        toggle_roi_statistic(self, roi, stat_name, checked)

"""
    input_rest = slice_lines(lines, 1996, 2662)
    marker = "                    scene_pos = self.mapToScene(event.position().toPoint())\n"
    exec_line = "                        context_menu.exec(event.globalPosition().toPoint())\n"
    mi = input_rest.find(marker)
    if mi == -1:
        raise RuntimeError("release menu marker not found")
    mj = input_rest.find(exec_line, mi)
    if mj == -1:
        raise RuntimeError("context_menu.exec marker not found")
    mj_end = mj + len(exec_line)
    release_call = """                    from gui.image_viewer_context_menu import (
                        show_image_background_context_menu_on_right_release,
                    )
                    show_image_background_context_menu_on_right_release(self, event)

"""
    input_rest = input_rest[:mi] + release_call + input_rest[mj_end:]

    input_part_c = slice_lines(lines, 2664, 2825)
    input_part_d = slice_lines(lines, 3358, 3427)

    input_header = '''"""
Image viewer — input routing: gestures, wheel, mouse, keys, drag/drop (Phase 3 split).

Mixin listed before `ImageViewerViewMixin` on `ImageViewer` so Qt event overrides resolve first.
"""
from __future__ import annotations

from PySide6.QtWidgets import QGraphicsView, QWidget, QApplication, QMenu
from PySide6.QtCore import Qt, QPointF, QTimer, QEvent
from PySide6.QtGui import (
    QWheelEvent,
    QKeyEvent,
    QMouseEvent,
    QDragEnterEvent,
    QDragMoveEvent,
    QDropEvent,
    QNativeGestureEvent,
)
import os
import time
from typing import Optional

from utils.debug_flags import DEBUG_NAV, DEBUG_MAGNIFIER, DEBUG_AGENT_LOG


class ImageViewerInputMixin:
    """event(), wheel, cursor/mouse modes, mouse press/move/release, keys, DnD."""

'''

    input_body = (
        input_part_a + right_delegate + after_press + toggle_method + input_rest + input_part_c + input_part_d
    )
    (ROOT / "src" / "gui" / "image_viewer_input.py").write_text(
        input_header + input_body, encoding="utf-8"
    )

    slim_header = '''"""
Image Viewer Widget

Coordinates display and interaction via `ImageViewerInputMixin`, `ImageViewerViewMixin`,
and `image_viewer_context_menu` (Phase 3). Behavior matches the pre-split implementation.

Requirements: PySide6, PIL, numpy.
"""
from __future__ import annotations

from PySide6.QtWidgets import QGraphicsView, QGraphicsScene, QGraphicsPixmapItem, QWidget
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QColor, QTransform
from PIL import Image
import os
from typing import Optional, Callable, Any, List, Tuple, TYPE_CHECKING

from gui.image_viewer_input import ImageViewerInputMixin
from gui.image_viewer_view import ImageViewerViewMixin

if TYPE_CHECKING:
    from tools.roi_manager import ROIItem


'''

    class_and_signals = slice_lines(lines, 41, 127)
    class_and_signals = class_and_signals.replace(
        "class ImageViewer(QGraphicsView):",
        "class ImageViewer(ImageViewerInputMixin, ImageViewerViewMixin, QGraphicsView):",
    )
    init_only = slice_lines(lines, 129, 325)

    (ROOT / "src" / "gui" / "image_viewer.py").write_text(
        slim_header + class_and_signals + init_only + "\n", encoding="utf-8"
    )

    print("Phase 3 split written under src/gui/.")


if __name__ == "__main__":
    main()
