"""
Measurement Config Mixin

Manages measurement tool appearance: font size/color and line
thickness/color for the distance/angle measurement tool.

Mixin contract:
    Expects `self.config` (dict) and `self.save_config()` to be provided by
    the concrete ConfigManager class that inherits this mixin.
"""


class MeasurementConfigMixin:
    """Config mixin: measurement font and line appearance settings."""

    def get_measurement_font_size(self) -> int:
        """Get measurement text font size."""
        return self.config.get("measurement_font_size", 14)

    def set_measurement_font_size(self, size: int) -> None:
        """Set measurement text font size."""
        if size > 0:
            self.config["measurement_font_size"] = size
            self.save_config()

    def get_measurement_font_color(self) -> tuple:
        """Get measurement text color as RGB tuple."""
        r = self.config.get("measurement_font_color_r", 0)
        g = self.config.get("measurement_font_color_g", 255)
        b = self.config.get("measurement_font_color_b", 0)
        return (r, g, b)

    def set_measurement_font_color(self, r: int, g: int, b: int) -> None:
        """Set measurement text color."""
        if 0 <= r <= 255 and 0 <= g <= 255 and 0 <= b <= 255:
            self.config["measurement_font_color_r"] = r
            self.config["measurement_font_color_g"] = g
            self.config["measurement_font_color_b"] = b
            self.save_config()

    def get_measurement_line_thickness(self) -> int:
        """Get measurement line thickness in viewport pixels."""
        return self.config.get("measurement_line_thickness", 6)

    def set_measurement_line_thickness(self, thickness: int) -> None:
        """Set measurement line thickness in viewport pixels."""
        if thickness > 0:
            self.config["measurement_line_thickness"] = thickness
            self.save_config()

    def get_measurement_line_color(self) -> tuple:
        """Get measurement line color as RGB tuple."""
        r = self.config.get("measurement_line_color_r", 0)
        g = self.config.get("measurement_line_color_g", 255)
        b = self.config.get("measurement_line_color_b", 0)
        return (r, g, b)

    def set_measurement_line_color(self, r: int, g: int, b: int) -> None:
        """Set measurement line color."""
        if 0 <= r <= 255 and 0 <= g <= 255 and 0 <= b <= 255:
            self.config["measurement_line_color_r"] = r
            self.config["measurement_line_color_g"] = g
            self.config["measurement_line_color_b"] = b
            self.save_config()
