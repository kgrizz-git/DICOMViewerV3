from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import ModuleType


def _load_module() -> ModuleType:
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "check_basedpyright_errors.py"
    spec = importlib.util.spec_from_file_location("check_basedpyright_errors", script_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_basedpyright_gate_uses_fixed_command_and_repo_cwd(monkeypatch):
    module = _load_module()
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append((cmd, kwargs))
        return subprocess.CompletedProcess(
            cmd,
            1,
            stdout=json.dumps({"summary": {"errorCount": 0, "warningCount": 3}}),
            stderr="",
        )

    monkeypatch.setattr(sys, "argv", ["check_basedpyright_errors.py"])
    monkeypatch.setattr(module.subprocess, "run", fake_run)

    assert module.main() == 0
    assert len(calls) == 1

    cmd, kwargs = calls[0]
    assert cmd == [
        sys.executable,
        "-m",
        "basedpyright",
        "--outputjson",
        "src",
        "scripts",
    ]
    assert kwargs["cwd"] == Path(module.__file__).resolve().parent.parent


def test_basedpyright_gate_rejects_caller_supplied_paths(monkeypatch):
    module = _load_module()

    def fail_if_called(*_args, **_kwargs):
        raise AssertionError("subprocess should not run when unexpected args are supplied")

    monkeypatch.setattr(sys, "argv", ["check_basedpyright_errors.py", "/tmp/evil"])
    monkeypatch.setattr(module.subprocess, "run", fail_if_called)

    try:
        module.main()
    except SystemExit as exc:
        assert exc.code == 2
    else:
        raise AssertionError("argparse should reject caller-supplied paths")
