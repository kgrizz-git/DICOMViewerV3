"""
Unit tests for utils.file_explorer.reveal_file_in_explorer (platform dispatch).
"""

from __future__ import annotations

import subprocess

import utils.file_explorer as file_explorer
from utils.file_explorer import reveal_file_in_explorer


def test_empty_path_returns_false():
    assert reveal_file_in_explorer("") is False


def test_macos_calls_open_dash_r(monkeypatch, tmp_path):
    monkeypatch.setattr(file_explorer.platform, "system", lambda: "Darwin")
    calls = {}

    def fake_run(args, check):
        calls["args"] = args
        assert check is True

    monkeypatch.setattr(file_explorer.subprocess, "run", fake_run)
    target = str(tmp_path / "file.dcm")
    assert reveal_file_in_explorer(target) is True
    assert calls["args"][0:2] == ["open", "-R"]


def test_windows_calls_explorer_select(monkeypatch, tmp_path):
    monkeypatch.setattr(file_explorer.platform, "system", lambda: "Windows")
    calls = {}

    def fake_run(cmd, check):
        calls["cmd"] = cmd

    monkeypatch.setattr(file_explorer.subprocess, "run", fake_run)
    target = str(tmp_path / "file.dcm")
    assert reveal_file_in_explorer(target) is True
    assert "explorer /select," in calls["cmd"]


def test_linux_falls_back_through_file_managers_to_xdg_open(monkeypatch, tmp_path):
    monkeypatch.setattr(file_explorer.platform, "system", lambda: "Linux")
    called = []

    def fake_run(args, check, timeout=None):
        called.append(args[0])
        if args[0] in ("nautilus", "dolphin", "thunar"):
            raise FileNotFoundError()

    monkeypatch.setattr(file_explorer.subprocess, "run", fake_run)
    target = str(tmp_path / "file.dcm")
    assert reveal_file_in_explorer(target) is True
    assert called == ["nautilus", "dolphin", "thunar", "xdg-open"]


def test_linux_nautilus_success_short_circuits(monkeypatch, tmp_path):
    monkeypatch.setattr(file_explorer.platform, "system", lambda: "Linux")
    called = []

    def fake_run(args, check, timeout=None):
        called.append(args[0])

    monkeypatch.setattr(file_explorer.subprocess, "run", fake_run)
    target = str(tmp_path / "file.dcm")
    assert reveal_file_in_explorer(target) is True
    assert called == ["nautilus"]


def test_linux_dolphin_success_short_circuits(monkeypatch, tmp_path):
    monkeypatch.setattr(file_explorer.platform, "system", lambda: "Linux")
    called = []

    def fake_run(args, check, timeout=None):
        called.append(args[0])
        if args[0] == "nautilus":
            raise FileNotFoundError()

    monkeypatch.setattr(file_explorer.subprocess, "run", fake_run)
    target = str(tmp_path / "file.dcm")
    assert reveal_file_in_explorer(target) is True
    assert called == ["nautilus", "dolphin"]


def test_linux_thunar_success_short_circuits(monkeypatch, tmp_path):
    monkeypatch.setattr(file_explorer.platform, "system", lambda: "Linux")
    called = []

    def fake_run(args, check, timeout=None):
        called.append(args[0])
        if args[0] in ("nautilus", "dolphin"):
            raise FileNotFoundError()

    monkeypatch.setattr(file_explorer.subprocess, "run", fake_run)
    target = str(tmp_path / "file.dcm")
    assert reveal_file_in_explorer(target) is True
    assert called == ["nautilus", "dolphin", "thunar"]


def test_linux_all_managers_fail_returns_false(monkeypatch, tmp_path):
    monkeypatch.setattr(file_explorer.platform, "system", lambda: "Linux")

    def fake_run(args, check, timeout=None):
        raise FileNotFoundError()

    monkeypatch.setattr(file_explorer.subprocess, "run", fake_run)
    target = str(tmp_path / "file.dcm")
    assert reveal_file_in_explorer(target) is False


def test_macos_called_process_error_returns_false(monkeypatch, tmp_path):
    monkeypatch.setattr(file_explorer.platform, "system", lambda: "Darwin")

    def fake_run(args, check):
        raise subprocess.CalledProcessError(1, args)

    monkeypatch.setattr(file_explorer.subprocess, "run", fake_run)
    target = str(tmp_path / "file.dcm")
    assert reveal_file_in_explorer(target) is False


def test_linux_skips_xdg_open_when_parent_dir_is_empty(monkeypatch):
    monkeypatch.setattr(file_explorer.platform, "system", lambda: "Linux")
    monkeypatch.setattr(file_explorer.os.path, "abspath", lambda p: "onlyfile")
    monkeypatch.setattr(file_explorer.os.path, "dirname", lambda p: "")
    called = []

    def fake_run(args, check, timeout=None):
        called.append(args[0])
        raise FileNotFoundError()

    monkeypatch.setattr(file_explorer.subprocess, "run", fake_run)
    assert reveal_file_in_explorer("onlyfile") is False
    assert "xdg-open" not in called


def test_windows_file_not_found_returns_false(monkeypatch, tmp_path):
    monkeypatch.setattr(file_explorer.platform, "system", lambda: "Windows")

    def fake_run(cmd, check):
        raise FileNotFoundError()

    monkeypatch.setattr(file_explorer.subprocess, "run", fake_run)
    target = str(tmp_path / "file.dcm")
    assert reveal_file_in_explorer(target) is False


def test_macos_generic_exception_returns_false(monkeypatch, tmp_path):
    monkeypatch.setattr(file_explorer.platform, "system", lambda: "Darwin")

    def fake_run(args, check):
        raise RuntimeError("boom")

    monkeypatch.setattr(file_explorer.subprocess, "run", fake_run)
    target = str(tmp_path / "file.dcm")
    assert reveal_file_in_explorer(target) is False


def test_invalid_path_returns_false(monkeypatch):
    monkeypatch.setattr(
        file_explorer.os.path, "abspath", lambda p: (_ for _ in ()).throw(OSError())
    )
    assert reveal_file_in_explorer("whatever") is False
