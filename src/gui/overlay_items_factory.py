"""
Graphics overlay item factory — constructs QGraphicsTextItem nodes for DICOM corner overlays.

Used by ``OverlayManager`` for the QGraphicsItem (non-widget) overlay path.

Inputs: plain text, scene position, font color/size, alignment, optional fixed width for right align.

Outputs: Configured ``QGraphicsTextItem`` (ItemIgnoresTransformations, z-order).

Requirements: PySide6.
"""

from typing import Optional

from PySide6.QtWidgets import QGraphicsTextItem, QGraphicsItem
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QColor, QTransform, QTextDocument, QTextOption


def create_graphics_overlay_text_item(
    text: str,
    x: float,
    y: float,
    font_color: tuple[int, int, int],
    font_size: int,
    alignment: Qt.AlignmentFlag = Qt.AlignmentFlag.AlignLeft,
    text_width: Optional[float] = None,
) -> QGraphicsTextItem:
    """
    Create a corner overlay text item with fixed screen-space font sizing.

    Font size is in points; sizes below 6pt use a 6pt font with a scale transform.
    """
    text_item = QGraphicsTextItem()
    text_item.setDefaultTextColor(QColor(*font_color))

    if font_size < 6:
        font = QFont("Arial", 6)
        scale_factor = font_size / 6.0
        transform = QTransform()
        transform.scale(scale_factor, scale_factor)
        text_item.setTransform(transform)
    else:
        font = QFont("Arial", font_size)

    font.setBold(True)
    text_item.setFont(font)

    document = QTextDocument()
    document.setDefaultFont(font)
    document.setDocumentMargin(0)
    text_option = QTextOption()
    if alignment & Qt.AlignmentFlag.AlignRight:
        text_option.setAlignment(Qt.AlignmentFlag.AlignRight)
    elif alignment & Qt.AlignmentFlag.AlignLeft:
        text_option.setAlignment(Qt.AlignmentFlag.AlignLeft)
    else:
        text_option.setAlignment(Qt.AlignmentFlag.AlignLeft)
    document.setDefaultTextOption(text_option)
    document.setPlainText(text)
    if text_width is not None and (alignment & Qt.AlignmentFlag.AlignRight):
        document.setTextWidth(text_width)
    text_item.setDocument(document)

    text_item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations, True)
    text_item.setZValue(1000)
    text_item.setPos(x, y)

    return text_item
