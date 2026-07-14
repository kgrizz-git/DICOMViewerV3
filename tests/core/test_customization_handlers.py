"""Unit tests for core.customization_handlers."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import core.customization_handlers as customization_handlers


def _make_config(**overrides) -> SimpleNamespace:
    defaults = {
        "get_last_export_path": MagicMock(return_value="/missing"),
        "set_last_export_path": MagicMock(),
        "export_customizations": MagicMock(return_value=True),
        "get_last_path": MagicMock(return_value="/missing"),
        "import_customizations": MagicMock(return_value=True),
        "get_tag_export_presets": MagicMock(return_value={"preset": {}}),
        "export_tag_export_presets": MagicMock(return_value=True),
        "import_tag_export_presets": MagicMock(return_value={"imported": 1, "skipped_conflicts": 0}),
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


class TestCustomizationHandlers:
    def test_export_customizations_success_and_default_path_fallback(self, monkeypatch) -> None:
        config = _make_config()
        handler = customization_handlers.CustomizationHandlers(config, main_window=object())
        info = MagicMock()
        monkeypatch.setattr(customization_handlers.os.path, "exists", MagicMock(return_value=False))
        monkeypatch.setattr(customization_handlers.os.path, "isfile", MagicMock(return_value=False))
        monkeypatch.setattr(customization_handlers.os, "getcwd", MagicMock(return_value="/cwd"))
        monkeypatch.setattr(customization_handlers.QFileDialog, "getSaveFileName", MagicMock(return_value=("/out/file", "")))
        monkeypatch.setattr(customization_handlers.QMessageBox, "information", info)

        handler.export_customizations()

        config.export_customizations.assert_called_once_with("/out/file.json")
        config.set_last_export_path.assert_called_once_with("/out")
        info.assert_called_once()

    def test_export_customizations_failure_and_cancel(self, monkeypatch) -> None:
        config = _make_config(export_customizations=MagicMock(return_value=False), get_last_export_path=MagicMock(return_value="/tmp/file.json"))
        handler = customization_handlers.CustomizationHandlers(config, main_window=object())
        warn = MagicMock()
        monkeypatch.setattr(customization_handlers.os.path, "exists", MagicMock(return_value=True))
        monkeypatch.setattr(customization_handlers.os.path, "isfile", MagicMock(return_value=True))
        monkeypatch.setattr(customization_handlers.QFileDialog, "getSaveFileName", MagicMock(side_effect=[("", ""), ("/tmp/out.json", "")]))
        monkeypatch.setattr(customization_handlers.QMessageBox, "warning", warn)

        handler.export_customizations()
        config.export_customizations.assert_not_called()

        handler.export_customizations()
        config.export_customizations.assert_called_once_with("/tmp/out.json")
        warn.assert_called_once()

    def test_import_customizations_success_failure_and_cancel(self, monkeypatch) -> None:
        after_import = MagicMock()
        config = _make_config(import_customizations=MagicMock(side_effect=[True, False]))
        handler = customization_handlers.CustomizationHandlers(config, main_window=object(), after_import_customizations=after_import)
        info = MagicMock()
        warn = MagicMock()
        monkeypatch.setattr(customization_handlers.os.path, "exists", MagicMock(return_value=False))
        monkeypatch.setattr(customization_handlers.os.path, "isfile", MagicMock(return_value=False))
        monkeypatch.setattr(customization_handlers.os, "getcwd", MagicMock(return_value="/cwd"))
        monkeypatch.setattr(
            customization_handlers.QFileDialog,
            "getOpenFileName",
            MagicMock(side_effect=[("", ""), ("/in/custom.json", ""), ("/in/bad.json", "")]),
        )
        monkeypatch.setattr(customization_handlers.QMessageBox, "information", info)
        monkeypatch.setattr(customization_handlers.QMessageBox, "warning", warn)

        handler.import_customizations()
        config.import_customizations.assert_not_called()

        handler.import_customizations()
        after_import.assert_called_once_with()
        info.assert_called_once()

        handler.import_customizations()
        warn.assert_called_once()

    def test_export_tag_presets_handles_empty_success_and_failure(self, monkeypatch) -> None:
        no_presets = _make_config(get_tag_export_presets=MagicMock(return_value={}))
        handler = customization_handlers.CustomizationHandlers(no_presets, main_window=object())
        info = MagicMock()
        monkeypatch.setattr(customization_handlers.QMessageBox, "information", info)

        handler.export_tag_presets()
        info.assert_called_once()

        config = _make_config(export_tag_export_presets=MagicMock(side_effect=[True, False]))
        handler = customization_handlers.CustomizationHandlers(config, main_window=object())
        warn = MagicMock()
        monkeypatch.setattr(customization_handlers.os.path, "exists", MagicMock(return_value=False))
        monkeypatch.setattr(customization_handlers.os.path, "isfile", MagicMock(return_value=False))
        monkeypatch.setattr(customization_handlers.os, "getcwd", MagicMock(return_value="/cwd"))
        monkeypatch.setattr(
            customization_handlers.QFileDialog,
            "getSaveFileName",
            MagicMock(side_effect=[("/out/presets", ""), ("/out/presets2.json", "")]),
        )
        monkeypatch.setattr(customization_handlers.QMessageBox, "warning", warn)

        handler.export_tag_presets()
        config.export_tag_export_presets.assert_any_call("/out/presets.json")

        handler.export_tag_presets()
        warn.assert_called_once()

    def test_import_tag_presets_handles_none_empty_complete_and_callback(self, monkeypatch) -> None:
        callback = MagicMock()
        config = _make_config(
            import_tag_export_presets=MagicMock(
                side_effect=[
                    None,
                    {"imported": 0, "skipped_conflicts": 0},
                    {"imported": 2, "skipped_conflicts": 1},
                ]
            )
        )
        handler = customization_handlers.CustomizationHandlers(
            config,
            main_window=object(),
            on_tag_presets_imported=callback,
        )
        critical = MagicMock()
        info = MagicMock()
        monkeypatch.setattr(customization_handlers.os.path, "exists", MagicMock(return_value=False))
        monkeypatch.setattr(customization_handlers.os.path, "isfile", MagicMock(return_value=False))
        monkeypatch.setattr(customization_handlers.os, "getcwd", MagicMock(return_value="/cwd"))
        monkeypatch.setattr(
            customization_handlers.QFileDialog,
            "getOpenFileName",
            MagicMock(side_effect=[("/in/a.json", ""), ("/in/b.json", ""), ("/in/c.json", "")]),
        )
        monkeypatch.setattr(customization_handlers.QMessageBox, "critical", critical)
        monkeypatch.setattr(customization_handlers.QMessageBox, "information", info)

        handler.import_tag_presets()
        critical.assert_called_once()
        callback.assert_not_called()

        handler.import_tag_presets()
        handler.import_tag_presets()

        assert info.call_count == 2
        assert callback.call_count == 2
