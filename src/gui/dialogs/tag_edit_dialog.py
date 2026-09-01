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

import re
from typing import Any, ClassVar

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QLabel,
    QLineEdit,
    QMessageBox,
    QSpinBox,
    QVBoxLayout,
)


class TagEditDialog(QDialog):
    """
    Dialog for editing individual DICOM tags.
    
    Features:
    - VR type display and validation
    - Input field appropriate for VR type
    - Validation before accepting changes
    """

    # VR types that are read-only (too complex for basic editing)
    READ_ONLY_VR_TYPES: ClassVar[set[str]] = {"SQ", "OB", "OD", "OF", "OL", "OV", "OW"}

    # String VR types
    STRING_VR_TYPES: ClassVar[set[str]] = {"AE", "AS", "AT", "CS", "DA", "DS", "DT", "IS", "LO",
                       "LT", "PN", "SH", "ST", "TM", "UI", "UT"}

    # Numeric VR types
    NUMERIC_VR_TYPES: ClassVar[dict[str, tuple[type, int | None, int | None]]] = {
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
        self.new_value: Any | None = None

        self.setWindowTitle(f"Edit Tag: {tag_name}")
        self.setMinimumWidth(400)

        self.value_input = self._create_ui()
        self._setup_validation()

    def _create_ui(self) -> QLineEdit | QDoubleSpinBox | QSpinBox:
        """Create the UI components."""
        layout = QVBoxLayout(self)
        layout.addLayout(self._create_tag_information_layout())
        notice = QLabel(
            "<b>Note:</b> Editing a tag changes the in-memory dataset and can affect later "
            "DICOM exports. This is not a de-identification workflow."
        )
        notice.setObjectName("tagEditScopeNotice")
        notice.setWordWrap(True)
        layout.addWidget(notice)
        value_layout, value_input = self._create_value_input_layout()
        layout.addLayout(value_layout)
        layout.addWidget(self._create_button_box())
        return value_input

    def _create_tag_information_layout(self) -> QVBoxLayout:
        """Build the read-only tag identity section."""
        info_layout = QVBoxLayout()
        info_layout.addWidget(QLabel(f"<b>Tag:</b> {self.tag_str}"))
        info_layout.addWidget(QLabel(f"<b>Name:</b> {self.tag_name}"))
        info_layout.addWidget(QLabel(f"<b>VR:</b> {self.vr}"))
        return info_layout

    def _create_value_input_layout(
        self,
    ) -> tuple[QVBoxLayout, QLineEdit | QDoubleSpinBox | QSpinBox]:
        """Build the value label and the VR-appropriate input widget."""
        value_layout = QVBoxLayout()
        value_layout.addWidget(QLabel("Value:"))
        value_input = self._create_value_input()
        value_layout.addWidget(value_input)
        return value_layout, value_input

    def _create_value_input(self) -> QLineEdit | QDoubleSpinBox | QSpinBox:
        """Return the input control for the dialog's value representation."""
        if self.vr in self.READ_ONLY_VR_TYPES:
            return self._create_read_only_input()
        if self.vr in self.NUMERIC_VR_TYPES:
            return self._create_numeric_input()
        return self._create_string_input()

    def _create_read_only_input(self) -> QLineEdit:
        """Create the fixed explanatory field for complex VR types."""
        value_input = QLineEdit()
        value_input.setReadOnly(True)
        value_input.setText("(Read-only: Complex VR type)")
        value_input.setStyleSheet("background-color: #f0f0f0; color: #666;")
        return value_input

    def _create_numeric_input(self) -> QLineEdit | QDoubleSpinBox | QSpinBox:
        """Create and populate the numeric control appropriate for ``self.vr``."""
        num_type, min_val, max_val = self.NUMERIC_VR_TYPES[self.vr]
        if num_type is float:
            return self._create_float_input(min_val, max_val, self.current_value)
        if self.vr == "UL" and max_val is not None and max_val > 2147483647:
            return self._create_unsigned_long_input()
        return self._create_integer_input(num_type, min_val, max_val)

    @staticmethod
    def _create_float_input(
        min_val: int | None,
        max_val: int | None,
        current_value: Any,
    ) -> QDoubleSpinBox:
        """Create the existing six-decimal floating-point editor."""
        value_input = QDoubleSpinBox()
        value_input.setDecimals(6)
        if min_val is not None:
            value_input.setMinimum(min_val)
        if max_val is not None:
            value_input.setMaximum(max_val)
        try:
            value_input.setValue(float(current_value))
        except (TypeError, ValueError):
            pass
        return value_input

    def _create_unsigned_long_input(self) -> QLineEdit:
        """Create the line editor required for unsigned values beyond QSpinBox range."""
        value_input = QLineEdit()
        try:
            if isinstance(self.current_value, list):
                value = self.current_value[0] if self.current_value else "0"
            else:
                value = int(self.current_value) if self.current_value else "0"
            value_input.setText(str(value))
        except (ValueError, TypeError):
            value_input.setText("0")
        return value_input

    def _create_integer_input(
        self,
        num_type: type,
        min_val: int | None,
        max_val: int | None,
    ) -> QSpinBox:
        """Create the bounded signed-integer editor and initialize its value."""
        value_input = QSpinBox()
        if min_val is not None:
            value_input.setMinimum(min_val)
        if max_val is not None:
            value_input.setMaximum(min(max_val, 2147483647))
        try:
            if isinstance(self.current_value, list):
                raw_value = self.current_value[0] if self.current_value else 0
            else:
                raw_value = num_type(self.current_value) if self.current_value else 0
            value_input.setValue(int(round(float(raw_value))))
        except (ValueError, TypeError):
            value_input.setValue(0)
        return value_input

    def _create_string_input(self) -> QLineEdit:
        """Create the default text editor with the existing list display format."""
        value_input = QLineEdit()
        if isinstance(self.current_value, list):
            value = ", ".join(str(item) for item in self.current_value)
        else:
            value = str(self.current_value) if self.current_value else ""
        value_input.setText(value)
        return value_input

    def _create_button_box(self) -> QDialogButtonBox:
        """Create and wire the dialog action buttons."""
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self._validate_and_accept)
        button_box.rejected.connect(self.reject)
        return button_box

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
                num_type, _min_val, max_val = self.NUMERIC_VR_TYPES[self.vr]
                try:
                    if num_type is float:
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
        elif self.vr == "UI" and not re.match(r'^[\d.]+$', value):
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

    def get_value(self) -> Any | None:
        """
        Get the new tag value.
        
        Returns:
            New tag value, or None if dialog was cancelled
        """
        return self.new_value
