# PHI / PII Repository Guardrails

**Last updated:** 2026-07-16

**Audience:** contributors and coding agents who add, generate, inspect, or export files in this repository.

This application processes clinical imaging. Treat every study, export, screenshot, log, spreadsheet, and unrecognised binary as potential protected health information (PHI) or personally identifiable information (PII) until it has been reviewed. Do not commit it merely because it is useful for debugging or testing.

## Non-negotiable rules

1. Never commit real patient studies, screenshots, pixel data, reports, exports, configuration captures, or local paths.
2. Use wholly synthetic fixtures. DICOM fixtures must contain only the approved synthetic identifiers and must not carry real nested sequence values.
3. Do not bypass hooks with `--no-verify` to admit a data or media file. Resolve the finding or obtain an explicit review decision.
4. Do not put patient names, identifiers, dates of birth, accession numbers, local paths, raw exceptions, or unredacted datasets into logs, dialogs, test assertions, issue text, or documentation.

## What the blocking artifact gate covers

`scripts/check_no_phi_artifacts.py` is run by the pre-commit hook and in the **No PHI artifacts tracked** GitHub Actions job.

- Denies runtime artifacts such as pytest captures, application config files, backups, `.DS_Store`, and diagnostic `.log`, `.trace`, `.err`, `.out`, `.pkl`, and `.cache` files—even if force-added.
- Denies every force-added file under the local-only `data/` (except its
  `.gitkeep`), `test-DICOM-data/`, `sample-DICOM-gitignored/`,
  `decoder-spike-artifacts/`, `resources/screenshots-ignored/`, `logs/`,
  `.sonar-local/`, `.phi-tools/`, `tmp/`, and `backups/` roots. It also reads the staged
  `.gitignore` blob and blocks removal of any privacy-critical ignore rule, so
  restoring a rule only in the working tree cannot mask a staged deletion.
- Scans tracked text data, including JSON, CSV/TSV, YAML, INI, XML, HTML, Markdown, TeX, PostScript/EPS, notebooks, and SVG, for local-path, patient-tag, private-network, and internal-endpoint indicators.
- Reads XLSX/XLSM cells for the same indicators. XLSX/XLSM, Office/OpenDocument packages (`.docx`, `.docm`, `.pptx`, `.pptm`, `.odt`, `.ods`, `.odp`, and templates/slideshows), and Apple iWork packages (`.pages`, `.numbers`, `.key`) also require manual review because they can embed images and other opaque content.
- Extracts text from every unencrypted PDF page and fails closed when a PDF cannot be read. PDFs, PostScript/EPS, and notebooks require hash-bound manual review because they can contain rendered or embedded images that text extraction cannot prove safe.
- Recursively reads DICOM metadata, including sequence items, private tags, and station names; it recognizes a standard `DICM` preamble even when a filename has no DICOM extension.
- Inspects ZIP, TAR, GZip, BZip2, and XZ containers in memory, including nested containers up to a bounded depth. It scans text/PDF/Excel payloads and detects DICOM by extension or preamble inside them. Archives and document packages always require hash-bound manual review. Encrypted, malformed, oversized, deeply nested, and unsupported archive formats (currently 7z, RAR, and Zstandard) fail closed rather than being waived by the hash manifest.
- Fails closed for extensionless assets and image formats: AVIF, BMP, GIF, HEIC, ICO, ICNS, JPEG, JPEG 2000, JXL, PNG, SVG, TIFF, and WebP.

Notebook outputs must be stripped before review. Text or spreadsheet fixtures that legitimately need a synthetic identifier require an exact hash and permitted rule category in [`approved-phi-text-exceptions.json`](../security/approved-phi-text-exceptions.json); broad fixture-directory exemptions are not permitted.

Existing reviewed assets are pinned in [`security/approved-media-sha256.json`](../security/approved-media-sha256.json). A new or modified image, DICOM, archive, document package, or extensionless asset must be reviewed for PHI, including burned-in text, before its individual hash or reviewed image-tree hash is updated. The existing `resources/icons/` tree is approved as a unit; additions or modifications invalidate that approval.

The repository gate does **not** perform OCR or prove that a bitmap, PDF, or PostScript file has no burned-in text. The hash manifest is admission control, not an automated de-identification claim. A human visual review (and OCR where appropriate) remains required before allowing any non-trivial image or document asset.

## Code and logging guard

`scripts/git_hook_privacy_checks.py --staged` examines staged application,
security-script, and external-data-test changes for unsafe logging, console
output, raw exception dialogs, debug payloads, patient/path/UID/network fields,
and traceback output. `--all` performs the corresponding full-tree audit.
Findings contain only repository-relative path, line, and rule category. Use the
shared APIs under `src/utils/privacy/`; do not add raw exception or data values
to an output sink. The `commit-msg` hook separately rejects local paths,
identity/network data, and clinical identifiers without printing matched text.

This hook is intentionally a conservative **syntactic** guard, not a complete
Python alias, scope, interprocedural, or data-flow proof. Direct unsafe sink
calls, direct low-level structural-event fabrication, schema misuse, and other
locally recognizable violations are blocking. More indirect alias/data-flow
patterns belong in advisory Semgrep/Hounddog review or focused human review;
do not expand this hook into a custom Python interpreter. The authoritative
application defense is fail-closed schema validation and redaction at every
final console, logging, dialog, report, and protected-storage boundary.

## Required checks

Activate the project environment, then run:

```bash
python scripts/check_no_phi_artifacts.py --root "$PWD"
python scripts/git_hook_privacy_checks.py --staged
python scripts/git_hook_privacy_checks.py --all
python scripts/git_hook_privacy_checks.py --all --critical
```

Staged mode blocks every newly introduced privacy rule. Full `--all` is the
advisory migration inventory for legacy print/debug debt; `--all --critical` is
the blocking pre-push/CI lane for directly recognizable raw dialogs, implicit
exception/traceback logging, unsafe logger/stream sinks, structural-event
fabrication/schema misuse, parse failures, and unreadable inputs. A clean
static scan is defense in depth; it is not proof that every possible Python
alias or runtime value is safe.

The installed pre-commit hook invokes the staged artifact gate, the repository harness, architecture check, agent smoke harness, Ruff, license check, and the privacy/logging gate. The `commit-msg` hook runs after Git writes the message and before the commit is finalized. The pre-push hook adds type, coverage, complexity, and security checks.

## Optional defense-in-depth tools

Coverage XML, test captures, scanner reports, crash telemetry, and repository
analysis must not be uploaded to Codecov, Coveralls, SonarQube Cloud,
DeepSource, Sentry, or similar third-party services. CI may print aggregate
coverage counts and may report value-free findings inside the private GitHub
repository, but it must not upload coverage/source-analysis payloads to an
external vendor. Keep the corresponding GitHub Apps/integrations disabled.
Secret scanners must also run without network verification of suspected
credentials; use TruffleHog `--no-verification` and value-redacted output.

- `phi-scan`, Presidio, and `dicom-phi-scan` are exactly pinned in the isolated
  `requirements-phi-tools.txt` environment. Do not install them into the app
  environment. PhiScan is restricted to staged data-like blobs; the DICOM and
  media lanes are explicit local reviews, not proof of de-identification.
- **Hounddog is local-only and non-blocking until further user direction.** Do not create an account, connect a repository, upload code or findings, enable cloud/hosted processing, add it to CI, or make it a required hook. Any future evaluation is restricted to an isolated working copy, source/configuration only, wholly synthetic findings, and safe local-only reports.
- Run the wrappers with `python scripts/privacy_tool_review.py hounddog`,
  `phiscan`, `media PATH`, or `dicom PATH`. Exit states are distinct:
  `CLEAN=0`, `FINDINGS=1`, `ERROR=2`, `SKIP=3`; a skip is never a pass.
- For secrets and dependency scanning, follow the [Security Tools CLI Guide](SECURITY_TOOLS_CLI_GUIDE.md).

The pre-commit hook invokes `scripts/run_conditional_privacy_reviews.py` only
when the staged index contains a relevant high-risk shape: data-like files under
`data/`, `resources/`, `tests/data/`, or `tests/fixtures/`; OCR-compatible raster
images; or DICOM extensions. It materializes exact staged blobs under opaque
names in an owner-only temporary directory. PhiScan and the DICOM reviewer skip
with an explicit status when the isolated `.phi-tools` environment is absent;
OCR/metadata review uses the isolated environment when present and otherwise
uses locally available Tesseract/ExifTool. Findings and missing optional tools
remain advisory; the artifact/hash/human-review gate remains blocking.

A proposed `main` push runs Hounddog only after all blocking pre-push gates pass.
This is preferable to a generic last-run timestamp: staged asset reviews are
bound directly to current index bytes, while the fast source-wide data-flow scan
is rerun at the promotion boundary. SonarQube alone uses a 30-day freshness
record because it is materially heavier.

When a scanner flags possible PHI/PII, do not paste the suspected value into a chat, commit message, issue, or documentation. Report only the affected path and rule category until the material has been safely reviewed.
