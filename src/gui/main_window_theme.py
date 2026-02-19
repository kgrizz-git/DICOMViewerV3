"""
Main Window Theme – stylesheet and viewer background for light/dark themes.

Provides stylesheet strings and viewer background color for MainWindow theme switching.
Used by gui.main_window.MainWindow._apply_theme(); no dependency on MainWindow or config.

Purpose:
    - Return stylesheet for a given theme name
    - Return image viewer background QColor for a given theme

Inputs:
    - theme: "light" or "dark"
    - (for get_theme_stylesheet) checkmark image paths for checkbox icons

Outputs:
    - Stylesheet string for QApplication.setStyleSheet
    - QColor for image viewer background

Requirements:
    - PySide6.QtGui.QColor
"""

from PySide6.QtGui import QColor


def get_theme_stylesheet(
    theme: str,
    white_checkmark_path: str,
    black_checkmark_path: str
) -> str:
    """
    Return the full application stylesheet for the given theme.

    Args:
        theme: "light" or "dark"
        white_checkmark_path: URL/path for checkbox checkmark image (dark theme)
        black_checkmark_path: URL/path for checkbox checkmark image (light theme)

    Returns:
        Stylesheet string to pass to QApplication.instance().setStyleSheet()
    """
    if theme == "dark":
        stylesheet = """

                /* Main window and panels - all same background */
                QMainWindow, QWidget {{
                    background-color: #2b2b2b;
                    color: #ffffff;
                }}
                
                /* Menu bar */
                QMenuBar {{
                    background-color: #2b2b2b;
                    color: #ffffff;
                    border-bottom: 1px solid #555555;
                }}
                
                QMenuBar::item {{
                    background-color: transparent;
                    padding: 4px 12px;
                }}
                
                QMenuBar::item:selected {{
                    background-color: #3a3a3a;
                }}
                
                QMenuBar::item:pressed {{
                    background-color: #4285da;
                }}
                
                /* Menus */
                QMenu {{
                    background-color: #2b2b2b;
                    color: #ffffff;
                    border: 1px solid #555555;
                }}
                
                QMenu::item {{
                    padding: 5px 25px 5px 25px;
                }}
                
                QMenu::item:selected {{
                    background-color: #4285da;
                }}
                
                QMenu::separator {{
                    height: 1px;
                    background-color: #555555;
                    margin: 5px 0px;
                }}
                
                /* Commented out to allow native checkmark rendering
                QMenu::indicator {{
                    width: 16px;
                    height: 16px;
                    border: none;
                }}
                
                QMenu::indicator:checked {{
                    border: none;
                }}
                */
                
                /* Toolbar */
                QToolBar {{
                    background-color: #3a3a3a;
                    border: 1px solid #555555;
                    spacing: 3px;
                    padding: 3px;
                }}
                
                QToolBar::separator {{
                    background-color: #555555;
                    width: 1px;
                    margin: 2px;
                }}
                
                /* Toolbar widgets (spacer) - transparent to match toolbar */
                QToolBar QWidget {{
                    background-color: transparent;
                }}
                
                /* Toolbar combobox - override transparent background */
                QToolBar QComboBox {{
                    background-color: #1b1b1b;
                    color: #ffffff;
                    border: 1px solid #555555;
                    padding: 3px 10px;
                    border-radius: 3px;
                }}
                
                QToolBar QComboBox:hover {{
                    border: 1px solid #6a6a6a;
                }}
                
                /* Toolbar buttons */
                QToolButton {{
                    background-color: #3a3a3a;
                    color: #ffffff;
                    border: none;
                    padding: 0px 2px;
                }}
                
                QToolButton:hover {{
                    background-color: #454545;
                }}
                
                QToolButton:pressed {{
                    background-color: #4285da;
                }}
                
                QToolButton:checked {{
                    background-color: #4285da;
                }}
                
                QToolButton:disabled {{
                    background-color: #2b2b2b;
                    color: #7f7f7f;
                }}
                
                /* Buttons */
                QPushButton {{
                    background-color: #3a3a3a;
                    color: #ffffff;
                    border: 1px solid #555555;
                    padding: 3px 8px;
                    border-radius: 3px;
                }}
                
                QPushButton:hover {{
                    background-color: #454545;
                }}
                
                QPushButton:pressed {{
                    background-color: #4285da;
                }}
                
                QPushButton:disabled {{
                    background-color: #2b2b2b;
                    color: #7f7f7f;
                    border: 1px solid #3a3a3a;
                }}
                
                QPushButton:checked {{
                    background-color: #4285da;
                }}
                
                QPushButton[objectName="cine_loop_button"]:checked {{
                    background-color: #4285da;
                    border: 2px solid #5a9de5;
                }}
                
                /* Text inputs, lists, tables */
                QTreeWidget, QTableWidget, QListWidget, QTextEdit, QPlainTextEdit {{
                    background-color: #1e1e1e;
                    color: #ffffff;
                    border: 1px solid #555555;
                    selection-background-color: #4285da;
                    selection-color: #ffffff;
                }}
                
                QTreeWidget::item:hover, QTableWidget::item:hover, QListWidget::item:hover {{
                    background-color: #3a3a3a;
                }}
                
                QTreeWidget::item:selected, QTableWidget::item:selected, QListWidget::item:selected {{
                    background-color: #4285da;
                }}
                
                /* Headers */
                QHeaderView::section {{
                    background-color: #3a3a3a;
                    color: #ffffff;
                    border: 1px solid #555555;
                    padding: 4px;
                }}
                
                /* Line edits, spin boxes */
                QLineEdit, QSpinBox, QDoubleSpinBox {{
                    background-color: #1e1e1e;
                    color: #ffffff;
                    border: 1px solid #555555;
                    padding: 3px;
                    border-radius: 3px;
                }}
                
                QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus {{
                    border: 1px solid #4285da;
                }}
                
                QLineEdit:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled {{
                    background-color: #2b2b2b;
                    color: #7f7f7f;
                }}
                
                /* Scrollbars */
                QScrollBar:vertical {{
                    background-color: #2b2b2b;
                    width: 12px;
                    border: none;
                }}
                
                QScrollBar::handle:vertical {{
                    background-color: #555555;
                    min-height: 20px;
                    border-radius: 6px;
                }}
                
                QScrollBar::handle:vertical:hover {{
                    background-color: #6a6a6a;
                }}
                
                QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                    height: 0px;
                }}
                
                QScrollBar:horizontal {{
                    background-color: #2b2b2b;
                    height: 12px;
                    border: none;
                }}
                
                QScrollBar::handle:horizontal {{
                    background-color: #555555;
                    min-width: 20px;
                    border-radius: 6px;
                }}
                
                QScrollBar::handle:horizontal:hover {{
                    background-color: #6a6a6a;
                }}
                
                QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
                    width: 0px;
                }}
                
                /* Checkboxes */
                QCheckBox {{
                    color: #ffffff;
                    spacing: 5px;
                }}
                
                QCheckBox:disabled {{
                    color: #7f7f7f;
                }}
                
                /* General checkbox styling - matches metadata panel */
                QCheckBox::indicator {{
                    width: 16px;
                    height: 16px;
                    border: 2px solid #6a6a6a;
                    border-radius: 3px;
                    background-color: #1e1e1e;
                }}
                
                QCheckBox::indicator:hover {{
                    border: 2px solid #8a8a8a;
                }}
                
                QCheckBox::indicator:checked {{
                    border: 2px solid #6a6a6a;
                    background-color: #1e1e1e;
                    image: url('{white_checkmark_path}');
                }}
                
                /* Metadata panel checkbox with border and custom checkmark */
                QWidget[objectName="metadata_panel"] QCheckBox::indicator {{
                    width: 16px;
                    height: 16px;
                    border: 2px solid #6a6a6a;
                    border-radius: 3px;
                    background-color: #1e1e1e;
                }}
                
                QWidget[objectName="metadata_panel"] QCheckBox::indicator:hover {{
                    border: 2px solid #8a8a8a;
                }}
                
                QWidget[objectName="metadata_panel"] QCheckBox::indicator:checked {{
                    border: 2px solid #6a6a6a;
                    background-color: #1e1e1e;
                    image: url('{white_checkmark_path}');
                }}
                
                /* Labels */
                QLabel {{
                    background-color: transparent;
                    color: #ffffff;
                }}
                
                QLabel:disabled {{
                    color: #7f7f7f;
                }}
                
                /* Status bar */
                QStatusBar {{
                    background-color: #2b2b2b;
                    color: #ffffff;
                    border-top: 1px solid #555555;
                }}
                
                /* Splitter handles */
                QSplitter::handle {{
                    background-color: #555555;
                }}
                
                QSplitter::handle:horizontal {{
                    width: 2px;
                }}
                
                QSplitter::handle:vertical {{
                    height: 2px;
                }}
                
                /* Combo boxes */
                QComboBox {{
                    background-color: #1b1b1b;
                    color: #ffffff;
                    border: 1px solid #555555;
                    padding: 3px 10px;
                    border-radius: 3px;
                }}
                
                QComboBox:hover {{
                    border: 1px solid #6a6a6a;
                }}
                
                QComboBox:disabled {{
                    background-color: #2b2b2b;
                    color: #7f7f7f;
                    border: 1px solid #3a3a3a;
                }}
                
                /* QComboBox::drop-down - COMMENTED OUT to preserve native arrow */
                /*
                QComboBox::drop-down {{
                    subcontrol-origin: padding;
                    subcontrol-position: top right;
                    width: 20px;
                    border-left-width: 1px;
                    border-left-color: #555555;
                    border-left-style: solid;
                    border-top-right-radius: 3px;
                    border-bottom-right-radius: 3px;
                }}
                */
                
                /* Combo box item view */
                /* Styles the dropdown list that opens when you click the combobox arrow */
                QComboBox QAbstractItemView {{
                    background-color: #1b1b1b;
                    color: #ffffff;
                    selection-background-color: #4285da;
                    border: 1px solid #555555;
                }}
                
                /* Tooltips */
                QToolTip {{
                    background-color: #3a3a3a;
                    color: #ffffff;
                    border: 1px solid #555555;
                    padding: 3px;
                }}
                
                /* Series Navigator */
                QWidget[objectName="series_navigator"] {{
                    background-color: #1b1b1b;
                }}
                
                QScrollArea[objectName="series_navigator_scroll_area"] {{
                    background-color: #1b1b1b;
                }}
                
                QWidget[objectName="series_navigator_container"] {{
                    background-color: #1b1b1b;
                }}
                
                /* Study sections and thumbnails containers inherit navigator background */
                /* Match direct children and all nested QWidget descendants */
                QWidget[objectName="series_navigator_container"] > QWidget,
                QWidget[objectName="series_navigator_container"] QWidget {{
                    background-color: #1b1b1b;
                }}
                
                /* Study label background - slightly lighter than navigator for dark theme */
                QWidget[objectName="series_navigator_container"] StudyLabel {{
                    background-color: #2a2a2a;
                }}
            
        """.format(white_checkmark_path=white_checkmark_path, black_checkmark_path=black_checkmark_path)
    else:
        stylesheet = """

                /* Main window and panels - all same background */
                QMainWindow, QWidget {{
                    background-color: #f0f0f0;
                    color: #000000;
                }}
                
                /* Menu bar */
                QMenuBar {{
                    background-color: #f0f0f0;
                    color: #000000;
                    border-bottom: 1px solid #c0c0c0;
                }}
                
                QMenuBar::item {{
                    background-color: transparent;
                    padding: 4px 12px;
                }}
                
                QMenuBar::item:selected {{
                    background-color: #e0e0e0;
                }}
                
                QMenuBar::item:pressed {{
                    background-color: #4285da;
                    color: #ffffff;
                }}
                
                /* Menus */
                QMenu {{
                    background-color: #f0f0f0;
                    color: #000000;
                    border: 1px solid #c0c0c0;
                }}
                
                QMenu::item {{
                    padding: 5px 25px 5px 25px;
                }}
                
                QMenu::item:selected {{
                    background-color: #4285da;
                    color: #ffffff;
                }}
                
                QMenu::separator {{
                    height: 1px;
                    background-color: #c0c0c0;
                    margin: 5px 0px;
                }}
                
                /* Commented out to allow native checkmark rendering
                QMenu::indicator {{
                    width: 16px;
                    height: 16px;
                    border: none;
                }}
                
                QMenu::indicator:checked {{
                    border: none;
                }}
                */
                
                /* Toolbar */
                QToolBar {{
                    background-color: #e0e0e0;
                    border: 1px solid #c0c0c0;
                    spacing: 3px;
                    padding: 3px;
                }}
                
                QToolBar::separator {{
                    background-color: #c0c0c0;
                    width: 1px;
                    margin: 2px;
                }}
                
                /* Toolbar widgets (spacer) - transparent to match toolbar */
                QToolBar QWidget {{
                    background-color: transparent;
                }}
                
                /* Toolbar combobox - override transparent background */
                QToolBar QComboBox {{
                    background-color: #ffffff;
                    color: #000000;
                    border: 1px solid #c0c0c0;
                    padding: 3px 10px;
                    border-radius: 3px;
                }}
                
                QToolBar QComboBox:hover {{
                    border: 1px solid #a0a0a0;
                }}
                
                /* Toolbar buttons */
                QToolButton {{
                    background-color: #e0e0e0;
                    color: #000000;
                    border: none;
                    padding: 0px 2px;
                }}
                
                QToolButton:hover {{
                    background-color: #d0d0d0;
                }}
                
                QToolButton:pressed {{
                    background-color: #4285da;
                    color: #ffffff;
                }}
                
                QToolButton:checked {{
                    background-color: #4285da;
                    color: #ffffff;
                }}
                
                QToolButton:disabled {{
                    background-color: #f0f0f0;
                    color: #a0a0a0;
                }}
                
                /* Buttons */
                QPushButton {{
                    background-color: #e0e0e0;
                    color: #000000;
                    border: 1px solid #c0c0c0;
                    padding: 3px 8px;
                    border-radius: 3px;
                }}
                
                QPushButton:hover {{
                    background-color: #d0d0d0;
                }}
                
                QPushButton:pressed {{
                    background-color: #4285da;
                    color: #ffffff;
                }}
                
                QPushButton:disabled {{
                    background-color: #f0f0f0;
                    color: #a0a0a0;
                    border: 1px solid #d0d0d0;
                }}
                
                QPushButton:checked {{
                    background-color: #4285da;
                    color: #ffffff;
                }}
                
                QPushButton[objectName="cine_loop_button"]:checked {{
                    background-color: #4285da;
                    color: #ffffff;
                    border: 2px solid #1a5da5;
                }}
                
                /* Text inputs, lists, tables */
                QTreeWidget, QTableWidget, QListWidget, QTextEdit, QPlainTextEdit {{
                    background-color: #ffffff;
                    color: #000000;
                    border: 1px solid #c0c0c0;
                    selection-background-color: #4285da;
                    selection-color: #ffffff;
                }}
                
                QTreeWidget::item:hover, QTableWidget::item:hover, QListWidget::item:hover {{
                    background-color: #e8e8e8;
                }}
                
                QTreeWidget::item:selected, QTableWidget::item:selected, QListWidget::item:selected {{
                    background-color: #4285da;
                }}
                
                /* Headers */
                QHeaderView::section {{
                    background-color: #e0e0e0;
                    color: #000000;
                    border: 1px solid #c0c0c0;
                    padding: 4px;
                }}
                
                /* Line edits, spin boxes */
                QLineEdit, QSpinBox, QDoubleSpinBox {{
                    background-color: #ffffff;
                    color: #000000;
                    border: 1px solid #c0c0c0;
                    padding: 3px;
                    border-radius: 3px;
                }}
                
                QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus {{
                    border: 1px solid #4285da;
                }}
                
                QLineEdit:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled {{
                    background-color: #f0f0f0;
                    color: #a0a0a0;
                }}
                
                /* Scrollbars */
                QScrollBar:vertical {{
                    background-color: #f0f0f0;
                    width: 12px;
                    border: none;
                }}
                
                QScrollBar::handle:vertical {{
                    background-color: #c0c0c0;
                    min-height: 20px;
                    border-radius: 6px;
                }}
                
                QScrollBar::handle:vertical:hover {{
                    background-color: #a0a0a0;
                }}
                
                QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                    height: 0px;
                }}
                
                QScrollBar:horizontal {{
                    background-color: #f0f0f0;
                    height: 12px;
                    border: none;
                }}
                
                QScrollBar::handle:horizontal {{
                    background-color: #c0c0c0;
                    min-width: 20px;
                    border-radius: 6px;
                }}
                
                QScrollBar::handle:horizontal:hover {{
                    background-color: #a0a0a0;
                }}
                
                QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
                    width: 0px;
                }}
                
                /* Checkboxes */
                QCheckBox {{
                    color: #000000;
                    spacing: 5px;
                }}
                
                QCheckBox:disabled {{
                    color: #a0a0a0;
                }}
                
                /* General checkbox styling - matches metadata panel */
                QCheckBox::indicator {{
                    width: 16px;
                    height: 16px;
                    border: 2px solid #808080;
                    border-radius: 3px;
                    background-color: #ffffff;
                }}
                
                QCheckBox::indicator:hover {{
                    border: 2px solid #606060;
                }}
                
                QCheckBox::indicator:checked {{
                    border: 2px solid #808080;
                    background-color: #ffffff;
                    image: url('{black_checkmark_path}');
                }}
                
                /* Metadata panel checkbox with border and custom checkmark */
                QWidget[objectName="metadata_panel"] QCheckBox::indicator {{
                    width: 16px;
                    height: 16px;
                    border: 2px solid #808080;
                    border-radius: 3px;
                    background-color: #ffffff;
                }}
                
                QWidget[objectName="metadata_panel"] QCheckBox::indicator:hover {{
                    border: 2px solid #606060;
                }}
                
                QWidget[objectName="metadata_panel"] QCheckBox::indicator:checked {{
                    border: 2px solid #808080;
                    background-color: #ffffff;
                    image: url('{black_checkmark_path}');
                }}
                
                /* Labels */
                QLabel {{
                    background-color: transparent;
                    color: #000000;
                }}
                
                QLabel:disabled {{
                    color: #a0a0a0;
                }}
                
                /* Status bar */
                QStatusBar {{
                    background-color: #f0f0f0;
                    color: #000000;
                    border-top: 1px solid #c0c0c0;
                }}
                
                /* Splitter handles */
                QSplitter::handle {{
                    background-color: #c0c0c0;
                }}
                
                QSplitter::handle:horizontal {{
                    width: 2px;
                }}
                
                QSplitter::handle:vertical {{
                    height: 2px;
                }}
                
                /* Combo boxes */
                QComboBox {{
                    background-color: #ffffff;
                    color: #000000;
                    border: 1px solid #c0c0c0;
                    padding: 3px 10px;
                    border-radius: 3px;
                }}
                
                QComboBox:hover {{
                    border: 1px solid #a0a0a0;
                }}
                
                QComboBox:disabled {{
                    background-color: #f0f0f0;
                    color: #a0a0a0;
                    border: 1px solid #d0d0d0;
                }}
                
                /* QComboBox::drop-down - COMMENTED OUT to preserve native arrow */
                /*
                QComboBox::drop-down {{
                    subcontrol-origin: padding;
                    subcontrol-position: top right;
                    width: 20px;
                    border-left-width: 1px;
                    border-left-color: #c0c0c0;
                    border-left-style: solid;
                    border-top-right-radius: 3px;
                    border-bottom-right-radius: 3px;
                }}
                */
                
                QComboBox QAbstractItemView {{
                    background-color: #f0f0f0;
                    color: #000000;
                    selection-background-color: #4285da;
                    selection-color: #ffffff;
                    border: 1px solid #c0c0c0;
                }}
                
                /* Tooltips */
                QToolTip {{
                    background-color: #ffffdc;
                    color: #000000;
                    border: 1px solid #c0c0c0;
                    padding: 3px;
                }}
                
                /* Series Navigator */
                QWidget[objectName="series_navigator"] {{
                    background-color: #d0d0d0;
                }}
                
                QScrollArea[objectName="series_navigator_scroll_area"] {{
                    background-color: #d0d0d0;
                }}
                
                QWidget[objectName="series_navigator_container"] {{
                    background-color: #d0d0d0;
                }}
                
                /* Study sections and thumbnails containers inherit navigator background */
                /* Match direct children and all nested QWidget descendants */
                QWidget[objectName="series_navigator_container"] > QWidget,
                QWidget[objectName="series_navigator_container"] QWidget {{
                    background-color: #d0d0d0;
                }}
                
                /* Study label background - slightly lighter than navigator for light theme */
                QWidget[objectName="series_navigator_container"] StudyLabel {{
                    background-color: #e0e0e0;
                }}
            
        """.format(white_checkmark_path=white_checkmark_path, black_checkmark_path=black_checkmark_path)
    return stylesheet


def get_theme_viewer_background_color(theme: str) -> QColor:
    """
    Return the image viewer background color for the given theme.

    Args:
        theme: "light" or "dark"

    Returns:
        QColor for ImageViewer.set_background_color()
    """
    if theme == "dark":
        return QColor(27, 27, 27)  # #1b1b1b
    else:
        return QColor(64, 64, 64)  # #404040
