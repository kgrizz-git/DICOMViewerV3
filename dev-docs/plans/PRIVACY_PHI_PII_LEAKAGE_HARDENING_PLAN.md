# Plan: Privacy, PHI/PII, and Leakage Hardening

**Last updated:** 2026-07-16

## Goal and success criteria

Build a local-first, defense-in-depth privacy system for a medical imaging and
medical-physics application. The system must prevent clinical identifiers,
filenames, paths, usernames, hostnames, IP addresses, UIDs, annotations, raw
exceptions, and derived clinical data from leaking through repository content,
Git metadata, logs, dialogs, reports, scanner output, tests, CI logs, or silent
runtime storage.

Success requires all of the following:

- Repository admission fails closed for unreviewed clinical/binary/runtime
  artifacts while reporting only path, line, and rule category.
- Runtime logging and diagnostic sinks redact at the handler boundary; call-site
  mistakes cannot expose sensitive formatting arguments or exception details.
- Internal runtime writes never target the source checkout or current working
  directory and use restrictive per-user storage where supported.
- Users are told before clinical metadata or derived pixels are persisted and
  can inspect, clear, or disable that storage.
- Fast local hooks, blocking CI, advisory scanners, and human-review lanes have
  distinct documented semantics; a missing mandatory tool never passes as a
  successful check.
- All detection tests use synthetic canaries only. No real PHI/PII or scanner
  match value enters source, logs, chat, issues, or reports.
- A redacted preflight supports an explicit decision on retaining the existing
  14-commit private remote, replacing it with a clean-history snapshot, or
  deleting/recreating it. No remote mutation occurs without user authorization.

## Context and links

- Canonical policy: `dev-docs/PHI_PII_REPOSITORY_GUARDRAILS.md`
- Security CLI: `dev-docs/SECURITY_TOOLS_CLI_GUIDE.md`
- Contribution workflow: `dev-docs/CONTRIBUTING.md`
- Current artifact gate: `scripts/check_no_phi_artifacts.py`
- Current staged source guard: `scripts/git_hook_privacy_checks.py`
- Commit-message guard: `scripts/git_hook_commit_message_privacy.py`
- Current sanitizer: `src/utils/log_sanitizer.py`
- Current optional diagnostic sink: `src/utils/debug_log.py`
- Current blocking CI artifact job: `.github/workflows/security-checks.yml`
- Reviewed media manifest: `security/approved-media-sha256.json`
- Text exception manifest: `security/approved-phi-text-exceptions.json`
- Isolated scanner dependencies: `requirements-phi-tools.txt`
- Historical execution notes remain in this plan; no orchestration state is active.

### Current-state evidence from the 2026-07-15 audit

- `check_no_phi_artifacts.py`: 1,151 tracked files clean.
- Focused privacy tests: 90 passed.
- Hounddog 3.3.0: 275 files, zero risky dataflows; many unconnected
  stdout/log/file sinks, so advisory only until configured.
- PhiScan 0.7.0: 5,569 `src/` findings; unsuitable as a repository-wide
  blocking gate without scoped configuration.
- Gitleaks: four reviewed pattern matches (SHA-256-like values and a historical
  example marker), no confirmed secret from that scan.
- Reachable path history: only the three approved synthetic DICOM fixtures;
  no historical pytest config/runtime path found by the audit.
- Git metadata: three historical commit messages match current privacy-rule
  categories; six unique author emails, five GitHub noreply; remote URL has no
  embedded userinfo; no basic risky branch/tag-name match.
- GitHub remote: private, `main`, 14 commits matching local; current tier does
  not expose branch protection and reports no secret-scanning/push-protection
  status. Local and CI enforcement therefore cannot depend on hosted controls.

## Threat model and policy boundaries

### Sensitive classes

Treat these as sensitive unless structurally proven synthetic and approved:

- DICOM patient, visit, study, series, instance, accession, institution,
  operator, physician, device/station, date/time, free-text, and private tags.
- DICOM UIDs and derived identifiers, filenames, directory names, full paths,
  usernames, home directories, hostnames, AE titles, endpoints, and IPs.
- Pixel data, screenshots, thumbnails, derived MPR arrays, OCR text, reports,
  annotations, ROI labels, exception values, and configuration captures.
- Git authors, messages, refs, remote URLs, PR/issue text, CI output, and scanner
  reports when they contain any of the above.

### Non-goals

- The viewer is allowed to open real clinical DICOM locally. On-demand DICOM
  scanning is not a prerequisite for normal viewing.
- Privacy Mode is display masking, not de-identification or at-rest protection.
- Regex/NER/OCR results do not certify de-identification; human review remains
  required for admitted visual/binary assets.
- `.gitignore`, editor ignores, encryption, and local-only operation are layers,
  not substitutes for repository and runtime sink controls.

## Enforcement matrix

| Concern | Pre-commit | Pre-push | CI | Manual/advisory |
|---|---|---|---|---|
| Tracked PHI/runtime artifacts | blocking staged | blocking full tracked | blocking full tracked | human exception review |
| Unsafe Python output sinks | blocking staged | optional full tree | blocking full tree | reviewer |
| Commit/ref/remote metadata | commit/ref blocking | blocking preflight | redacted audit | author/remote review |
| Secrets | blocking staged Gitleaks | blocking reachable history | blocking diff + repository mode | narrow fingerprint review |
| Hounddog data flow | none | advisory local | not installed/skipped | configured local scan |
| PhiScan text classification | scoped advisory | none | optional scoped lane | isolated staged-data review |
| Image/PDF/PostScript OCR | admission blocks until review | none | hash admission only | metadata + OCR + visual review |
| DICOM tag/pixel review | admission blocks until review | none | deterministic metadata gate | local dicom-phi-scan review |
| Runtime storage/consent | unit tests | targeted tests | blocking tests | manual UI smoke |
| Dependency/SAST checks | existing fast lane | existing full lane | existing workflows | secops review |

Mandatory checks fail if their executable/parser is missing. Advisory wrappers
may report `SKIP`, but their names and exit semantics must make clear that a skip
is not a passing security result.

## Task graph and gates

### Ordering

- P0 plan/preflight -> P1 shared privacy primitives -> P2 sink migration.
- P1 -> P3 static enforcement and canary tests.
- P1 -> P4 artifact/Git admission.
- P1 -> P5 scanner/review tooling.
- P1 -> P6 runtime storage and consent; UI design may proceed after the storage
  inventory, but implementation shares config/settings paths and is sequential.
- P2 + P3 + P4 + P5 + P6 -> P7 hooks/CI/docs integration.
- P7 -> P8 full reviewer/tester/secops/manual gates.
- P8 -> remote-history decision; only explicit user approval permits mutation.

### Verification gates

1. **G0 — Plan gate:** orchestrator accepts this task graph and resolves any
   blocking product questions before product edits.
2. **G1 — Primitive API gate:** reviewer approves classification/redaction and
   safe-storage interfaces before broad sink migration.
3. **G2 — Slice gates:** targeted tests, Ruff, and basedpyright for every slice.
4. **G3 — CI-output gate:** deliberately triggered canaries prove local and CI
   checkers never echo matched values.
5. **G4 — Product-storage gate:** reviewer + UX/manual smoke approve consent,
   disclosure, retention, and clear controls.
6. **G5 — High-risk final gate:** full pytest, link/harness/architecture/privacy
   checks, reviewer alignment, and secops assessment.
7. **G6 — Remote gate:** present retain/rewrite/recreate evidence and obtain an
   explicit user choice before any history or GitHub mutation.

## File and area ownership

| Stream | Primary areas | Notes |
|---|---|---|
| PR-A | `src/utils/privacy/`, `src/utils/log_sanitizer.py`, shared tests | foundational; sequential first |
| PR-B | application sinks under `src/`, `src/utils/debug_log.py` | after PR-A; split by module groups if needed |
| PR-C | `scripts/*privacy*`, `scripts/check_no_phi_artifacts.py`, hook tests | may run after PR-A, disjoint from PR-B |
| PR-D | `.githooks/`, `.github/workflows/`, secret-scan config, agent ignores | after PR-C interfaces stabilize |
| PR-E | scanner/review wrappers, `requirements-phi-tools.txt`, scanner docs | disjoint from product sink migration |
| PR-F | config/MPR cache/study-index/settings UI and tests/user docs | sequential within stream; UX smoke required |
| PR-G | canonical docs, changelog/version, verification ledgers/assessments | fan-in after implementation |

## Phases

### Phase 0 — Baseline and remote preflight

- [x] **(PRIV-P0)** Preserve a redacted baseline of current checks, installed
  tools, dependency conflicts, Git metadata category counts, remote privacy,
  and GitHub-tier limitations. (owner: secops, parallel-safe: no, stream: PR-A,
  after: none)
- [x] **(PRIV-P1)** Implement a read-only `scripts/privacy_remote_preflight.py`
  that audits tracked/reachable paths, commit messages, author email classes,
  refs, remote URL userinfo, initial-push coverage, and secret-scan categories;
  never print matched values. (owner: coder, parallel-safe: no, stream: PR-C,
  after: PRIV-P0)
- [x] **(PRIV-P2)** Add tests for redacted preflight output and synthetic risky
  metadata in temporary repositories. (owner: coder, parallel-safe: no,
  stream: PR-C, after: PRIV-P1)
- [ ] **(PRIV-P3)** At G6, present: retain 14 commits, clean-history snapshot in
  the existing private repo, or delete/recreate; include rollback and local tag
  preservation steps. (owner: orchestrator, parallel-safe: no, stream: PR-A,
  after: PRIV-FINAL)

### Phase 1 — Shared classification, redaction, and safe storage primitives

- [x] **(PRIV-R1)** Create a single canonical sensitive-field and identifier
  registry shared by artifact checks, logging, dialogs, and tests; include UIDs,
  filenames/paths, endpoints/IPs, annotations, and free text. (owner: coder,
  parallel-safe: no, stream: PR-A, after: PRIV-P0)
- [x] **(PRIV-R2)** Implement structured redaction APIs that replace full paths
  including basenames, sanitize every formatting argument and exception, and
  expose safe operation/count/error-class fields. Default must fail closed.
  (owner: coder, parallel-safe: no, stream: PR-A, after: PRIV-R1)
- [x] **(PRIV-R3)** Add a logging `Filter`/adapter/formatter boundary that
  sanitizes `LogRecord.msg`, `args`, exception data, stack data, and extra fields
  before any handler emits them. (owner: coder, parallel-safe: no, stream: PR-A,
  after: PRIV-R2)
- [x] **(PRIV-R4)** Add safe internal-storage helpers: platform per-user paths,
  no source-checkout/CWD writes, restrictive file/dir permissions where
  supported, atomic writes, retention metadata, and safe deletion. (owner:
  coder, parallel-safe: no, stream: PR-A, after: PRIV-R2)
- [x] **(PRIV-R5)** Add unit tests for all primitives on Windows/POSIX/UNC paths,
  user/host/IP/UID/annotation canaries, logger percent/f-string/args/exceptions,
  and permission/path boundaries. (owner: coder, parallel-safe: no,
  stream: PR-A, after: PRIV-R3)

**Gate G1:** reviewer approves APIs and verifies no sensitive basename survives.

**G1 evidence (2026-07-15):** primary applied the repository reviewer checklist
after two reviewer workers failed to return a verdict. Ruff passed; basedpyright
reported 0 errors/0 warnings; 117 privacy-focused regression tests passed;
adversarial POSIX, Windows, UNC, quoted-space basename, formatting-argument,
exception, extra-field, checkout-boundary, permissions, and retention-metadata
cases passed. Gate closed with explicit non-independent review provenance.

### Phase 2 — Application, debug, dialog, test, and report sink migration

- [ ] **(PRIV-S1)** Inventory executable `print`, `pprint`, stdout/stderr,
  `logger.*`, `logging.exception`, `exc_info=True`, traceback, dialog, report,
  and debug-log sinks using AST-backed tooling; record categories, not values.
  (owner: coder, parallel-safe: no, stream: PR-B, after: PRIV-R5)
- [ ] **(PRIV-S2)** Replace raw loader/decoder/rendering/ROI/MPR/config and QA
  exception/path output with central safe logging and generic user messages.
  (owner: coder, parallel-safe: no, stream: PR-B, after: PRIV-S1)
- [x] **(PRIV-S3)** Replace repository-local `.cursor/debug.log` and other fixed
  diagnostic files with opt-in protected app storage; redact payloads, disclose
  location/retention, and add clear/delete controls. Remove annotation text and
  UID payloads unless structurally reduced to safe counts/types. (owner: coder,
  parallel-safe: no, stream: PR-B, after: PRIV-R4)
  Implemented protected opt-in diagnostics with central redaction, an exact
  2 MiB cap, per-entry seven-day pruning, disclosed location, and clear-now UI.
  MPR cache metadata now stores a one-way series key rather than a raw UID.
  Follow-up 2026-07-16: recursive persisted-diagnostic values and mapping keys
  now fail closed; only validated operation/error-class strings and typed
  metrics survive. A nested free-text JSONL regression covers the G4 finding.
- [x] **(PRIV-S4)** Harden external-data audit/test scripts so real input folder,
  filename, UID, patient values, and output directory are never printed; require
  explicit protected output roots. (owner: coder, parallel-safe: no,
  stream: PR-B, after: PRIV-S1)
- [ ] **(PRIV-S5)** Add regression tests for each migrated sink and prove raw
  exception/path content is absent from console, caplog, dialogs, and files.
  (owner: coder, parallel-safe: no, stream: PR-B, after: PRIV-S2)

### Phase 3 — Static enforcement and synthetic canaries

- [x] **(PRIV-C1)** Refactor the staged privacy checker into small AST/token/path
  modules with explicit `--staged` and `--all` modes. (owner: coder,
  parallel-safe: no, stream: PR-C, after: PRIV-R5)
- [ ] **(PRIV-C2)** Inspect every logger argument, dynamic print/stdout/stderr,
  debug-log payload, dialog exception, traceback, `logging.exception`, and
  `exc_info=True` sink over `src/`, relevant `scripts/`, and external-data tests.
  Inline exceptions require named rules and review. (owner: coder,
  parallel-safe: no, stream: PR-C, after: PRIV-C1)
- [x] **(PRIV-C3)** Ensure violations print only repository-relative path, line,
  and rule category; test that canary values never appear in checker output.
  (owner: coder, parallel-safe: no, stream: PR-C, after: PRIV-C2)
- [ ] **(PRIV-C4)** Add end-to-end synthetic canary failures across stdout,
  stderr, caplog, dialogs, reports, debug files, and internal storage. (owner:
  coder, parallel-safe: no, stream: PR-C, after: PRIV-S5)
  Evidence 2026-07-16: the category-only advisory inventory fell from 183
  regenerated findings to zero without a baseline, blanket ignore, or
  value-bearing output. Central fail-closed console, logging, dialog, report,
  debug, and protected-storage boundaries replace raw sinks; external DICOM/QC
  tools require explicit protected output roots and do not persist raw source
  paths or exception text. Synthetic canaries cover stdout, stderr, caplog,
  dialogs, reports, debug JSONL, and internal storage. Focused privacy tests:
  92 passed; advisory and critical scans, artifact gate, Ruff, basedpyright on
  new privacy modules, compilation, and diff checks passed.
  Reviewer follow-up 2026-07-16: channel canary absence remains verified, but
  the sink slice is reopened below because the checker missed a dynamic
  output-directory print and no positive tests prove useful safe output is
  retained by the console/logging boundaries.
- [x] **(PRIV-C5)** Add repository-local custom Semgrep rules for forbidden sink
  and unapproved outbound-network patterns, with focused tests/fixtures.
  (owner: coder, parallel-safe: yes, stream: PR-C, after: PRIV-C2)

### Phase 4 — Artifact, filename, symlink, Git, and secret admission

- [x] **(PRIV-A1)** Extend artifact scanning to sensitive repository filenames
  and archive member names, absolute/escaping symlinks, UNC paths, authenticated
  URLs, `.gitmodules`, AE/internal endpoints, local identities, and public/private
  IPs while allowing loopback and standards-reserved documentation ranges.
  (owner: coder, parallel-safe: no, stream: PR-C, after: PRIV-R1)
- [x] **(PRIV-A2)** Fail closed on parser absence, malformed/encrypted/oversized
  content and ensure exception/manifest output remains redacted. (owner: coder,
  parallel-safe: no, stream: PR-C, after: PRIV-A1)
- [x] **(PRIV-A3)** Add Gitleaks staged and reachable-history wrappers. Review the
  four known patterns and use narrow fingerprints/path+rule exceptions, never a
  broad detector disable. (owner: coder, parallel-safe: yes, stream: PR-D,
  after: PRIV-P0)
- [x] **(PRIV-A4)** Extend commit/ref validation to branch/tag/pre-push ref names,
  author email policy, remote URL userinfo, and initial-push zero-base cases.
  (owner: coder, parallel-safe: no, stream: PR-D, after: PRIV-P1)
  Read-only preflight and blocking pre-push enforcement cover ref names,
  noreply author-email policy, remote URL userinfo, ranges, and zero-base
  initial pushes with category-only diagnostics.
- [x] **(PRIV-A5)** Track privacy-oriented `.cursorignore` and
  `.cursorindexingignore` files; remove their current blanket `.gitignore`
  exclusion and cover clinical/local data, config, cache, reports, screenshots,
  exports, scanner outputs, and temporary directories. (owner: coder,
  parallel-safe: yes, stream: PR-D, after: PRIV-P0)
- [x] **(PRIV-A6)** Add artifact/preflight/secret/ref tests using temporary Git
  repositories and synthetic values. (owner: coder, parallel-safe: no,
  stream: PR-D, after: PRIV-A4)

### Phase 5 — Local scanner and asset-review workflows

- [x] **(PRIV-T1)** Add a Hounddog advisory wrapper with version display,
  no-account/no-SCM policy, `--no-git`, project source/sink config, redacted
  summaries, and distinct CLEAN/FINDINGS/SKIP/ERROR statuses. Never add a
  pass-by-skip CI job. (owner: coder, parallel-safe: yes, stream: PR-E,
  after: PRIV-R1)
- [x] **(PRIV-T2)** Repair and pin the isolated PHI-tools environment, including
  the Typer mismatch; correct stale Click-conflict documentation; include
  dicom-phi-scan reproducibly without polluting the application venv. (owner:
  coder, parallel-safe: no, stream: PR-E, after: PRIV-P0)
- [x] **(PRIV-T3)** Add a PhiScan wrapper that scans only staged data-like blobs
  materialized in protected temp storage; no 5,569-finding whole-code baseline.
  (owner: coder, parallel-safe: no, stream: PR-E, after: PRIV-T2)
- [x] **(PRIV-T4)** Add media review tooling for EXIF/XMP/embedded metadata,
  Tesseract/Presidio OCR, protected temporary reports, redacted summaries, and
  explicit human confirmation before updating the approved-media manifest.
  (owner: coder, parallel-safe: no, stream: PR-E, after: PRIV-T2)
- [x] **(PRIV-T5)** Add an on-demand DICOM tag/pixel review wrapper for fixture,
  share, screenshot, publication, and admission workflows; do not require it for
  ordinary local viewing. (owner: coder, parallel-safe: no, stream: PR-E,
  after: PRIV-T2)
- [x] **(PRIV-T6)** Test missing-tool, clean, finding, malformed-output, timeout,
  report-permission, and cleanup paths without recording matched values.
  (owner: coder, parallel-safe: no, stream: PR-E, after: PRIV-T5)

### Phase 6 — Runtime storage, disclosure, retention, and consent

- [x] **(PRIV-U1)** Inventory config recent/export paths, MPR derived pixel cache,
  encrypted study index, reports, screenshots, scanner output, and every other
  persistent clinical-data sink; document location, format, encryption,
  retention, and clear/disable controls. (owner: coder, parallel-safe: no,
  stream: PR-F, after: PRIV-R4)
- [x] **(PRIV-U2)** Move internal caches/logs/reports to protected platform app
  storage and apply permissions/retention/cleanup. Do not move explicit user
  exports without preserving the chosen destination. (owner: coder,
  parallel-safe: no, stream: PR-F, after: PRIV-U1)
  MPR pixels and diagnostics now use protected platform-private storage; the
  encrypted index uses that location for new installs while preserving an
  existing legacy database, and explicit export destinations remain unchanged.
- [x] **(PRIV-U3)** Add first-launch opt-in for study-index auto-add, remember the
  answer, preserve encrypted storage, and expose current path/encryption/clear
  controls. Default behavior for users who have already answered must be
  migration-safe. (owner: coder+ux, parallel-safe: no, stream: PR-F,
  after: PRIV-U1)
  Automatic indexing fails closed until an explicit choice. Unanswered legacy
  settings receive the same one-time choice with migration-specific copy.
- [x] **(PRIV-U4)** Disclose MPR derived-pixel caching and recent-path config;
  provide clear-cache/recent-history controls and disable/retention options.
  (owner: coder+ux, parallel-safe: no, stream: PR-F, after: PRIV-U2)
  Settings disclose purpose, encryption, locations, caps, retention, and clear
  controls. Persistent MPR caching defaults off; disabling clears current and
  legacy cache files. Remembered input/export/report paths can be cleared.
- [x] **(PRIV-U5)** Add storage-location, restrictive-permission, consent,
  migration, retention, and clear-control tests. (owner: coder,
  parallel-safe: no, stream: PR-F, after: PRIV-U4)
  Temporary-storage tests cover defaults, consent persistence/migration,
  protected permissions, bounded/aged diagnostics, current/legacy MPR cleanup,
  index sidecars, recent paths, and Settings application behavior.

**Gate G4:** manual desktop smoke verifies first-launch and settings behavior.

### Phase 7 — Hooks, CI, documentation, and release integration

- [x] **(PRIV-I1)** Wire fast blocking staged artifact/privacy/Gitleaks checks to
  pre-commit; commit/ref metadata to commit-msg/pre-push; full local gates to
  pre-push without reclassifying findings as successful `review`. (owner: coder,
  parallel-safe: no, stream: PR-D, after: PRIV-C3)
- [x] **(PRIV-I2)** Replace the informational CI grep job that echoes source
  lines with blocking redacted full-tree privacy checks; preserve least
  permissions and pinned actions. (owner: coder, parallel-safe: no,
  stream: PR-D, after: PRIV-C3)
- [x] **(PRIV-I3)** Cover initial-push secret scanning; keep Grype advisory only
  if policy says so, but label it accurately. Mandatory scanner absence/errors
  must fail the job. (owner: coder, parallel-safe: no, stream: PR-D,
  after: PRIV-A3)
- [ ] **(PRIV-I4)** Update `AGENTS.md`, guardrails, contributing/setup/security
  CLI docs, user storage/privacy docs, and maintenance history. Define exact
  conditions under which agents run each scanner and where protected reports
  may be written. (owner: docwriter, parallel-safe: no, stream: PR-G,
  after: PRIV-U5)
- [ ] **(PRIV-I5)** Update CHANGELOG/version only for shipped user-facing
  consent/storage behavior according to release policy. (owner: orchestrator,
  parallel-safe: no, stream: PR-G, after: PRIV-I4)

### Phase 8 — High-risk verification and completion

- [ ] **(PRIV-V1)** Run focused privacy, artifact, hook, scanner-wrapper,
  storage, consent, and canary tests from `.venv`. (owner: tester,
  parallel-safe: no, stream: PR-G, after: PRIV-I3)
- [ ] **(PRIV-V2)** Run Ruff and basedpyright on touched Python modules and fix
  new findings. (owner: coder, parallel-safe: no, stream: PR-G, after: PRIV-I3)
- [ ] **(PRIV-V3)** Run full `python -m pytest tests/ -v`, user-doc links,
  repository harness, architecture boundaries, agent smoke, no-PHI artifact
  scan, full privacy scan, and redacted secret/history preflight. (owner: tester,
  parallel-safe: no, stream: PR-G, after: PRIV-V2)
- [ ] **(PRIV-V4)** Reviewer verifies plan/spec alignment and marks only evidenced
  tasks complete; secops writes the timestamped final assessment. (owner:
  reviewer+secops, parallel-safe: no, stream: PR-G, after: PRIV-V3)
- [ ] **(PRIV-V5)** Perform manual smoke for consent/settings/cache/index clear
  flows and protected diagnostic logging. (owner: tester+ux, parallel-safe: no,
  stream: PR-G, after: PRIV-V3)
- [ ] **(PRIV-FINAL)** Archive this completed plan only after G5 closes and all
  follow-ups are durably tracked. (owner: orchestrator, parallel-safe: no,
  stream: PR-G, after: PRIV-V5)

## Modularity and file-size guardrails

- Do not continue growing a monolithic `log_sanitizer.py` or privacy hook.
  Prefer `src/utils/privacy/` modules for classification, redaction, log-filter,
  and safe-storage responsibilities and `scripts/privacy_checks/` for AST,
  staged-blob, Git-metadata, and result-formatting responsibilities.
- Maintain one canonical sensitive-field registry; adapters may extend but not
  fork it. Add drift tests between artifact and runtime consumers.
- Scanner wrappers share process execution, timeout, protected-temp, and
  redacted-summary helpers. Tool-specific modules contain no policy duplication.
- UI consent/storage controls should use existing config/settings/service
  boundaries; avoid adding persistence logic directly to dialogs.
- Broad sink migration may be split by disjoint module groups after G1, but each
  group needs targeted tests before the next group begins.

## Testing strategy

- Use high-entropy but wholly synthetic canaries and synthetic DICOM datasets
  generated in `tmp_path`; never paste a real scanner finding into a fixture.
- Test positive detection and negative/redaction behavior, including multiline,
  lazy logging args, nested exceptions, Unicode, UNC, IPv6, archive member names,
  symlinks, and platform path variants.
- Capture every output channel: stdout, stderr, caplog, Qt dialogs, reports,
  debug files, config/cache/database metadata, hook/CI summaries.
- Assert canary absence, not only presence of `[REDACTED]`.
- Test wrapper exit codes for CLEAN, FINDINGS, SKIP, ERROR, and TIMEOUT.
- Use temporary Git repositories for author/message/ref/remote/history tests.
- Avoid golden binary clinical assets; existing reviewed synthetic RDSR fixtures
  remain governed by the media manifest.

## UX and UI

UX implementation remains subject to a desktop/Qt review. Required outcomes:

- First launch asks before automatic study-index persistence.
- Settings show what is stored, location, encryption state, retention, and
  clear/disable controls for recent paths, MPR cache, diagnostic logs, and index.
- Enabling detailed diagnostics warns that local troubleshooting data will be
  created, shows its location/retention, and provides a clear button.
- Dialogs show generic safe errors plus actionable recovery, not raw exception
  text or paths.
- User-selected exports still show the chosen destination as part of the export
  workflow; internal logs must not repeat it.

## Risks and mitigations

- **Over-redaction reduces diagnostics:** preserve operation identifiers, error
  classes, counts, durations, and local correlation IDs; never preserve basename.
- **False positives block development:** use typed/AST rules and narrow reviewed
  exceptions with reason, owner, hash/fingerprint, and expiry trigger.
- **Scanner reports become PHI:** protected temp storage, restrictive permissions,
  redacted summaries, explicit retention, and deletion by default.
- **Heavy OCR/NER slows hooks:** keep OCR in asset-review workflow; hash admission
  remains the blocking hook/CI layer.
- **Consent migration surprises existing users:** distinguish answered/unanswered
  state, document upgrade behavior, and test both paths.
- **Cross-platform permissions differ:** enforce POSIX modes, Windows ACL-capable
  APIs where available, and fail/warn according to an explicit platform policy.
- **GitHub tier lacks branch protection:** require local hooks and blocking CI,
  document manual merge discipline, and do not make the repository public merely
  to obtain hosted controls.
- **History rewrite is irreversible remotely:** create a local bundle/mirror
  backup and present hashes/counts before any user-approved mutation.

## Questions for user

These are gates, not blockers to Phases 1-5:

1. **Remote history (blocking G6 only):** retain 14 commits, replace `main` with a
   clean single-commit history in the existing private repo, or delete/recreate?
   Recommendation after G5: clean single-commit history, because the repo is new,
   small, private, and the user accepts recreation.
2. **Resolved 2026-07-16 — index:** automatic indexing is off pending explicit
   opt-in; new and unanswered legacy installations receive a one-time prompt.
3. **Resolved 2026-07-16 — MPR:** persistent derived-pixel caching is off pending
   explicit opt-in; disabling clears retained cache data.
4. **Resolved 2026-07-16 — diagnostics:** off by default, centrally redacted,
   capped at 2 MiB, pruned after seven days, with visible location and clear-now.

## Branch and rollout recommendation

- Proposed branch after G0: `feature/privacy-phi-pii-hardening`.
- No branch, commit, push, PR, remote rewrite, or remote deletion is performed by
  this plan.
- Land as reviewable slices: primitives -> sink migration -> enforcement ->
  artifact/Git -> scanners -> storage/UX -> CI/docs -> final verification.
- Roll back each slice independently; do not weaken the existing artifact gate
  during migration.

## Completion notes

Fill this section only with verified task IDs, commands, results, assessment
paths, manual-smoke evidence, and the user's final remote-history decision.

**Ready for orchestrator to assign coder after Gate G0.**

**PRIV-S3/U2-U5 evidence (2026-07-16):** 166 focused config, consent,
study-index, diagnostic, MPR, and controller tests passed.
Ruff passed on the touched scope; basedpyright reported 0 errors/0 warnings on
the new storage/config/diagnostic modules; the critical full-tree privacy audit
and `git diff --check` passed. Gate G4 was still open at this evidence point;
see the FIX2 re-review below.

**Gate G4 reviewer disposition (2026-07-16): changes required.** The headless
consent/settings flows and repaired diagnostic free-text regression are green,
but formal G4 remains open pending narrow fixes and independent retest:

- protected writes currently reject every target below the process working
  directory, which can block legitimate per-user config/diagnostic storage when
  the application starts from a home/root-like working directory;
- MPR-cache and diagnostic enablement coerce arbitrary persisted values with
  `bool(...)` instead of requiring a literal explicit `True`, and the legacy
  diagnostic environment/debug override can leave logging active while Settings
  reports the persisted choice as disabled;
- clear actions must report deletion/persistence failures accurately and index
  cleanup must cover all owned SQLite sidecars before the controls are treated as
  fail-closed.

Native human visual smoke remains an explicit follow-up because only disposable
offscreen Qt evidence was available; it is not claimed by this review.

**Gate G4 FIX2 re-review (2026-07-16): approved with follow-ups.** All five
review blockers are closed in code and exact regressions: protected writes use
an explicit source-checkout boundary while allowing legitimate private launch
roots; all privacy-sensitive enablement requires literal `True`; persisted
Settings is the sole diagnostic authority; failed persistence rolls back and
clear controls report truthful partial outcomes; and study-index cleanup covers
the database plus `-journal`, `-wal`, and `-shm`. Independent tester evidence is
green (11 exact, 38 focused, 27 adjacent, and 2,256 full-suite tests passed;
18 skipped), as are the critical privacy and 1,151-file artifact gates. Reviewer
rerun: 38 passed, Ruff clean, basedpyright 0 errors with nine pre-existing or
out-of-scope warnings. Formal G4 is accepted on the combined independent tests
and real-Qt disposable-profile headless evidence. **PRIV-V5 remains unchecked:**
native human visual smoke was unavailable, was not performed, and remains an
explicit release follow-up. Storage/user documentation must be refreshed after
the behavior is stable; G5 and G6 remain open.

**PRIV-SINK-REVIEW disposition (2026-07-16): changes required.** Independent
test/lifecycle evidence, multi-channel canary absence, protected report writes,
and the no-baseline/no-blanket-ignore audit are accepted. The reported 22
quantitative-fusion type errors are line-shifted legacy debt and out of this
slice; the direct reviewer run found two legacy warnings (missing SciPy stubs
and an unused parameter), not one. The sink slice is nevertheless reopened:

- `tests/fusion_audit_quantitative_verification.py` still prints its protected
  output directory dynamically. The zero-finding scan missed the `_dir`
  identifier, so S1/S4/C2 are not substantively complete. Extend the AST rule
  to cover directory/root aliases and add a category-only regression that
  proves no matched value is emitted.
- `print_redacted()` fails closed for arbitrary strings, but migrations pass
  complete f-strings to it. This reduces dependency-license rows, decoder and
  fusion metrics, and similar useful audit output to `[REDACTED]`.
  `PrivacyLogFilter` likewise replaces every no-argument message with the same
  marker. Add an explicit typed structural console/log event API: validated
  operation/category/error-class identifiers plus typed counts, durations,
  dimensions, booleans, and other reviewed metrics; arbitrary free text must
  remain redacted. Migrate the affected useful-output call sites to that API.
- Add positive regressions for safe semantic output as well as existing
  negative canary assertions. Tests must prove the reviewed operation/category
  and typed metrics survive, formatting/stream/flush/exit behavior is retained,
  and path, filename, UID, exception text, and nested synthetic canaries remain
  absent across stdout, stderr, caplog, dialogs, reports, and protected files.

PRIV-S1/S2/S4/S5/C2 are therefore unchecked. PRIV-C4 remains checked because
the channel canaries themselves exist and pass; it does not substitute for the
new positive semantic-output coverage. Route a narrow coder fix, independent
exact/focused/full verification, and this reviewer again before docs/G5.

**PRIV-SINK-OUTPUT-REREVIEW disposition (2026-07-16): changes required; soft
cap reached at iteration 6/6.** The original three blockers are repaired:
external audit output no longer prints the protected pair directory, directory
and contextual-root aliases have focused category-only coverage, useful
license/decoder/fusion/performance/application semantics survive typed output,
and arbitrary no-argument logger messages remain fail-closed. Independent
evidence is green through the fresh 2,277-pass suite. PRIV-S4 is therefore
closed.

The generic typed-event boundary creates one new blocking bypass. Runtime
validation accepts any syntactically valid suffix under an approved operation
namespace and accepts arbitrary syntax-matching values in reviewed identifier
slots. The AST checker treats the complete structural-event call as sanitized,
so it does not inspect a dynamic operation, category, identifier value, or
metric value. A reviewer probe showed zero AST findings for sensitive dynamic
values in each of those positions, and a valid `privacy.*` operation plus a
simple alphanumeric synthetic marker was emitted unchanged through both the
operation and package fields. Existing negative coverage uses an invalid
operation namespace and path/UID-shaped identifier values, so it does not test
this route.

Before another coder pass, reassess the boundary at the iteration soft cap.
The required design is an exact reviewed event-schema registry: each operation
must be a registered identity with explicit allowed category values, identifier
keys, and metric keys. Dynamic/unregistered operation and category labels must
fail closed. The AST checker must inspect structural-wrapper arguments instead
of blanket-trusting the call, reject sensitive references, and require a
static/reviewed operation plus schema keys. Add valid-namespace, simple
alphanumeric canaries; direct structural-object construction coverage; and
performance-label coverage. Preserve the already-green safe semantics,
stream/format/flush/exit behavior, lifecycle, and full regression. PRIV-S1,
S2, S5, C2, and C4 remain open; docs/G5 must not proceed.

**PRIV-SINK-SCHEMA-REVIEW disposition (2026-07-16): blocked / needs
user-architect; bounded exception exhausted.** The exact schema-v1 inventory,
strict loader, staged candidate-schema scan, operation/variant contracts,
narrow adapters, PyInstaller data inclusion, migrated call sites, and
independent 2,313-pass regression are accepted. The final adversarial review
nevertheless validated one residual construction bypass that contradicts the
sealed-runtime and fabricated-event requirements.

`StructuralEvent` blocks its public constructor, but a caller can allocate an
exact instance with `object.__new__`, inject arbitrary `_parts` with
`object.__setattr__`, and pass it to `render_structural_event()`. The renderer
checks the exact class and then emits the injected tuple without a seal or
schema revalidation. A simple synthetic marker was emitted unchanged. The AST
checker returned no finding for the allocation, private-state mutation, and
render path because its direct-construction rule covers only
`StructuralEvent(...)`. The existing fabrication regression allocates an empty
object and therefore exercises only the missing-attribute fallback, not
injected parts. Focused reviewer tests (**96 passed**) and both zero-finding
scanner lanes remained green, confirming this is a coverage and boundary gap
rather than a caught misuse.

Per the one-reset contract, do not route another broad coder loop. Mark the
bounded exception 1/1 and hard-stop to the user/architect. Any approved remedy
must make rendering depend on validated sealed state rather than exact type
alone (or revalidate every rendered part against the canonical schema), block
fabrication/private sealing/state mutation outside the canonical implementation
in static enforcement, and add injected-parts stdout/log canaries. PRIV-S1,
S2, S5, C2, and C4 remain open; S4 remains closed. Sentry remains out of scope.

**PRIV-SINK-BINDER-REVIEW historical disposition (2026-07-16): no further
custom binder work.** The independent full-suite, runtime final-boundary,
schema-v1 19/55, registered binder, and repository evidence are accepted as
executed, but change-aware review found uncovered lexical-provenance defects:

- normal and async function names are marked local before decorators, defaults,
  and annotations are visited. Python evaluates those expressions in the
  enclosing scope, so a canonical builtins alias reused as the function name
  can invoke the prohibited low-level allocation in a default or decorator with
  zero findings;
- class bodies are visited in the enclosing symbol map. A class-body assignment
  can therefore overwrite a canonical module binding in the checker and hide a
  prohibited use that occurs after the class definition;
- non-builtins imports are not registered as opaque local ownership. Legitimate
  modules or imported objects named like canonical builtins are falsely
  classified as prohibited low-level calls;
- function-local assignments are recorded only when reached, although Python
  determines local names lexically for the complete function body. A use before
  a later assignment can therefore inherit an enclosing canonical identity and
  generate a false positive even though runtime resolution is local.

Reviewer probes reproduced all four classes while the complete checker test
file still passed (**109 passed**) and the current critical lane remained green.
This invalidates the claimed enclosing-default, canonical-provenance, opaque
local-ownership, nested/local, and zero-false-positive closure. Per the bounded
contract, do not auto-route another repair: return to the user/architect with
the exact findings. PRIV-S1/S2/S5/C2/C4 remain open; S4 remains closed. Runtime
keyed final-boundary behavior and schema v1 were not changed or challenged by
this static-review defect. Sentry and remote/history operations remain out of
scope.

**Simplification decision (2026-07-16):** the user accepted the recommended
runtime-first design and cancelled further custom lexical scope/data-flow
emulation as disproportionate. Keep the direct, reliable syntactic checks
blocking. Treat sophisticated aliases, interprocedural flows, and indirect
provenance as advisory scanner/reviewer concerns. Runtime schema validation,
redaction, and safe-storage enforcement at final boundaries are authoritative.
No `scope_bindings.py` implementation is planned, and the architecture sketch
below is retained only as historical design analysis, not an active checklist.

### Cancelled historical proposal: PRIV-SINK-SCOPE-ARCH

**Architecture disposition (2026-07-16): cancelled; do not implement.**
Replace the sequential `_symbol_scopes` bookkeeping in
`scripts/privacy_checks/ast_rules.py` with a precomputed lexical scope graph and
a separate evaluation-order provenance walk. This is one bounded architecture
remediation, not another list of name-specific exceptions.

Use a custom AST binding prepass rather than `symtable` as the production
source of truth. `symtable` correctly classifies many compiler locals, frees,
globals, nonlocals, parameters, imports, classes, and comprehensions, but its
tables are awkward to map reliably back to duplicate lambdas/comprehensions and
do not describe expression provenance, alias values, or the fact that
decorators/defaults/annotations and class bases/keywords execute outside the
new body scope. Using it would still require the custom model and create a
second semantic source. It may be used only as a test oracle for selected
binding matrices. The custom prepass must key scopes and uses by AST node
identity and cover the supported Python 3.10-3.12 grammar explicitly.

The immutable prepass model must provide:

- scope records for module, normal function, async function, lambda, class,
  and every list/set/dict/generator comprehension; lexical parent, closure
  parent, body owner, child-scope mapping, parameters, local names,
  `global` names, `nonlocal` names, and binding occurrences;
- whole-body function/lambda locals collected before sink analysis from every
  parameter, import, assignment/annotation/augmentation/deletion target,
  function/class definition, loop target, with target, exception name, match
  capture, and applicable named expression, while never collecting through a
  nested scope;
- module and class bindings isolated in their own flow frames. Module/class
  lookup remains execution-order based; unlike functions, a later assignment
  must not make an earlier load local. A class body can read its enclosing
  function/module as Python permits, but ordinary class locals are not closure
  parents for methods, lambdas, comprehensions, or nested functions;
- explicit resolution for `global` to the module frame and `nonlocal` to the
  nearest enclosing function-like binding, skipping class frames. Analysis of
  a nested body must not mutate the enclosing analysis frame merely because
  the nested code could execute later;
- comprehension evaluation semantics: the outermost iterable is evaluated in
  the enclosing scope; iteration targets and the remaining iterables/filters/
  element execute in a function-like comprehension scope; named-expression
  targets bind to the containing non-comprehension scope where the grammar
  permits them;
- definition evaluation order: function/async decorators, defaults,
  keyword-only defaults, parameter annotations, and return annotation execute
  in the enclosing scope before the function name is flow-bound; lambda
  defaults execute before its parameter scope; class decorators, bases, and
  keywords execute in the enclosing scope, then the isolated class body runs,
  and only then is the class name flow-bound. With `from __future__ import
  annotations`, annotation expressions are non-executing and must not create a
  provenance false positive;
- opaque provenance for every parameter, non-builtins import, unknown
  expression, destructured target, loop/with/except/match target, and ordinary
  definition. Only implicit unshadowed builtins, `import builtins`, and
  `from builtins import ...` create canonical builtin provenance. Assigning a
  known canonical alias preserves it; rebinding makes it opaque. Constant-name
  `getattr` preserves provenance only when the callee itself resolves to the
  canonical builtin `getattr`, the owner is canonical, there are two or three
  positional arguments, no keywords, and the attribute is a string literal
  known to exist on that canonical owner (so an optional default cannot change
  the result);
- whole-tree analysis independent of `selected_lines`. Scope construction and
  provenance updates must use all lines; only violation emission applies the
  existing selected-span filter.

Use a three-file ownership cap: new
`scripts/privacy_checks/scope_bindings.py`, integration changes only in
`scripts/privacy_checks/ast_rules.py`, and regressions only in
`tests/test_git_hook_privacy_checks.py`. Keeping the scope model separate is
more reviewable than adding another large state machine to `ast_rules.py`.
Do not edit runtime structural-event modules, schema-v1 data/loader, scanner
coverage, CI, Sentry, product code, or Git/remote/history behavior.

Historical acceptance draft (cancelled; do not execute):

- [x] **PRIV-SCOPE-P0:** architecture contract records the scope kinds,
  binding inventory, lookup/closure parents, evaluation order, provenance
  rules, selected-line behavior, ownership cap, and ordered gates.
- [ ] **PRIV-SCOPE-P1:** fail-before tests reproduce normal/async function
  decorator, default, parameter-annotation, and return-annotation prohibited
  calls when the function name shadows the enclosing canonical alias; class
  decorator/base/keyword evaluation and class-body isolation are covered.
- [ ] **PRIV-SCOPE-P2:** legitimate import controls cover non-builtins modules
  and imported members named `builtins`, `object`, `getattr`, and `setattr`;
  whole-function local controls cover later assignment, import, definition,
  class, loop, with, except, match capture, and named expression.
- [ ] **PRIV-SCOPE-P3:** nested-scope controls cover method lookup skipping
  class locals, class-in-function closure, lambda defaults/parameters,
  comprehension outer-iterable versus target scope, and canonical/opaque
  `global` and `nonlocal` cases.
- [ ] **PRIV-SCOPE-P4:** selected-line tests prove that unselected bindings and
  later whole-function declarations affect a selected prohibited call while
  violations outside selected spans remain unreported.
- [ ] **PRIV-SCOPE-G1:** primary preserves prohibited and critical **19/19**,
  all existing binder/legitimate/registered tests, full-tree zero-finding
  lanes, and exact runtime/schema **19 operations / 55 performance labels**.
- [ ] **PRIV-SCOPE-G2:** independent tester runs the complete scope matrices,
  focused checker/privacy suites, runtime final-boundary and schema tests,
  Ruff, basedpyright, compile, artifact, advisory/critical privacy, harness,
  architecture, license, smoke, diff, and a fresh full pytest run.
- [ ] **PRIV-SCOPE-G3:** final reviewer inspects the scope graph and reruns the
  original four blocker classes plus adjacent class/method/comprehension and
  selected-line probes. No closure claim is allowed from a green matrix alone.

This draft no longer governs implementation or closure. The simplification
decision above supersedes its gates and handoff requirements.
