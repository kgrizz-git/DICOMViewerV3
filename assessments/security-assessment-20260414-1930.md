# Security assessment — MPR2 (Save MPR as DICOM)

**Timestamp (filename):** 2026-04-14 19:30 UTC (aligned with scan run metadata)  
**Scope (delta):** `src/core/mpr_dicom_export.py`, `src/gui/dialogs/mpr_dicom_save_dialog.py`, and MPR-save wiring in `src/core/mpr_controller.py`, `src/gui/main_window.py`, `src/gui/main_window_menu_builder.py`, `src/core/app_signal_wiring.py`, `src/main.py`.  
**Precondition:** Full `pytest tests/` reported **439 passed** (per orchestration state / user).

## Executive summary

Static and lightweight secret checks on the scoped paths did **not** surface injection, unsafe deserialization, or shell-invocation issues. **Semgrep** rulesets `p/python` and `p/security-audit` completed with **exit code 0** on the listed files. **`semgrep scan --config auto`** could not be used on this Windows host because Semgrep’s registry fetch hit a **`UnicodeEncodeError` (cp1252)** while writing rules (environment limitation; not a code finding). **TruffleHog** and **Gitleaks** were **not available on PATH** in the activated venv session. **`detect-secrets`** reported **no findings** for the two primary new modules. **`pip-audit`** on the active venv reported **three upstream CVEs** in **cryptography**, **pypdf**, and **pytest** — **repo-wide baseline**, not specific to the MPR2 slice.

The main **actionable security-adjacent** note is **privacy / de-identification expectations**: the UI checkbox matches existing **`DICOMAnonymizer`** behavior (**patient group 0010 only**), but exported datasets and paths can still carry **study-level identifiers and dates**, and the writer **re-injects the original source `SeriesInstanceUID`** into **`ImageComments`** and **`ReferencedSeriesSequence`**. Risk is **user-expectation / compliance clarity** (low) rather than remote exploitation.

## Tools and commands run

| Step | Command / action | Result |
|------|-------------------|--------|
| Versions | `semgrep --version` (venv) | `1.157.0` |
| Availability | `trufflehog`, `gitleaks` | Not in PATH |
| Semgrep (auto) | `semgrep scan --config auto` on export + dialog | **Failed**: `UnicodeEncodeError` writing config (cp1252 / `\u202a` in remote content) |
| Semgrep (narrow) | `PYTHONUTF8=1` `semgrep scan --config p/python --quiet` → `mpr_dicom_export.py`, `mpr_dicom_save_dialog.py` | **Exit 0** |
| Semgrep (audit) | `semgrep scan --config p/security-audit --quiet` → all scoped files | **Exit 0** |
| Secrets | `.venv\Scripts\detect-secrets.exe scan` → `src/core/mpr_dicom_export.py` `src/gui/dialogs/mpr_dicom_save_dialog.py` | **`results`: {}** |
| Dependencies | `pip-audit` (current venv) | **3** known issues (see below); not MPR2-specific |

## Findings by severity

### Informational / low — De-ID scope vs “Anonymize” checkbox

- **Where:** `src/core/mpr_dicom_export.py` (`write_mpr_series`), `src/utils/dicom_anonymizer.py` (patient tags only).
- **What:** `DICOMAnonymizer` only modifies tags in **patient group (0010,xxxx)** per `is_patient_tag`. **Study date**, **study description**, **study/series UIDs**, and other non-0010 metadata remain in written files and influence **folder names** under `output_dir`. Additionally, `source_series_uid` is taken from the **original** `template_dataset` (before anonymization) and written into **`ReferencedSeriesSequence`** and **`ImageComments`** even when **`opts.anonymize`** is true.
- **Risk:** Users or workflows assuming “fully de-identified export” may **over-trust** the checkbox; residual **re-identification** linkage via UIDs and study tags is possible.
- **Disposition:** Acceptable if product intent is strictly **“patient identifiers”** (consistent with dialog text). Otherwise treat as **hardening / UX / policy** follow-up.

### Informational — Partial artifacts on cancel / failure

- **Where:** `write_mpr_series` writes files incrementally; cancel raises `MprDicomExportError` after some instances may already exist.
- **Risk:** **Operational** (orphan/partial series on disk), not network attack surface. Align with user docs / QA expectations.

### Baseline (not MPR2-introduced) — `pip-audit`

- **cryptography** 46.0.6 — CVE-2026-39892 — fix 46.0.7  
- **pypdf** 6.9.2 — CVE-2026-40260 — fix 6.10.0  
- **pytest** 9.0.2 — CVE-2025-71176 — fix 9.0.3  

Triage at **dependency / CI** level; outside the MPR2 code delta.

### None observed (checked)

- **Path traversal:** `output_root` comes from **`QFileDialog`** directory selection; nested directory names use **`_sanitize_folder_name`** (removes `<>:"/\|?*`).
- **`eval` / `exec` / `pickle.loads`** on user-controlled blobs: **not present** in scoped code.
- **`subprocess`** with **`shell=True`**: **not present** in scoped code.
- **World-writable file modes:** **not set** in export path (pydicom `dcmwrite` defaults).

## Remediation order (if acting beyond “slice clean”)

1. **Optional product clarity:** Tooltip or help text stating that anonymization is **0010 patient tags only**, and that **study/series UIDs and dates** may remain unless a stronger policy is implemented later.
2. **Optional export hardening (coder):** When `anonymize=True`, omit or replace **source UID** in **`ImageComments`** / **`ReferencedSeriesSequence`**, or map through anonymized identifiers if a project-wide de-ID profile exists.
3. **Repo maintenance:** Address **`pip-audit`** findings on **`requirements.txt` / venv pins** on a separate hygiene pass.

## Merge recommendation (secops)

**n/a** — no merge-blocking security defects identified in the MPR2 delta; privacy notes are **disclosure / enhancement** class.
