# Developer setup and troubleshooting

Use this page with [CONTRIBUTING.md](CONTRIBUTING.md) (hooks, CI, releases), [AGENTS.md](../AGENTS.md) (venv, module layout, agents), and [tests/README.md](../tests/README.md).

## Common issues

### "Module not found" when running the app or tests

- Install dependencies: `pip install -r requirements.txt` (from project root, venv activated).
- Run from the **project root**, or use absolute paths to `src/main.py`.
- For tests, ensure `PYTHONPATH` includes `src` (see `tests/run_tests.py`).

### Wrong working directory

- **"No such file or directory"** for `src/main.py`: `cd` to the folder that contains `requirements.txt` and `src/`.

### Python version and native wheels (Windows)

- **Python 3.10+** is required for the full `requirements.txt` stack (including **pylinac**); on Windows **3.11 or 3.12** is recommended so packages like **pyjpegls** install from pre-built wheels.
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

**Privacy / logging gate:** `scripts/git-hook-security-gate.py` invokes **`scripts/git_hook_privacy_checks.py`** on every **pre-commit** and **pre-push** invocation (before branch-gated scans). It reads the **staged** index for **`src/*.py`**: forbids real **`traceback.print_exc(`** calls (matches inside **`tokenize`** **STRING**/**COMMENT** tokens—e.g. docstrings—are skipped); on **git-added** lines only, applies heuristics for patient tag names in logs, path-like literals in **`logger.*`** calls, raw-exception patterns in **`QMessageBox`**-style calls, and **`logger.*`** with non-literal messages without **`sanitize_message`** / **`sanitize_exception`**. Set **`DICOMVIEWER_PRIVACY_HOOK=warn`** to print findings without blocking. From repo root: `.venv\Scripts\python.exe scripts\git_hook_privacy_checks.py`.

The `pre-commit` hook also prunes **`backups/`** when the current branch is
**`main`** or **`WIP`**. **Intent age** is **not** plain filesystem mtime for
**tracked** files (checkouts refresh mtime). **Tracked:** a file is removed if
**more than 10 commits** have occurred since the **latest commit that touched
that path**, **or** if **more than 10 commits** landed on the branch in the last
**3** days **and** that touch’s committer time is **strictly older than 3 days**
(quiet branches use the commit-depth rule only). **Untracked:** newest embedded
**`YYYYMMDD`** and **mtime** (the **older** of the two) must be **strictly older
than 3 days**. See `scripts/git-hook-prune-backups.py` (`--days`, `--max-commits`,
optional `--velocity-commits`). **Shallow clones** may skew Git counts and times.
The hook then runs **`git add -u -- backups`** so tracked deletions are staged
for the same commit. Other branches are unchanged. Failures are non-fatal.
Preview: `python scripts/git-hook-prune-backups.py --days 3 --max-commits 10 --dry-run`
(repo root, venv on).
