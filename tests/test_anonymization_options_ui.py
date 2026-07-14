"""
Tests for the anonymization presets and the shared de-identification options UI.

Covers:
- DeepAnonymizerOptions preset factories + the resulting CID 7050 method codes.
- AnonymizationOptionsWidget preset round-trip and Custom detection (needs Qt).
"""

from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from utils.deep_anonymizer import ANONYMIZER_PRESETS, DeepAnonymizerOptions
from utils.deid_provenance import build_method_codes


def _codes_for(options: DeepAnonymizerOptions) -> set:
    if options.date_remove:
        date_mode = "remove"
    elif options.date_shift:
        date_mode = "shift"
    else:
        date_mode = "keep"
    return {
        c[0]
        for c in build_method_codes(
            date_mode=date_mode,
            retain_device_identity=options.retain_device_identity,
            retain_institution_identity=options.retain_institution_identity,
            retain_uids=not options.remint_uids,
        )
    }


class TestPresets:
    def test_standard_share_is_base_profile_shift(self) -> None:
        opts = DeepAnonymizerOptions.standard_share()
        assert opts.remint_uids is True
        assert opts.retain_device_identity is False
        assert opts.retain_institution_identity is False
        assert opts.date_shift is True and opts.date_remove is False
        assert _codes_for(opts) == {"113100", "113107"}

    def test_maximal_strip_removes_dates_no_temporal_code(self) -> None:
        opts = DeepAnonymizerOptions.maximal_strip()
        assert opts.date_remove is True
        codes = _codes_for(opts)
        assert codes == {"113100"}
        assert "113106" not in codes and "113107" not in codes

    def test_research_retains_device_identity(self) -> None:
        opts = DeepAnonymizerOptions.research()
        assert opts.retain_device_identity is True
        assert opts.retain_institution_identity is False
        codes = _codes_for(opts)
        assert "113109" in codes
        assert "113107" in codes  # dates still shifted

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
