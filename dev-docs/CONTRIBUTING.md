# Contributing to DICOM Viewer V3

This guide is for **human contributors**: workflows, hooks, CI expectations, and release hygiene. **AI agents and Cursor** should continue to follow **[`AGENTS.md`](../AGENTS.md)** for venv commands, the `src/` module map, signal-wiring rules, and product-oriented display notes.

## Development setup

- **[`DEVELOPER_SETUP.md`](DEVELOPER_SETUP.md)** — environment, hooks, troubleshooting.
- **[`tests/README.md`](../tests/README.md)** — running the test suite.
- **[`README.md`](../README.md)** — clone, install, run from source.

Activate a virtual environment before installing or running (see **`AGENTS.md`**).

## Refactor backups and Git hooks

- See **`.cursor/rules`** and project user rules. **Before major refactors only**, copy files to **`backups/`** with an ISO-like date in the name; do not proceed until the backup exists or the user has waived it. See **`scripts/git-hook-prune-backups.py`** for how **`backups/`** is pruned.
- **Local Git hooks** (details in **`DEVELOPER_SETUP.md`**): with **`pre-commit`** installed, the hook prunes **`backups/`** on **`main`** and **`WIP`** by intent (`scripts/git-hook-prune-backups.py --days 3 --max-commits 10`). Removals are staged with **`git add -u -- backups`**; the **`main`** **pre-commit** hook runs a **light** security check (debug flags + **detect-secrets** on **staged** files via `scripts/run_security_scan.py --pre-commit`). A **full** scan (`--all`) runs on **pre-push** to **`main`**. Set **`DICOMVIEWER_PRECOMMIT_FULL_SECURITY_SCAN=1`** to force the full suite on pre-commit.

## Security tooling and optional dev dependencies

- **`pip install -r requirements-dev.txt`** — adds local Python security scanners (semgrep, detect-secrets).
- **TruffleHog v3:** install separately via `powershell -ExecutionPolicy Bypass -File .\scripts\install-trufflehog-v3.ps1 -AddToUserPath` so local scans align with CI’s TruffleHog v3 action/binary line.
- **Debug flags:** do not merge with **`DEBUG_*`** set to **`True`** in `src/utils/debug_flags.py` (CI fails on that).

## Versioning and changelog

- Application version lives in **`src/version.py`** (`__version__`). Follow **[`info/SEMANTIC_VERSIONING_GUIDE.md`](info/SEMANTIC_VERSIONING_GUIDE.md)** and **[`RELEASING.md`](RELEASING.md)** when cutting releases (changelog, tags, **Current version** line in **`CHANGELOG.md`**).

## Pylinac pin and QA documentation

- **`requirements.txt`** pins an exact **`pylinac`** version; that pin is the only upstream release **verified** with the viewer’s ACR CT / MRI integration. When **bumping** the pin, re-verify and update **`info/PYLINAC_INTEGRATION_OVERVIEW.md`** (**Verified pylinac package version**).
- Default Stage‑1 runs use **`src/qa/pylinac_extent_subclasses.py`** (**`ACRCTForViewer`** / **`ACRMRILargeForViewer`**) so origin indices may be **0 … N−1** (stock pylinac is stricter); JSON **`pylinac_analysis_profile`** records **`relaxed_image_extent`**. Users may enable **Vanilla pylinac** in the ACR CT/MRI options dialogs (persisted in **`qa_pylinac_config`**) to run stock **`ACRCT`** / **`ACRMRILarge`** instead.

## Third-party license inventory

Maintain a rolling checklist of bundled Python packages, vendored binaries (e.g. FFmpeg), and **`resources/fonts/`** in **[`info/BUNDLED_PACKAGES_AND_FONTS_LICENSES.md`](info/BUNDLED_PACKAGES_AND_FONTS_LICENSES.md)** when pins, PyInstaller `datas`, or fonts change.

**Cine export:** **`requirements.txt`** pins **`imageio`** + **`imageio-ffmpeg`** (vendored FFmpeg; LGPL/GPL-style stack). Frozen/redistributed builds must meet FFmpeg license obligations; see **`AGENTS.md`** for the short product note and this inventory doc for packaging.

## CI and GitHub Actions

- Workflows live under **`.github/workflows/`**. Use current **major tags** for first-party actions (`actions/checkout@v6`, `actions/upload-artifact@v7`, `github/codeql-action/*@v4`) so Dependabot can propose updates. Pin **third-party** actions to release tags when reproducibility matters (e.g. `trufflesecurity/trufflehog@v3.x.x` plus matching `version:` for the scanner image).
- **Storage / billing:** artifact and cache usage accrues in **GB-hours**; see **`info/GITHUB_ACTIONS_STORAGE_AND_BILLING.md`**. The **Build Executables** workflow uploads **`dist/`** (and the Linux AppImage) only — **not** PyInstaller’s **`build/`** folder. **`actions-cache-prune.yml`** (weekly + manual) prunes stale Actions caches on non-protected refs while keeping the default branch, **`develop`**, and optional extra refs.
- **macOS PySide6 submodule excludes** are **off** by default; set **`PYINSTALLER_MACOS_SLIM=1`** locally or enable the optional **workflow_dispatch** slim job — see **`info/BUILDING_EXECUTABLES.md`** / **`info/PYINSTALLER_BUNDLE_SIZE_AND_BASELINES.md`**. **`tests/test_pyinstaller_exclude_audit.py`** guards excluded module names against **`src/`** and **`tests/`** imports.
- **`actions/upload-artifact` v6+** and related actions may require **self-hosted runners ≥ 2.327.1** (Node 24); GitHub-hosted **`ubuntu-latest`** satisfies this.
- If **`.github/dependabot.yml`** lists **`labels:`**, those labels must exist on the repo (e.g. `dependencies`, `github-actions`) or Dependabot will warn on PRs.

## User documentation links

After editing files under **`user-docs/`** (or **`dev-docs/README.md`**), run:

```bash
python scripts/check_user_docs_links.py
```

or:

```bash
python -m pytest tests/test_user_docs_links.py -q
```

CI runs **`.github/workflows/user-docs-links.yml`** on **`main`** / **`develop`**.

## Module layout and agent orchestration

- **`AGENTS.md`** at the repo root documents the **`src/`** tree, controller roles, **`_connect_signals`** rules, multi-agent **`Task`** chaining, and in-app display options for tooling context.
- Multi-agent details: **`.cursor/rules/orchestration-auto-chain.mdc`**, **`.claude/skills/team-orchestration-delegation/SKILL.md`**, **`.claude/agents/orchestrator.md`**, **`orchestration/RUN_PACKET_TEMPLATE.md`**.
