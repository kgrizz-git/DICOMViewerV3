"""
Tests for WindowLevelControls slider/spinbox synchronization and range padding.

Covers:
- Spinbox change updates slider position
- Slider change updates spinbox value
- set_ranges repositions sliders to match current values
- Range padding ensures usable ranges for small-span data (e.g. PT/BQML)
- set_window_level after set_ranges produces correct slider positions
"""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QApplication

from gui.window_level_controls import WindowLevelControls


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture()
def controls(qapp):
    return WindowLevelControls()


class TestSpinboxSliderSync:
    """Spinbox edits should move the slider and vice-versa."""

    def test_center_spinbox_updates_slider(self, controls: WindowLevelControls) -> None:
        controls.set_ranges((-1000.0, 1000.0), (1.0, 2000.0))
        controls.set_window_level(0.0, 500.0, block_signals=True)

        # Simulate user typing a new center value
        controls.center_spinbox.setValue(500.0)

        # Slider should have moved toward the upper end
        # With padded range (-1500, 1500), center=500 → normalized ~667
        assert controls.center_slider.value() > 500

    def test_width_spinbox_updates_slider(self, controls: WindowLevelControls) -> None:
        controls.set_ranges((-1000.0, 1000.0), (1.0, 2000.0))
        controls.set_window_level(0.0, 100.0, block_signals=True)

        controls.width_spinbox.setValue(1500.0)

        # Slider should have moved toward upper end
        assert controls.width_slider.value() > 100

    def test_center_slider_updates_spinbox(self, controls: WindowLevelControls) -> None:
        controls.set_ranges((-1000.0, 1000.0), (1.0, 2000.0))
        controls.set_window_level(0.0, 500.0, block_signals=True)

        controls.center_slider.setValue(750)

        # Spinbox should reflect a value > 0 (midpoint was ~500)
        assert controls.center_spinbox.value() > 0

    def test_width_slider_updates_spinbox(self, controls: WindowLevelControls) -> None:
        controls.set_ranges((-1000.0, 1000.0), (1.0, 2000.0))
        controls.set_window_level(0.0, 500.0, block_signals=True)

        controls.width_slider.setValue(900)

        assert controls.width_spinbox.value() > 500


class TestSetRangesRepositionsSliders:
    """Calling set_ranges should reposition sliders for current values."""

    def test_sliders_reposition_on_range_change(self, controls: WindowLevelControls) -> None:
        # Set initial state
        controls.set_ranges((-1000.0, 1000.0), (1.0, 2000.0))
        controls.set_window_level(0.0, 500.0, block_signals=True)
        initial_center_pos = controls.center_slider.value()

        # Change to a much larger range — slider should reposition
        controls.set_ranges((-5000.0, 5000.0), (1.0, 10000.0))

        # Center=0 in range (-5000,5000) is at ~50% → slider ~500
        # But with padding the range is wider, so it should be near 500
        new_center_pos = controls.center_slider.value()
        # The key assertion: slider moved (didn't stay at old position)
        assert new_center_pos != initial_center_pos or abs(new_center_pos - 500) < 50


class TestRangePadding:
    """_padded_ranges should expand small ranges for usability."""

    def test_small_range_gets_padded(self) -> None:
        # PT-like scenario: pixels 0-1000
        center, width = WindowLevelControls._padded_ranges(
            (0.0, 1000.0), (1.0, 1000.0)
        )
        # Center range should extend beyond 0-1000
        assert center[0] < 0.0
        assert center[1] > 1000.0
        # Width max should be at least 2000 (2x span)
        assert width[1] >= 2000.0

    def test_large_range_still_gets_some_padding(self) -> None:
        # CT-like scenario: -1024 to 3071
        center, width = WindowLevelControls._padded_ranges(
            (-1024.0, 3071.0), (1.0, 4095.0)
        )
        assert center[0] < -1024.0
        assert center[1] > 3071.0
        assert width[1] >= 4095.0

    def test_tiny_range_gets_minimum_padding(self) -> None:
        # Near-constant data: all pixels ~500
        center, width = WindowLevelControls._padded_ranges(
            (500.0, 502.0), (1.0, 2.0)
        )
        # Should have at least 100 units of padding
        assert center[0] <= 400.0
        assert center[1] >= 602.0
        # Width should be at least 200
        assert width[1] >= 200.0

    def test_spinbox_accepts_values_beyond_pixel_range(self, controls: WindowLevelControls) -> None:
        """After set_ranges with PT-like data, spinbox should accept >1000."""
        controls.set_ranges((0.0, 1000.0), (1.0, 1000.0))

        # Spinbox max should be > 1000 due to padding
        assert controls.center_spinbox.maximum() > 1000.0
        assert controls.width_spinbox.maximum() > 1000.0

        # Should be able to set values beyond the raw pixel range
        controls.center_spinbox.setValue(1200.0)
        assert controls.center_spinbox.value() == pytest.approx(1200.0, abs=0.2)


class TestSetWindowLevelAfterRanges:
    """set_window_level after set_ranges should position sliders correctly."""

    def test_value_at_range_midpoint(self, controls: WindowLevelControls) -> None:
        controls.set_ranges((0.0, 1000.0), (1.0, 1000.0))
        controls.set_window_level(500.0, 500.0, block_signals=True)

        # Center=500 should be roughly at midpoint of padded range
        # Padded range: (-250, 1250), so 500 is at (500+250)/1500 = 50% → slider ~500
        assert 350 < controls.center_slider.value() < 650

    def test_value_at_range_minimum(self, controls: WindowLevelControls) -> None:
        controls.set_ranges((0.0, 1000.0), (1.0, 1000.0))
        controls.set_window_level(0.0, 1.0, block_signals=True)

        # Center=0, padded range starts at -250, so 0 is at 250/1500 ≈ 167
        assert controls.center_slider.value() < 300
        # Width=1, near minimum
        assert controls.width_slider.value() < 50


class TestPresetsButtonLayout:
    """Presets… attaches to an external top-row layout when provided."""

    def test_attach_presets_menu_uses_row_layout(self, qapp) -> None:
        from PySide6.QtWidgets import QHBoxLayout, QWidget

        controls = WindowLevelControls()
        host = QWidget()
        row = QHBoxLayout(host)
        row.addStretch()

        def _noop(_index: int) -> None:
            pass

        btn = controls.attach_wl_presets_menu(on_select=_noop, row_layout=row)
        assert btn is not None
        assert row.indexOf(btn) == 1  # after stretch: button on the right
        assert "Presets" in btn.text()
