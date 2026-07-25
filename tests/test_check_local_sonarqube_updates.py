from __future__ import annotations

import importlib.util
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


def test_remote_image_id_reads_docker_hub_tag_digest(monkeypatch):
    module = _load_module()

    class Response:
        def __init__(self, body: bytes, headers: dict[str, str] | None = None):
            self._body = body
            self.headers = headers or {}

        def read(self) -> bytes:
            return self._body

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

    responses = iter(
        [
            Response(b'{"token": "public-token"}'),
            Response(b"", {"Docker-Content-Digest": "sha256:tag"}),
        ]
    )
    monkeypatch.setattr(module, "urlopen", lambda *_args, **_kwargs: next(responses))

    assert module.remote_image_id() == "sha256:tag"


def test_version_key_compares_numeric_scanner_versions():
    module = _load_module()

    assert module.version_key("8.1.0.6389") < module.version_key("8.2.0.7000")
    assert module.version_key("8.1.beta") is None
