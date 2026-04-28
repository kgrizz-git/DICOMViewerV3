# GitHub Actions, CI/CD, and storage — review and recommendations

**Purpose:** Support the Maintenance checklist item in `dev-docs/TO_DO.md` about periodically examining GitHub Actions, CI, CD, and related usage (minutes, noise, and **limited storage quota**). This document is an **assessment and recommendation** guide, not a mandate to strip automation.

**Audience:** Maintainers familiar with the repo’s workflows and GitHub billing.

**Related (existing):** Artifact vs cache vs GB-hours, and guardrails already in the repo, are documented in [`dev-docs/info/GITHUB_ACTIONS_STORAGE_AND_BILLING.md`](../../info/GITHUB_ACTIONS_STORAGE_AND_BILLING.md).

---

## 1. Current workflow inventory (snapshot)

| Workflow | Triggers (summary) | Primary cost drivers |
|----------|-------------------|----------------------|
| [`build.yml`](../../../.github/workflows/build.yml) | Version tags `v*`, `workflow_dispatch` | **Heavy:** 3 OS matrix, PyInstaller, Linux AppImage tooling, **artifact uploads** (30-day retention noted in workflow). Releases via `softprops/action-gh-release`. |
| [`security-checks.yml`](../../../.github/workflows/security-checks.yml) | PR + push to `main` / `develop` | 3 jobs (`ubuntu-latest` each): debug flags, TruffleHog (+ range logic), PII grep heuristics. Modest; `fetch-depth: 0` on one job increases checkout size/time slightly. |
| [`semgrep.yml`](../../../.github/workflows/semgrep.yml) | PR + push to `main` / `develop` / `feature/**`, weekly cron | `pip install semgrep`, multiple rulesets, SARIF upload, optional PR comment. |
| [`grype.yml`](../../../.github/workflows/grype.yml) | PR + push to `main` / `develop`, weekly cron | `anchore/scan-action`, SARIF upload, optional PR comment. |
| [`user-docs-links.yml`](../../../.github/workflows/user-docs-links.yml) | PR + push to `main` / `develop` | Lightweight Python link check. |
| [`actions-cache-prune.yml`](../../../.github/workflows/actions-cache-prune.yml) | Weekly cron + `workflow_dispatch` | Low cost; **reduces** cache storage churn via scripted prune. |
| **Dependabot** ([`dependabot.yml`](../../../.github/dependabot.yml)) | Scheduled weekly | Creates PRs; each PR triggers the same CI gates as human PRs. |

**Assessment:** The repo already applies **thoughtful storage guardrails** (pip cache key alignment in `build.yml`, artifact `retention-days`, weekly cache prune). The main **ongoing** costs on typical branches are **runner minutes** and **workflow run count**, not large artifact churn from day-to-day commits (release builds are the exception).

---

## 2. Storage and quota (moderate view)

- **Artifacts:** Release builds dominate artifact size. Shortening `retention-days` further is a **tradeoff** against debugging failed builds; **GitHub Releases** are already the canonical distribution path for tagged builds—see the billing note linked above.
- **Actions cache:** PR and feature-branch caches can accumulate; the **weekly prune** workflow is the right primary control. Prefer adjusting **prune age** or **protected refs** over disabling pip caching on heavy jobs (caching usually **saves** minutes at the cost of some cache entries).
- **Security / SARIF:** Uploads go to GitHub’s security data model; they are not the same billing bucket as multi-gigabyte PyInstaller artifacts, but they add **noise** in the Security tab if scans run very frequently with overlapping results.

**Recommendation:** Re-read [`GITHUB_ACTIONS_STORAGE_AND_BILLING.md`](../../info/GITHUB_ACTIONS_STORAGE_AND_BILLING.md) when GitHub changes pricing or when storage alerts appear; tune **artifact retention** and **prune parameters** before deleting workflows.

---

## 3. “Busy CI” and Dependabot / bot cascades

**Observed pattern:** A push runs workflows; a tool opens a **follow-up PR**; that PR triggers **another full** round of jobs. Dependabot is configured for **pip** and **github-actions** on a weekly schedule with reasonable open-PR limits.

**Assessment:** This is **normal** for secure repos. The cost is mostly **duplicate minutes** on similar SHAs, not necessarily storage.

**Low-risk mitigations (pick any that fit team process):**

- **Batch dependency work:** Merge Dependabot PRs in a small batch window so fewer “CI cold starts” span the week.
- **Path filters (use sparingly):** For workflows that only need docs (e.g. link checker), `paths` / `paths-ignore` can skip runs when only unrelated files change—**only** if you accept the risk of missing a break introduced alongside a doc-only change in one commit.
- **Concurrency:** Adding `concurrency` with `cancel-in-progress` on **PR** workflows can reduce wasted minutes when the same branch is pushed repeatedly; verify it does not cancel jobs you rely on for required checks display.

**Avoid (unless there is a measured problem):** Turning off Semgrep or Grype on `main`/`develop` just to save minutes—they provide **defense in depth** alongside TruffleHog and are already on a **weekly** schedule in addition to push/PR.

---

## 4. Overlap between security scans

| Capability | `security-checks.yml` | `semgrep.yml` | `grype.yml` |
|-------------|------------------------|---------------|-------------|
| Secrets in repo | TruffleHog (verified), detect-secrets (non-blocking) | Semgrep `p/secrets` rules | Not primary focus |
| Static analysis | Debug / PII heuristics | Broad SAST rulesets | CVEs / dependencies |

**Assessment:** Overlap is **limited and intentional** (secrets vs SAST vs dependency CVEs). Consolidating into one mega-workflow **slightly** reduces YAML surface area but can **increase** single-job failure blast radius and make logs harder to read.

**Recommendation:** Keep separate workflows unless maintenance burden is proven high; if consolidating, do it as a **single file with multiple jobs** so failures stay isolated.

---

## 5. CD scope

**Current state:** “CD” for this project is effectively **tag-driven release builds** (`build.yml` on `v*` tags) plus GitHub Releases—not continuous deployment of a web service.

**Recommendation:** No aggressive CD expansion is implied by the checklist; any future automation (notarized macOS, signing, staged releases) should be added with **explicit** retention and secrets handling documented next to the billing note.

---

## 6. Periodic review checklist (suggested cadence: quarterly or when billing alerts fire)

- [ ] **Billing / usage:** GitHub → *Settings → Billing* (or org equivalent): Actions minutes, **artifact** usage, **cache** usage.
- [ ] **Artifacts:** Spot-check large artifacts on recent **Build Executables** runs; confirm `retention-days` still matches policy.
- [ ] **Cache prune:** Confirm `actions-cache-prune` last run succeeded; optionally run **manual** `workflow_dispatch` with `dry_run: true` first.
- [ ] **Dependabot:** Review open PR count and whether grouping/versioning strategy (future Dependabot options) would reduce churn without delaying security patches.
- [ ] **Required checks:** If changing triggers or concurrency, verify branch protection still matches the intended required jobs.
- [ ] **Third-party actions:** Pin bumps go through the repo’s **[Dependency bump verification plan](../DEPENDENCY_BUMP_VERIFICATION_PLAN.md)** when materially risky.

---

## 7. Summary stance (not overly aggressive)

The repository is **already** in reasonable shape for a desktop app with multi-platform release builds. Favor **measurement → small tuning** (retention, prune age, batching bot PRs, optional path filters) over removing security automation. Treat **storage** and **minutes** as related but different problems: storage is addressed mainly by **artifacts + cache**; “noisy” CI is addressed by **triggers, concurrency, and merge habits**.
