# Developer setup and troubleshooting

**Last updated:** 2026-07-18

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

- A project clone on a local drive sometimes avoids venv or pip quirks seen with shared-folder paths.

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

Install repo-managed security hooks (recommended, one-time per clone):

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\install-local-git-hooks.ps1
```

macOS/Linux equivalent:

```bash
bash ./scripts/setup-hooks.sh
```

This sets `core.hooksPath` to `.githooks/`, so Git runs the `pre-commit`, `commit-msg`, and `pre-push` hooks directly from the
version-controlled directory. No file copying — edits to `.githooks/` take effect
immediately without re-running the installer.

### Optional direnv setup

The tracked `.envrc` loads an ignored `.env` file and activates an existing
`.venv` or `venv`. It intentionally performs no package installation or network
access. It watches `requirements.txt` and `requirements-dev.txt` and prints a
short reminder when the active venv has not been explicitly synchronized.

```bash
cp .env.example .env
# Edit only .env and add the local SONAR_TOKEN.
direnv allow
python scripts/sync_dev_environment.py
```

The sync command is the explicit network/install step. It installs
`requirements-dev.txt` and writes a content-hash stamp inside the ignored venv.
After either requirements file changes, direnv reloads and reminds contributors
to run the command again. A requirements change does **not** require another
`direnv allow`; approval is required only when `.envrc` itself changes.

The `.env`, `.direnv/`, Sonar scanner work/cache directories, and local analysis
records are ignored and blocked from staging even with `git add -f`. Run
`direnv deny` to revoke approval for this checkout. Contributors without direnv
can continue exporting variables and activating the venv manually.

## Optional local SonarQube Community Build analysis

This repository supports opt-in analysis against a local SonarQube Community
Build instance. SonarQube Cloud and other external analysis uploads are
disabled by policy. The local scan is intentionally **not** a Git hook: it can
take time, and `--with-coverage` runs the full pytest suite first.

1. Start the existing local SonarQube Community Build service and confirm its UI
   is reachable at `http://localhost:9000` (or set `SONAR_HOST_URL` to another
   loopback URL such as `http://127.0.0.1:9000`). Remote hosts are rejected so
   the local analysis token cannot be sent off-machine.
2. In its UI, create a user or project analysis token at **User → My Account →
   Security**. Do not put the token in a tracked file. Copy `.env.example` to
   ignored `.env` and populate `SONAR_TOKEN`. Both the runner and reporter load
   simple `KEY=VALUE` entries from that file automatically; an explicitly
   exported variable takes precedence. With direnv, also run `direnv allow`.
3. Activate this project’s venv and run:

   ```bash
   python scripts/run_local_sonarqube.py
   ```

   PowerShell equivalent:

   ```powershell
   python scripts/run_local_sonarqube.py
   ```

The runner uses an installed `sonar-scanner` when available; otherwise it runs
the official scanner image through Docker. It checks `/api/system/status`, submits
the analysis using [`tools/sonarqube/sonar-project.properties`](../tools/sonarqube/sonar-project.properties),
and records the last successful scanner submission in the ignored
`.sonar-local/last-analysis.json` file. Check that record without contacting the
server with:

```bash
python scripts/run_local_sonarqube.py --status
```

To include test coverage, use `python scripts/run_local_sonarqube.py
--with-coverage`; this deliberately runs the full suite first. When the Docker
scanner cannot reach a service published on host `localhost`, the script maps it
to `host.docker.internal`. `SONAR_DOCKER_HOST_URL` may only name that Docker host
gateway; named Docker network services are deliberately unsupported because the
local-only policy must not permit an arbitrary token destination.

After a successful analysis, report priority findings that belong to this
repository's exact component key. The reporter uses the same ignored `.env`
file automatically:

```bash
python scripts/report_local_sonarqube_issues.py --fail-on-findings \
  --expected-revision "$(git rev-parse HEAD)" \
  --output tmp/sonarqube-priority-findings.md
```

The reporter queries `componentKeys=dicom-viewer-v3` for three scoped tiers:

| Tier | SonarQube filter | Typical use |
|------|------------------|-------------|
| **BLOCKER** | All BLOCKER issues | Must-fix before release |
| **CRITICAL** | All CRITICAL issues (any type) | High-severity bugs, smells, and vulnerabilities |
| **MAJOR** | All MAJOR issues (any type) | Code-smell backlog triage (`TO_DO.md` tracks deferred MAJOR cleanup) |

It verifies every returned component has the `dicom-viewer-v3` prefix and
rejects a mixed-project response. `--fail-on-findings` exits **1** when any
scoped issue is present (all three tiers). The optional Markdown report is
restricted to ignored `tmp/`; neither the token nor SonarQube issue messages are
written to it. On PowerShell, pass the `git rev-parse HEAD` result as the
`--expected-revision` value, or omit that optional assertion when only reading
the report.

For a release or remediation branch, pair the reporter with a fresh analysis of
the same revision:

```bash
python scripts/run_local_sonarqube.py --with-coverage
python scripts/report_local_sonarqube_issues.py \
  --expected-revision "$(git rev-parse HEAD)" \
  --output tmp/sonarqube-priority-findings.md
```

Recommended cadence: run `python scripts/run_local_sonarqube.py
--with-coverage` at least every 30 days, before a release, and after a large
dependency or security-sensitive change. A push that updates `main` checks the
ignored timestamp only after the blocking privacy, PHI, secret, type, test, and
full local scanner gates pass. Missing or stale analysis prints a reminder but
does not block contributors who do not have the local service or token. Check
freshness without contacting SonarQube:

```bash
python scripts/run_local_sonarqube.py --check-freshness-days 30
```

Do not add a root `sonar-project.properties` or cloud-analysis configuration.
The separate local settings file is passed only by this runner.

**Privacy / logging gate:** `scripts/git-hook-security-gate.py` invokes **`scripts/git_hook_privacy_checks.py`** on every **pre-commit** and **pre-push** invocation (before branch-gated scans). It reads the **staged** index for **`src/*.py`**: forbids real **`traceback.print_exc(`** calls (matches inside **`tokenize`** **STRING**/**COMMENT** tokens—e.g. docstrings—are skipped); on **git-added** lines only, applies heuristics for patient tag names in logs, path-like literals in **`logger.*`** calls, raw-exception patterns in **`QMessageBox`**-style calls, and **`logger.*`** with non-literal messages without **`sanitize_message`** / **`sanitize_exception`**. Set **`DICOMVIEWER_PRIVACY_HOOK=warn`** to print findings without blocking. From repo root: `.venv\Scripts\python.exe scripts\git_hook_privacy_checks.py`.

**Static typing gate:** the `pre-push` hook runs `scripts/check_basedpyright_errors.py`, matching the GitHub **Pyright** workflow: **0 basedpyright errors** are required across `src/` and `scripts/`, while the existing warning baseline is reported but does not block pushes.

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
