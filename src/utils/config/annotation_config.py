"""
Annotation Config Mixin

Manages text and arrow annotation appearance settings: color and font size
for text annotations; color and size for arrow annotations.

Mixin contract:
    Expects `self.config` (dict) and `self.save_config()` to be provided by
    the concrete ConfigManager class that inherits this mixin.
"""


class AnnotationConfigMixin:
    """Config mixin: text annotation and arrow annotation appearance."""

    def get_text_annotation_color(self) -> tuple:
        """Get text annotation color as RGB tuple."""
        r = self.config.get("text_annotation_color_r", 255)
        g = self.config.get("text_annotation_color_g", 255)
        b = self.config.get("text_annotation_color_b", 0)
        return (r, g, b)

    def set_text_annotation_color(self, r: int, g: int, b: int) -> None:
        """Set text annotation color."""
        if 0 <= r <= 255 and 0 <= g <= 255 and 0 <= b <= 255:
            self.config["text_annotation_color_r"] = r
            self.config["text_annotation_color_g"] = g
            self.config["text_annotation_color_b"] = b
            self.save_config()

    def get_text_annotation_font_size(self) -> int:
        """Get text annotation font size."""
        return self.config.get("text_annotation_font_size", 12)

    def set_text_annotation_font_size(self, size: int) -> None:
        """Set text annotation font size."""
        if size > 0:
            self.config["text_annotation_font_size"] = size
            self.save_config()

    def get_arrow_annotation_color(self) -> tuple:
        """Get arrow annotation color as RGB tuple."""
        r = self.config.get("arrow_annotation_color_r", 255)
        g = self.config.get("arrow_annotation_color_g", 255)
        b = self.config.get("arrow_annotation_color_b", 0)
        return (r, g, b)

    def set_arrow_annotation_color(self, r: int, g: int, b: int) -> None:
        """Set arrow annotation color."""
        if 0 <= r <= 255 and 0 <= g <= 255 and 0 <= b <= 255:
            self.config["arrow_annotation_color_r"] = r
            self.config["arrow_annotation_color_g"] = g
            self.config["arrow_annotation_color_b"] = b
            self.save_config()

    def get_arrow_annotation_size(self) -> int:
        """Get arrow annotation size (line thickness; arrowhead scales via multiplier)."""
        return self.config.get("arrow_annotation_size", 6)

    def set_arrow_annotation_size(self, size: int) -> None:
        """Set arrow annotation size (arrowhead size and line thickness). Valid range 4-30."""
        if 4 <= size <= 30:
            self.config["arrow_annotation_size"] = size
            self.save_config()
