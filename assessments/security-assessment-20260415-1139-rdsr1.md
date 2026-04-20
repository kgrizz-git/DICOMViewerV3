# Security Assessment — RDSR1 targeted review

- Date: 2026-04-15
- Scope:
  - `src/core/rdsr_dose_sr.py`
  - `src/gui/dialogs/radiation_dose_report_dialog.py`
  - `src/main.py` (RDSR entrypoint)
  - `src/gui/image_viewer_context_menu.py`
  - `src/core/app_signal_wiring.py`
  - `src/core/roi_export_service.py`
  - Related tests/docs in this slice
- Branch: `feature/rdsr-dose-sr`

## Executive summary

Targeted scanner checks for this slice were clean for SAST, secrets, and dependency CVEs.  
One manual review finding remains: CSV/XLSX export values are written without spreadsheet-formula hardening, which can allow formula injection when exported files are opened in spreadsheet software.

## Commands run

1. Full local security wrapper (venv):
   - `.\.venv\Scripts\python.exe scripts/run_security_scan.py --semgrep --secrets --deps --report`
   - Result: pass (Semgrep, detect-secrets, TruffleHog, pip-audit)
2. Targeted Semgrep over changed security-sensitive files:
   - `.\.venv\Scripts\semgrep.exe --config=p/security-audit --config=p/python --error --quiet <scoped files>`
   - Result: pass (no findings)
3. Targeted secret scan over scoped files:
   - `.\.venv\Scripts\detect-secrets.exe scan <scoped files>`
   - Result: pass (`"results": {}`)

## Findings

### 1) Medium — Spreadsheet formula injection risk in CSV/XLSX exports

- Files:
  - `src/core/roi_export_service.py`
  - `src/core/rdsr_dose_sr.py` (CSV writer path)
- Description:
  - CSV/XLSX exports include string values from DICOM metadata and UI-derived text (for example series descriptions, pixel value strings, manufacturer/device fields) without guarding against values beginning with spreadsheet formula triggers (`=`, `+`, `-`, `@`).
  - Opening such files in Excel-like tools may evaluate attacker-controlled formulas.
- Impact:
  - Potential data exfiltration or command execution pathways via spreadsheet formula behavior, depending on viewer/tooling and environment hardening.
- Remediation:
  - Add a centralized export-cell sanitizer for CSV/XLSX text fields:
    - If value is a string and begins with `=`, `+`, `-`, or `@`, prefix with a single quote `'`.
    - Apply consistently to all textual export columns for CSV/XLSX writers.
  - Add unit tests with malicious-looking strings (for example `=HYPERLINK(...)`) to verify neutralization.

## PHI / privacy review notes

- Positive:
  - `RadiationDoseReportDialog` defaults `Anonymize export` to checked.
  - `dose_summary_to_export_dict(..., anonymize=True)` masks key identifiers (UIDs and device-identifying strings) before write.
  - Privacy-mode display masking for RDSR summary is present and dynamically refreshed.
- Residual:
  - Users can intentionally export non-anonymized RDSR summaries.
  - ROI export currently appears to include potentially identifying context fields by design; this is product-policy dependent and should be documented/confirmed.

## Recommendation

- `RDSR1-G` secops closure: **NO (not yet)**.
- Reason: unresolved medium-severity export hardening issue (formula injection class).
- Path to close:
  1. Implement CSV/XLSX formula hardening in `roi_export_service` and RDSR CSV export path.
  2. Add regression tests.
  3. Re-run targeted secops scans/review.
