# PHI / PII Repository Guardrails

**Last updated:** 2026-07-14

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
- Scans tracked text data, including JSON, CSV/TSV, YAML, INI, XML, HTML, Markdown, notebooks, and SVG, for local-path, patient-tag, private-network, and internal-endpoint indicators.
- Reads XLSX/XLSM cells for the same indicators.
- Recursively reads DICOM metadata, including sequence items, private tags, and station names; it recognizes a standard `DICM` preamble even when a filename has no DICOM extension.
- Fails closed for extensionless assets and image formats: AVIF, BMP, GIF, HEIC, ICO, ICNS, JPEG, JPEG 2000, JXL, PNG, SVG, TIFF, and WebP.

Notebook outputs must be stripped before review. Text or spreadsheet fixtures that legitimately need a synthetic identifier require an exact hash and permitted rule category in [`approved-phi-text-exceptions.json`](../security/approved-phi-text-exceptions.json); broad fixture-directory exemptions are not permitted.

Existing reviewed assets are pinned in [`security/approved-media-sha256.json`](../security/approved-media-sha256.json). A new or modified image, DICOM, or extensionless asset must be reviewed for PHI, including burned-in text, before its individual hash or reviewed image-tree hash is updated. The existing `resources/icons/` tree is approved as a unit; additions or modifications invalidate that approval.

The repository gate does **not** perform OCR or prove that a bitmap has no burned-in text. The hash manifest is admission control, not an automated de-identification claim. A human visual review (and OCR where appropriate) remains required before allowing any non-trivial image asset.

## Code and logging guard

`scripts/git_hook_privacy_checks.py` examines staged `src/*.py` changes for unsafe logging, raw exception dialogs, patient fields in output, and machine-specific paths. Use `sanitize_message` and `sanitize_exception` from `src/utils/log_sanitizer.py`; do not add `traceback.print_exc()` to application code. The `commit-msg` hook separately rejects local paths, the local username/hostname, RFC1918/ULA addresses, internal PACS/DICOM endpoints, and patient/study identifiers from commit messages without printing the matched value.

## Required checks

Activate the project environment, then run:

```bash
python scripts/check_no_phi_artifacts.py --root "$PWD"
python scripts/git_hook_privacy_checks.py
```

The installed pre-commit hook invokes the staged artifact gate, the repository harness, architecture check, agent smoke harness, Ruff, license check, and the privacy/logging gate. The `commit-msg` hook runs after Git writes the message and before the commit is finalized. The pre-push hook adds type, coverage, complexity, and security checks.

## Optional defense-in-depth tools

- `phi-scan` and Microsoft Presidio are isolated in `requirements-phi-tools.txt`: PhiScan's Click constraint conflicts with Semgrep, and Presidio's current NumPy constraint conflicts with the application's NumPy requirement. Use a dedicated environment; Presidio image redaction also requires OCR and a spaCy model.
- For secrets and dependency scanning, follow the [Security Tools CLI Guide](SECURITY_TOOLS_CLI_GUIDE.md).

When a scanner flags possible PHI/PII, do not paste the suspected value into a chat, commit message, issue, or documentation. Report only the affected path and rule category until the material has been safely reviewed.
