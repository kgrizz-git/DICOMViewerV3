from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from scripts import gitleaks_privacy_scan as gitleaks
from scripts import privacy_remote_preflight as preflight

ROOT = Path(__file__).resolve().parent.parent


def _repo(tmp_path: Path) -> Path:
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "Synthetic Author"], cwd=tmp_path, check=True)
    subprocess.run(
        ["git", "config", "user.email", "1+synthetic@users.noreply.github.com"],
        cwd=tmp_path,
        check=True,
    )
    (tmp_path / "README.md").write_text("synthetic", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-qm", "Initial synthetic snapshot"], cwd=tmp_path, check=True)
    return tmp_path


def test_preflight_is_read_only_and_redacts_values(tmp_path, capsys):
    repo = _repo(tmp_path)
    marker = "SentinelAlpha9876"
    subprocess.run(["git", "branch", f"patient-{marker}-record"], cwd=repo, check=True)
    subprocess.run(
        ["git", "remote", "add", "origin", f"https://{marker}:credential@example.test/repo.git"],
        cwd=repo,
        check=True,
    )
    before = subprocess.run(["git", "show-ref"], cwd=repo, capture_output=True, text=True, check=True).stdout
    report = preflight.audit_repository(repo, run_gitleaks=False)
    preflight._print_text(report)
    output = capsys.readouterr().out
    after = subprocess.run(["git", "show-ref"], cwd=repo, capture_output=True, text=True, check=True).stdout
    assert report.risk_count > 0
    assert marker not in output
    assert before == after


def test_gitleaks_wrapper_never_relays_tool_output(tmp_path):
    repo = _repo(tmp_path)
    fake = tmp_path / "fake-gitleaks"
    fake.write_text(
        "#!/usr/bin/env python3\n"
        "import json,sys\n"
        "p=next(x.split('=',1)[1] for x in sys.argv if x.startswith('--report-path='))\n"
        "json.dump([{'Fingerprint':'abc:file.txt:synthetic-rule:1','File':'file.txt','RuleID':'synthetic-rule','Secret':'SentinelSecret'}],open(p,'w'))\n"
        "print('SentinelSecret')\n"
        "raise SystemExit(7)\n",
        encoding="utf-8",
    )
    fake.chmod(0o700)
    code, message = gitleaks.run_scan(repo, "staged", executable=str(fake))
    assert code == 1
    assert "SentinelSecret" not in message
    assert "synthetic-rule" in message


@pytest.mark.parametrize(
    "wrapper", ["check_gitleaks_staged.py", "check_gitleaks_history.py"]
)
def test_gitleaks_wrappers_execute_directly(wrapper):
    completed = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / wrapper), "--help"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0
    assert "usage:" in completed.stdout.lower()
