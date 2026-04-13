# GitHub Actions storage and billing (maintainers)

This note explains how **artifact and related Actions storage** interact with GitHub plan limits—especially why the **GitHub Free** tier’s small **artifact** allowance conflicts with **large PyInstaller / multi-OS CI uploads**—and how that relates to **`retention-days`**.

Official reference (pricing and definitions change over time): [About billing for GitHub Actions](https://docs.github.com/en/billing/managing-billing-for-github-actions/about-billing-for-github-actions).

---

## How storage is measured: GB-hours (not “one upload”)

GitHub measures storage over time using **GB-hours**:

- **1 GB-hour** = **1 gibibyte (GiB)** of data stored for **one hour** (GitHub uses binary GB: 1 GB = 2³⁰ bytes).
- Usage **accrues continuously** through the billing period. A steady **~0.5 GB** of artifacts sitting online all month is not a flat “500 MB one-time” cap—it is roughly **0.5 GB × hours in the month** of GB-hours against your included amount.
- **Rule of thumb** for a **~30-day** month: many examples use about **720 hours**. Then holding **0.5 GB** continuously is on the order of **0.5 × 720 ≈ 360 GB-hours**—the ballpark for “about half a gig for the whole month” under that model.
- Holding **~1 GB** continuously for the same period is on the order of **~720 GB-hours**, i.e. **about double**—so **~1 GB of artifacts on the free tier’s 500 MB artifact allowance** can plausibly trigger “100% of included storage” alerts even when the UI shows “only” about a gigabyte **current** size.

**Current vs accrued**

- The **Actions → workflow run → Artifacts** UI shows roughly **current** stored size.
- Billing also reflects **accrued** GB-hours for the cycle. **Deleting** artifacts drops **current** storage quickly and stops **future** accrual; GitHub’s docs note that **usage already accrued** in the billing cycle may still affect that cycle’s reporting.

---

## Included allowances (verify on your account)

Exact numbers depend on **plan and GitHub’s current docs**. As of the doc snapshot used when this file was written:

- **GitHub Free** includes **500 MB** of **artifact** storage in the published table (alongside monthly minutes).
- **Actions cache** (e.g. `actions/setup-python` with `cache: 'pip'`) is governed by **separate cache** rules; the same billing page lists a **10 GB** per-repository included cache tier with detailed rules.
- **GitHub Packages** may share the overall storage picture on the account—check **Billing → Plans and usage** for your org/user.

Always confirm in GitHub UI and the live billing docs before making quota decisions.

---

## Actions **cache** (dependency cache) vs **artifacts**

These are billed and managed differently:

- **Artifacts** (`actions/upload-artifact`): workflow output zips; controlled mainly by **`retention-days`** and what paths you upload.
- **Actions cache** (`actions/cache`, `actions/setup-python` with `cache: pip`, etc.): keyed blobs scoped to a **ref** (branch, `refs/pull/…/merge`, tag, …). Repositories get a pooled allowance (see GitHub’s current billing page; often **10 GB** per repo on free tier) with automatic eviction when full, but **many PR/feature-branch runs** can still create a large number of entries and churn.

### Long-term guardrails in this repo

| Guardrail | Where |
|-----------|--------|
| Weekly prune of **stale** caches on **non-protected** refs | `.github/workflows/actions-cache-prune.yml` + `.github/scripts/prune-actions-caches.sh` |
| Protected refs (never deleted by the prune job) | Repository **default branch** (e.g. `refs/heads/main`), **`refs/heads/develop`**, plus optional **`extra_protected_refs`** on manual runs |
| Staleness rule | Delete only if **`last_accessed_at`** (fallback **`created_at`**) is older than **`min_age_days`** (default **7**) |
| Narrower pip cache keys for Build Executables | `build.yml` — `cache-dependency-path` lists **`requirements.txt`** and **`requirements-build.txt`** so one hash covers both install steps |
| Shorter build artifact retention | `build.yml` **`retention-days`** (see table below); release assets remain on **GitHub Releases** |

Scheduled runs use **`dry_run: false`** implicitly (they always delete eligible caches). **Manual** `workflow_dispatch` defaults to **`dry_run: true`** so you can confirm the list before turning off dry run.

### One-off cleanup (maintainer CLI)

With [GitHub CLI](https://cli.github.com/) and a token that can manage Actions caches:

```bash
gh cache list --repo OWNER/REPO
# Delete a specific cache id after inspecting the list:
gh cache delete CACHE_ID --repo OWNER/REPO
```

The prune workflow is preferred for recurring cleanup because it applies the **protected ref** and **age** policy consistently.

---

## `retention-days` on `upload-artifact`

When a workflow uses `actions/upload-artifact` with **`retention-days`**:

- That value is how long GitHub **retains** those files before **automatic deletion**.
- **Longer** retention (e.g. **90 days**) means large artifacts contribute **more GB-hours** over the month and are more likely to overlap with the next billing cycle.
- **Shorter** retention reduces storage-time if **GitHub Releases** (or another system) already holds the binaries users need.

---

## This repository

| Item | Detail |
|------|--------|
| **Large artifacts** | `.github/workflows/build.yml` uploads **Windows / macOS / Linux** outputs (`dist/` + Linux **AppImage** only — not PyInstaller **`build/`**). |
| **Retention** | See **`retention-days`** in `build.yml` (tuned for **GB-hours**; verify current value in the workflow). |
| **Actions cache** | **Build** uses **`setup-python`** pip caching; PRs create branch-scoped caches. **`actions-cache-prune.yml`** trims stale non-protected entries weekly. |
| **Other workflows** | `security-checks.yml`, `semgrep.yml`, `grype.yml` do not upload comparable artifact zips; they still consume **runner minutes** and may use **cache** or **SARIF** to the Security tab. |

**Practical levers to reduce GB-hours:** omit unnecessary paths from artifacts (often **`build/`** if not needed for debugging), shorten **`retention-days`** if release assets are canonical, and periodically delete stale workflow artifacts.

---

## See also

- [BUILDING_EXECUTABLES.md](BUILDING_EXECUTABLES.md) — Step 7, GitHub Actions builds and artifacts.
- [GITHUB_RELEASES_AND_VERSIONING.md](GITHUB_RELEASES_AND_VERSIONING.md) — tags and releases as the primary distribution path.
