"""
About Dialog

Builds and shows the application About dialog with scrollable HTML content,
embedded icon, theme-based link styling, and an in-dialog disclaimer link.

Inputs:
    - Parent widget (typically MainWindow)
    - ConfigManager for theme selection
    - Optional callback when the disclaimer:// anchor is clicked

Outputs:
    - Modal About dialog (blocks until dismissed)

Requirements:
    - PySide6 for dialog components
    - ConfigManager for theme
    - version.APP_VERSION for displayed version string
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import QBuffer, QIODevice, Qt, QUrl
from PySide6.QtGui import QDesktopServices, QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from utils.config_manager import ConfigManager
from version import __version__ as APP_VERSION


def _on_disclaimer_link_clicked(
    url: QUrl,
    on_disclaimer: Callable[[], None] | None,
) -> None:
    """
    Handle anchor link clicks in About dialog.

    Args:
        url: QUrl of the clicked link
        on_disclaimer: Callback invoked when disclaimer:// is clicked
    """
    scheme = url.scheme()
    if scheme == "disclaimer" and on_disclaimer is not None:
        on_disclaimer()
    elif scheme in ("http", "https"):
        QDesktopServices.openUrl(url)


def show_about(
    parent: QWidget,
    config_manager: ConfigManager,
    on_disclaimer: Callable[[], None] | None = None,
) -> None:
    """Show the about dialog with scrollable content."""
    dialog = QDialog(parent)
    dialog.setWindowTitle("About DICOM Viewer V3")
    dialog.setMinimumSize(500, 400)
    dialog.resize(600, 500)

    theme = config_manager.get_theme()
    layout = QVBoxLayout(dialog)

    # Create scrollable text area - use QTextBrowser for anchor link support
    text_edit = QTextBrowser()
    text_edit.setOpenExternalLinks(False)  # Don't open external links in browser
    text_edit.setReadOnly(True)
    # Styling inherited from app-level QSS (QDialog → QWidget, QTextBrowser → QTextEdit)

    # Load icon and convert to base64 for HTML embedding
    icon_html = ""
    icon_path = (
        Path(__file__).parent.parent.parent.parent
        / "resources"
        / "icons"
        / "dvv6ldvv6ldvv6ld_edit-removebg-preview.png"
    )
    if icon_path.exists():
        pixmap = QPixmap(str(icon_path))
        # Scale icon to reasonable size (96x96 pixels for inline display)
        scaled_pixmap = pixmap.scaled(
            96,
            96,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        # Convert to base64 for HTML embedding
        buffer = QBuffer()
        buffer.open(QIODevice.OpenModeFlag.WriteOnly)
        scaled_pixmap.save(buffer, "PNG")
        icon_data = bytes(buffer.data().toBase64().data()).decode("ascii")
        icon_html = (
            f'<img src="data:image/png;base64,{icon_data}" '
            'style="vertical-align: middle; margin-right: 10px;" />'
        )

    # Create HTML content with theme-based link styling
    if theme == "dark":
        link_color = "#4a9eff"  # Light blue for dark theme
    else:
        link_color = "#2980b9"  # Darker blue for light theme

    html_content = f"""<html>
<head>
    <style>
        a {{ color: {link_color}; }}
    </style>
</head>
<body>
    <h2>{icon_html}Medical Physics DICOM Viewer</h2>
    <p><b>Version {APP_VERSION}</b></p>
    <p><b>Made by Kevin Grizzard</b><br>
    Available at <a href='https://github.com/kgrizz-git/DICOMViewerV3'>https://github.com/kgrizz-git/DICOMViewerV3</a></p>
    <hr>
    <p>A cross-platform DICOM viewer application.</p>
    <h3>Features:</h3>
    <h4>File Management:</h4>
    <ul>
    <li>Open DICOM files and folders</li>
    <li>Recursive folder search</li>
    <li>Multiple file selection</li>
    <li>Recent files support</li>
    </ul>
    <h4>Image Display:</h4>
    <ul>
    <li>Zoom and pan functionality</li>
    <li>Window width and level adjustment</li>
    <li>Window/Level presets: Multiple presets from DICOM tags with context menu switching</li>
    <li>Slice navigation (arrow keys, mouse wheel)</li>
    <li>Series navigation with thumbnail navigator</li>
    <li>Dark and light themes</li>
    <li>Reset view to fit viewport</li>
    <li>Intensity projections: Combine slices (AIP, MIP, MinIP)</li>
    <li>Image inversion (I key)</li>
    <li>Cine Playback: Automatic frame-by-frame playback for multi-frame DICOM series with a play/pause toggle, stop, adjustable speed, and loop option</li>
    <li>Image Fusion: Overlay functional imaging (PET/SPECT) on anatomical imaging (CT/MR) with automatic spatial alignment, adjustable opacity/threshold/colormap, and 2D/3D resampling modes</li>
    </ul>
    <h4>Analysis Tools:</h4>
    <ul>
    <li>Draw elliptical and rectangular ROIs</li>
    <li>ROI statistics (mean, std dev, min, max, area)</li>
    <li>Distance measurements (pixels, mm, cm)</li>
    <li>Text annotations: Add and edit text labels on images</li>
    <li>Arrow annotations: Add arrows to point to features</li>
    <li>Histogram display: View pixel value distribution with window/level overlay (Cmd+Shift+H / Ctrl+Shift+H)</li>
    <li>Undo/redo functionality</li>
    </ul>
    <h4>Metadata and Overlays:</h4>
    <ul>
    <li>Customizable DICOM metadata overlays</li>
    <li>Toggle overlay visibility (3 states)</li>
    <li>View and edit all DICOM tags</li>
    <li>Tag filtering/search functionality</li>
    <li>Expand/collapse tag groups in metadata panel</li>
    <li>Reorder columns in metadata panel</li>
    <li>Privacy View: Toggle to mask patient-related tags in display (View menu, context menu, or Cmd+P/Ctrl+P)</li>
    <li>Anonymization on Export: Option to anonymize patient information when exporting to DICOM</li>
    <li>Export selected tags to Excel/CSV</li>
    <li>Annotations support: Presentation States, Key Objects, embedded overlays</li>
    </ul>
    <h4>Data Management:</h4>
    <ul>
    <li>Clear ROIs from slice or dataset</li>
    <li>Clear measurements</li>
    <li>ROI list panel with selection</li>
    </ul>
    <h4>Export:</h4>
    <ul>
    <li>Export images as PNG, JPEG, or DICOM</li>
    <li>Hierarchical selection (studies, series, slices)</li>
    <li>Include overlays, ROIs, and measurements</li>
    <li>Export at displayed resolution option</li>
    <li>Export selected DICOM tags to Excel/CSV</li>
    <li>Export/Import Customizations: Save and share overlay config, annotation options, metadata panel settings, and theme as JSON files</li>
    </ul>
    <hr>
    <p><a href="disclaimer://show">View Disclaimer</a></p>
</body>
</html>"""

    text_edit.setHtml(html_content)
    # Handle disclaimer link click
    text_edit.anchorClicked.connect(
        lambda url: _on_disclaimer_link_clicked(url, on_disclaimer)
    )
    layout.addWidget(text_edit)

    # Add OK button
    button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
    button_box.accepted.connect(dialog.accept)
    layout.addWidget(button_box)

    dialog.exec()
