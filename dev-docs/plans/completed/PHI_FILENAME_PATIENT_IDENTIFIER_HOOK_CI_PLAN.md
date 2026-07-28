# PHI Filename & Patient-Identifier Hook/CI Hardening Plan

**Status:** implemented
**Last updated:** 2026-07-27 (revision 4: **expanded `PATIENT_NAME_TOKENS` from ~71 to ~266**, replacing the UK-census-weighted seed with an SSA-given-names + US-Census-surnames base (collision-filtered; `ward` excluded as a hospital-ward collision) so US Hispanic/Asian/African patient surnames are covered. **Cleaned up `SAFE_NAME_COMPOUNDS`**: removed dead single-word entries (`jackknife`, `davidson`, `evansville`, `goldsmith`, `johnson`, `jenkins`, `johansson`, `rabin_karp`) that the token-based lane can never flag — `johnson`/`jenkins`/`johansson` were real surnames wrongly parked in the allowlist — and added an explicit membership rule (an entry belongs only if its stem splits into ≥1 token). Revision 3: **reversed the basename-only name-lane scope** — this is a DICOM/medical-imaging repo where patient names routinely appear as directory components (`patients/SMITH_JOHN/…`), so basename-only left the *dominant* leak shape uncaught; the name lane now scans every path component like the identifier lane, with a new review-gated `SAFE_DIR_COMPOUNDS` allowlist for genuine org directories as the FP control instead of scope narrowing. Also: fixed the content-lane word-boundary spec — bare `\b` misses `_`-glued names like `patient_smith_id`; switched `NAME_CONTENT_PATTERN` to explicit ASCII-alnum boundary assertions. Fixed the migration audit-script invocation to `python -m scripts.audit_filename_phi` so the `scripts` package import resolves. Added a `casefold()` length-stability caveat for future non-ASCII seeds. Added a "Rejected assessment suggestions" section giving explicit merits-based rationale for declining warn-only mode, external config, and automated seed expansion — rev 2 had deferred these without stating why. Rev 2 added: audit script, rollback procedure, migration workflow, `SAFE_NAME_COMPOUNDS` governance, casefold/`os.path.splitext`/lookbehind specs, and directory/boundary test cases.)
**Owner:** kevin (with agent assistance)
**Blocking enforcement:** pre-commit hook + `.github/workflows/privacy-gates.yml` CI job

## Problem

The existing artifact gate (`scripts/check_no_phi_artifacts.py`) already matches
a small set of *structurally* sensitive filenames (e.g. `patientid-…`,
`mrn-…`, `accession-…`, `patientname-Smith^John`) plus local identities and
network addresses. It also blocks runtime artifacts and content-bearing data
files. But two common leakage patterns are not yet covered by the **filename**
lane — only caught later by the content lane, if at all:

1. **Common patient surnames / given names** appearing directly in tracked
   filenames (`Smith`, `jack`, `JONES`, `bob`, `gupta`, `martin`, …). These do
   not match the existing `SENSITIVE_FILENAME_PATTERNS` regexes, which require a
   *prefix token* (`patientid`, `mrn`, `accession`, `patientname`, …) before the
   name.
2. **Structured patient-identifier strings** such as `MRN_123456`,
   `acc-1234567`, `ACC_0001`, `MRN-0099-a`, that use a keyword + separator +
   digits run but escape the current patterns because the current `[-_]` token
   assumes the prefix is glued with `[-._]` only and the digit run is >= 4
   characters.

Both classes are real PHI/PII and must be **blocking** at commit and on CI.

## Non-goals

- No OCR, no Presidio, no Hounddog changes. This is a static filename/identifier
  gate only.
- No new third-party dependency. Pure-Python regex + a managed name list.
- No scanning of file *contents* (that is the existing content lane). Only the
  basename and the staged filename are evaluated, plus the same name list
  applied as a content rule so a name like `Smith` inside a committed CSV/JSON
  line also blocks.
- Do not commit the plan, the new fixture names, or any new manifest entries.
  This document only describes the intended approach.

## Design principles (matching existing guardrails)

- **Never echo matched values.** Findings carry only the repository-relative path,
  line number, and rule category. The same redaction discipline as
  `privacy_checks/models.py` / `check_no_phi_artifacts.py:298-305` is reused.
- **Fail closed on read errors** and on an unreadable name list.
- **Reviewed exceptions** are hash-bound (`security/approved-phi-text-exceptions.json`)
  for content findings, and an inline `privacy-check: allow[rule]`
  (`scripts/privacy_checks/allowances.py`) marker is reused for source lines.
- **The blocking artifact gate is the pre-commit gate and the CI gate.** Hook can
  be skipped with `--no-verify`, so CI is the authoritative one.
- **Local-identity detection already exists** (`local_identities()` at
  `check_no_phi_artifacts.py:308`) and must continue to work — the new name
  lane is a strict superset for thesurname/given-name category, not a
  replacement.

## Where the new logic lives

A single new module owns the new patterns so the artifact gate and CI share
them. The privacy-output hook (`git_hook_privacy_checks.py` /
`privacy_checks/text_rules.py`) is **not** modified — that module is AST/sink
oriented and its `scan_staged` orchestrator only iterates Python source paths
(see `scripts/privacy_checks/scanner.py`), so a data-content check would have
no call site there. All name/identifier scanning stays within
`check_no_phi_artifacts.py`, which already owns both the filename lane
(`check_paths`) and the content lane (`check_contents`).

```
scripts/privacy_checks/names.py   (new)
```

It exposes:

- `PATIENT_NAME_TOKENS`: a `frozenset[str]` of lowercased common patient
  surnames/given names (seed list below; extensible from a single constants
  block, not a hidden data file).
- `PATIENT_IDENTIFIER_PATTERN`: a single `re.Pattern[str]` for structured
  identifier strings in filenames (one pattern, not two — see Pattern design).
- `NAME_CONTENT_PATTERN`: a `re.Pattern[str]` built once from
  `PATIENT_NAME_TOKENS` for the content lane.
- `SAFE_NAME_COMPOUNDS`: a `frozenset[str]` of lowercased safe full-basename
  stems that would otherwise match a name token (seeded below; review-gated).
- `SAFE_DIR_COMPOUNDS`: a `frozenset[str]` of lowercased safe directory-component
  stems (org units like `smith_lab`) that would otherwise match a name token
  (review-gated, seeded from the pre-merge audit; see Directory-name scope).
- `name_in_path(path) -> str | None` — returns a rule category string
  (`"patient-name-in-filename"` / `"patient-identifier-in-filename"`) or
  `None`. Never returns the matched value. Checks **every path component**
  (directories and basename — see Directory-name scope). Each component is
  split on `[-_.\s]`, lowercased, and compared to the token set. Before token
  matching, each directory component (suffix-stripped) is checked against
  `SAFE_DIR_COMPOUNDS` and the basename stem against `SAFE_NAME_COMPOUNDS`; a
  compound match short-circuits that component so it does not hit.
- `IDENTIFIER_CONTENT_PATTERN` and `NAME_CONTENT_PATTERN` — precompiled
  `re.Pattern[str]` consumed directly by `_content_reasons` (see Content lane).

Const names are stable; the lists are pure literals so they are inspectable in
review and create no new binary asset. The data file
`security/patient-name-watchlist.json` is an option for future extension but is
**out of scope** for this slice — a literal in-source list is simpler to review
and avoids adding a new security-managed data file.

### Integration with `check_no_phi_artifacts.py`

The existing functions are *augmented in place*, not replaced:

- `_path_reasons(path, identities)` (`check_no_phi_artifacts.py:350`) currently
  appends `"sensitive-looking filename"` when any of
  `SENSITIVE_FILENAME_PATTERNS` matches a path component. The new logic adds
  **two** additional reason strings returned by `name_in_path`:
  `"patient-name-in-filename"` and `"patient-identifier-in-filename"`. The
  existing `SENSITIVE_FILENAME_PATTERNS` block stays unchanged (it still
  catches the `patientname-Smith^John` DICOM-style shape); the new
  `PATIENT_IDENTIFIER_PATTERN` broadens the keyword/digit coverage without
  weakening the older patterns.
- `_content_reasons(text, identities)` (`check_no_phi_artifacts.py:500`)
  iterates `CONTENT_RULES: list[tuple[re.Pattern[str], str]]`. Two new
  `(pattern, reason)` tuples are appended to that list:
  `(IDENTIFIER_CONTENT_PATTERN, "patient-identifier-in-content")` and
  `(NAME_CONTENT_PATTERN, "patient-name-in-content")`. Because
  `_content_reasons` already does `match = pattern.search(text)` and returns
  the reason string, no signature change is needed — the new module just
  supplies the compiled patterns and the reason strings as plain literals.

No function in `check_no_phi_artifacts.py` changes its return type or caller.
The new module is a drop-in supplier of constants and helpers.

## Pattern design

### 1. Common patient surname/given-name lane (filename)

Match a *token* equal to one of `PATIENT_NAME_TOKENS` in **any path component**
(each directory and the basename), scoped to word boundaries and only when it
appears *as an identifying segment* (not part of a longer compound like
`smith_waterman.py`, which is a real algorithm name).

Rule `patient-name-in-filename`:

- Token-aware: split each path component on `[-_.\s]`, casefold each token (use
  `str.casefold()` rather than `str.lower()` for consistency with future
  non-ASCII additions; both behave identically on the ASCII seed list), and
  compare to the casefolded `PATIENT_NAME_TOKENS`. Comparisons use
  casefold, not `re.IGNORECASE`, for the token membership path. **Caveat:**
  `casefold()` is not length-stable (`ß` → `ss`, `ﬁ` → `fi`), so seed tokens
  must be stored already-casefolded; a raw non-ASCII seed added later without
  pre-casefolding would silently never match its own source form. The seed
  list is ASCII-only for this slice, so this is a forward-looking guard, not a
  present bug.
- Refuse initials-only ambiguity: single-letter tokens are ignored.
- Before token matching, compute the **suffix-stripped basename stem** with
  `os.path.splitext` (strips one trailing extension only, so `foo.tar.gz` ->
  `foo.tar`; documented here so reviewers know multi-suffix names keep an
  inner suffix and are then token-split). Casefold the stem and compare to
  the casefolded `SAFE_NAME_COMPOUNDS`. A compound match short-circuits the
  basename component so `smith_waterman.py`, `robinson_crusoe.md`, and
  `martin_fowler_refactoring.txt` — whose split *does* contain a token
  (`smith`, `robinson`, `martin`) — do not block. (Stems like `jackknife.txt`
  or `davidson_profile.csv` never split into a listed token in the first place,
  so they need no allowlist entry — see the `SAFE_NAME_COMPOUNDS` membership
  rule.) This is a review-gated escape hatch for true compound names that
  contain a surname token; it does not allowlist a simple `smith.txt`.
- Each **directory** component (casefolded, suffix-stripped) is likewise checked
  against `SAFE_DIR_COMPOUNDS` before token matching, so a reviewed org dir like
  `smith_lab/` short-circuits while a bare patient-named dir like `smith/` or
  `doe^jane/` still hits (see Directory-name scope).

Seed `PATIENT_NAME_TOKENS` (lowercase, sorted, duplicates removed). Derived
from **SSA given names** (recent + mid-century top-100 each sex) and **US
Census top-~200 surnames**, plus a set of internationally common surnames, then
**collision-filtered**: English/code words and ambiguous short tokens that would
false-positive on a blocking gate are deliberately excluded (e.g. `park`, `sun`,
`grace`, `wu`, `cho`, and — specific to a clinical repo — **`ward`**, which
collides with "hospital ward"). ~266 tokens:

```
abdi, abigail, adams, adeyemi, aguilar, aiden, alexander, allen,
alvarez, amanda, amelia, amy, anderson, andrew, angela, anna, anthony,
asher, ashley, aurora, ava, bailey, baker, barbara, bell, benjamin,
betty, brandon, brian, brown, callahan, camila, campbell, carol, carter,
castillo, charles, chavez, chen, chloe, choi, chowdhury, christopher,
clark, cohen, coleman, cook, cooper, cortez, cruz, cynthia, daniel,
david, davies, davis, deborah, delgado, delilah, dennis, desai, diallo,
donald, donna, donnelly, dorothy, edward, edwards, elijah, elizabeth,
ella, emily, emma, emmett, eric, ethan, evans, evelyn, ezra, fitzgerald,
flores, frank, friedman, fuentes, garcia, gary, george, goldberg,
gonzalez, grayson, green, gregory, guerrero, gupta, gutierrez, hall,
harper, harris, hazel, hernandez, hill, howard, huang, hudson, hughes,
isabella, iyer, jace, jack, jackson, jacob, james, jang, jason, jayden,
jeffrey, jennifer, jeong, jerry, jessica, jimenez, john, johnson,
jonathan, jones, jordan, joseph, joshua, julian, justin, kai, kang,
kapoor, karen, kathleen, katz, kelly, kenneth, kevin, khan, kim,
kimberly, king, kumar, larry, laura, layla, lee, leo, levine, lewis,
liam, linda, lisa, liu, logan, lopez, lucas, margaret, mark, martin,
martinez, mary, mason, mateo, matthew, mcdonald, mehta, melissa,
mendoza, mia, michael, michelle, mila, miller, mitchell, moore, morales,
morgan, morris, murphy, mwangi, nair, nancy, nelson, nguyen, nicholas,
noah, nora, nwosu, obrien, okafor, oliver, olivia, ortiz, patel,
patricia, patrick, paul, penelope, perez, ramirez, ramos, raymond,
rebecca, reddy, reyes, richard, riley, rivera, robert, roberts,
robinson, rodriguez, rojas, romero, ronald, rosenberg, ruiz, russell,
ryan, ryder, salazar, samuel, sanchez, sandra, sarah, scarlett,
schwartz, scott, sebastian, shah, sharma, sharon, shirley, singh, smith,
sophia, stephanie, stephen, steven, sullivan, susan, taylor, theo,
thomas, thompson, timothy, torres, turner, vasquez, violet, walker,
wang, watson, white, william, williams, wilson, wood, wright, yoon,
young, zhang, zhao, zhou, zoey
```

The list gives US demographic coverage — the top US Hispanic surnames (Garcia,
Rodriguez, Martinez, Hernandez, Lopez, Gonzalez, Perez, Sanchez, Ramirez,
Torres, Flores, Rivera), East/South Asian surnames (Nguyen, Chen, Wang, Kim,
Patel, Singh, Gupta, Shah), African surnames (Okafor, Nwosu, Mwangi, Diallo,
Adeyemi, Abdi), and modern + mid-century SSA given names — which a UK-census
seed misses entirely. It is still **not** a de-identification engine; the
privacy guardrails doc states the artifact gate is admission control, not a
de-identification claim (`dev-docs/PHI_PII_REPOSITORY_GUARDRAILS.md:38-40`).
Growth stays PR-reviewed and collision-checked against the tracked tree (see
governance).

Seed `SAFE_NAME_COMPOUNDS` (lowercased full basename stems, suffix-stripped;
review-gated and intentionally narrow):

```
smith_waterman, robinson_crusoe, martin_fowler, gupta_blei, lee_angle,
cooper_pair, hill_climbing, bell_curve, cook_distance, green_function,
young_modulus
```

**Membership rule (this fixes a bug in the earlier draft):** because the name
lane is **token-based** (split the stem on `[-_.\s]`, whole-token equality
against `PATIENT_NAME_TOKENS`), an entry only belongs here if splitting its stem
yields **≥1 token that is in `PATIENT_NAME_TOKENS`**. A single-word stem never
splits into a listed token, so it can never match the token lane and must **not**
be added. The earlier draft listed single words — `jackknife`, `davidson`,
`evansville`, `goldsmith`, `johnson`, `jenkins`, `johansson` — none of which the
token lane can ever flag (e.g. `jackknife` is one token, not `jack`); they were
dead entries and are removed. `johnson`/`jenkins`/`johansson` are additionally
harmful there: they are real surnames, so parking them in the allowlist would
silently neutralize them if later added as tokens (`johnson` is the #2 US
surname). `rabin_karp` is also dropped because neither `rabin` nor `karp` is a
token, so it never hits.

The list must be reviewed before merge: run the pre-merge audit (rollout step 2)
to split every tracked basename on separators against `PATIENT_NAME_TOKENS`,
collect every real-tree hit that is a legitimate compound, and add only those
stems. Anything that is a bare surname (e.g. `smith.txt`) is **not** added here;
it stays blocked and is resolved by renaming the file, never by allowlisting.

Seed `SAFE_DIR_COMPOUNDS` (lowercased directory-component stems for genuine
organizational units, review-gated; **empty at first** and populated from the
pre-merge audit — a directory stem is added only with reviewer sign-off that it
names an org unit, not a patient):

```
smith_lab, davidson_group
```

A bare patient-name directory (`smith/`, `doe^jane/`) is **never** added here;
it is renamed. The two seeds above are illustrative and must be re-derived from
the actual tracked tree during the migration audit.

### 2. Structured patient-identifier lane (filename)

Broaden the keyword/digit coverage beyond the existing
`SENSITIVE_FILENAME_PATTERNS` (which only matches `patientid|mrn|accession|
account` glued with `[-._]` followed by 4+ chars). The new
`PATIENT_IDENTIFIER_PATTERN` is a **single** regex; the earlier draft had two
near-identical alternations where the optional-separator variant subsumed the
no-separator variant, so the redundant second pattern is removed.

Rule `patient-identifier-in-filename`:

- Keyword set: `mrn`, `acc` / `accession`, `accn`, `patientid`, `pid`,
  `studyid`, `encounter`, `caseid` (case-insensitive). **`account` is
  intentionally excluded** — see False-positive handling below.
- Separators: `-`, `_`, `.`, or space, all optional so `MRN12345` and
  `MRN_12345` both match.
- Min digit run: **3** for MRN/PID/study identifiers (catches `MRN_007`);
  **5** for `acc`/`accession`/`accn` (matches the user example `acc-1234567`
  and avoids `acc-2024` year-tag false positives).
- Anchoring: the keyword must be a leading or separated token, not a substring
  inside another word (so `accidentally-…`, `mrndataset` without a separator
  are *not* matched). The pattern uses `(?<=[\s_.\-])` lookbehind behind a
  `^|` alternation. Python's `re` module supports fixed-width lookbehind;
  this class is single-char so it is fixed-width and compatible. Variable-
  width lookbehind is not used. Add explicit tests for separator combos
  (`MRN-1`, `MRN_1`, `MRN.1`, `MRN 1`, `MRN1`)

Regex sketch (single pattern; final form TBD in implementation, kept
conservative here):

```python
re.compile(
    r"(?:^|(?<=[\s_.\-]))"
    r"(?:"
    r"  (?:mrn|patientid|pid|studyid|encounter|caseid)[\s_.\-]?\d{3,}"
    r"  |"
    r"  acc(?:ession|n)?[\s_.\-]?\d{5,}"
    r")",
    re.IGNORECASE,
)
```

The two digit floors are split with an inline alternation so the harder
`account`-style false positives stay rare while still catching the short
`MRN_007` shape the user asked about. `account` as a keyword is **dropped**
from this lane: in practice filenames like `account_123_config.csv` or
`account_balance.csv` are common administrative fixtures and the keyword is
not specific to patient identity. The existing `SENSITIVE_FILENAME_PATTERNS`
entry `account[._-]…` at `check_no_phi_artifacts.py:298-305` already covers the
high-confidence `account-` shape with a 4-char floor and remains in place.

### Directory-name scope

`_path_reasons` (`check_no_phi_artifacts.py:356`) splits the full path on `/`
and inspects each component.

**Recall gap — resolve before implementing.** This is a DICOM viewer. Patient
exports routinely nest under a patient-named directory
(`patients/SMITH_JOHN/study1/img001.dcm`, `exports/DOE^JANE/…`), so a
**basename-only** name lane would let a real patient name in a directory
component escape the gate entirely — the file inside may be a bland `img001.dcm`
with no name to catch. For a medical-imaging repo this is the *primary* leak
shape, not an edge case, so basename-only is the wrong default here. The
identifier lane already scans every component for exactly this reason; the name
lane should not be weaker.

**Decision: the name lane scans every path component too** (matching the
identifier lane), with directory false positives handled by an explicit
allowlist rather than by narrowing scope:

- Common surnames do appear legitimately in directory names (`smith_lab/`,
  `davidson_group/`) as organizational units. Handle these with a
  `SAFE_DIR_COMPOUNDS` frozenset (per assessment idea #5) — a directory-scoped
  sibling of `SAFE_NAME_COMPOUNDS`, seeded from the pre-merge tracked-tree audit
  and governed the same way. This keeps recall high (patient-named dirs block)
  while giving a reviewed escape hatch for genuine org dirs.
- `SAFE_NAME_COMPOUNDS` stays keyed to whole basename stems; `SAFE_DIR_COMPOUNDS`
  is keyed to whole directory-component stems. A path is checked component by
  component: each directory component against `SAFE_DIR_COMPOUNDS`, the basename
  stem against `SAFE_NAME_COMPOUNDS`.
- The migration audit (rollout step 2) must therefore report the **component**
  and rule for each hit, not just the path, so directory hits can be triaged
  into `SAFE_DIR_COMPOUNDS` or renamed.

(An earlier draft restricted the name lane to the basename to reduce
directory-name false positives. That traded away recall on the dominant
patient-named-directory leak shape and is rejected; the allowlist is the correct
FP control, not scope narrowing.)

### 3. Content lane (text + spreadsheet + doc)

`_content_reasons` already loops `CONTENT_RULES: list[tuple[re.Pattern[str],
str]]`. Two new tuples are appended (see Integration above):

- `(IDENTIFIER_CONTENT_PATTERN, "patient-identifier-in-content")` — same
  keyword/digit regex as the filename lane, applied to the whole line so
  `MRN_1234567` inside a CSV cell is caught.
- `(NAME_CONTENT_PATTERN, "patient-name-in-content")` — an alternation built
  programmatically from `PATIENT_NAME_TOKENS` at module import, gated on
  **ASCII-alphanumeric boundaries** so `_`-glued tokens still match (avoids
  `goldsmith` false positives while catching `patient_smith_id`; see Word
  boundary behavior below for why `\b` alone is insufficient). Applied only to
  staged data/doc files (the
  existing `DATA_SUFFIXES` scope), **not** to `src/` Python source where
  comments and identifiers legitimately mention names (the existing rules
  already restrict the content lane to data-suffix paths via
  `check_contents`' guard at `check_no_phi_artifacts.py:541`).

#### Documentation-path carve-out

`DATA_SUFFIXES` includes `.md`, `.txt`, `.yaml`, `.json`. Prose under
`dev-docs/` and `user-docs/` regularly discusses names ("the Smith case
study", "patient John Doe example") and would false-positive on the new
`patient-name-in-content` rule. Decision for this slice: the content lane
**skips** any staged path whose first component is `dev-docs/` or
`user-docs/` for the two new content rules only — the existing content rules
(local paths, DICOM tags, network addresses) still apply to those paths
unchanged. This keeps the blocking gate focused on data fixtures, not
documentation prose. The carve-out is implemented as an explicit path-prefix
check inside the two new content-rule closures, not as a global suffix-list
edit, so the existing rules cannot accidentally inherit it.

#### Word boundary behavior for `NAME_CONTENT_PATTERN`

**Do not use plain `\b`.** A regex `\b` is a transition between `\w` and `\W`,
and `_` is a `\w` character. So `\b(smith)\b` would **fail** to match `smith`
inside `patient_smith_id` (no boundary between `_` and `s`) — the very
underscore-delimited shape the filename lane splits on. This is the most common
data-fixture pattern for embedded names, so a bare `\b` leaves a real gap and
is inconsistent with the filename lane's `[-_.\s]` tokenization.

Use explicit ASCII-alphanumeric boundaries instead:

```python
re.compile(r"(?<![A-Za-z0-9])(?:" + alternation + r")(?![A-Za-z0-9])",
           re.IGNORECASE)
```

Underscore, punctuation, whitespace, digits, and start/end-of-string all count
as boundaries; only an adjacent ASCII letter/digit suppresses a match:

- `smith,` / `smith.` / `smith-` / `smith_` / `patient_smith_id` — the adjacent
  char is a separator (or `_`), so → **matches** as expected.
- `smithson` / `goldsmith` — an adjacent ASCII letter, so → **does not match**,
  avoiding the compound-word false positive.
- `SMITH` — `re.IGNORECASE` covers ASCII case; the seed list is ASCII so
  `casefold` is not needed for the regex path, but the test suite must
  include mixed-case cases (`Smith`, `SMITH`, `smith`).
- Digit adjacency: `smith2` → **does not match** (trailing digit is a
  boundary-suppressing char), matching the filename lane's token semantics.

Test cases for the boundary behavior are added to
`tests/test_names_privacy.py` (punctuation-suffixed names, `_`-glued tokens,
glued alpha prefixes/suffixes, digit-adjacent tokens).

#### Lookbehind behavior for `PATIENT_IDENTIFIER_PATTERN`

`(?<=[\s_.\-])` is a fixed-width (1-char) lookbehind; Python `re` supports
fixed-width lookbehind unconditionally. Variable-width lookbehind is not
used. The test suite adds cases for every separator variant and start-of-string.

### Allowances

- Reuse the existing `security/approved-phi-text-exceptions.json` hash-bound
  manifest for **content** findings. **No new allowance file** for this slice.
- **Filename findings have no hash-bound allowance path.** The
  `approved-phi-text-exceptions.json` manifest is keyed by repository path and
  is only consulted by `check_contents` (`check_no_phi_artifacts.py:538`);
  `check_paths` never reads it. This is deliberate: a filename that looks like
  PHI is the finding itself, and a hash cannot make `Smith_John_report.txt`
  safe. Reviewers must know that the only resolution for a name-lane filename
  hit is to **rename the file** or to add the basename to
  `SAFE_NAME_COMPOUNDS` (compound only). There is no per-file override.
- For the existing source-side AST/sink lane, the inline
  `privacy-check: allow[<rule>] review=<…>` marker
  (`scripts/privacy_checks/allowances.py`) remains; the new rules do not
  introduce source-side findings, so no new marker categories are needed.

#### `SAFE_NAME_COMPOUNDS` / `SAFE_DIR_COMPOUNDS` governance

Both compound allowlists are review-gated. Additions require:

1. A PR that names the proposed stem, the tracked file(s)/dir(s) it unblocks,
   and a one-line rationale (e.g. "algorithm name," "British locality," "lab
   org unit").
2. Reviewer sign-off that the stem is genuinely compound / an org unit (contains
   a non-name token alongside the surname stem, or names a group/lab/site) and
   is **not** a bare patient surname.
3. The entry appears in the `SAFE_NAME_COMPOUNDS` (basename) or
   `SAFE_DIR_COMPOUNDS` (directory) block in `scripts/privacy_checks/names.py`;
   no external data file is introduced in this slice.
4. The PR records the decision in `dev-docs/MAINTENANCE_LOG.md` so additions
   are auditable without grepping git blame.

`PATIENT_NAME_TOKENS` growth follows the same governance: additions are PR-
reviewed, ASCII-only for this slice, and recorded in the maintenance log.

## Enforcement points (all blocking)

| Layer | File | New call(s) | Trigger |
|-------|------|-------------|---------|
| Pre-commit (staged) | `scripts/check_no_phi_artifacts.py` `_path_reasons` | import and call `name_in_path` per basename; append the two new reason strings | every staged file path |
| Pre-commit (staged) | `scripts/check_no_phi_artifacts.py` `_content_reasons` | append the two new `(pattern, reason)` tuples to `CONTENT_RULES` | every staged text/data file |
| Pre-push (full tree) | `scripts/check_no_phi_artifacts.py` (no `--staged`) | same — already iterates all tracked files | `pre-push` hook |
| CI (blocking) | `.github/workflows/privacy-gates.yml` `phi-artifact-scan` job | already invokes `scripts/check_no_phi_artifacts.py` | every PR + push to main/develop |

The plan intentionally reuses the existing gating script and the two existing
hook + job seams rather than introducing a third script or workflow. That keeps
the blocking policy in one place per lane we already own. The privacy-output
hook (`git_hook_privacy_checks.py`) and `privacy_checks/text_rules.py` are
**not** modified — they own Python source-sink checks, not data-content rules.

## CI vs hooks

The user asked for **both hooks and CI**. Per the comment block in
`security-checks.yml:157-165` (the authoritative gate statement is at lines
161-165), CI is the authoritative gate because hooks can be bypassed with
`--no-verify` or simply not installed on a fresh clone. The plan therefore:

1. Augments `check_no_phi_artifacts.py` (the blocking computer shared by hook +
   CI) so both lanes light up at once. No CI workflow structure change needed.
2. Adds the explicit reason string in the finding output so humans see "patient
   name in filename" rather than a generic "sensitive-looking filename."
3. The `no PHI artifacts tracked` job's **required parsers** step is unchanged
   (no new pip deps needed — pure regex).

Optional (not required for this slice): add the same scan as a second CI job
under `repo-harness.yml` so the new lane runs even on the lighter harness job
without the XLSX/PDF/DICOM exporters installed. Skipped initially to keep the
blast radius small.

## Tests (must be added before merge, blocking)

New file `tests/test_names_privacy.py` uses `pytest.mark.parametrize` for the
seed name list so additions auto-expand coverage. It covers:

- Each seed name in `PATIENT_NAME_TOKENS` blocks when it appears as a basename
  token (e.g. `Smith_report.txt`, `JONES_export.csv`, `gupta-study.json`);
  each `SAFE_NAME_COMPOUNDS` stem does **not** block (`smith_waterman.py`,
  `robinson_crusoe.md`, `martin_fowler_refactoring.txt`); and a stem that never
  splits into a token is **not** in the allowlist yet still does not block
  (`jackknife.txt`, `davidson_profile.csv`) — assert both paths so the
  membership rule is regression-tested.
- Identifier patterns match `MRN_1234567`, `acc-1234567`, `MRN007`, `PID-001`,
  `studyid_42`, and negatives (`accidentally.txt`, `master_mr.txt`,
  `acc-2024` year-tag, `account_balance.csv`).
- `_content_reasons` returns the new categories for an embedded
  name/identifier in a CSV/JSON line; **does not** flag `src/`-style mentions
  (those paths are not in `DATA_SUFFIXES`); and **skips** name-token findings
  on `dev-docs/` and `user-docs/` paths while still applying the existing
  network/path rules there.
- Allowance asymmetry: a fixture `Smith_report.csv` is blocked on the
  filename lane even when its content is registered as a hash-bound approved
  text exception, because `check_paths` never consults the text-exception
  manifest. Document this in a dedicated test so reviewers see the contract.
- Directory-name scope (name lane scans **every** component): a bare
  patient-named directory `data/smith/results.csv` **blocks** on the name lane
  (dir component `smith` hits), as does `exports/doe^jane/img001.dcm` — the
  dominant DICOM leak shape. A reviewed org dir `data/smith_lab/results.csv`
  does **not** block (dir stem in `SAFE_DIR_COMPOUNDS`), but
  `data/smith_lab/smith.txt` **does** block (basename `smith` still hits).
  `data/mrn-12345/results.csv` blocks on the identifier lane (dir component
  matches). Additional cases: nested `data/cohorts/smith/john.txt` (dir hit on
  `smith` and basename hit on `john`); mixed-case `data/MRN-Records/x` (dir
  match on the identifier lane, case-insensitive); exact-token dir
  `data/gupta/x.csv` (name lane **blocks** on the `gupta` dir component unless
  `gupta` is a reviewed `SAFE_DIR_COMPOUNDS` org unit).
- Word-boundary cases for `NAME_CONTENT_PATTERN`: `smith,` matches,
  `smith.` matches, `smithson` does not, `goldsmith` does not, `SMITH`
  matches (re.IGNORECASE), `report smith end` matches.
- Lookbehind cases for `PATIENT_IDENTIFIER_PATTERN`: `MRN-1`, `MRN_1`,
  `MRN.1`, `MRN 1`, `MRN1`, `acc-12345` no match (5-digit floor for acc),
  `acc-123456` matches, `accidentally-199` no match (keyword not delimited).

The harness check `python scripts/check_repo_harness.py` already enforces a
test for every script-level gate; the new module must also be wireable through
the existing `import` smoke (`scripts/agent_smoke_harness.py`).

## Documentation updates (commit alongside code later)

- `dev-docs/PHI_PII_REPOSITORY_GUARDRAILS.md` — add a bullet under "What the
  blocking artifact gate covers" covering the new name-based and identifier
  filename lanes; bump `**Last updated:**`.
- `AGENTS.md` — one line in the "Privacy checks" paragraph pointing at the two
  new rule categories so contributors know filenames are now scanned for
  patient names/identifiers, not just structural prefixes.
- `security/security-tool-inventory.json` — **not** modified (no new tool
  introduced; pure stdlib regex).
- `CHANGELOG.md` — entry under the next patch/minor version noting the new
  blocking filename/identifier scan.
- `dev-docs/MAINTENANCE_LOG.md` — entry recording the gate addition.

No docs-link changes needed; `scripts/check_user_docs_links.py` does not track
the files modified here.

## Rollout order (when the plan is approved for implementation)

1. Add `scripts/privacy_checks/names.py` with `PATIENT_NAME_TOKENS`,
   `SAFE_NAME_COMPOUNDS`, `SAFE_DIR_COMPOUNDS`, the single `PATIENT_IDENTIFIER_PATTERN`, and the
   two precompiled content patterns `IDENTIFIER_CONTENT_PATTERN` and
   `NAME_CONTENT_PATTERN` (plus the `dev-docs/` / `user-docs/` carve-out).
2. **Pre-merge migration audit (blocking):** run the audit script below against
   the full tracked tree. Every hit must be resolved before the gate is merged
   — either rename the file, or (for a true compound) add the stem to
   `SAFE_NAME_COMPOUNDS` via the governance process above. There is no
   per-file hash allowance for filenames. Record the audit result (counts per
   rule, list of resolutions) in `dev-docs/MAINTENANCE_LOG.md`.

   Migration workflow:

   1. Check out the feature branch with the new `names.py` landed but not yet
      wired into `_path_reasons`/`_content_reasons`.
   2. Run the audit script; save output to a temp file (do not commit it —
      it may contain name tokens).
   3. Triage each hit: **rename** the file (preferred for bare surname
      hits), **add to `SAFE_NAME_COMPOUNDS`** (for genuine compound stems
      with reviewer sign-off), or **confirm false positive and file a
      follow-up** (no override mechanism — the rule must be amended or
      the file renamed).
   4. Commit the renames and `SAFE_NAME_COMPOUNDS` additions in the same
      feature branch.
   5. Re-run the audit; expect zero hits before opening the PR.

   Audit script (run as a module from repo root so the `scripts` package
   resolves — `python -m scripts.audit_filename_phi`, **not** `python
   scripts/audit_filename_phi.py`, which puts only the script's own dir on
   `sys.path` and fails the `from scripts.privacy_checks…` import; requires
   `scripts/__init__.py`). Prints `path: rule` only, never the matched value:

   ```python
   # python -m scripts.audit_filename_phi  (new, dev-only — not wired to hooks)
   import subprocess, sys
   from pathlib import PurePosixPath
   from scripts.privacy_checks.names import name_in_path, PATIENT_IDENTIFIER_PATTERN

   files = subprocess.check_output(["git", "ls-files"], text=True).splitlines()
   hits = 0
   for path in files:
       reason = name_in_path(path)
       if reason:
           print(f"{path}: {reason}")
           hits += 1
           continue
       if PATIENT_IDENTIFIER_PATTERN.search(path):
           print(f"{path}: patient-identifier-in-path")
           hits += 1
   print(f"[audit] {hits} hit(s) across {len(files)} tracked files")
   sys.exit(1 if hits else 0)
   ```

   The script is dev-only and lives under `scripts/`; it is **not** invoked by
   hooks or CI. It exists so the migration audit is reproducible. `PurePosixPath`
   is imported for basename derivation inside `name_in_path`; if the audit adds
   its own basename handling, drop the unused import to keep lint clean.
3. Wire into `check_no_phi_artifacts.py`: import from `names.py` and append
   the two reason strings in `_path_reasons` + append the two
   `(pattern, reason)` tuples to `CONTENT_RULES` for `_content_reasons`. The
   existing `SENSITIVE_FILENAME_PATTERNS` stays unchanged (it still owns the
   `patientname-Smith^John` DICOM shape and the `account[._-]` 4-char floor).
   Do **not** alias or rename `SENSITIVE_FILENAME_PATTERNS` — keep both sets
   active in parallel.
4. Add `tests/test_names_privacy.py` (parametrized) and run the full
   verification table below.
5. Update guardrails doc, AGENTS.md hint, CHANGELOG, MAINTENANCE_LOG.
6. Run the local hooks once with a synthetic offender to confirm blocking
   status; do not commit the offender.
7. Squash to one commit on a feature branch; open PR; CI gates enforce.
8. After CI passes, merge (no extra step — the plan is delivered).

## Rollback procedure

If the new rules cause unexpected blocking or false positives after merge,
revert in this order (fastest to slowest):

1. **Empty the constants in place (one commit):** set `PATIENT_NAME_TOKENS =
   frozenset()` (leaving `SAFE_NAME_COMPOUNDS`/`SAFE_DIR_COMPOUNDS` intact is
   harmless once the token set is empty), and delete the two
   `(pattern, reason)` tuples added to `CONTENT_RULES` and the two reason
   strings appended in `_path_reasons`. The `names.py` module and its import
   stay; only the active patterns are blanked. Re-run hooks and CI to confirm
   the gate no longer fires. This is the preferred **hot-fix** path because it
   does not require reverting the renames done during migration.
2. **Revert the merge commit** if a clean revert applies (`git revert
   <merge-sha>`). This also reverts the migration renames, so it is only safe
   on the same day as merge; later history with follow-up commits to the
   renamed files makes a revert conflict-prone.
3. **Feature flag (out of scope for this slice):** a `DICOMVIEWER_NAMES_GATE`
   env var read inside `name_in_path` and `_content_reasons` would allow a
   config-only disable. It is intentionally **not** added in v1 to keep the
   gate behavior identical locally and in CI; if operational reality demands
   it, add it in a fast follow-up and gate it the same way the existing
   `DICOMVIEWER_PRIVACY_HOOK` warn-only override works
   (`scripts/git_hook_privacy_checks.py:113`).

All rollback paths must be recorded in `dev-docs/MAINTENANCE_LOG.md` with the
incident summary and the chosen path.

## Verification before declaring done

| Check | Command |
|-------|---------|
| Unit tests | `python -m pytest tests/test_names_privacy.py -v` |
| Full test suite | `python -m pytest tests/ -v` |
| Repo harness | `python scripts/check_repo_harness.py` |
| Architecture boundaries | `python scripts/check_architecture_boundaries.py` |
| Agent smoke | `python scripts/agent_smoke_harness.py` |
| Hook dry-run (staged offender) create a temp file `Smith_John_report.txt`, `git add` it, run `python scripts/check_no_phi_artifacts.py --staged --root "$PWD"` and confirm exit 1 | manual, do not commit |
| Hook dry-run (ID offender) repeat with `MRN_1234567.txt` | manual, do not commit |

## Risk & false-positive analysis

- Compound names whose split **contains a token** (`smith_waterman` → `smith`,
  `robinson_crusoe` → `robinson`) are handled via the **explicit, seeded**
  `SAFE_NAME_COMPOUNDS` allowlist (basename stems) and `SAFE_DIR_COMPOUNDS`
  (directory stems). Single-word look-alikes that never split into a token
  (`jackknife`, `davidson`, `goldsmith`) do not need an allowlist entry at all —
  the token lane cannot flag them. The pre-merge migration audit (rollout step 2)
  drives the allowlists' initial contents from the actual tracked tree, so the
  first run does not break legitimate files.
- The name lane scans every path component and is token-based, so substrings
  inside words (`goldsmith.csv`, `davidson_profile.txt`) do not block via the
  token split —
  but `goldsmith.csv` would block under whole-word content matching in
  `NAME_CONTENT_PATTERN`. To avoid that, `NAME_CONTENT_PATTERN` uses explicit
  ASCII-alphanumeric boundary assertions (`(?<![A-Za-z0-9])…(?![A-Za-z0-9])`,
  **not** bare `\b`) so the token must be delimited by a separator/`_`/digit or
  start/end of line; a token glued into a longer word by an ASCII letter
  (`goldsmith`) is not delimited, so it does not match, while a `_`-glued token
  (`patient_smith_id`) still does. The `SAFE_NAME_COMPOUNDS`
  set is a second layer for the filename lane; the content lane relies on
  word-boundary anchoring plus the `dev-docs/` / `user-docs/` carve-out.
- The identifier lane drops the `account` keyword (see Pattern design) and
  keeps a 3-digit floor for MRN/PID/study and a 5-digit floor for
  `acc`/`accession`/`accn`. Year-tag false positives like `acc-2024` no longer
  match; legitimate `acc-2024` test fixtures that *should* match a study-id
  shape can be renamed.
- Filename findings have **no hash-bound override path** (see Allowances). The
  resolution is always to rename the file or, for a true compound, add the
  stem to `SAFE_NAME_COMPOUNDS`. This is a deliberate asymmetry to keep the
  gate conservative.
- Internationalized names (`Müller`, `González`, CJK names) are not in the
  seed list and will not match. The tokenization splits on ASCII `[-_.\s]`
  and lowercases with `str.lower`, which is Unicode-aware but the seed set is
  ASCII. Handling non-Latin patient names is documented as future work and is
  not part of this slice.
- Performance: filename scan is one regex per basename plus one set lookup.
  The content lane adds one alternation per line on staged text files;
  existing `MAX_TEXT_BYTES` (16 MB) caps and the `DATA_SUFFIXES` guard already
  bound the work. The alternation is compiled once at module import.
- Worst case (huge watchlist): keep `PATIENT_NAME_TOKENS` under ~500 entries;
  compile the alternation once at module import. If it grows beyond that,
  switch to the out-of-scope JSON watchlist (see Future work).

## Rejected assessment suggestions (deliberate, not oversights)

The revision-2 assessment proposed several operability features. These are
**rejected on the merits** for a blocking PHI gate, not merely deferred:

- **Warn-only trial period (assessment idea #1).** For ordinary lint, warn-then-
  block is prudent. For a *blocking PHI gate* the warn window is precisely a
  window in which real PHI can be committed into history — the exact failure the
  gate exists to prevent, and the most expensive to remediate (history rewrite,
  possible disclosure). The gate ships blocking from commit 1. An operational
  *disable* path already exists via the rollback procedure (blank the constants
  in one commit); that is the correct escape hatch, not a warn window.
- **External YAML/TOML config for tunable patterns (assessment idea #3).** A
  security allowlist/keyword set is a review artifact. Moving it to an external
  config file that can be edited without a code review weakens the admission
  boundary — the whole point is that adding a name/compound is PR-reviewed and
  logged. In-source frozen literals stay.
- **Automated seed-list expansion from public census data (assessment idea #7).**
  Bulk-importing thousands of common names does **not** strictly improve safety:
  name-lane precision is a trade-off, and **a larger token set raises the false-
  positive rate** on legitimate files (org directories, algorithm names,
  contributor surnames). Growth must be FP-measured against the real tracked
  tree, not maximized. Curated, small, and reviewed beats large and automatic.
  (A sibling repo that consolidated a similar list kept it hand-curated and
  explicitly dropped English-word/ambiguous collisions such as `park`, `wu`,
  `cho`, `grace`, `sun` for this reason.)

## Out of scope / future work

- An external `security/patient-name-watchlist.json` once the in-source list
  grows beyond a single screen of review.
- Extending the keyword set to facility/site name tokens (`Mercy`, `StMary`,
  `Methodist`) — same architecture, but a separate review thread.
- Adding the same scan as a Semgrep rule to also catch name leakage inside
  Python string literals — left to the advisory Semgrep lane, not the
  blocking hook, per the conservative-syntactic-guard split described in
  `dev-docs/PHI_PII_REPOSITORY_GUARDRAILS.md:53-60`.
- OCR for burned-in names in images/PDFs — explicitly out of scope per the
  existing guardrail text.
- Unicode/non-Latin patient name tokens and accented surnames — same
  architecture, separate review thread when the ASCII seed list proves
  insufficient.
