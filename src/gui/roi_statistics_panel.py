"""
ROI Statistics Panel

This module provides a panel for displaying ROI statistics including
mean, standard deviation, min, max, and pixel count.

Inputs:
    - ROI statistics data
    
Outputs:
    - Displayed statistics in a formatted panel
    
Requirements:
    - PySide6 for GUI components
"""

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QLabel, QTableWidget,
                                QTableWidgetItem, QGroupBox, QHeaderView)
from PySide6.QtCore import Qt
from typing import Optional, Dict


class ROIStatisticsPanel(QWidget):
    """
    Panel for displaying ROI statistics.
    
    Features:
    - Display mean, std dev, min, max, count
    - Update dynamically when ROI is selected
    """
    
    def __init__(self, parent=None):
        """
        Initialize the ROI statistics panel.
        
        Args:
            parent: Parent widget
        """
        super().__init__(parent)
        
        self._create_ui()
        self.current_statistics: Optional[Dict[str, float]] = None
    
    def _create_ui(self) -> None:
        """Create the UI components."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        
        # Title (will be updated with ROI identifier)
        self.title_label = QLabel("ROI Statistics")
        self.title_label.setStyleSheet("font-weight: bold; font-size: 12pt;")
        layout.addWidget(self.title_label)
        
        # Statistics table
        self.stats_table = QTableWidget()
        self.stats_table.setColumnCount(2)
        self.stats_table.setHorizontalHeaderLabels(["Statistic", "Value"])
        self.stats_table.setRowCount(6)
        self.stats_table.verticalHeader().setVisible(False)
        self.stats_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        
        # Set columns to stretch mode so they expand/contract with widget width
        header = self.stats_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        
        # Set row labels
        self.stats_table.setItem(0, 0, QTableWidgetItem("Mean"))
        self.stats_table.setItem(1, 0, QTableWidgetItem("Std Dev"))
        self.stats_table.setItem(2, 0, QTableWidgetItem("Min"))
        self.stats_table.setItem(3, 0, QTableWidgetItem("Max"))
        self.stats_table.setItem(4, 0, QTableWidgetItem("Pixels"))
        self.stats_table.setItem(5, 0, QTableWidgetItem("Area"))
        
        # Initialize with empty values
        for i in range(6):
            self.stats_table.setItem(i, 1, QTableWidgetItem(""))
        
        # Calculate minimum height to show all 6 rows without scrolling
        # Header height + (row height * 6 rows) + some padding
        header_height = self.stats_table.horizontalHeader().height()
        row_height = self.stats_table.rowHeight(0) if self.stats_table.rowHeight(0) > 0 else 25  # Default row height
        min_table_height = header_height + (row_height * 6) + 10  # 10px padding
        
        # Set minimum height for the table to show all rows
        self.stats_table.setMinimumHeight(min_table_height)
        
        layout.addWidget(self.stats_table)
        layout.addStretch()
    
    def update_statistics(self, statistics: Dict[str, float], roi_identifier: Optional[str] = None,
                         rescale_type: Optional[str] = None) -> None:
        """
        Update displayed statistics.
        
        Args:
            statistics: Dictionary with statistics (mean, std, min, max, count)
            roi_identifier: Optional ROI identifier string (e.g., "ROI 1 (rectangle)")
            rescale_type: Optional rescale type (e.g., "HU") to append to values
        """
        self.current_statistics = statistics
        
        # Update title with ROI identifier
        if roi_identifier:
            self.title_label.setText(f"ROI Statistics - {roi_identifier}")
        else:
            self.title_label.setText("ROI Statistics")
        
        # Format values with units if rescale_type is provided
        unit_suffix = f" {rescale_type}" if rescale_type else ""
        
        # Update table
        self.stats_table.setItem(0, 1, QTableWidgetItem(f"{statistics.get('mean', 0):.2f}{unit_suffix}"))
        self.stats_table.setItem(1, 1, QTableWidgetItem(f"{statistics.get('std', 0):.2f}{unit_suffix}"))
        self.stats_table.setItem(2, 1, QTableWidgetItem(f"{statistics.get('min', 0):.2f}{unit_suffix}"))
        self.stats_table.setItem(3, 1, QTableWidgetItem(f"{statistics.get('max', 0):.2f}{unit_suffix}"))
        self.stats_table.setItem(4, 1, QTableWidgetItem(f"{statistics.get('count', 0)}"))
        
        # Format area with appropriate units
        area_mm2 = statistics.get('area_mm2')
        area_pixels = statistics.get('area_pixels', 0.0)
        if area_mm2 is not None:
            # Display in mm² or cm² (if >= 100 mm²)
            if area_mm2 >= 100.0:
                area_cm2 = area_mm2 / 100.0
                area_text = f"{area_cm2:.2f} cm²"
            else:
                area_text = f"{area_mm2:.2f} mm²"
        else:
            # Display in pixels
            area_text = f"{area_pixels:.1f} pixels"
        self.stats_table.setItem(5, 1, QTableWidgetItem(area_text))
    
    def clear_statistics(self) -> None:
        """Clear displayed statistics."""
        for i in range(6):
            self.stats_table.setItem(i, 1, QTableWidgetItem(""))
        self.current_statistics = None
        self.title_label.setText("ROI Statistics")

