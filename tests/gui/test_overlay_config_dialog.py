"""Unit tests for gui.dialogs.overlay_config_dialog."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from gui.dialogs.overlay_config_dialog import COMMON_TAGS, OverlayConfigDialog
from utils.config_manager import ConfigManager

_EMPTY_CORNERS = {
    "upper_left": [],
    "upper_right": [],
    "lower_left": [],
    "lower_right": [],
}

_ALL_MODALITIES = ["default", "CR", "CT", "DX", "MG", "MR", "NM", "PT", "RF", "RT", "US", "XA"]


def _cm(tmp_path: Path) -> ConfigManager:
    cm = ConfigManager()
    cm.config_path = tmp_path / "cfg.json"
    cm.config = cm.default_config.copy()
    return cm


def _cm_empty(tmp_path: Path) -> ConfigManager:
    """ConfigManager with empty overlay tags for all modalities (lists start empty)."""
    cm = _cm(tmp_path)
    for mod in _ALL_MODALITIES:
        cm.set_overlay_tags(mod, _EMPTY_CORNERS)
        cm.set_overlay_tags_detailed_extra(mod, _EMPTY_CORNERS)
    return cm


class _CountingConfigManager(ConfigManager):
    """ConfigManager test double that records disk-save requests."""

    def __init__(self, tmp_path: Path):
        super().__init__()
        self.config_path = tmp_path / "cfg.json"
        self.config = self.default_config.copy()
        self.save_calls = 0

    def save_config(self) -> bool:
        self.save_calls += 1
        return True


def _cm_empty_counting(tmp_path: Path) -> _CountingConfigManager:
    cm = _CountingConfigManager(tmp_path)
    for mod in _ALL_MODALITIES:
        cm.set_overlay_tags(mod, _EMPTY_CORNERS)
        cm.set_overlay_tags_detailed_extra(mod, _EMPTY_CORNERS)
    cm.save_calls = 0
    return cm


@pytest.fixture
def config_manager(tmp_path: Path) -> ConfigManager:
    return _cm_empty(tmp_path)


@pytest.fixture
def dialog(qapp, config_manager: ConfigManager) -> OverlayConfigDialog:
    return OverlayConfigDialog(config_manager)


def _simple_tags(dlg: OverlayConfigDialog, corner: str) -> list[str]:
    return [dlg.selected_lists[corner].item(i).text() for i in range(dlg.selected_lists[corner].count())]


def _detailed_tags(dlg: OverlayConfigDialog, corner: str) -> list[str]:
    return [dlg.detailed_selected_lists[corner].item(i).text() for i in range(dlg.detailed_selected_lists[corner].count())]


# ---------------------------------------------------------------------------
# Initialization
# ---------------------------------------------------------------------------


class TestDialogInitialization:
    def test_default_modality_is_default(self, dialog: OverlayConfigDialog):
        assert dialog.current_modality == "default"

    def test_initial_modality_set(self, qapp, tmp_path: Path):
        cm = _cm_empty(tmp_path)
        dlg = OverlayConfigDialog(cm, initial_modality="CT")
        assert dlg.current_modality == "CT"

    def test_invalid_initial_modality_falls_back_to_default(self, qapp, tmp_path: Path):
        cm = _cm_empty(tmp_path)
        dlg = OverlayConfigDialog(cm, initial_modality="INVALID")
        assert dlg.current_modality == "default"

    def test_whitespace_initial_modality_stripped(self, qapp, tmp_path: Path):
        cm = _cm_empty(tmp_path)
        dlg = OverlayConfigDialog(cm, initial_modality="  MR  ")
        assert dlg.current_modality == "MR"

    def test_window_title(self, dialog: OverlayConfigDialog):
        assert dialog.windowTitle() == "Overlay Tags Configuration"

    def test_dialog_is_modal(self, dialog: OverlayConfigDialog):
        assert dialog.isModal()

    def test_four_corner_tabs_exist(self, dialog: OverlayConfigDialog):
        for corner in ("Upper Left", "Upper Right", "Lower Left", "Lower Right"):
            assert corner in dialog.selected_lists
            assert corner in dialog.detailed_selected_lists

    def test_ui_dicts_populated(self, dialog: OverlayConfigDialog):
        for corner in ("Upper Left", "Upper Right", "Lower Left", "Lower Right"):
            assert corner in dialog.search_edits
            assert corner in dialog.available_lists
            assert corner in dialog.selected_lists
            assert corner in dialog.detailed_selected_lists
            assert corner in dialog.move_up_buttons
            assert corner in dialog.move_down_buttons
            assert corner in dialog.detailed_move_up_buttons
            assert corner in dialog.detailed_move_down_buttons

    def test_common_tags_in_catalog(self, dialog: OverlayConfigDialog):
        catalog = dialog.available_lists["Upper Left"]
        catalog_tags = {catalog.item(i).text() for i in range(catalog.count())}
        for tag in COMMON_TAGS:
            assert tag in catalog_tags, f"{tag} missing from catalog"

    def test_modality_combo_contains_all_modalities(self, dialog: OverlayConfigDialog):
        combo_texts = {dialog.modality_combo.itemText(i) for i in range(dialog.modality_combo.count())}
        for mod in _ALL_MODALITIES:
            assert mod in combo_texts

    def test_detail_mode_combo_has_three_options(self, dialog: OverlayConfigDialog):
        assert dialog.detail_mode_combo.count() == 3
        assert dialog.detail_mode_combo.itemData(0) == "minimal"
        assert dialog.detail_mode_combo.itemData(1) == "detailed"
        assert dialog.detail_mode_combo.itemData(2) == "hidden"

    def test_lists_start_empty_with_empty_config(self, dialog: OverlayConfigDialog):
        for corner in ("Upper Left", "Upper Right", "Lower Left", "Lower Right"):
            assert dialog.selected_lists[corner].count() == 0
            assert dialog.detailed_selected_lists[corner].count() == 0


class TestDefaultTagsPopulated:
    """When no saved config exists, get_overlay_tags returns defaults."""

    def test_default_tags_loaded_when_no_config(self, qapp, tmp_path: Path):
        cm = _cm(tmp_path)
        dlg = OverlayConfigDialog(cm)
        tags = _simple_tags(dlg, "Upper Left")
        assert "PatientName" in tags
        assert "PatientID" in tags
        assert "StudyDate" in tags


# ---------------------------------------------------------------------------
# Modality switching
# ---------------------------------------------------------------------------


class TestModalitySwitching:
    def test_switching_modality_changes_current_modality(self, dialog: OverlayConfigDialog):
        dialog.modality_combo.setCurrentText("CT")
        assert dialog.current_modality == "CT"

    def test_switching_modality_preserves_tags(self, dialog: OverlayConfigDialog):
        dialog.modality_combo.setCurrentText("CT")
        dialog.selected_lists["Upper Left"].addItem("TestTag")
        dialog._on_live_update()

        dialog.modality_combo.setCurrentText("MR")
        assert dialog.selected_lists["Upper Left"].count() == 0

        dialog.modality_combo.setCurrentText("CT")
        assert "TestTag" in _simple_tags(dialog, "Upper Left")

    def test_modality_change_emits_config_changed(self, dialog: OverlayConfigDialog):
        signals: list[bool] = []
        dialog.config_changed.connect(lambda: signals.append(True))
        dialog.modality_combo.setCurrentText("CT")
        assert len(signals) >= 1

    def test_modality_change_handler_propagates_exceptions_for_direct_tests(
        self, monkeypatch, dialog: OverlayConfigDialog
    ):
        def fail_commit() -> None:
            raise RuntimeError("commit failed")

        monkeypatch.setattr(dialog, "_commit_current_modality_to_config", fail_commit)

        with pytest.raises(RuntimeError, match="commit failed"):
            dialog._handle_modality_changed("CT")

    def test_modality_change_slot_logs_exceptions_without_raising(
        self, monkeypatch, caplog, dialog: OverlayConfigDialog
    ):
        def fail_commit() -> None:
            raise RuntimeError("commit failed")

        monkeypatch.setattr(dialog, "_commit_current_modality_to_config", fail_commit)

        with caplog.at_level(logging.ERROR):
            dialog._on_modality_changed("CT")

        assert "Overlay config modality change failed" in caplog.text
        assert "commit failed" in caplog.text


# ---------------------------------------------------------------------------
# Tag operations
# ---------------------------------------------------------------------------


class TestTagOperations:
    def test_add_tag_to_simple(self, dialog: OverlayConfigDialog):
        dialog._add_tag_to_corner("Upper Left", "PatientName", "simple")
        assert "PatientName" in _simple_tags(dialog, "Upper Left")

    def test_add_tag_to_detailed(self, dialog: OverlayConfigDialog):
        dialog._add_tag_to_corner("Upper Left", "PatientName", "detailed")
        assert "PatientName" in _detailed_tags(dialog, "Upper Left")

    def test_add_duplicate_tag_ignored(self, dialog: OverlayConfigDialog):
        dialog._add_tag_to_corner("Upper Left", "PatientName", "simple")
        dialog._add_tag_to_corner("Upper Left", "PatientName", "simple")
        assert dialog.selected_lists["Upper Left"].count() == 1

    def test_remove_tag_from_simple(self, dialog: OverlayConfigDialog):
        dialog._add_tag_to_corner("Upper Left", "PatientName", "simple")
        dialog._add_tag_to_corner("Upper Left", "PatientID", "simple")
        dialog.selected_lists["Upper Left"].item(0).setSelected(True)
        dialog._remove_selected_tags("Upper Left", "simple")
        tags = _simple_tags(dialog, "Upper Left")
        assert "PatientName" not in tags
        assert "PatientID" in tags

    def test_remove_tag_from_detailed(self, dialog: OverlayConfigDialog):
        dialog._add_tag_to_corner("Upper Left", "PatientName", "detailed")
        dialog.detailed_selected_lists["Upper Left"].item(0).setSelected(True)
        dialog._remove_selected_tags("Upper Left", "detailed")
        assert dialog.detailed_selected_lists["Upper Left"].count() == 0

    def test_remove_with_no_selection_does_nothing(self, dialog: OverlayConfigDialog):
        dialog._add_tag_to_corner("Upper Left", "PatientName", "simple")
        before = dialog.selected_lists["Upper Left"].count()
        dialog._remove_selected_tags("Upper Left", "simple")
        assert dialog.selected_lists["Upper Left"].count() == before


# ---------------------------------------------------------------------------
# Tag movement
# ---------------------------------------------------------------------------


class TestTagMovement:
    def test_move_tag_up(self, dialog: OverlayConfigDialog):
        dialog._add_tag_to_corner("Upper Left", "Alpha", "simple")
        dialog._add_tag_to_corner("Upper Left", "Beta", "simple")
        dialog._add_tag_to_corner("Upper Left", "Gamma", "simple")

        dialog.selected_lists["Upper Left"].item(1).setSelected(True)
        dialog._move_tag_up("Upper Left", "simple")

        tags = _simple_tags(dialog, "Upper Left")
        assert tags == ["Beta", "Alpha", "Gamma"]

    def test_move_tag_down(self, dialog: OverlayConfigDialog):
        dialog._add_tag_to_corner("Upper Left", "Alpha", "simple")
        dialog._add_tag_to_corner("Upper Left", "Beta", "simple")
        dialog._add_tag_to_corner("Upper Left", "Gamma", "simple")

        dialog.selected_lists["Upper Left"].item(0).setSelected(True)
        dialog._move_tag_down("Upper Left", "simple")

        tags = _simple_tags(dialog, "Upper Left")
        assert tags == ["Beta", "Alpha", "Gamma"]

    def test_move_up_at_top_does_nothing(self, dialog: OverlayConfigDialog):
        dialog._add_tag_to_corner("Upper Left", "Alpha", "simple")
        dialog._add_tag_to_corner("Upper Left", "Beta", "simple")

        dialog.selected_lists["Upper Left"].item(0).setSelected(True)
        dialog._move_tag_up("Upper Left", "simple")

        assert _simple_tags(dialog, "Upper Left") == ["Alpha", "Beta"]

    def test_move_down_at_bottom_does_nothing(self, dialog: OverlayConfigDialog):
        dialog._add_tag_to_corner("Upper Left", "Alpha", "simple")
        dialog._add_tag_to_corner("Upper Left", "Beta", "simple")

        dialog.selected_lists["Upper Left"].item(1).setSelected(True)
        dialog._move_tag_down("Upper Left", "simple")

        assert _simple_tags(dialog, "Upper Left") == ["Alpha", "Beta"]

    def test_move_no_selection_does_nothing(self, dialog: OverlayConfigDialog):
        dialog._add_tag_to_corner("Upper Left", "Alpha", "simple")
        before = _simple_tags(dialog, "Upper Left")
        dialog._move_tag_up("Upper Left", "simple")
        assert _simple_tags(dialog, "Upper Left") == before


# ---------------------------------------------------------------------------
# Simple ↔ Detailed movement
# ---------------------------------------------------------------------------


class TestSimpleDetailedMovement:
    def test_move_simple_to_detailed(self, dialog: OverlayConfigDialog):
        dialog._add_tag_to_corner("Upper Left", "PatientName", "simple")
        dialog.selected_lists["Upper Left"].item(0).setSelected(True)
        dialog._move_selected_simple_to_detailed("Upper Left")

        assert "PatientName" not in _simple_tags(dialog, "Upper Left")
        assert "PatientName" in _detailed_tags(dialog, "Upper Left")

    def test_move_detailed_to_simple(self, dialog: OverlayConfigDialog):
        dialog._add_tag_to_corner("Upper Left", "PatientName", "detailed")
        dialog.detailed_selected_lists["Upper Left"].item(0).setSelected(True)
        dialog._move_selected_detailed_to_simple("Upper Left")

        assert "PatientName" not in _detailed_tags(dialog, "Upper Left")
        assert "PatientName" in _simple_tags(dialog, "Upper Left")

    def test_move_simple_to_detailed_avoids_duplicates(self, dialog: OverlayConfigDialog):
        dialog._add_tag_to_corner("Upper Left", "PatientName", "simple")
        dialog._add_tag_to_corner("Upper Left", "PatientName", "detailed")

        dialog.selected_lists["Upper Left"].item(0).setSelected(True)
        dialog._move_selected_simple_to_detailed("Upper Left")

        assert "PatientName" not in _simple_tags(dialog, "Upper Left")
        assert _detailed_tags(dialog, "Upper Left").count("PatientName") == 1

    def test_move_no_selection_does_nothing(self, dialog: OverlayConfigDialog):
        dialog._add_tag_to_corner("Upper Left", "Alpha", "simple")
        before_simple = _simple_tags(dialog, "Upper Left")
        before_detailed = _detailed_tags(dialog, "Upper Left")
        dialog._move_selected_simple_to_detailed("Upper Left")
        assert _simple_tags(dialog, "Upper Left") == before_simple
        assert _detailed_tags(dialog, "Upper Left") == before_detailed


# ---------------------------------------------------------------------------
# Filter / search
# ---------------------------------------------------------------------------


class TestFilterTags:
    def test_filter_hides_non_matching(self, dialog: OverlayConfigDialog):
        dialog.search_edits["Upper Left"].setText("Patient")
        catalog = dialog.available_lists["Upper Left"]
        visible = [catalog.item(i).text() for i in range(catalog.count()) if not catalog.item(i).isHidden()]
        hidden = [catalog.item(i).text() for i in range(catalog.count()) if catalog.item(i).isHidden()]
        assert len(visible) > 0
        assert len(hidden) > 0

    def test_filter_case_insensitive(self, dialog: OverlayConfigDialog):
        dialog.search_edits["Upper Left"].setText("patient")
        catalog = dialog.available_lists["Upper Left"]
        visible = [catalog.item(i).text() for i in range(catalog.count()) if not catalog.item(i).isHidden()]
        assert any("Patient" in t for t in visible)

    def test_empty_filter_shows_all(self, dialog: OverlayConfigDialog):
        dialog.search_edits["Upper Left"].setText("Patient")
        dialog.search_edits["Upper Left"].setText("")
        catalog = dialog.available_lists["Upper Left"]
        visible = sum(1 for i in range(catalog.count()) if not catalog.item(i).isHidden())
        assert visible == catalog.count()


# ---------------------------------------------------------------------------
# Live update / apply / reject
# ---------------------------------------------------------------------------


class TestLiveUpdate:
    def test_live_update_emits_config_changed(self, dialog: OverlayConfigDialog):
        signals: list[bool] = []
        dialog.config_changed.connect(lambda: signals.append(True))
        dialog._on_live_update()
        assert len(signals) == 1

    def test_live_update_saves_to_config(self, dialog: OverlayConfigDialog):
        dialog._add_tag_to_corner("Upper Left", "PatientName", "simple")
        dialog._on_live_update()
        tags = dialog.config_manager.get_overlay_tags("default")
        assert "PatientName" in tags["upper_left"]

    def test_live_update_updates_memory_without_saving_to_disk(self, qapp, tmp_path: Path):
        cm = _cm_empty_counting(tmp_path)
        dialog = OverlayConfigDialog(cm)

        dialog._add_tag_to_corner("Upper Left", "UniqueLivePreviewTag", "simple")

        tags = dialog.config_manager.get_overlay_tags("default")
        assert "UniqueLivePreviewTag" in tags["upper_left"]
        assert cm.save_calls == 0

    def test_modality_switch_updates_preview_without_saving_to_disk(self, qapp, tmp_path: Path):
        cm = _cm_empty_counting(tmp_path)
        dialog = OverlayConfigDialog(cm)

        dialog.modality_combo.setCurrentText("CT")

        assert dialog.current_modality == "CT"
        assert cm.save_calls == 0


class TestApplyConfiguration:
    def test_apply_emits_config_applied(self, dialog: OverlayConfigDialog):
        signals: list[bool] = []
        dialog.config_applied.connect(lambda: signals.append(True))
        dialog._apply_configuration()
        assert len(signals) == 1

    def test_apply_saves_all_modalities(self, dialog: OverlayConfigDialog):
        dialog.modality_combo.setCurrentText("CT")
        dialog._add_tag_to_corner("Upper Left", "CTTag", "simple")
        dialog._on_live_update()

        dialog.modality_combo.setCurrentText("MR")
        dialog._add_tag_to_corner("Upper Left", "MRTag", "simple")
        dialog._on_live_update()

        dialog._apply_configuration()

        assert "CTTag" in dialog.config_manager.get_overlay_tags("CT")["upper_left"]
        assert "MRTag" in dialog.config_manager.get_overlay_tags("MR")["upper_left"]

    def test_apply_saves_detailed_tags(self, dialog: OverlayConfigDialog):
        dialog._add_tag_to_corner("Upper Left", "DetailTag", "detailed")
        dialog._on_live_update()
        dialog._apply_configuration()

        detailed = dialog.config_manager.get_overlay_tags_detailed_extra("default")
        assert "DetailTag" in detailed["upper_left"]

    def test_apply_flushes_preview_changes_to_disk_once(self, qapp, tmp_path: Path):
        cm = _cm_empty_counting(tmp_path)
        dialog = OverlayConfigDialog(cm)
        dialog._add_tag_to_corner("Upper Left", "PendingTag", "simple")
        assert cm.save_calls == 0

        dialog._apply_configuration()

        assert cm.save_calls == 1


class TestReject:
    def test_reject_restores_original_config(self, dialog: OverlayConfigDialog):
        original_tags = dialog.config_manager.get_overlay_tags("default")

        dialog._add_tag_to_corner("Upper Left", "Added", "simple")
        dialog._on_live_update()
        dialog.reject()

        assert dialog.config_manager.get_overlay_tags("default") == original_tags

    def test_reject_restores_overlay_mode(self, qapp, tmp_path: Path):
        cm = _cm_empty(tmp_path)
        cm.set_overlay_mode("detailed")
        dlg = OverlayConfigDialog(cm)

        cm.set_overlay_mode("hidden")
        dlg.reject()

        assert cm.get_overlay_mode() == "detailed"

    def test_reject_emits_config_changed(self, dialog: OverlayConfigDialog):
        signals: list[bool] = []
        dialog.config_changed.connect(lambda: signals.append(True))
        dialog.reject()
        assert len(signals) == 1


# ---------------------------------------------------------------------------
# Detail mode combo
# ---------------------------------------------------------------------------


class TestDetailModeCombo:
    def test_sync_from_config_minimal(self, dialog: OverlayConfigDialog):
        dialog.config_manager.set_overlay_mode("minimal")
        dialog._sync_detail_mode_combo_from_config()
        assert dialog.detail_mode_combo.currentData() == "minimal"

    def test_sync_from_config_detailed(self, dialog: OverlayConfigDialog):
        dialog.config_manager.set_overlay_mode("detailed")
        dialog._sync_detail_mode_combo_from_config()
        assert dialog.detail_mode_combo.currentData() == "detailed"

    def test_sync_from_config_hidden(self, dialog: OverlayConfigDialog):
        dialog.config_manager.set_overlay_mode("hidden")
        dialog._sync_detail_mode_combo_from_config()
        assert dialog.detail_mode_combo.currentData() == "hidden"

    def test_sync_invalid_mode_defaults_to_minimal(self, dialog: OverlayConfigDialog):
        dialog.config_manager.config["overlay_mode"] = "invalid"
        dialog._sync_detail_mode_combo_from_config()
        assert dialog.detail_mode_combo.currentData() == "minimal"

    def test_combo_change_persists_mode(self, dialog: OverlayConfigDialog):
        dialog.detail_mode_combo.setCurrentIndex(1)
        assert dialog.config_manager.get_overlay_mode() == "detailed"

    def test_combo_change_updates_memory_without_saving_to_disk(self, qapp, tmp_path: Path):
        cm = _cm_empty_counting(tmp_path)
        dialog = OverlayConfigDialog(cm)

        dialog.detail_mode_combo.setCurrentIndex(1)

        assert dialog.config_manager.get_overlay_mode() == "detailed"
        assert cm.save_calls == 0

    def test_combo_change_emits_config_changed(self, dialog: OverlayConfigDialog):
        signals: list[bool] = []
        dialog.config_changed.connect(lambda: signals.append(True))
        dialog.detail_mode_combo.setCurrentIndex(1)
        assert len(signals) == 1


# ---------------------------------------------------------------------------
# Move button state
# ---------------------------------------------------------------------------


class TestMoveButtonState:
    def test_move_up_disabled_at_top(self, dialog: OverlayConfigDialog):
        dialog._add_tag_to_corner("Upper Left", "Solo", "simple")
        dialog.selected_lists["Upper Left"].item(0).setSelected(True)
        dialog._update_move_buttons_state("Upper Left", "simple")
        assert not dialog.move_up_buttons["Upper Left"].isEnabled()

    def test_move_down_disabled_at_bottom(self, dialog: OverlayConfigDialog):
        dialog._add_tag_to_corner("Upper Left", "Solo", "simple")
        dialog.selected_lists["Upper Left"].item(0).setSelected(True)
        dialog._update_move_buttons_state("Upper Left", "simple")
        assert not dialog.move_down_buttons["Upper Left"].isEnabled()

    def test_move_up_enabled_when_not_at_top(self, dialog: OverlayConfigDialog):
        dialog._add_tag_to_corner("Upper Left", "Alpha", "simple")
        dialog._add_tag_to_corner("Upper Left", "Beta", "simple")
        dialog.selected_lists["Upper Left"].item(1).setSelected(True)
        dialog._update_move_buttons_state("Upper Left", "simple")
        assert dialog.move_up_buttons["Upper Left"].isEnabled()

    def test_move_down_enabled_when_not_at_bottom(self, dialog: OverlayConfigDialog):
        dialog._add_tag_to_corner("Upper Left", "Alpha", "simple")
        dialog._add_tag_to_corner("Upper Left", "Beta", "simple")
        dialog.selected_lists["Upper Left"].item(0).setSelected(True)
        dialog._update_move_buttons_state("Upper Left", "simple")
        assert dialog.move_down_buttons["Upper Left"].isEnabled()

    def test_no_selection_disables_both(self, dialog: OverlayConfigDialog):
        dialog._add_tag_to_corner("Upper Left", "Solo", "simple")
        dialog._update_move_buttons_state("Upper Left", "simple")
        assert not dialog.move_up_buttons["Upper Left"].isEnabled()
        assert not dialog.move_down_buttons["Upper Left"].isEnabled()


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_operations_on_invalid_corner_name_noop(self, dialog: OverlayConfigDialog):
        dialog._add_tag_to_corner("NonExistent", "PatientName", "simple")
        dialog._remove_selected_tags("NonExistent", "simple")
        dialog._move_tag_up("NonExistent", "simple")
        dialog._move_tag_down("NonExistent", "simple")
        dialog._filter_tags("NonExistent")

    def test_corner_ui_maps_simple_layer(self, dialog: OverlayConfigDialog):
        se, al, sl, mu, md = dialog._corner_ui_maps("simple")
        assert se is dialog.search_edits
        assert al is dialog.available_lists
        assert sl is dialog.selected_lists
        assert mu is dialog.move_up_buttons
        assert md is dialog.move_down_buttons

    def test_corner_ui_maps_detailed_layer(self, dialog: OverlayConfigDialog):
        se, al, sl, mu, md = dialog._corner_ui_maps("detailed")
        assert se is dialog.search_edits
        assert al is dialog.available_lists
        assert sl is dialog.detailed_selected_lists
        assert mu is dialog.detailed_move_up_buttons
        assert md is dialog.detailed_move_down_buttons

    def test_load_configurations_from_config_manager(self, qapp, tmp_path: Path):
        cm = _cm(tmp_path)
        cm.set_overlay_tags("CT", {
            "upper_left": ["PatientName"],
            "upper_right": ["StationName"],
            "lower_left": ["InstanceNumber"],
            "lower_right": ["SeriesNumber"],
        })
        cm.set_overlay_tags_detailed_extra("CT", _EMPTY_CORNERS)
        dlg = OverlayConfigDialog(cm, initial_modality="CT")
        assert "PatientName" in _simple_tags(dlg, "Upper Left")

    def test_double_click_adds_to_simple(self, dialog: OverlayConfigDialog):
        catalog = dialog.available_lists["Upper Left"]
        for i in range(catalog.count()):
            if catalog.item(i).text() == "PatientName":
                dialog._add_tag_to_corner("Upper Left", catalog.item(i).text(), "simple")
                break
        assert "PatientName" in _simple_tags(dialog, "Upper Left")
