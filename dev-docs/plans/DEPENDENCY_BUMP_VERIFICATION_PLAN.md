# Dependency bump — post-change verification

**Purpose:** After changing pinned or security-sensitive dependencies (for example **`pylinac`** in `requirements.txt`, **`actions/github-script`** in `.github/workflows/`, or other packages that affect QA, DICOM I/O, or CI), run the checks below so install, tests, CI, and docs stay aligned.

**Tracked in:** [To-Do — Maintenance](../TO_DO.md#maintenance) (checklist item *Post–dependency bump verification*).

---

## How to use this plan (required protocol)

1. **Perform the bump** (separate commit or PR is fine): update pins, lockfiles if any, workflow `uses:` tags, and any version callouts in user/dev docs when you intentionally change the shipped pin.
2. **Work through the sections below in order** (or note in the plan why a section is N/A, e.g. “no workflow changes this round”).
3. **Edit this file as you go:** turn each `[ ]` into `[x]` only after that step is **fully** done and you are satisfied with the outcome.
4. **When every applicable checkbox in this document is `[x]`** (or explicitly N/A with a one-line reason next to the item):
   - Open [`dev-docs/TO_DO.md`](../TO_DO.md).
   - Find the Maintenance item **Post–dependency bump verification** and set it to **`[x]`**.
   - In the **Changes** line under **Last updated** at the top of `TO_DO.md`, add a short dated note (e.g. `2026-04-21 — dependency bump verification plan completed for <what changed>.`).
5. If verification **fails** mid-way, leave incomplete items as `[ ]`, **do not** check off the TO_DO item, and file a bug or follow-up task with what broke.

---

## A. Environment and install sanity

- [ ] Activate the project **virtual environment** (see `AGENTS.md` / `.claude/skills/python-venv-dependencies`).
- [ ] Confirm **Python version** meets new minimums (e.g. **pylinac ≥ 3.43.x** requires **Python ≥ 3.10** per PyPI `requires_python`).
- [ ] **`python -m pip install -U pip`** (optional but helps reproducible resolution), then **`python -m pip install -r requirements.txt`** (or your documented install path).
- [ ] **`python -m pip check`** — no broken dependencies reported.
- [ ] **Cold import smoke:** `python -c "import pylinac; print(pylinac.__version__)"` (skip only if pylinac was not bumped).
- [ ] **Application import smoke (optional):** from project root with `PYTHONPATH=src` (see `tests/README.md`), e.g. `python -c "from qa.pylinac_extent_subclasses import ACRCTForViewer"` (skip if pylinac / `src/qa` unchanged).

---

## B. Automated tests

- [ ] From the activated venv, run the **full suite:** `python -m pytest tests/ -v` (or `python tests/run_tests.py` if that is the team standard for the same coverage).
- [ ] If **`pylinac`** changed, also run **`python -m pytest tests/test_pylinac_extent_subclasses.py tests/test_pylinac_extent_relaxed.py -v`** (add any other `test_*pylinac*` paths if present).
- [ ] If **`pydicom`** or DICOM decoding plugins changed, spot-check any tests tagged or documented for compressed transfer syntaxes (JPEG-LS, JPEG 2000, etc.) if they exist in the tree.

---

## C. pylinac / QA integration (when `pylinac` or its stack was bumped)

- [ ] Read **upstream changelog** for the new version (e.g. [pylinac changelog](https://github.com/jrkerns/pylinac/blob/master/docs/source/changelog.rst)) for **breaking** or **behavior** notes affecting **ACRCT**, **ACRMRILarge**, or **CatPhan**-related APIs.
- [ ] **Manual QA smoke (recommended):** one **ACR CT** and one **ACR MRI Large** run on known-good local phantoms (vanilla and non-vanilla paths if you use both), comparing PDF/JSON or key metrics to **prior baseline** where clinically appropriate.
- [ ] Update **version callouts** if the project documents a verified pin: e.g. `requirements.txt` comment, [`user-docs/USER_GUIDE_QA_PYLINAC.md`](../../user-docs/USER_GUIDE_QA_PYLINAC.md), [`dev-docs/info/PYLINAC_FLEXIBILITY_AND_WORKAROUNDS.md`](../info/PYLINAC_FLEXIBILITY_AND_WORKAROUNDS.md), and any **HIGHDICOM / pydicom** constraint notes that cite the pylinac pin.

---

## D. GitHub Actions and `actions/github-script` (when that action or workflow logic changed)

- [ ] Re-read **release breaking changes** for the new major (e.g. [github-script v9](https://github.com/actions/github-script/releases)): no `require('@actions/github')`; do not **`const`/`let` redeclare** injected `getOctokit`.
- [ ] **Grep** `.github/workflows/` for `github-script` and confirm each `script:` block only uses supported patterns (`github`, `context`, `core`, injected `getOctokit`, Node built-ins like `fs`).
- [ ] Open a **draft PR** (or push to a branch) and confirm workflows that use **`actions/github-script`** still **complete** (comment-on-PR steps may only run on `pull_request`; use a test PR if needed).
- [ ] Confirm **Semgrep / Grype / security-checks** jobs still upload SARIF or post comments as expected when those paths are exercised.

---

## E. Release hygiene (when the bump is part of a user-visible release)

- [ ] **`CHANGELOG.md`:** add an entry under the correct section (e.g. **Dependencies** / **Changed**) describing the bump and any user-visible impact (Python floor, QA behavior caution, CI-only change).
- [ ] **`src/version.py`** (and any packaging metadata): align with your semver policy if this bump ships in a tagged release.

---

## F. Completion record (fill in when done)

| Field | Value |
|--------|--------|
| **Date completed** | <!-- YYYY-MM-DD --> |
| **What was bumped** | <!-- e.g. pylinac 3.42.0 → 3.43.2; actions/github-script v8 → v9 --> |
| **PR / commit** | <!-- link or hash --> |
| **pytest result** | <!-- e.g. N passed, 0 failed --> |
| **TO_DO Maintenance item** | <!-- confirmed checked `[x]` in TO_DO.md --> |

---

## Notes

- This plan is **not** a substitute for **secops** or **Dependabot** policy; it complements them after merges.
- If you only bumped **CI-only** actions (no `requirements.txt` change), sections **A–C** may be mostly N/A—state that inline beside the checkboxes.
