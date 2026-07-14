# Product Tiers & Licensing Enforcement Plan

**Status:** Notes / recommendations only — not started (no implementation)
**Priority:** P1 (P0-blocked by `LICENSE_AND_COMPLIANCE_PLAN.md` Phase 0)
**TO_DO ref:** Release / Product — three-tier distribution (free basic / full trial / paid full)

> **Scope.** This document covers the **product packaging and in-app enforcement** of a
> tiered offering: which features are free vs paid, how a trial works, and the technical
> mechanism that grants/denies features at runtime. It is **distinct** from
> [`LICENSE_AND_COMPLIANCE_PLAN.md`](LICENSE_AND_COMPLIANCE_PLAN.md), which covers the
> *legal* side (open-source dependency licenses, the project's own license, EULA, SaMD).
> The two are linked: you cannot ship a closed-source paid binary until that plan's
> **Phase 0 GPL blockers are resolved** (`pylibjpeg-libjpeg` in particular).
>
> **This is not legal or business advice.** Pricing, license terms, and tax/MoR choices
> have financial and legal consequences — see Open Questions.

---

## 1. Product model

Three SKUs delivered from **one binary** (see §3 — do *not* maintain separate builds):

| SKU | What the user gets | License artifact |
|-----|--------------------|------------------|
| **Free Basic** | Core viewing, permanently free, no expiry | None required (default state with no license) |
| **Full Trial** | Every paid feature, time-limited (e.g. 14–30 days) | A signed *trial* license with an `expiry` date |
| **Full (Paid)** | Every paid feature, no expiry | A signed *paid* license (perpetual or subscription) |

**Key principles**
- **One build, runtime gating.** The downloaded app is identical for everyone; the
  presence/contents of a license file determine the tier. (§3)
- **Graceful downgrade, never lockout.** When a trial expires or no license is present,
  the app runs as **Free Basic** — the user can always still open and view their images.
  Paid features become disabled with an upsell affordance; their *data* is never held hostage.
- **Not for diagnostic use.** Per the compliance plan's intended-use decision, all tiers
  carry the non-diagnostic disclaimer; tiering does not change regulatory posture.

---

## 2. Tier feature split (PROPOSED — needs your sign-off)

Starting proposal based on the current feature set. The boundary is a **business decision**;
this is a strawman to react to, not a final answer. Rule of thumb: things people use to
*produce a work deliverable* (exports, QA reports, advanced reconstruction) are the paid hooks.

| Capability | Free Basic | Full (Trial + Paid) |
|------------|:---------:|:-------------------:|
| Open files / folders, drag-drop | ✅ | ✅ |
| 2D view, scroll, pan/zoom, smoothing | ✅ | ✅ |
| Window/Level + presets (DICOM/built-in/custom) | ✅ | ✅ |
| Multi-window & asymmetric layouts | ✅ | ✅ |
| Basic measurements (distance/angle) | ✅ | ✅ |
| ROI draw + **on-screen** statistics | ✅ | ✅ |
| Cine playback | ✅ | ✅ |
| Single-image screenshot / PNG-JPG export | ✅ (consider watermark) | ✅ (no watermark) |
| Tag browser (view) | ✅ | ✅ |
| **Tag export** (CSV/TXT/XLSX) | — | ✅ |
| **ROI statistics export** (CSV/XLSX) | — | ✅ |
| **MPR** (multiplanar reconstruction) | — | ✅ |
| **3D volume rendering** | — | ✅ |
| **Image fusion** (e.g. PET/CT) | — | ✅ |
| **Study index / local database** | — | ✅ |
| **SR / RDSR dose browser** | — | ✅ |
| **Automated QA (pylinac: ACR CT/MRI, CatPhan, nuclear SPECT QC)** | — | ✅ |
| **DICOM export & anonymization** | — | ✅ |
| **Hanging protocols / priors** | — | ✅ |
| **Cine video export** (AVI/MP4/GIF) | — | ✅ |

Open boundary questions are collected in §8.

---

## 3. Enforcement architecture (single build + entitlements)

**Do not** ship three binaries. Maintain **one** PyInstaller build; tier is resolved at
runtime from the license. This keeps one release pipeline, one test matrix, and lets a user
upgrade by dropping in a license file (no re-download).

### 3a. Entitlement layer (single source of truth)
- New module, e.g. `src/core/licensing/entitlements.py`:
  - `class Feature(Enum)` — one member per gated capability (`TAG_EXPORT`, `MPR`,
    `VOLUME_3D`, `FUSION`, `STUDY_INDEX`, `SR_BROWSER`, `QA_PYLINAC`, `DICOM_EXPORT`,
    `HANGING_PROTOCOLS`, `VIDEO_EXPORT`, …).
  - `class Tier(Enum)` = `FREE | TRIAL | PAID`.
  - A static map `TIER_FEATURES: dict[Tier, frozenset[Feature]]`.
  - `current_tier() -> Tier` and `is_enabled(Feature) -> bool` (TRIAL grants the PAID set).
  - `require(Feature)` raises/returns a typed result for call sites that must hard-gate.
- **Every gated feature asks the entitlement layer** — no scattered `if paid:` checks.
  This is the same centralization discipline used for `spreadsheet_safety` /
  `dependency_license_policy`: one authority, many callers.

### 3b. UI affordances (no dead ends)
- Disabled menu/toolbar actions for locked features show a **"Pro"** badge and, on click,
  an **upsell dialog** ("This feature requires a Full license — Start free trial / Enter
  license / Buy"). Never silently no-op.
- **Help → About**: show current tier, license holder, expiry (trial), and a "Manage
  license…" entry. Add "Start free trial", "Enter license key…", and "Buy" entry points.

### 3c. Threat model (be honest about it)
- Because it is one client-side binary, a determined attacker **can** patch out the gate.
  That is acceptable: the goal is to deter **casual** sharing and make the honest path easy,
  not to defeat reverse engineering. (Same realism the compliance plan applies to LGPL.)
- Stronger protection (revocation, seat limits, hard subscription enforcement) requires
  **online activation** (§4d) — defer unless the business model needs it.

---

## 4. License mechanism

### 4a. Recommended: offline signed license file (per user decision)
- App embeds a **public** key (Ed25519). You hold the **private** key offline and sign each
  license. The app verifies the signature locally — **no server, works air-gapped** (good
  for hospital networks).
- **Payload schema** (signed JSON or compact token):
  ```
  {
    "license_id": "<uuid>",
    "tier": "PAID" | "TRIAL",
    "issued_to": "<name/org/email>",
    "issued_at": "<ISO date>",
    "expires_at": "<ISO date | null>",     // null = perpetual; set for TRIAL
    "product": "DICOMViewerV3",
    "max_version": "<semver | null>",       // optional: limit to versions released during a maintenance window
    "machine_id": "<hash | null>"           // optional node-binding (§8)
  }
  ```
- **Verification flow on startup:** locate license file → verify signature against embedded
  public key → check `product`, `expires_at`, optional `machine_id`/`max_version` → set tier.
  Any failure → fall back to **FREE** (never crash, never lock out viewing).
- **Storage location:** per-user app data (e.g. `%APPDATA%\DICOMViewerV3\license.lic` on
  Windows) plus an "Import license…" action that copies a user-provided file into place.

### 4b. Trial enforcement specifics
- A trial is just a signed license with `tier=TRIAL` and a near `expires_at`. Two ways to
  start it:
  1. **Server/email issues** a trial license on signup (cleanest, ties trial to an identity); or
  2. **Local self-serve** "Start free trial" that records a first-run timestamp.
- **Clock-rollback defense** (for local self-serve): persist a monotonic "last seen" / "first
  seen" timestamp in two places (app data + OS registry/keychain). If the wall clock is
  earlier than last-seen, treat the trial as expired. Realistically deters casual abuse only.
- **Expiry behavior:** revert to FREE, show a one-time "trial ended" dialog with a Buy CTA.
  Do **not** delete data or block the app.
- **Reminders:** unobtrusive banner at e.g. T-3 days.

### 4c. Paid: perpetual vs subscription (decision in §8)
- **Perpetual + maintenance window:** `expires_at=null`, use `max_version` so a perpetual
  license covers versions released within the purchased support window; older license still
  runs the version it was bought for. Friendly to offline users.
- **Subscription:** time-boxed `expires_at`, renewed by re-issuing a license. Without an
  online check, enforcement is weak (user can keep an old binary + license) — see §4d.

### 4d. Optional later: online activation / 3rd-party licensing
- Adds revocation, seat counts, real subscription enforcement, analytics — at the cost of a
  server and an internet dependency at activation time.
- **Build vs buy:** rolling your own crypto is doable (the offline scheme above), but a
  hosted licensing service removes a lot of toil:
  - **Keygen**, **Cryptolens** — licensing-focused (keys, activations, machine fingerprints).
  - **Paddle**, **Lemon Squeezy** — *Merchant of Record*: they handle **global sales tax/VAT**,
    payments, refunds, **and** license-key issuance. For a solo developer this offloads a
    real compliance burden (worth serious consideration even if enforcement stays offline).
- **Recommendation:** ship v1 with the **offline signed-file** scheme; evaluate a MoR
  (Paddle/Lemon Squeezy) purely for **payments + key delivery** before launch, since you
  need *some* way to sell and deliver keys regardless.

---

## 5. Packaging & release impact
- One `DICOMViewerV3.spec` PyInstaller build for all tiers (no `--define`-style variants).
- Embed the **public** key as a resource; **never** ship the private key.
- About dialog + EULA already on the compliance plan's radar — add tier/license display there.
- Coordinate with [`VERSIONED_RELEASE_PLAN.md`](VERSIONED_RELEASE_PLAN.md): the version
  string feeds `max_version` checks if perpetual+maintenance is chosen.

---

## 6. Testing strategy (when implemented)
- Pure-logic unit tests for `entitlements` (tier→feature mapping; TRIAL == PAID set).
- License verification tests: valid/expired/tampered/wrong-product/wrong-key → correct tier
  with **fallback to FREE** on every failure path.
- Clock-rollback test for trial.
- UI tests: locked actions disabled + upsell dialog; About shows correct tier/expiry.
- No network in tests (offline scheme keeps this easy).

---

## 7. Phased rollout (future work — unchecked)
- [ ] **Phase A — Decisions:** finalize §2 feature split, trial length, perpetual vs
      subscription, machine-binding yes/no, sales/delivery channel (§8). Record in
      `dev-docs/info/COMMERCIAL_LICENSE_MODEL.md` (the file the compliance plan also expects).
- [ ] **Phase B — Resolve compliance Phase 0** (GPL `pylibjpeg-libjpeg`, etc.) — hard
      prerequisite for any closed-source paid binary.
- [ ] **Phase C — Entitlement layer** (`entitlements.py` + `Feature`/`Tier`), wire every
      gated feature through it; default everything to FREE behavior.
- [ ] **Phase D — License verification** (embedded public key, signed-file parse/verify,
      app-data storage, "Import license…").
- [ ] **Phase E — Trial flow** (start, expiry, rollback defense, reminders).
- [ ] **Phase F — UI** (Pro badges, upsell dialog, About/Manage-license, Buy/Trial CTAs).
- [ ] **Phase G — Sales/delivery** (MoR or store; key generation/signing workflow; EULA per
      compliance plan Phase 4).
- [ ] **Phase H — Docs** (user-facing tier comparison; how to activate; how to start trial).

---

## 8. Open questions (need your decisions)
1. **Exact feature split** — confirm/adjust §2. Anything to move between Free and Full?
2. **Trial length** — 14 or 30 days? One trial per machine/identity?
3. **Free-tier watermark** — watermark Free PNG/JPG exports, or leave clean?
4. **Perpetual vs subscription** (or both)? If perpetual, maintenance-window length?
5. **Machine binding** — bind paid licenses to a machine fingerprint (reduces sharing, adds
   support burden on hardware changes) or keep portable?
6. **Sales & delivery channel** — Merchant of Record (Paddle / Lemon Squeezy) vs Stripe +
   self-issued keys vs a licensing SaaS (Keygen/Cryptolens)? This drives tax handling.
7. **Online activation** — needed at launch, or defer (offline-only v1)?
8. **License transfer / refunds** policy.
9. **Contributor IP / CLA** — same question the compliance plan raises if relicensing.

---

## 9. Files likely touched (future implementation)
| File | Change |
|------|--------|
| `src/core/licensing/entitlements.py` | **New** — `Feature`/`Tier`, tier→feature map, `is_enabled`/`require` |
| `src/core/licensing/license_file.py` | **New** — signed-file parse + Ed25519 verify + storage |
| `src/core/licensing/trial.py` | **New** — trial start/expiry + clock-rollback defense |
| `resources/keys/license_public.pem` | **New** — embedded public key (public only!) |
| `src/gui/dialogs/about_dialog.py` | Tier/expiry display, Manage-license, Buy/Trial CTAs |
| `src/gui/dialogs/upsell_dialog.py` | **New** — locked-feature upsell |
| gated feature call sites (export, MPR, fusion, 3D, study index, SR, QA, …) | Route through `entitlements.is_enabled` |
| `DICOMViewerV3.spec` | Bundle public key resource |
| `dev-docs/info/COMMERCIAL_LICENSE_MODEL.md` | **New** — business-model & tier decision record (shared with compliance plan) |
| `dev-docs/TO_DO.md` | Link this plan under Release / Product |

---

## Related
- [`LICENSE_AND_COMPLIANCE_PLAN.md`](LICENSE_AND_COMPLIANCE_PLAN.md) — legal/dependency licensing, EULA, SaMD, **Phase 0 GPL blockers (prerequisite)**.
- [`VERSIONED_RELEASE_PLAN.md`](VERSIONED_RELEASE_PLAN.md) — release/build pipeline this rides on.
