"""
Tests for the anonymization presets and the shared de-identification options UI.

Covers DeepAnonymizerOptions preset factories and AnonymizationOptionsWidget
preset round-trip and Custom detection (needs Qt).
"""

from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from utils.deep_anonymizer import ANONYMIZER_PRESETS, DeepAnonymizerOptions


class TestPresets:
    def test_standard_share_remints_uids_and_shifts_dates(self) -> None:
        opts = DeepAnonymizerOptions.standard_share()
        assert opts.remint_uids is True
        assert opts.retain_device_identity is False
        assert opts.retain_institution_identity is False
        assert opts.date_shift is True and opts.date_remove is False

    def test_maximal_strip_removes_dates(self) -> None:
        opts = DeepAnonymizerOptions.maximal_strip()
        assert opts.date_remove is True

    def test_research_retains_device_identity(self) -> None:
        opts = DeepAnonymizerOptions.research()
        assert opts.retain_device_identity is True
        assert opts.retain_institution_identity is False
        assert opts.date_shift is True  # dates still shifted

    def test_registry_factories_match_methods(self) -> None:
        keys = [k for k, _label, _f in ANONYMIZER_PRESETS]
        assert keys == ["standard_share", "maximal_strip", "research"]
        for _key, _label, factory in ANONYMIZER_PRESETS:
            assert isinstance(factory(), DeepAnonymizerOptions)


@pytest.mark.qt
class TestOptionsWidget:
    def _widget(self, qapp, options=None):
        from gui.dialogs.anonymization_options_widget import AnonymizationOptionsWidget

        return AnonymizationOptionsWidget(options)

    def test_default_is_standard_share_preset(self, qapp) -> None:
        w = self._widget(qapp)
        assert w.preset_combo.currentIndex() == 0  # standard_share
        opts = w.get_options()
        assert opts.remint_uids is True and opts.date_shift is True

    def test_selecting_preset_fills_toggles(self, qapp) -> None:
        w = self._widget(qapp)
        w.preset_combo.setCurrentIndex(1)  # maximal_strip
        opts = w.get_options()
        assert opts.date_remove is True

        w.preset_combo.setCurrentIndex(2)  # research
        opts = w.get_options()
        assert opts.retain_device_identity is True

    def test_editing_toggle_switches_to_custom(self, qapp) -> None:
        w = self._widget(qapp)
        custom_index = len(ANONYMIZER_PRESETS)
        w.retain_institution_cb.setChecked(True)  # not in any preset
        assert w.preset_combo.currentIndex() == custom_index
        assert w.get_options().retain_institution_identity is True

    def test_set_options_round_trip(self, qapp) -> None:
        w = self._widget(qapp)
        src = DeepAnonymizerOptions.research()
        w.set_options(src)
        out = w.get_options()
        assert out.retain_device_identity == src.retain_device_identity
        assert out.date_shift == src.date_shift
        assert w.preset_combo.currentIndex() == 2  # detected as research preset
