"""
Unit tests for ``qa.pylinac_nuclear_plots``.

``is_plottable`` is pure logic. ``render_nuclear_figures`` guards before
importing pylinac, so the unsupported-class and missing-pylinac branches are
tested without a real pylinac install.
"""

from __future__ import annotations

import builtins
from unittest.mock import patch

import pytest

from qa import pylinac_nuclear_plots as pnp
from utils.config.qa_nuclear_config import (
    PLANAR_UNIFORMITY_CLASS,
)


class TestIsPlottable:
    def test_known_class_plottable(self):
        assert pnp.is_plottable(PLANAR_UNIFORMITY_CLASS) is True

    def test_simple_sensitivity_not_plottable(self):
        assert pnp.is_plottable("SimpleSensitivity") is False

    def test_unknown_class_not_plottable(self):
        assert pnp.is_plottable("DoesNotExist") is False


class TestRenderGuards:
    def test_unsupported_class_raises_before_import(self):
        # Must raise without importing pylinac (guard is before the import).
        with patch.object(builtins, "__import__", side_effect=AssertionError(
            "pylinac should not be imported for an unsupported class"
        )), pytest.raises(RuntimeError, match="not supported"):
            pnp.render_nuclear_figures(
                "x.dcm", analysis_class="SimpleSensitivity", out_path="o.png"
            )

    def test_missing_pylinac_raises_clear_error(self):
        def _fake_import(name, *args, **kwargs):
            if name.startswith("pylinac"):
                raise ImportError("no pylinac")
            return builtins.__import__(name, *args, **kwargs)

        with patch.object(builtins, "__import__", side_effect=_fake_import), pytest.raises(
            RuntimeError, match="pylinac is not installed"
        ):
            pnp.render_nuclear_figures(
                "x.dcm", analysis_class=PLANAR_UNIFORMITY_CLASS, out_path="o.png"
            )
