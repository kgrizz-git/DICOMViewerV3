# Privacy Runtime Storage Inventory

**Last updated:** 2026-07-15

This inventory distinguishes internal application state from destinations a
user explicitly selects. Paths and example clinical values are intentionally
omitted.

| Store | Contents | Location / protection | Current retention and controls | Required disposition |
|---|---|---|---|---|
| Application config | Recent/open/export directories and preferences | Per-user app config directory; atomic writes; private directory/file mode where the platform permits | Until changed; recent-file editor exists | Disclose path history; add one clear/disable control |
| Local study index | Patient/study/series/instance metadata and source paths | User-selectable or app-config directory; SQLCipher; key in OS credential manager | Until rows/database are removed; browser supports row removal | Default new installs to opt-in; expose encryption/path/clear state |
| MPR disk cache | Derived resampled pixel arrays and structural metadata | App config `mpr_cache`; containing directory is private where supported | LRU size cap, default 500 MB; no settings clear/disable control yet | Disclose derived pixels; add disable, size, and clear controls |
| Optional diagnostic log | Redacted event categories and structural data only | Protected per-user diagnostics directory; atomic private file | Opt-in environment flag; 2 MiB cap; seven-day policy metadata; programmatic clear | Add visible location/status/clear control before treating as user-ready diagnostics |
| Explicit exports | Screenshots, DICOM, video, QA, SR, ROI, JSON/CSV/XLSX/PDF chosen by user | User-selected destination | User-managed | Preserve destination; warn when formats may contain identifiers; never silently relocate |
| Scanner reports | Local security/PHI review status and temporary tool output | Protected temporary or per-user scanner-review directory | Wrapper cleanup; redacted summary | Never write raw matches to the checkout; document manual deletion/retention |
| In-memory caches | Loaded datasets, decoded pixels, thumbnails, navigation state | Process memory | Cleared on close/reset/exit | No persistence notice needed; do not serialize implicitly |

## Implementation rules

- Internal sensitive writes must use `utils.privacy.safe_storage`; the source
  checkout and current working directory are forbidden destinations.
- A write selected through an export dialog is user-directed and must retain
  that destination, but errors and logs must not repeat its path or basename.
- Privacy Mode masks display text only. It does not anonymize exports, encrypt
  cache content, or change these retention rules.
- Diagnostic and scanner summaries may contain operation names, counts, error
  classes, rule categories, and repository-relative source locations. They may
  not contain matched text, clinical fields, UIDs, filenames, host data, or
  exception values.

## Open product decisions

The remaining UI work needs explicit choices at plan Gate G4:

1. Whether an existing installation with study-index auto-add enabled keeps
   that setting or is asked again after migration. New installations should
   default to disabled until the user opts in.
2. Whether disabling the MPR disk cache also clears existing derived pixels or
   leaves them until the user presses **Clear**.
3. Whether optional redacted diagnostics retain seven days or are deleted when
   the application exits.
