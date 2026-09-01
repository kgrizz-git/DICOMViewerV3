# PS3.15 Table E.1-1 action-resolution method

**Status:** Active research method; not an implementation matrix or DICOM conformance statement

**Last updated:** 2026-09-01

## Purpose and boundary

[`ps315_e1_inventory.json`](ps315_e1_inventory.json) preserves the raw Table
E.1-1 actions and option columns from the pinned PS3.15 source. Those values
are not generic dataset-transformation instructions. This document defines the
evidence required to turn one raw row into an assessed, IOD-specific expected
action.

It does not select a formal supported IOD/SOP Class, resolve any of the 656
rows, validate a serialized instance, or state that the application conforms
to a DICOM profile, a legal regime, or a privacy standard. An `unresolved`
matrix entry is not a pass.

## Primary source and inputs

The method is based on the source recorded in
[`ps315_e1_inventory.json`](ps315_e1_inventory.json): National Electrical
Manufacturers Association (NEMA), DICOM PS3.15 2026c, Annex E, Table E.1-1 and
Table E.1-1a, retrieved 2026-08-31. Its source digest, byte count, and
retrieval metadata are the pin while the edition-specific URL remains
unavailable. See the [primary-source review record](PS315_E1_PRIMARY_SOURCE_REVIEWS.md)
for independent verification of that raw dataset.

Each future assessment also needs a separately version-pinned PS3.3 IOD source
for the exact candidate SOP Class/IOD. A source modality, a `pydicom` write,
or an inherited `SOPClassUID` does not establish an Attribute Type.

## Resolution inputs for one row

Every effective-action decision must record all of the following:

| Input | Required evidence |
| --- | --- |
| Table row | `stable_id`, tag/path, raw base action, and option columns from `ps315_e1_inventory.json` |
| Candidate object | SOP Class UID and IOD name; ordinary source re-export must not be treated as an implicit finite scope |
| IOD requirement | Pinned PS3.3 edition, section/table, source fingerprint, Attribute Type (`1`, `1C`, `2`, `2C`, or `3`), and the full nested path |
| Condition | Condition text and an assessment input showing whether each `1C`/`2C` requirement applies |
| Option set | Exact enabled/disabled transformation options, including the preset or explicit `DeepAnonymizerOptions` values |
| Table precedence | The applicable option-column value, if any, and the resulting raw action before Type resolution |
| Object context | Whether a sequence contains UID references, whether the row is nested, and any required batch/reference relationship |
| Replacement constraints | VR-valid non-identifying replacement/blank/removal strategy and Type-presence constraint |
| Repository evidence | Current code path, synthetic fixture, final serialized-output check, and status: `pass`, `fail`, `not_applicable`, or `unresolved` |

## Table E.1-1a decision rules

The following is a direct decision procedure derived from the raw compound
actions in the pinned Table E.1-1a. It is a method for an already selected IOD,
not a fallback for a generic `Dataset`.

| Raw action after option precedence | Required Type/context evidence | Effective action when the stated case applies |
| --- | --- | --- |
| `Z/D` | Type 2 or Type 1 | Type 2 → `Z`; Type 1 → `D` |
| `X/Z` | Type 3 or Type 2 | Type 3 → `X`; Type 2 → `Z` |
| `X/D` | Type 3 or Type 1 | Type 3 → `X`; Type 1 → `D` |
| `X/Z/D` | Type 3, Type 2, or Type 1 | Type 3 → `X`; Type 2 → `Z`; Type 1 → `D` |
| `X/Z/U*` | Type 3, Type 2, or Type 1 sequence containing UID references | Type 3 → `X`; Type 2 → `Z`; stated Type 1 case → keep the sequence, recurse, and replace its contained instance UID references (`U*`) |

If the IOD Type does not fit the stated alternatives, or a conditional
requirement has not been evaluated, the matrix status is `unresolved` and the
row cannot supply an implementation expectation. `1C` and `2C` are first
resolved by their IOD condition, then handled as Type 1 or Type 2 when that
condition applies.

The `U*` case is not a replacement value for the sequence attribute itself. Its
assessment record must preserve the sequence structure and separately identify
the contained UID-reference paths subject to internally consistent replacement.
Represent that result as `K+U*` (or an equally explicit structured value), not
as bare `U`.

For the direct raw actions `D`, `Z`, `X`, `K`, `C`, and `U`, the matrix still
records nested-sequence context, option precedence, VR/replacement constraints,
and current serialized-output evidence. In particular, `K` and `C` cannot be
treated as a shallow keep/remove rule, and `U` requires a protected-set
consistency assessment.

## Required assessment record

The eventual machine-readable matrix must chain to both source records and
contain at least:

```text
matrix_id, ps315_inventory_sha256, ps33_source_sha256,
sop_class_uid, iod_name, attribute_path, stable_id, iod_type,
condition_text, condition_applies, selected_option_set,
raw_action, option_override, effective_action,
replacement_strategy, implementation_anchor, fixture_id,
serialized_check_id, status, notes
```

`effective_action` remains empty while `status` is `unresolved`; its allowed
values include an explicit composite such as `K+U*` when the Table E.1-1a
sequence case applies. The matrix
must distinguish a DICOM-derived expected action from observed current code;
matching code behavior alone is not evidence that the row is resolved.

## Sequencing and stopping rules

1. Record a candidate IOD scope without describing it as a support promise.
2. Retrieve and fingerprint the corresponding PS3.3 definition from the same
   DICOM edition where available.
3. Enumerate each applicable attribute path and Type, including conditional
   modules and nested sequences.
4. Select one exact option set and apply table option precedence before the
   Type/context procedure above. In the pinned inventory, option cells are
   `K`, `C`, or empty; revisit this ordering rule if a future edition adds a
   compound option override.
5. Record expected action, current code behavior, and fixture/serialized-output
   evidence separately.
6. Keep incomplete, unsupported, and out-of-scope rows `unresolved`; do not
   fill gaps using a curated tag list or a generic data-element presence check.

The first candidate objects for evidence collection may be the MPR writer's
currently emitted CT, MR, and Secondary Capture SOP Classes, but their current
selection is not a formal IOD-validity promise. Projection DICOM and arbitrary
source re-export require separate source-IOD decisions before they enter a
matrix.

## Current repository implication

The current deep engine applies a curated set of metadata transformations and
does not dispatch Table E.1-1 actions from an IOD Type table. The base engine
is narrower still. This method therefore records no current `pass` result and
does not authorize a profile/provenance assertion. It exists to make any later
gap visible and reproducible before a code-design phase.
