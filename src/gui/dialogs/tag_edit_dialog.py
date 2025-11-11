"""
DICOM Tag Edit Dialog

This module provides a dialog for editing individual DICOM tags with
validation based on VR (Value Representation) types.

Inputs:
    - DICOM tag information (tag string, name, VR, current value)
    - User input for new tag value
    
Outputs:
    - Validated tag value
    - Updated tag information
    
Requirements:
    - PySide6 for GUI components
    - pydicom for DICOM tag handling
"""

from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                                QLineEdit, QPushButton, QDialogButtonBox,
                                QMessageBox, QSpinBox, QDoubleSpinBox)
from PySide6.QtCore import Qt
from typing import Optional, Any, Tuple
import re
from pydicom.tag import Tag


class TagEditDialog(QDialog):
    """
    Dialog for editing individual DICOM tags.
    
    Features:
    - VR type display and validation
    - Input field appropriate for VR type
    - Validation before accepting changes
    """
    
    # VR types that are read-only (too complex for basic editing)
    READ_ONLY_VR_TYPES = {"SQ", "OB", "OD", "OF", "OL", "OV", "OW"}
    
    # String VR types
    STRING_VR_TYPES = {"AE", "AS", "AT", "CS", "DA", "DS", "DT", "IS", "LO", 
                       "LT", "PN", "SH", "ST", "TM", "UI", "UT"}
    
    # Numeric VR types
    NUMERIC_VR_TYPES = {
        "FL": (float, None, None),  # Float
        "FD": (float, None, None),   # Double
        "SL": (int, -2147483648, 2147483647),  # Signed Long
        "SS": (int, -32768, 32767),  # Signed Short
        "UL": (int, 0, 4294967295),  # Unsigned Long
        "US": (int, 0, 65535),       # Unsigned Short
    }
    
    def __init__(self, parent=None, tag_str: str = "", tag_name: str = "",
                 vr: str = "", current_value: Any = ""):
        """
        Initialize the tag edit dialog.
        
        Args:
            parent: Parent widget
            tag_str: Tag string (e.g., "(0010,0010)")
            tag_name: Tag name (e.g., "Patient Name")
            vr: Value Representation type (e.g., "PN")
            current_value: Current tag value
        """
        super().__init__(parent)
        
        self.tag_str = tag_str
        self.tag_name = tag_name
        self.vr = vr.upper() if vr else ""
        self.current_value = current_value
        self.new_value: Optional[Any] = None
        
        self.setWindowTitle(f"Edit Tag: {tag_name}")
        self.setMinimumWidth(400)
        
        self._create_ui()
        self._setup_validation()
    
    def _create_ui(self) -> None:
        """Create the UI components."""
        layout = QVBoxLayout(self)
        
        # Tag information
        info_layout = QVBoxLayout()
        
        tag_label = QLabel(f"<b>Tag:</b> {self.tag_str}")
        info_layout.addWidget(tag_label)
        
        name_label = QLabel(f"<b>Name:</b> {self.tag_name}")
        info_layout.addWidget(name_label)
        
        vr_label = QLabel(f"<b>VR:</b> {self.vr}")
        info_layout.addWidget(vr_label)
        
        layout.addLayout(info_layout)
        
        # Value input
        value_layout = QVBoxLayout()
        value_label = QLabel("Value:")
        value_layout.addWidget(value_label)
        
        # Create appropriate input widget based on VR type
        if self.vr in self.READ_ONLY_VR_TYPES:
            # Read-only for complex types
            self.value_input = QLineEdit()
            self.value_input.setReadOnly(True)
            self.value_input.setText("(Read-only: Complex VR type)")
            self.value_input.setStyleSheet("background-color: #f0f0f0; color: #666;")
        elif self.vr in self.NUMERIC_VR_TYPES:
            # Numeric input
            num_type, min_val, max_val = self.NUMERIC_VR_TYPES[self.vr]
            if num_type == float:
                self.value_input = QDoubleSpinBox()
                self.value_input.setDecimals(6)
                if min_val is not None:
                    self.value_input.setMinimum(min_val)
                if max_val is not None:
                    self.value_input.setMaximum(max_val)
            else:  # int
                # QSpinBox can only handle signed 32-bit integers (max 2147483647)
                # For UL (Unsigned Long) which can go up to 4294967295, use QLineEdit with validation
                if self.vr == "UL" and max_val is not None and max_val > 2147483647:
                    # Use QLineEdit for UL to handle full unsigned long range
                    self.value_input = QLineEdit()
                    # Set current value
                    try:
                        if isinstance(self.current_value, list):
                            val_str = str(self.current_value[0]) if self.current_value else "0"
                        else:
                            val_str = str(int(self.current_value)) if self.current_value else "0"
                        self.value_input.setText(val_str)
                    except (ValueError, TypeError):
                        self.value_input.setText("0")
                else:
                    # Use QSpinBox for other integer types
                    self.value_input = QSpinBox()
                    if min_val is not None:
                        self.value_input.setMinimum(min_val)
                    if max_val is not None:
                        # Cap at QSpinBox maximum if needed
                        actual_max = min(max_val, 2147483647) if max_val > 2147483647 else max_val
                        self.value_input.setMaximum(actual_max)
                    
                    # Set current value
                    try:
                        if isinstance(self.current_value, list):
                            val = self.current_value[0] if self.current_value else 0
                        else:
                            val = num_type(self.current_value) if self.current_value else 0
                        self.value_input.setValue(val)
                    except (ValueError, TypeError):
                        self.value_input.setValue(0)
        else:
            # String input (default)
            self.value_input = QLineEdit()
            if isinstance(self.current_value, list):
                value_str = ", ".join(str(v) for v in self.current_value)
            else:
                value_str = str(self.current_value) if self.current_value else ""
            self.value_input.setText(value_str)
        
        value_layout.addWidget(self.value_input)
        layout.addLayout(value_layout)
        
        # Buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self._validate_and_accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
    
    def _setup_validation(self) -> None:
        """Set up validation based on VR type."""
        if self.vr in self.READ_ONLY_VR_TYPES:
            # Disable OK button for read-only types
            button_box = self.findChild(QDialogButtonBox)
            if button_box:
                ok_button = button_box.button(QDialogButtonBox.StandardButton.Ok)
                if ok_button:
                    ok_button.setEnabled(False)
    
    def _validate_and_accept(self) -> None:
        """
        Validate input and accept the dialog.
        
        Returns:
            None (closes dialog with accept if valid)
        """
        if self.vr in self.READ_ONLY_VR_TYPES:
            QMessageBox.warning(
                self,
                "Read-Only Tag",
                f"Tags with VR type '{self.vr}' cannot be edited.\n"
                "These are complex types (sequences or binary data) that require special handling."
            )
            return
        
        # Get value from input widget
        if isinstance(self.value_input, (QSpinBox, QDoubleSpinBox)):
            self.new_value = self.value_input.value()
        else:
            value_str = self.value_input.text().strip()
            
            # Validate based on VR type
            if not self._validate_string_value(value_str):
                return
            
            # Convert to appropriate type if needed
            if self.vr in self.STRING_VR_TYPES:
                self.new_value = value_str
            elif self.vr in self.NUMERIC_VR_TYPES:
                # For numeric types using QLineEdit (like UL), convert to appropriate type
                num_type, min_val, max_val = self.NUMERIC_VR_TYPES[self.vr]
                try:
                    if num_type == float:
                        self.new_value = float(value_str)
                    else:  # int
                        self.new_value = int(value_str)
                        # Validate range for UL
                        if self.vr == "UL" and max_val is not None:
                            if self.new_value < 0 or self.new_value > max_val:
                                QMessageBox.warning(
                                    self,
                                    "Invalid Value",
                                    f"Value must be between 0 and {max_val} for VR type '{self.vr}'"
                                )
                                return
                except ValueError:
                    QMessageBox.warning(
                        self,
                        "Invalid Number",
                        f"Please enter a valid {num_type.__name__} value."
                    )
                    return
            else:
                self.new_value = value_str
        
        self.accept()
    
    def _validate_string_value(self, value: str) -> bool:
        """
        Validate string value based on VR type.
        
        Args:
            value: String value to validate
            
        Returns:
            True if valid, False otherwise
        """
        if not value and self.vr not in {"AS", "AT", "DA", "DT", "TM"}:
            # Empty values are generally allowed except for some date/time types
            return True
        
        # Date validation (DA: YYYYMMDD)
        if self.vr == "DA":
            if not re.match(r'^\d{8}$', value):
                QMessageBox.warning(
                    self,
                    "Invalid Date Format",
                    "Date must be in YYYYMMDD format (e.g., 20240101)"
                )
                return False
        
        # Time validation (TM: HHMMSS.FFFFFF)
        elif self.vr == "TM":
            if not re.match(r'^\d{2,6}(\.\d{1,6})?$', value):
                QMessageBox.warning(
                    self,
                    "Invalid Time Format",
                    "Time must be in HHMMSS.FFFFFF format (e.g., 120000.000000)"
                )
                return False
        
        # DateTime validation (DT: YYYYMMDDHHMMSS.FFFFFF)
        elif self.vr == "DT":
            if not re.match(r'^\d{8}\d{6}(\.\d{1,6})?$', value):
                QMessageBox.warning(
                    self,
                    "Invalid DateTime Format",
                    "DateTime must be in YYYYMMDDHHMMSS.FFFFFF format"
                )
                return False
        
        # UID validation (UI: must be valid UID format)
        elif self.vr == "UI":
            if not re.match(r'^[\d.]+$', value):
                QMessageBox.warning(
                    self,
                    "Invalid UID Format",
                    "UID must contain only digits and dots"
                )
                return False
        
        # String length validation
        max_lengths = {
            "AE": 16,   # Application Entity
            "AS": 4,    # Age String
            "AT": 4,    # Attribute Tag
            "CS": 16,   # Code String
            "DA": 8,    # Date
            "DS": 16,   # Decimal String
            "DT": 26,   # Date Time
            "IS": 12,   # Integer String
            "LO": 64,   # Long String
            "LT": 10240, # Long Text
            "PN": 64,   # Person Name
            "SH": 16,   # Short String
            "ST": 1024, # Short Text
            "TM": 16,   # Time
            "UI": 64,   # Unique Identifier
            "UT": 4294967295,  # Unlimited Text
        }
        
        if self.vr in max_lengths and len(value) > max_lengths[self.vr]:
            QMessageBox.warning(
                self,
                "Value Too Long",
                f"Value exceeds maximum length of {max_lengths[self.vr]} characters for VR type '{self.vr}'"
            )
            return False
        
        return True
    
    def get_value(self) -> Optional[Any]:
        """
        Get the new tag value.
        
        Returns:
            New tag value, or None if dialog was cancelled
        """
        return self.new_value

