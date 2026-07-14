# Plan: Modular optional-feature packaging

## Goal and success criteria

Consider splitting DICOM Viewer V3 into installable feature tiers so users can run a lightweight core viewer and opt into heavier capabilities at install time or later on demand.

Success means:

- A core profile can open, view, navigate, window/level, annotate/measure, and export basic images without installing heavyweight or specialized optional dependencies.
- Optional profiles are documented, testable, and map to real dependency boundaries such as automated QA, non-DICOM image formats, advanced 3D, DICOM networking, and structure/mesh export.
- Users can tell which feature is unavailable because an optional pack is missing, and the app gives a clear install/configuration path instead of failing with an import error.
- Packaging decisions account for frozen builds, offline installs, licensing obligations, binary size, update behavior, and platform differences.

## Context and links

- Backlog: [`dev-docs/TO_DO.md`](../../TO_DO.md) under `Tier D - Platform & optional polish`.
- Related optional dependency areas:
  - Pylinac and automated QA: [`PYLINAC_INTEGRATION_OVERVIEW.md`](../../info/PYLINAC_INTEGRATION_OVERVIEW.md), [`QA_RESULTS_EXPORT_CLI_AND_HISTORY_PLAN.md`](QA_RESULTS_EXPORT_CLI_AND_HISTORY_PLAN.md).
  - Non-DICOM formats: [`NONDICOM_FORMAT_IMPORT_AND_CONVERSION_PLAN.md`](NONDICOM_FORMAT_IMPORT_AND_CONVERSION_PLAN.md).
  - 3D rendering: [`3D_VOLUME_RENDERING_PLAN.md`](../3D_VOLUME_RENDERING_PLAN.md).
  - Structure/ROI exports: [`ROI_PROPAGATION_STATS_AND_3D_ROI_PLAN.md`](ROI_PROPAGATION_STATS_AND_3D_ROI_PLAN.md).
  - Release and installer notes: [`RELEASING.md`](../../RELEASING.md), [`BUILDING_EXECUTABLES.md`](../../BUILDING_EXECUTABLES.md).

## Task graph and gates

### Ordering

- S1 -> Gate 1 -> T1/T2.
- T1 -> T3 -> Gate 2 -> T4/T5.
- T2 -> T6.
- T4/T5/T6 -> Gate 3 -> T7.

### Verification gates

- Gate 1: reviewer approves candidate feature-pack boundaries before dependency manifests or installer scripts change.
- Gate 2: release reviewer approves packaging strategy for source installs, frozen builds, and offline installs.
- Gate 3: tester verifies core-only and full-feature installs on at least one supported platform before any profile is documented as supported.

## Candidate feature profiles

- `core`: basic DICOM open/display/navigation, W/L, measurements/annotations, screenshots, local configuration, and privacy-safe diagnostics.
- `qa`: pylinac and automated QC analysis, report exports, CLI/batch analysis, QC history.
- `formats`: NIfTI/NRRD/MHA and related conversion dependencies.
- `render3d`: VTK/advanced 3D rendering and heavier 3D visualization dependencies.
- `networking`: PACS/query-retrieve/C-STORE and networking-specific dependencies.
- `structures`: DICOM SEG/RTSTRUCT/GSPS/SR writing, non-DICOM labelmap/vector/mesh export, and mesh-generation dependencies.
- `dev`: test, lint, docs, security-scan, and build tooling.

## Phases

### Phase 1 - Dependency and import-boundary audit

- [ ] (S1) Audit imports, dependency sizes, licenses, binary wheels, platform constraints, and current feature ownership to identify realistic optional package boundaries. (owner: researcher/coder, parallel-safe: yes, stream: A, after: none)
- [ ] (T1) Create a dependency map from user-visible features to Python packages, native libraries, optional executables, and license notices. (owner: coder, parallel-safe: no, stream: none, after: Gate 1)
- [ ] (T2) Identify current eager imports that would break a core-only install and define lazy-import/service-boundary changes needed before modular packaging. (owner: coder, parallel-safe: no, stream: none, after: Gate 1)

### Phase 2 - Packaging model

- [ ] (T3) Decide packaging mechanism for source installs, such as extras (`.[qa]`, `.[formats]`, `.[render3d]`, `.[all]`) or split requirements files, without changing runtime behavior yet. (owner: release/coder, parallel-safe: no, stream: none, after: T1)
- [ ] (T4) Decide frozen-app strategy: separate installers, installer-selectable components, a full installer plus disabled missing-feature UI, or documented post-install add-ons. (owner: release, parallel-safe: no, stream: none, after: Gate 2)
- [ ] (T5) Define on-demand install/update UX only if it is safe for the target environment: prompts, admin rights, offline sites, checksum/source validation, and rollback behavior. (owner: ux/release, parallel-safe: no, stream: none, after: Gate 2)
- [ ] (T6) Define feature-detection APIs so menus/dialogs can show unavailable optional features with clear messages and links to install docs. (owner: coder/ux, parallel-safe: no, stream: none, after: T2)

### Phase 3 - Validation and documentation

- [ ] (T7) Add smoke tests or CI jobs for at least core-only and full-feature dependency sets before declaring modular profiles supported. (owner: tester, parallel-safe: no, stream: none, after: Gate 3)
- [ ] (T8) Document install profiles, optional dependency licensing, binary-size tradeoffs, and troubleshooting in user/developer packaging docs. (owner: docwriter/release, parallel-safe: no, stream: none, after: T7)

## Risks and mitigations

| Risk | Mitigation |
|------|------------|
| Optional dependency split creates fragile import errors | Add feature-detection services and lazy imports with user-facing missing-feature messages. |
| Core-only install is not actually lightweight | Measure install size and startup import cost before and after the split. |
| Frozen-app packaging cannot add packages safely after install | Treat on-demand add-ons as optional; support separate installers or installer-selected components first. |
| Optional packs hide license obligations | Keep license notices per profile and require release review before bundling new binaries. |
| QA or medical-format workflows behave differently across profiles | Run profile-specific smoke tests and require explicit unavailable-feature states. |
| Dependency versions drift between packs | Pin compatible versions and test `core`, each pack, and `all` together. |

## Modularity and file-size guardrails

- Keep optional feature checks in a small service/module rather than scattering `try/except ImportError` through UI code.
- Keep packaging metadata separate from runtime feature registry where practical.
- Avoid turning the app into a plugin system unless the broader deferred plugin/extension architecture is explicitly approved.
- Do not move domain code only for packaging aesthetics; split where dependency boundaries are real.

## Testing strategy

- Core-only environment:
  - import app entrypoint,
  - open a basic DICOM fixture,
  - verify optional QA/format/3D/network/structure actions are hidden or disabled with useful messages.
- Feature-pack environments:
  - run one focused smoke per optional profile,
  - verify the full `all` profile still works,
  - verify frozen build behavior for missing or included optional packs.
- Packaging checks:
  - dependency/license report per profile,
  - install size comparison,
  - startup import timing for core-only vs full profile.

## UX / UI

Deferred to UX once the packaging model is chosen. Expected surfaces include disabled menu items, install-profile status in About/Settings, and feature-specific missing-dependency dialogs.

## Questions for user

- Should the first target be source/developer installs, frozen installers, or both?
- Is a small core viewer more important than a simple single full installer?
- Should on-demand install be allowed in clinical/offline environments, or should optional packs be installer-only?
- Which optional pack matters most first: pylinac/QA, non-DICOM formats, advanced 3D, networking, or structure export?

## Completion notes

Not started. This is a docs-only supporting plan as of 2026-06-11.
