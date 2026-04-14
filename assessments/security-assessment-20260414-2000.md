# Security assessment — MPR2 (Save MPR as DICOM)

**Timestamp (filename):** 2026-04-14 20:00 local (Windows host; same calendar date as orchestration **MPR2** gate).  
**Scope (delta):** `src/core/mpr_dicom_export.py`, `src/gui/dialogs/mpr_dicom_save_dialog.py`, `src/core/mpr_controller.py` (save path), and wiring-only touch points: `src/gui/main_window.py`, `src/gui/main_window_menu_builder.py`, `src/core/app_signal_wiring.py`, `src/main.py`.  
**Precondition:** Full `pytest tests/` **439 passed** (per user / orchestration state).

## Executive summary

Targeted static review and **Semgrep** (`p/security-audit` + `p/python`, **200** rules, **3** files) reported **no findings**. There is **no** use of `eval` / `exec` / `pickle.loads`, **no** `subprocess` with `shell=True`, and **no** broad permissive `chmod` in scope. **Path components** derived from DICOM header fields are passed through `_sanitize_folder_name`, which strips Windows-forbidden characters and slashes, reducing directory-name injection risk; the **output root** is user-chosen via `QFileDialog` (intended write destination).

**TruffleHog** and **Gitleaks** were **not** present under the project `.venv` Scripts or on PATH in this session (not executed). **`detect-secrets`** on the two primary modules returned **`results`: {}**. **`pip-audit -r requirements.txt`** completed with **no known vulnerabilities** in that manifest pass (time-boxed; venv-wide audit may differ).

**Primary residual risk** is **privacy / expectation management**, not remote exploitation: the checkbox **“Anonymize patient identifiers (same as DICOM export)”** reflects **`DICOMAnonymizer`** behavior (**DICOM group 0010 only** per `utils/dicom_utils.is_patient_tag`). **Study- and series-level UIDs and dates** outside group **0010** remain in written files and in folder names built from `StudyDate`, `StudyDescription`, etc. When **`opts.anonymize`** is true, **`ReferencedSeriesSequence`** and **`ImageComments`** still carry the **original source `SeriesInstanceUID`** string from the pre-anonymize template, preserving cross-series linkage for PACS workflows but **not** a full de-identification profile.

## Tools and commands run

| Step | Command / action | Result |
|------|-------------------|--------|
| Semgrep version | `.\.venv\Scripts\Activate.ps1`; `semgrep --version` | **1.157.0** |
| Semgrep `--config auto` | `semgrep scan --config auto` on scoped `.py` files | **Failed**: `UnicodeEncodeError` / **cp1252** while Semgrep wrote fetched registry content (Windows console encoding; not an application defect) |
| Semgrep (bundled) | `$env:PYTHONUTF8='1'; semgrep scan --config=p/security-audit --config=p/python` → `mpr_dicom_export.py`, `mpr_dicom_save_dialog.py`, `mpr_controller.py` | **Exit 0**, **0 findings** |
| Secrets | `detect-secrets scan` → `src/core/mpr_dicom_export.py` `src/gui/dialogs/mpr_dicom_save_dialog.py` | **`results`: {}** |
| Dependencies | `pip-audit -r requirements.txt --desc on` (first lines / completion) | **No known vulnerabilities found** (requirements.txt pass) |
| Availability | `Test-Path` for `.venv\Scripts\trufflehog.exe`, `gitleaks.exe` | **False** / **False** |

**Note:** An earlier assessment for the same slice may exist as `assessments/security-assessment-20260414-1930.md`; this file records the **current** command transcript and conclusions for traceability.

## Findings by severity

### Informational / low — De-identification scope vs UI wording

- **Where:** `write_mpr_series` in `src/core/mpr_dicom_export.py` with `opts.anonymize`; `src/utils/dicom_anonymizer.py` (patient group **0010** only).
- **What:** Exported DICOM can still contain **StudyInstanceUID**, **FrameOfReferenceUID**, **study date/description** in tags and path segments, and **source series UID** in **`ReferencedSeriesSequence`** / **`ImageComments`** (see template-based `source_series_uid` around the per-slice loop).
- **Risk:** Operational / compliance **expectation gap** if users assume checkbox equals **full** DICOM de-identification (e.g. PS3.15 Basic / Cleanse profiles).
- **Remediation order (if product requires):** (1) UX copy or user-docs clarification; (2) optional stronger profile (new option) if regulatory need—**coder** scope, with tests.

### Informational — Partial series on disk after cancel

- **Where:** `write_mpr_series` writes sequentially; `progress_callback` returning false raises **`MprDicomExportError("Export cancelled.")`** without rolling back prior files.
- **Risk:** **Operational** (orphan files / inconsistent series), not attacker-driven.

### None blocking — Path traversal from attacker-controlled strings

- **Assessment:** `output_dir` is the user’s chosen folder. Subfolders use `_sanitize_folder_name` on metadata strings; no `..` injection via those components in typical inputs. Residual risk is limited to **user-chosen sensitive directories** (policy/UX).

## Remediation order

1. **None required for merge** from a classical **AppSec** perspective (no injection / deserialization / shell findings in scope).
2. **Optional (product):** clarify or extend anonymization policy if “full de-ID” is a stated goal.
3. **Tooling (CI):** prefer **pinned Semgrep rules** or **UTF-8** runners so `--config auto` is reproducible on Windows developers’ machines.

## Cloud

No **Cloud: REQUEST** — delta scans completed locally.
