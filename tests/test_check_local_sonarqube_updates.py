from __future__ import annotations

import importlib.util
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import ModuleType


def _load_module() -> ModuleType:
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "check_local_sonarqube_updates.py"
    spec = importlib.util.spec_from_file_location("check_local_sonarqube_updates", script_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_update_check_records_only_a_due_manifest_comparison(tmp_path, monkeypatch, capsys):
    module = _load_module()
    now = datetime(2026, 7, 24, tzinfo=UTC)
    monkeypatch.setattr(module, "local_image_details", lambda: ("sha256:local", "arm64", "linux"))
    monkeypatch.setattr(module, "remote_image_id", lambda *_args: "sha256:remote")
    monkeypatch.setattr(module, "native_scanner_version", lambda: "8.1.0.6389")
    monkeypatch.setattr(module, "latest_scanner_version", lambda: "8.1.0.6389")

    assert module.check_for_update(tmp_path, now=now) == 0
    assert "newer" in capsys.readouterr().out
    state = module.read_state(tmp_path)
    assert state is not None
    assert state["update_available"] is True
    assert state["local_image_id"] == "sha256:local"
    assert state["scanner_update_available"] is False

    assert module.check_for_update(tmp_path, now=now + timedelta(days=6)) == 0
    assert "not due" in capsys.readouterr().out


def test_remote_image_id_selects_the_local_platform(monkeypatch):
    module = _load_module()
    payload = [
        {"Descriptor": {"platform": {"architecture": "amd64", "os": "linux"}}, "OCIManifest": {"config": {"digest": "sha256:amd"}}},
        {"Descriptor": {"platform": {"architecture": "arm64", "os": "linux"}}, "OCIManifest": {"config": {"digest": "sha256:arm"}}},
    ]
    monkeypatch.setattr(
        module,
        "run_docker",
        lambda _command: subprocess.CompletedProcess([], 0, module.json.dumps(payload), ""),
    )

    assert module.remote_image_id("arm64", "linux") == "sha256:arm"


def test_version_key_compares_numeric_scanner_versions():
    module = _load_module()

    assert module.version_key("8.1.0.6389") < module.version_key("8.2.0.7000")
    assert module.version_key("8.1.beta") is None
