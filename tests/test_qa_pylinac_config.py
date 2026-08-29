"""
Unit tests for ``utils.config.qa_pylinac_config.QaPylinacConfigMixin``.

The mixin expects a host providing ``self.config`` (dict) and ``self.save_config()``.
A minimal ``_Host`` stands in for ConfigManager.
"""

from __future__ import annotations

from utils.config.qa_pylinac_config import (
    DEFAULT_ACR_MRI_LOW_CONTRAST_METHOD,
    QaPylinacConfigMixin,
)


def _make_host() -> QaPylinacConfigMixin:
    class _Host(QaPylinacConfigMixin):
        def __init__(self) -> None:
            self.config: dict = {}
            self.save_calls = 0

        def save_config(self) -> None:
            self.save_calls += 1

    return _Host()


class TestAcrMriLowContrastMethod:
    def test_default_method(self):
        host = _make_host()
        assert host.get_acr_mri_low_contrast_method() == DEFAULT_ACR_MRI_LOW_CONTRAST_METHOD
        assert host.save_calls == 0

    def test_set_and_get_valid_method(self):
        host = _make_host()
        host.set_acr_mri_low_contrast_method("Ratio")
        assert host.get_acr_mri_low_contrast_method() == "Ratio"
        assert host.save_calls == 1

    def test_set_invalid_method_falls_back_to_default(self):
        host = _make_host()
        host.set_acr_mri_low_contrast_method("NotARealMethod")
        assert host.get_acr_mri_low_contrast_method() == DEFAULT_ACR_MRI_LOW_CONTRAST_METHOD
        assert host.save_calls == 1

    def test_get_invalid_stored_method_falls_back(self):
        host = _make_host()
        host.config["acr_mri_low_contrast_method"] = "Bogus"
        assert host.get_acr_mri_low_contrast_method() == DEFAULT_ACR_MRI_LOW_CONTRAST_METHOD

    def test_get_none_stored_uses_default(self):
        host = _make_host()
        host.config["acr_mri_low_contrast_method"] = None
        assert host.get_acr_mri_low_contrast_method() == DEFAULT_ACR_MRI_LOW_CONTRAST_METHOD


class TestAcrMriLowContrastVisibilityThreshold:
    def test_default_threshold(self):
        host = _make_host()
        assert host.get_acr_mri_low_contrast_visibility_threshold() == 0.001

    def test_set_and_get_persists(self):
        host = _make_host()
        host.set_acr_mri_low_contrast_visibility_threshold(0.5)
        assert host.get_acr_mri_low_contrast_visibility_threshold() == 0.5
        assert host.config["acr_mri_low_contrast_visibility_threshold"] == 0.5
        assert host.save_calls == 1

    def test_set_below_min_clamped_to_default(self):
        host = _make_host()
        host.set_acr_mri_low_contrast_visibility_threshold(-1.0)
        assert host.get_acr_mri_low_contrast_visibility_threshold() == 0.001
        # setter writes the coerced (default) value and does not save.
        assert host.config["acr_mri_low_contrast_visibility_threshold"] == 0.001
        assert host.save_calls == 1

    def test_set_above_max_clamped_to_default(self):
        host = _make_host()
        host.set_acr_mri_low_contrast_visibility_threshold(200.0)
        assert host.get_acr_mri_low_contrast_visibility_threshold() == 0.001
        assert host.config["acr_mri_low_contrast_visibility_threshold"] == 0.001

    def test_set_exact_min_accepted(self):
        host = _make_host()
        host.set_acr_mri_low_contrast_visibility_threshold(0.0)
        assert host.get_acr_mri_low_contrast_visibility_threshold() == 0.0

    def test_set_exact_max_accepted(self):
        host = _make_host()
        host.set_acr_mri_low_contrast_visibility_threshold(100.0)
        assert host.get_acr_mri_low_contrast_visibility_threshold() == 100.0

    def test_set_non_numeric_clamped_to_default(self):
        host = _make_host()
        host.set_acr_mri_low_contrast_visibility_threshold("abc")  # type: ignore[arg-type]
        assert host.get_acr_mri_low_contrast_visibility_threshold() == 0.001

    def test_set_non_finite_clamped_to_default(self):
        host = _make_host()
        host.set_acr_mri_low_contrast_visibility_threshold(float("nan"))
        assert host.get_acr_mri_low_contrast_visibility_threshold() == 0.001

    def test_get_non_numeric_falls_back(self):
        host = _make_host()
        host.config["acr_mri_low_contrast_visibility_threshold"] = "abc"
        assert host.get_acr_mri_low_contrast_visibility_threshold() == 0.001

    def test_get_non_finite_falls_back(self):
        host = _make_host()
        host.config["acr_mri_low_contrast_visibility_threshold"] = float("nan")
        assert host.get_acr_mri_low_contrast_visibility_threshold() == 0.001

    def test_get_missing_falls_back(self):
        host = _make_host()
        assert "acr_mri_low_contrast_visibility_threshold" not in host.config
        assert host.get_acr_mri_low_contrast_visibility_threshold() == 0.001


class TestAcrMriLowContrastSanityMultiplier:
    def test_default_multiplier(self):
        host = _make_host()
        assert host.get_acr_mri_low_contrast_visibility_sanity_multiplier() == 3.0

    def test_set_and_get_persists(self):
        host = _make_host()
        host.set_acr_mri_low_contrast_visibility_sanity_multiplier(5.0)
        assert host.get_acr_mri_low_contrast_visibility_sanity_multiplier() == 5.0
        assert host.config["acr_mri_low_contrast_visibility_sanity_multiplier"] == 5.0
        assert host.save_calls == 1

    def test_set_below_min_clamped_to_default(self):
        host = _make_host()
        host.set_acr_mri_low_contrast_visibility_sanity_multiplier(0.0)
        assert host.get_acr_mri_low_contrast_visibility_sanity_multiplier() == 3.0
        assert host.config["acr_mri_low_contrast_visibility_sanity_multiplier"] == 3.0

    def test_set_above_max_clamped_to_default(self):
        host = _make_host()
        host.set_acr_mri_low_contrast_visibility_sanity_multiplier(500.0)
        assert host.get_acr_mri_low_contrast_visibility_sanity_multiplier() == 3.0
        assert host.config["acr_mri_low_contrast_visibility_sanity_multiplier"] == 3.0

    def test_set_exact_min_accepted(self):
        host = _make_host()
        host.set_acr_mri_low_contrast_visibility_sanity_multiplier(0.01)
        assert host.get_acr_mri_low_contrast_visibility_sanity_multiplier() == 0.01

    def test_set_exact_max_accepted(self):
        host = _make_host()
        host.set_acr_mri_low_contrast_visibility_sanity_multiplier(100.0)
        assert host.get_acr_mri_low_contrast_visibility_sanity_multiplier() == 100.0

    def test_set_non_numeric_clamped_to_default(self):
        host = _make_host()
        host.set_acr_mri_low_contrast_visibility_sanity_multiplier("x")  # type: ignore[arg-type]
        assert host.get_acr_mri_low_contrast_visibility_sanity_multiplier() == 3.0

    def test_get_none_falls_back(self):
        host = _make_host()
        host.config["acr_mri_low_contrast_visibility_sanity_multiplier"] = None
        assert host.get_acr_mri_low_contrast_visibility_sanity_multiplier() == 3.0


class TestAcrQaEmbedModuleImages:
    def test_default_true(self):
        host = _make_host()
        assert host.get_acr_qa_embed_module_images_in_xlsx() is True

    def test_set_false(self):
        host = _make_host()
        host.set_acr_qa_embed_module_images_in_xlsx(False)
        assert host.get_acr_qa_embed_module_images_in_xlsx() is False
        assert host.save_calls == 1

    def test_set_true(self):
        host = _make_host()
        host.set_acr_qa_embed_module_images_in_xlsx(True)
        assert host.get_acr_qa_embed_module_images_in_xlsx() is True

    def test_get_explicit_value(self):
        host = _make_host()
        host.config["acr_qa_embed_module_images_in_xlsx"] = False
        assert host.get_acr_qa_embed_module_images_in_xlsx() is False

    def test_persists_through_save(self):
        host = _make_host()
        host.set_acr_qa_embed_module_images_in_xlsx(False)
        assert host.config["acr_qa_embed_module_images_in_xlsx"] is False


class TestAcrQaVanillaPylinac:
    def test_default_false(self):
        host = _make_host()
        assert host.get_acr_qa_vanilla_pylinac() is False

    def test_set_true(self):
        host = _make_host()
        host.set_acr_qa_vanilla_pylinac(True)
        assert host.get_acr_qa_vanilla_pylinac() is True
        assert host.save_calls == 1

    def test_set_false(self):
        host = _make_host()
        host.set_acr_qa_vanilla_pylinac(False)
        assert host.get_acr_qa_vanilla_pylinac() is False

    def test_get_explicit_value(self):
        host = _make_host()
        host.config["acr_qa_vanilla_pylinac"] = "truthy-string"
        assert host.get_acr_qa_vanilla_pylinac() is True
