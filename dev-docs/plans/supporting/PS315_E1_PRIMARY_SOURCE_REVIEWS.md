# PS3.15 Table E.1-1 primary-source review record

**Status:** Completed evidence record; not a DICOM conformance statement
**Last updated:** 2026-09-01

## Purpose and boundary

This record closes the Phase 1 requirement for two independent checks of the
source-derived [`ps315_e1_inventory.json`](ps315_e1_inventory.json) dataset.
It confirms that the recorded inventory reproduces the retrieved Table E.1-1
source at the documented point in time. It does **not** resolve compound action
codes, select options, validate an IOD, or establish that the application
conforms to a DICOM profile or a legal/privacy regime.

The normative source for both reviews is the National Electrical Manufacturers
Association (NEMA) DICOM PS3.15 Annex E, Table E.1-1:
<https://dicom.nema.org/medical/dicom/current/output/chtml/part15/chapter_E.html>.
`current` is a discovery URL only; the inventory's content digest is the
immutable evidence pin while the edition-specific URL remains unavailable.

## Review 1 — retained source and committed inventory

**Evidence source:** the ignored local retrieval artifact recorded by
`ps315_e1_inventory.json`, retrieved 2026-08-31 at 22:58:12 UTC.

| Check | Result |
| --- | --- |
| Declared edition | `2026c` |
| Retrieved HTML bytes | `1,600,064` |
| SHA-256 | `26710b02dfd00d255ac58b944a1962c87f23f02e4590fba2736bf3203da9d247` |
| Table header | All 15 recorded columns matched |
| Data rows | 656 recorded rows matched |
| Complete extracted requirements array | Exact match to the committed inventory |

The comparison also checked a deliberately varied sample spanning ordinary,
compound, UID, wildcard, private-attribute, overlay, and final-table rows:

| Stable ID | Attribute | Tag | Raw basic action |
| --- | --- | --- | --- |
| `E1-T-001` | Accession Number | `(0008,0050)` | `Z` |
| `E1-T-002` | Acquisition Comments | `(0018,4000)` | `X` |
| `E1-T-004` | Acquisition Context Sequence | `(0040,0555)` | `X/Z` |
| `E1-T-007` | Acquisition Device Processing Description | `(0018,1400)` | `X/D` |
| `E1-T-011` | Acquisition UID | `(0008,0017)` | `U` |
| `E1-T-091` | Curve Data | `(50xx,xxxx)` | `X` |
| `E1-T-321` | Overlay Comments | `(60xx,4000)` | `X` |
| `E1-T-322` | Overlay Data | `(60xx,3000)` | `X` |
| `E1-T-396` | Private Attributes | `(gggg,eeee) where gggg is odd` | `X` |
| `E1-T-432` | Referenced Image Sequence | `(0008,1140)` | `X/Z/U*` |
| `E1-T-656` | X-Ray Source ID | `(0018,9367)` | `D` |

## Review 2 — separately retrieved source snapshot

**Retrieval date:** 2026-09-01 UTC
**Evidence source:** a separately retrieved, ignored local copy of the same
NEMA `current` page, saved as
`tmp/ps315-assessment/PS3.15-current-Annex-E-rereview-2026-09-01.html`.

The second retrieval had the same byte count and SHA-256 digest as the retained
source from Review 1. Running
`scripts/build_ps315_e1_inventory.py` against it produced 656 rows whose full
`requirements` array exactly matched the committed inventory. Its extracted
15-column header and the documented Review 1 sample also matched. Equal source
fingerprints are reported as a finding about those two retrievals, not as an
assertion that the moving `current` URL will remain unchanged.

## Method and follow-up

Both reviews used the repository's local-only extractor
[`scripts/build_ps315_e1_inventory.py`](../../../scripts/build_ps315_e1_inventory.py).
The script does not download standards content; it verifies the table structure
and rejects unexpected cells or tag patterns. The raw HTML remains ignored to
avoid distributing a copied standards artifact in the repository.

Independent free-model reviews were used as non-authoritative cross-checks of
the source comparison. The recorded hashes, local extraction results, and this
document are the auditable evidence; model reports are not a substitute for the
primary source.

The next Phase 1 task remains action resolution by supported IOD Type and option
set. In particular, the raw action values above must not be treated as a generic
dataset transformation rule.
