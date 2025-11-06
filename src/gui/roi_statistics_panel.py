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
                                QTableWidgetItem, QGroupBox)
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
        
        # Title
        title_label = QLabel("ROI Statistics")
        title_label.setStyleSheet("font-weight: bold; font-size: 12pt;")
        layout.addWidget(title_label)
        
        # Statistics table
        self.stats_table = QTableWidget()
        self.stats_table.setColumnCount(2)
        self.stats_table.setHorizontalHeaderLabels(["Statistic", "Value"])
        self.stats_table.setRowCount(5)
        self.stats_table.setColumnWidth(0, 120)
        self.stats_table.setColumnWidth(1, 100)
        self.stats_table.verticalHeader().setVisible(False)
        self.stats_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        
        # Set row labels
        self.stats_table.setItem(0, 0, QTableWidgetItem("Mean"))
        self.stats_table.setItem(1, 0, QTableWidgetItem("Std Dev"))
        self.stats_table.setItem(2, 0, QTableWidgetItem("Min"))
        self.stats_table.setItem(3, 0, QTableWidgetItem("Max"))
        self.stats_table.setItem(4, 0, QTableWidgetItem("Count"))
        
        # Initialize with empty values
        for i in range(5):
            self.stats_table.setItem(i, 1, QTableWidgetItem(""))
        
        layout.addWidget(self.stats_table)
        layout.addStretch()
    
    def update_statistics(self, statistics: Dict[str, float]) -> None:
        """
        Update displayed statistics.
        
        Args:
            statistics: Dictionary with statistics (mean, std, min, max, count)
        """
        self.current_statistics = statistics
        
        # Update table
        self.stats_table.setItem(0, 1, QTableWidgetItem(f"{statistics.get('mean', 0):.2f}"))
        self.stats_table.setItem(1, 1, QTableWidgetItem(f"{statistics.get('std', 0):.2f}"))
        self.stats_table.setItem(2, 1, QTableWidgetItem(f"{statistics.get('min', 0):.2f}"))
        self.stats_table.setItem(3, 1, QTableWidgetItem(f"{statistics.get('max', 0):.2f}"))
        self.stats_table.setItem(4, 1, QTableWidgetItem(f"{statistics.get('count', 0)}"))
    
    def clear_statistics(self) -> None:
        """Clear displayed statistics."""
        for i in range(5):
            self.stats_table.setItem(i, 1, QTableWidgetItem(""))
        self.current_statistics = None

