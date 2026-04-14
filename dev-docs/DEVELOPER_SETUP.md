# Developer setup and troubleshooting

Use this page with [AGENTS.md](../AGENTS.md) (venv, module layout) and [tests/README.md](../tests/README.md).

## Common issues

### "Module not found" when running the app or tests

- Install dependencies: `pip install -r requirements.txt` (from project root, venv activated).
- Run from the **project root**, or use absolute paths to `src/main.py`.
- For tests, ensure `PYTHONPATH` includes `src` (see `tests/run_tests.py`).

### Wrong working directory

- **"No such file or directory"** for `src/main.py`: `cd` to the folder that contains `requirements.txt` and `src/`.

### Python version and native wheels (Windows)

- **Python 3.9+** is required; on Windows **3.11 or 3.12** is recommended so packages like **pyjpegls** install from pre-built wheels.
- If **`pip install` fails building pyjpegls** with *Microsoft Visual C++ 14.0 or greater is required*, either switch the venv to **Python 3.11/3.12**, or install [Visual Studio Build Tools](https://visualstudio.microsoft.com/visual-cpp-build-tools/) with the C++ workload.

### Parallels / network home paths (Windows guests)

- A project clone under a local drive such as **`C:\`** sometimes avoids venv or pip quirks seen with `\\Mac\Home\...`-style paths.

## Optional contributor tooling

Security scanners and related CLI tools are **not** in `requirements.txt`. For parity with CI docs:

```bash
pip install -r requirements-dev.txt
```

Optional dependency audit tool:

```bash
python -m pip install pip-audit
```

TruffleHog v3 (Windows):

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\install-trufflehog-v3.ps1 -AddToUserPath
```

See [SECURITY_TOOLS_CLI_GUIDE.md](SECURITY_TOOLS_CLI_GUIDE.md).

Quick local run (PowerShell):

```powershell
.\scripts\scan-security.ps1 -All -Report
```

Install repo-managed security hooks (recommended):

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\install-local-git-hooks.ps1
```

macOS/Linux equivalent:

```bash
bash ./scripts/setup-hooks.sh
```

After updating hook scripts under `.githooks/`, run the installer again so your
local `.git/hooks/` copies pick up the change.

The `pre-commit` hook also prunes **`backups/`** when the current branch is
**`main`** or **`WIP`**, removing paths whose **backup intent age** is **strictly
older than 3 days** (local time). **Intent age** is **not** plain filesystem mtime
(checkouts refresh mtime). **Tracked** files use the **committer time of the
latest Git commit** that touched each path (see `scripts/git-hook-prune-backups.py`);
**untracked** files use the newest embedded **`YYYYMMDD`** in the path and **mtime**
(whichever is newer). **Shallow clones** may make Git-derived ages inaccurate. The
hook then runs **`git add -u -- backups`** so tracked deletions are staged for the
same commit. Other branches are unchanged. Failures are non-fatal. Preview:
`python scripts/git-hook-prune-backups.py --days 3 --dry-run` (repo root, venv on).
