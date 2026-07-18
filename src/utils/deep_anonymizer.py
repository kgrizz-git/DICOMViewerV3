"""
Deep DICOM anonymization for export batches.

Strips patient PHI (group 0010), institution/device metadata, operator names,
optional UIDs and dates, private tags, and free-text comments. Supports batch
UID remapping and per-study date shifting for consistent multi-slice exports.

Inputs:
    pydicom Dataset objects, DeepAnonymizerOptions

Outputs:
    Anonymized Dataset copies with PS3.15 de-identification tags set

Requirements:
    pydicom, utils.dicom_anonymizer, utils.deep_anonymizer_profile
"""

from __future__ import annotations

import secrets
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta

from pydicom.dataset import Dataset
from pydicom.tag import BaseTag, Tag
from pydicom.uid import PYDICOM_IMPLEMENTATION_UID, generate_uid

from utils.deep_anonymizer_profile import (
    DEIDENTIFICATION_METHOD,
    FREE_TEXT_TAGS,
    IDENTIFIER_TAGS,
    INSTITUTION_SITE_TAGS,
    OPERATOR_PHYSICIAN_TAGS,
    SR_NARRATIVE_TAGS,
    STATION_DEVICE_TAGS,
    UID_TAGS,
)
from utils.deid_provenance import apply_deidentification_provenance
from utils.dicom_anonymizer import DICOMAnonymizer
from utils.dicom_vr_helpers import is_date_vr

# DICOM-defined UIDs (SOP Class, Transfer Syntax, well-known coding schemes, etc.)
# all live under this root. They are *not* instance identifiers and must NEVER be
# remapped during de-identification — regenerating e.g. SOPClassUID produces
# non-conformant DICOM and breaks tools that dispatch on SOP class (incl. pylinac).
# Instance/study/series/frame-of-reference UIDs are organization-rooted (not under
# this root), so this guard remaps real identifiers while preserving standard UIDs.
DICOM_STANDARD_UID_ROOT = "1.2.840.10008"

# Date-shift anchor: the earliest StudyDate in a batch is mapped to this date
# (clearly fake, far in the past) minus a cryptographically unpredictable
# batch-wide jitter drawn via secrets.randbelow. The single offset is applied to
# every dataset, so all relative gaps are preserved while the anchor lands in
# [DATE_ANCHOR - DATE_JITTER_MAX_DAYS, DATE_ANCHOR] — obscuring the true baseline
# so dates can't be reversed just from knowing the tool's anchor.
DATE_ANCHOR = datetime(1900, 1, 1)
DATE_JITTER_MAX_DAYS = 3650  # up to ~10 years earlier than the anchor

# Identifies this de-identifying application in regenerated File Meta Information.
IMPLEMENTATION_VERSION_NAME = "DICOMViewerV3"

# File Meta (group 0002) elements that can leak the originating site/device and
# are removed during de-identification (PS3.15 E.1.1 step 7).
FILE_META_IDENTIFYING_TAGS = (
    Tag(0x0002, 0x0016),  # SourceApplicationEntityTitle
    Tag(0x0002, 0x0017),  # SendingApplicationEntityTitle
    Tag(0x0002, 0x0018),  # ReceivingApplicationEntityTitle
    Tag(0x0002, 0x0102),  # PrivateInformation
    Tag(0x0002, 0x0101),  # PrivateInformationCreatorUID
)


@dataclass
class DeepAnonymizerOptions:
    """User-configurable de-identification options.

    Defaults = PS3.15 Basic Application Confidentiality Profile with no retain
    options (institution + device stripped, UIDs re-minted, dates shifted). Each
    ``retain_*`` flag that is enabled is declared via a CID 7050 code in the
    De-identification Method Code Sequence (see ``deid_provenance``).
    """

    # Retain options (off by default = base profile). Each, when on, keeps the
    # corresponding attributes AND adds its CID 7050 declaration.
    retain_institution_identity: bool = False  # → 113112
    retain_device_identity: bool = False  # → 113109 (StationName, serial, manufacturer…)
    retain_uids: bool = False  # → 113110 (skip UID re-mint; re-identification vector)

    strip_operators: bool = True
    uid_remap: bool = True
    date_shift: bool = True
    # When True, blank date values (DICOM-conformant "Z" action) instead of shifting.
    # Takes precedence over date_shift. Times (TM) are left intact.
    date_remove: bool = False
    strip_private: bool = True
    strip_free_text: bool = True

    @property
    def remint_uids(self) -> bool:
        """Whether UIDs are re-minted (base profile) vs retained (113110)."""
        return self.uid_remap and not self.retain_uids

    @classmethod
    def standard_share(cls) -> DeepAnonymizerOptions:
        """Default conformant preset for routine sharing.

        Pure PS3.15 Basic Profile with dates shifted (113107): institution and
        device stripped, UIDs re-minted, operators/free-text/private removed.
        """
        return cls()

    @classmethod
    def maximal_strip(cls) -> DeepAnonymizerOptions:
        """Most aggressive preset: dates removed entirely (no temporal option).

        Same as Standard Share but dates are blanked (base profile, no 113106/7).
        """
        return cls(date_shift=False, date_remove=True)

    @classmethod
    def research(cls) -> DeepAnonymizerOptions:
        """Research preset: retain device identity (declares 113109).

        Keeps station / serial / manufacturer for equipment-correlated analysis;
        institution still stripped, UIDs re-minted, dates shifted.
        """
        return cls(retain_device_identity=True)


# Ordered preset registry for the de-identification UI: (key, label, factory).
ANONYMIZER_PRESETS = (
    ("standard_share", "Standard share (recommended)", DeepAnonymizerOptions.standard_share),
    ("maximal_strip", "Maximal strip (remove dates)", DeepAnonymizerOptions.maximal_strip),
    ("research", "Research (keep device identity)", DeepAnonymizerOptions.research),
)


class DeepDICOMAnonymizer:
    """
    Applies deep anonymization to DICOM datasets.

    Use ``anonymize_batch`` when exporting multiple slices so UID remapping and
    date offsets stay consistent within the export selection.
    """

    def __init__(self, options: DeepAnonymizerOptions | None = None) -> None:
        self.options = options or DeepAnonymizerOptions()
        self._patient_anonymizer = DICOMAnonymizer()
        self._uid_map: dict[str, str] = {}
        self._date_shift_offset: int = 0

    def anonymize_batch(self, datasets: Sequence[Dataset]) -> list[Dataset]:
        """
        Anonymize a list of datasets with shared UID and date-shift state.

        Args:
            datasets: Source datasets (copies are returned).

        Returns:
            Anonymized datasets in the same order.
        """
        if self.options.remint_uids:
            self._build_uid_map(datasets)
        if self.options.date_shift and not self.options.date_remove:
            self._build_date_offset(datasets)
        return [self.anonymize_dataset(ds) for ds in datasets]

    def anonymize_dataset(self, dataset: Dataset) -> Dataset:
        """
        Anonymize a single dataset using current batch UID/date state.

        Args:
            dataset: Source pydicom Dataset.

        Returns:
            Deep-anonymized copy with de-identification provenance tags.
        """
        anonymized = self._patient_anonymizer.anonymize_dataset(dataset)

        # Study/order identifiers: always blanked (PS3.15 base profile action Z,
        # no retain option). Blank rather than delete to keep Type-2 conformance.
        self._blank_tags_in_dataset_tree(anonymized, IDENTIFIER_TAGS)

        # Institution + device identity: stripped unless the matching retain option
        # is set (PS3.15 §E.3.8 / §E.3.11). Retention is declared via CID 7050.
        if not self.options.retain_institution_identity:
            self._remove_tags_in_dataset_tree(anonymized, INSTITUTION_SITE_TAGS)
        if not self.options.retain_device_identity:
            self._remove_tags_in_dataset_tree(anonymized, STATION_DEVICE_TAGS)

        if self.options.strip_operators:
            self._remove_tags_in_dataset_tree(anonymized, OPERATOR_PHYSICIAN_TAGS)

        if self.options.strip_free_text:
            self._remove_tags_in_dataset_tree(
                anonymized, FREE_TEXT_TAGS + SR_NARRATIVE_TAGS
            )

        if self.options.strip_private:
            self._strip_private_tags(anonymized)

        if self.options.remint_uids and self._uid_map:
            self._apply_uid_remap(anonymized)

        if self.options.date_remove:
            self._blank_dates_in_dataset(anonymized)
        elif self.options.date_shift and self._date_shift_offset:
            self._shift_dates_in_dataset(anonymized, self._date_shift_offset)

        # PS3.15 E.1.1 steps 5 & 7: protect the SOP Instance UID in File Meta and
        # replace File Meta Information (incl. preamble) with the de-identifying app's.
        self._sanitize_file_meta(anonymized)

        self._set_deidentification_tags(anonymized)
        return anonymized

    def _sanitize_file_meta(self, ds: Dataset) -> None:
        """Sync File Meta UIDs to the (possibly remapped) dataset, drop identifying
        File Meta elements, and zero the 128-byte preamble.

        Without this, ``MediaStorageSOPInstanceUID (0002,0003)`` keeps the original
        instance UID after a remap — a linkage leak and a PS3.10 mismatch with
        ``SOPInstanceUID (0008,0018)``. AE-title and private File Meta elements can
        also leak the source site/device.
        """
        file_meta = getattr(ds, "file_meta", None)
        if file_meta is None:
            # Nothing stored yet; the writer will synthesize File Meta on save.
            return

        sop_instance = getattr(ds, "SOPInstanceUID", None)
        if sop_instance:
            file_meta.MediaStorageSOPInstanceUID = sop_instance
        sop_class = getattr(ds, "SOPClassUID", None)
        if sop_class:
            file_meta.MediaStorageSOPClassUID = sop_class

        # Identify the de-identifying application (per E.1.1 step 7).
        file_meta.ImplementationClassUID = PYDICOM_IMPLEMENTATION_UID
        file_meta.ImplementationVersionName = IMPLEMENTATION_VERSION_NAME

        # Drop File Meta elements that can leak the originating site/device.
        for tag in FILE_META_IDENTIFYING_TAGS:
            if tag in file_meta:
                try:
                    del file_meta[tag]
                except Exception:
                    pass

        # Replace the preamble (it may embed non-DICOM identifying data).
        try:
            ds.preamble = b"\x00" * 128
        except Exception:
            pass

    def _build_uid_map(self, datasets: Sequence[Dataset]) -> None:
        """Collect UIDs from the batch and assign stable replacements."""
        seen: set[str] = set()
        for ds in datasets:
            for tag in UID_TAGS:
                if tag in ds:
                    val = ds[tag].value
                    for uid in self._ui_values(val):
                        if uid:
                            seen.add(uid)
            self._collect_ui_values_from_element(ds, seen)

        for old_uid in sorted(seen):
            if old_uid not in self._uid_map:
                self._uid_map[old_uid] = generate_uid()

    def _build_date_offset(self, datasets: Sequence[Dataset]) -> None:
        """Compute one batch-wide offset mapping the earliest StudyDate near 1900.

        A single offset for the whole export preserves every relative gap — across
        studies, not just within one — while landing the earliest date on a clearly
        fake epoch (DATE_ANCHOR minus an unpredictable jitter) instead of a
        plausibly recent one. The jitter is chosen once per batch via
        ``secrets.randbelow`` so the absolute baseline is hidden: knowing the tool
        anchors to 1900 is not enough to recover real dates.
        """
        # Inclusive upper bound matches the former random.randint(0, MAX) range.
        jitter = secrets.randbelow(DATE_JITTER_MAX_DAYS + 1)
        target = DATE_ANCHOR - timedelta(days=jitter)
        earliest: datetime | None = None
        for ds in datasets:
            study_date = str(getattr(ds, "StudyDate", "") or "").strip()
            if len(study_date) >= 8:
                try:
                    parsed = datetime.strptime(study_date[:8], "%Y%m%d")
                except ValueError:
                    continue
                if earliest is None or parsed < earliest:
                    earliest = parsed
        if earliest is not None:
            self._date_shift_offset = (target - earliest).days
        else:
            self._date_shift_offset = (target - datetime(2000, 1, 1)).days

    def _set_deidentification_tags(self, ds: Dataset) -> None:
        """Write PS3.15 provenance + CID 7050 method codes for the applied options."""
        if self.options.date_remove:
            date_mode = "remove"
        elif self.options.date_shift:
            date_mode = "shift"
        else:
            date_mode = "keep"
        apply_deidentification_provenance(
            ds,
            method_text=DEIDENTIFICATION_METHOD,
            date_mode=date_mode,
            retain_device_identity=self.options.retain_device_identity,
            retain_institution_identity=self.options.retain_institution_identity,
            retain_uids=not self.options.remint_uids,
        )

    @staticmethod
    def _remove_tag(ds: Dataset, tag: BaseTag) -> None:
        if tag in ds:
            try:
                del ds[tag]
            except Exception:
                try:
                    ds[tag].value = ""
                except Exception:
                    pass

    @staticmethod
    def _blank_tag(ds: Dataset, tag: BaseTag) -> None:
        """Set a present element to a zero-length value (PS3.15 action Z).

        Keeps the element so Type-2 attributes stay IOD-conformant; only acts when
        the tag is present.
        """
        if tag in ds:
            try:
                ds[tag].value = ""
            except Exception:
                pass

    def _remove_tags_in_dataset_tree(
        self, ds: Dataset, tags: Sequence[BaseTag]
    ) -> None:
        """Remove matching tags from ``ds`` and every nested sequence item."""
        tag_set = set(tags)
        for elem in list(ds):
            if elem.tag in tag_set:
                self._remove_tag(ds, elem.tag)
                continue
            if elem.VR == "SQ" and elem.value:
                for item in elem.value:
                    if isinstance(item, Dataset):
                        self._remove_tags_in_dataset_tree(item, tags)

    def _blank_tags_in_dataset_tree(
        self, ds: Dataset, tags: Sequence[BaseTag]
    ) -> None:
        """Blank matching tags in ``ds`` and every nested sequence item."""
        tag_set = set(tags)
        for elem in list(ds):
            if elem.tag in tag_set:
                self._blank_tag(ds, elem.tag)
                continue
            if elem.VR == "SQ" and elem.value:
                for item in elem.value:
                    if isinstance(item, Dataset):
                        self._blank_tags_in_dataset_tree(item, tags)

    def _strip_private_tags(self, ds: Dataset) -> None:
        """Remove odd-group (private) tags from the dataset and nested sequences."""
        to_delete: list[BaseTag] = []
        for elem in ds:
            if elem.tag.group % 2 == 1:
                to_delete.append(elem.tag)
        for tag in to_delete:
            self._remove_tag(ds, tag)
        for elem in ds:
            if elem.VR == "SQ" and elem.value:
                for item in elem.value:
                    if isinstance(item, Dataset):
                        self._strip_private_tags(item)

    def _apply_uid_remap(self, ds: Dataset) -> None:
        """Replace known UIDs in the dataset tree."""
        for elem in list(ds):
            if elem.VR == "UI":
                ds[elem.tag].value = self._remap_ui_value(elem.value)
            elif elem.VR == "SQ" and elem.value:
                for item in elem.value:
                    if isinstance(item, Dataset):
                        self._apply_uid_remap(item)

    def _remap_ui_value(
        self, value: str | bytes | list[str] | None
    ) -> str | list[str] | None:
        if value is None:
            return None
        if isinstance(value, (list, tuple)):
            return [self._remap_single_uid(str(v)) for v in value]
        return self._remap_single_uid(str(value))

    def _remap_single_uid(self, uid: str) -> str:
        uid = uid.strip()
        # Never remap empty or DICOM-standard UIDs (SOP Class, Transfer Syntax,
        # coding schemes). Defense-in-depth: these are never collected into the
        # map either (see _collect_ui_values_from_element).
        if not uid or uid.startswith(DICOM_STANDARD_UID_ROOT):
            return uid
        return self._uid_map.get(uid, uid)

    def _collect_ui_values_from_element(self, ds: Dataset, seen: set[str]) -> None:
        for elem in ds:
            if elem.VR == "UI":
                for uid in self._ui_values(elem.value):
                    # Skip DICOM-standard UIDs (e.g. SOPClassUID, TransferSyntaxUID,
                    # ReferencedSOPClassUID) — only instance identifiers are remapped.
                    if uid and not uid.startswith(DICOM_STANDARD_UID_ROOT):
                        seen.add(uid)
            elif elem.VR == "SQ" and elem.value:
                for item in elem.value:
                    if isinstance(item, Dataset):
                        self._collect_ui_values_from_element(item, seen)

    @staticmethod
    def _ui_values(value: object) -> list[str]:
        if value is None:
            return []
        if isinstance(value, (list, tuple)):
            return [str(v).strip() for v in value if str(v).strip()]
        text = str(value).strip()
        return [text] if text else []

    def _blank_dates_in_dataset(self, ds: Dataset) -> None:
        """Replace date values with zero-length strings (PS3.15 "Z" action).

        Blanks DA/DT (date-bearing) elements rather than deleting them, so Type-2
        attributes like StudyDate/PatientBirthDate stay present-but-empty and the
        file remains DICOM-conformant. Pure time (TM) elements are left intact.
        """
        for elem in list(ds):
            if elem.VR in ("DA", "DT"):
                try:
                    ds[elem.tag].value = ""
                except Exception:
                    pass
            elif elem.VR == "SQ" and elem.value:
                for item in elem.value:
                    if isinstance(item, Dataset):
                        self._blank_dates_in_dataset(item)

    def _shift_dates_in_dataset(self, ds: Dataset, offset_days: int) -> None:
        for elem in list(ds):
            if is_date_vr(elem.VR):
                shifted = self._shift_date_value(elem.value, elem.VR, offset_days)
                if shifted is not None:
                    try:
                        ds[elem.tag].value = shifted
                    except Exception:
                        pass
            elif elem.VR == "SQ" and elem.value:
                for item in elem.value:
                    if isinstance(item, Dataset):
                        self._shift_dates_in_dataset(item, offset_days)

    @staticmethod
    def _shift_date_value(
        value: object, vr: str, offset_days: int
    ) -> str | list[str] | None:
        if value is None or value == "":
            return None
        if isinstance(value, (list, tuple)):
            out = [
                DeepDICOMAnonymizer._shift_single_date(str(v), vr, offset_days)
                for v in value
            ]
            return out
        return DeepDICOMAnonymizer._shift_single_date(str(value), vr, offset_days)

    @staticmethod
    def _shift_single_date(text: str, vr: str, offset_days: int) -> str:
        text = text.strip()
        if not text:
            return text
        try:
            if vr == "DA" and len(text) >= 8:
                dt = datetime.strptime(text[:8], "%Y%m%d")
                return (dt + timedelta(days=offset_days)).strftime("%Y%m%d")
            if vr == "DT" and len(text) >= 8:
                # Preserve time fraction when possible.
                date_part = text[:8]
                rest = text[8:]
                dt = datetime.strptime(date_part, "%Y%m%d")
                shifted = (dt + timedelta(days=offset_days)).strftime("%Y%m%d")
                return shifted + rest
            if vr == "TM":
                return text
        except ValueError:
            return text
        return text
