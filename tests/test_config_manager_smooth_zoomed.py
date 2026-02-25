"""
Tests for ConfigManager smooth_image_when_zoomed setting.

Covers default value, get/set round-trip, and persistence.
Uses a dedicated test config filename to avoid overwriting user config; cleans up after tests.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from pathlib import Path
from utils.config_manager import ConfigManager


TEST_CONFIG_FILENAME = "dicom_viewer_config_test_smooth_zoomed.json"


class TestSmoothImageWhenZoomedConfig(unittest.TestCase):
    """Tests for smooth_image_when_zoomed config key and getters/setters."""

    def setUp(self):
        """Create a ConfigManager using a test config file."""
        self.config = ConfigManager(config_filename=TEST_CONFIG_FILENAME)
        self.config_path = self.config.config_path

    def tearDown(self):
        """Remove test config file if it was created."""
        if self.config_path.exists():
            try:
                self.config_path.unlink()
            except OSError:
                pass

    def test_default_value_is_false(self):
        """Default value of smooth_image_when_zoomed should be False."""
        # New manager with no existing file gets defaults
        self.assertFalse(self.config.get_smooth_image_when_zoomed())

    def test_get_smooth_image_when_zoomed_returns_bool(self):
        """get_smooth_image_when_zoomed should return a bool."""
        self.assertIsInstance(self.config.get_smooth_image_when_zoomed(), bool)

    def test_set_then_get_true(self):
        """Setting smooth_image_when_zoomed to True should persist and be returned by get."""
        self.config.set_smooth_image_when_zoomed(True)
        self.assertTrue(self.config.get_smooth_image_when_zoomed())

    def test_set_then_get_false(self):
        """Setting smooth_image_when_zoomed to False should persist and be returned by get."""
        self.config.set_smooth_image_when_zoomed(True)
        self.config.set_smooth_image_when_zoomed(False)
        self.assertFalse(self.config.get_smooth_image_when_zoomed())

    def test_persists_to_disk(self):
        """Value should be written to config file and reloaded in a new ConfigManager instance."""
        self.config.set_smooth_image_when_zoomed(True)
        self.assertTrue(self.config_path.exists(), "Config file should exist after set")

        config2 = ConfigManager(config_filename=TEST_CONFIG_FILENAME)
        self.assertTrue(
            config2.get_smooth_image_when_zoomed(),
            "Reloaded config should have smooth_image_when_zoomed True"
        )
        config2.set_smooth_image_when_zoomed(False)
        config3 = ConfigManager(config_filename=TEST_CONFIG_FILENAME)
        self.assertFalse(
            config3.get_smooth_image_when_zoomed(),
            "After setting False and reloading, value should be False"
        )


if __name__ == "__main__":
    unittest.main()
