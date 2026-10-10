"""Unit tests for the MPR session/view admission-cap config mixin.

Covers strict validation (no unsafe coercion), the view>=session>=1 pair
invariant, save-failure rollback, JSON persistence through a real
ConfigManager, and alignment with the core registry defaults.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from core.mpr_session_types import DEFAULT_SESSION_CAP, DEFAULT_VIEW_CAP
from utils.config.mpr_session_config import (
    MPR_SESSION_CAP_DEFAULT,
    MPR_VIEW_CAP_DEFAULT,
    MprSessionConfigMixin,
)
from utils.config_manager import ConfigManager


def _make_host(mixin_cls=MprSessionConfigMixin):
    class _Host(mixin_cls):
        def __init__(self):
            self.config = {}
            self.save_calls = 0
            self.save_result = True

        def save_config(self):
            self.save_calls += 1
            return self.save_result

    return _Host()


class TestDefaults:
    def test_compiled_defaults(self):
        host = _make_host()
        assert host.get_mpr_session_cap() == 8
        assert host.get_mpr_view_cap() == 16
        assert host.get_mpr_caps() == (8, 16)

    def test_defaults_mirror_core_registry(self):
        assert MPR_SESSION_CAP_DEFAULT == DEFAULT_SESSION_CAP == 8
        assert MPR_VIEW_CAP_DEFAULT == DEFAULT_VIEW_CAP == 16


class TestStrictValidation:
    def test_getters_reject_non_int_storage(self):
        for bad in (True, False, "8", 8.0, None, [8], "16"):
            host = _make_host()
            host.config["mpr_session_cap"] = bad
            host.config["mpr_view_cap"] = bad
            assert host.get_mpr_session_cap() == 8
            assert host.get_mpr_view_cap() == 16

    def test_getters_reject_non_positive(self):
        host = _make_host()
        host.config["mpr_session_cap"] = 0
        host.config["mpr_view_cap"] = -2
        assert host.get_mpr_caps() == (8, 16)

    def test_view_getter_never_below_session(self):
        host = _make_host()
        host.config["mpr_session_cap"] = 12
        host.config["mpr_view_cap"] = 4
        assert host.get_mpr_caps() == (12, 16)

    def test_view_fallback_covers_session_above_default(self):
        host = _make_host()
        host.config["mpr_session_cap"] = 32
        host.config["mpr_view_cap"] = 8
        assert host.get_mpr_caps() == (32, 32)
        host.config["mpr_view_cap"] = "bad"
        assert host.get_mpr_caps() == (32, 32)
        del host.config["mpr_view_cap"]
        assert host.get_mpr_caps() == (32, 32)
        host.config["mpr_view_cap"] = 40
        assert host.get_mpr_caps() == (32, 40)

    def test_setters_reject_bad_types_without_mutating(self):
        cases: list[Any] = [True, "8", 8.0, None, 0, -1]
        for bad in cases:
            host = _make_host()
            assert host.set_mpr_session_cap(bad) is False
            assert host.set_mpr_view_cap(bad) is False
            assert host.save_calls == 0
            assert "mpr_session_cap" not in host.config
            assert "mpr_view_cap" not in host.config


class TestPairInvariant:
    def test_view_cap_cannot_drop_below_session_cap(self):
        host = _make_host()
        assert host.set_mpr_view_cap(10) is True
        assert host.set_mpr_view_cap(7) is False
        assert host.get_mpr_view_cap() == 10

    def test_session_cap_cannot_exceed_view_cap(self):
        host = _make_host()
        assert host.set_mpr_view_cap(10) is True
        assert host.set_mpr_session_cap(12) is False
        assert host.get_mpr_session_cap() == 8
        assert host.set_mpr_view_cap(12) is True
        assert host.set_mpr_session_cap(12) is True
        assert host.get_mpr_caps() == (12, 12)

    def test_lowering_caps_allowed_and_blocks_only_growth(self):
        host = _make_host()
        assert host.set_mpr_session_cap(4) is True
        assert host.set_mpr_view_cap(6) is True
        assert host.get_mpr_caps() == (4, 6)


class TestPersistence:
    def test_save_failure_rolls_back(self):
        host = _make_host()
        host.save_result = False
        assert host.set_mpr_session_cap(4) is False
        assert host.get_mpr_session_cap() == 8
        assert host.config["mpr_session_cap"] == 8  # previous value restored

    def test_round_trip_through_real_config_manager(self, tmp_path: Path):
        manager = ConfigManager(config_dir=str(tmp_path))
        assert manager.get_mpr_caps() == (8, 16)
        assert manager.set_mpr_session_cap(5) is True
        assert manager.set_mpr_view_cap(9) is True
        reloaded = ConfigManager(config_dir=str(tmp_path))
        assert reloaded.get_mpr_caps() == (5, 9)

    def test_real_manager_falls_back_on_invalid_stored_json(self, tmp_path: Path):
        import json

        manager = ConfigManager(config_dir=str(tmp_path))
        assert manager.set_mpr_session_cap(5) is True  # creates the file
        path = tmp_path / "dicom_viewer_config.json"
        stored = json.loads(path.read_text(encoding="utf-8"))
        stored["mpr_session_cap"] = "eight"
        stored["mpr_view_cap"] = True
        path.write_text(json.dumps(stored), encoding="utf-8")
        reloaded = ConfigManager(config_dir=str(tmp_path))
        assert reloaded.get_mpr_caps() == (8, 16)

    def test_keys_live_in_regular_config_not_privacy_storage(self, tmp_path: Path):
        manager = ConfigManager(config_dir=str(tmp_path))
        assert manager.set_mpr_session_cap(3) is True
        assert (tmp_path / "dicom_viewer_config.json").exists()
        assert not (tmp_path / "private-storage").exists()


class TestAtomicPair:
    def test_pair_can_raise_the_session_cap_above_the_old_view_cap(self):
        host = _make_host()
        host.config.update(mpr_session_cap=8, mpr_view_cap=16)
        assert host.set_mpr_caps(20, 40) is True  # two single setters could not do this in either order
        assert host.get_mpr_caps() == (20, 40)
        assert host.save_calls == 1  # one save for the pair

    def test_pair_can_lower_both_without_a_transient_invalid_state(self):
        host = _make_host()
        host.config.update(mpr_session_cap=8, mpr_view_cap=16)
        assert host.set_mpr_caps(2, 3) is True
        assert host.get_mpr_caps() == (2, 3)

    @pytest.mark.parametrize(
        "pair",
        [(0, 4), (3, 2), (-1, 5), (True, 9), (2, True), ("2", 4), (2, "4"), (2.0, 4), (None, 4), (1, 0)],
    )
    def test_invalid_pairs_mutate_nothing_and_do_not_save(self, pair):
        host = _make_host()
        host.config.update(mpr_session_cap=8, mpr_view_cap=16)
        assert host.set_mpr_caps(*pair) is False
        assert host.config == {"mpr_session_cap": 8, "mpr_view_cap": 16}
        assert host.save_calls == 0

    def test_failed_save_restores_both_keys(self):
        host = _make_host()
        host.config.update(mpr_session_cap=8, mpr_view_cap=16)
        host.save_result = False
        assert host.set_mpr_caps(2, 3) is False
        assert host.config == {"mpr_session_cap": 8, "mpr_view_cap": 16}
        assert host.get_mpr_caps() == (8, 16)

    def test_failed_save_restores_absent_keys_as_absent(self):
        host = _make_host()
        host.save_result = False
        assert host.set_mpr_caps(2, 3) is False
        assert host.config == {}

    def test_pair_round_trips_through_a_real_config_manager(self, tmp_path):
        config = ConfigManager(config_dir=tmp_path / "config")
        assert config.set_mpr_caps(12, 30) is True
        assert ConfigManager(config_dir=tmp_path / "config").get_mpr_caps() == (12, 30)
