"""Shared privacy primitives for runtime output and internal storage."""

from utils.privacy.classification import (
    PATIENT_PII_FIELDS,
    SENSITIVE_CONTEXT_KEYS,
    SENSITIVE_DICOM_FIELDS,
)
from utils.privacy.console import print_redacted, print_structural_event
from utils.privacy.dialogs import generic_error_message
from utils.privacy.logging_filter import PrivacyLogFilter, install_privacy_filter
from utils.privacy.redaction import (
    redact_exception,
    redact_text,
    redact_value,
    safe_event_fields,
)
from utils.privacy.reports import write_redacted_json_report
from utils.privacy.safe_storage import (
    RETENTION_METADATA_FILENAME,
    RetentionPolicy,
    assert_safe_internal_path,
    atomic_write_private_text,
    ensure_private_directory,
    get_private_app_dir,
    secure_unlink,
    write_retention_metadata,
)
from utils.privacy.streams import PrivacyTextStream, install_privacy_streams
from utils.privacy.structural_events import (
    StructuralEvent,
    log_structural_event,
    render_structural_event,
    structural_event,
)

__all__ = [
    "PATIENT_PII_FIELDS",
    "RETENTION_METADATA_FILENAME",
    "SENSITIVE_CONTEXT_KEYS",
    "SENSITIVE_DICOM_FIELDS",
    "PrivacyLogFilter",
    "PrivacyTextStream",
    "RetentionPolicy",
    "StructuralEvent",
    "assert_safe_internal_path",
    "atomic_write_private_text",
    "ensure_private_directory",
    "generic_error_message",
    "get_private_app_dir",
    "install_privacy_filter",
    "install_privacy_streams",
    "log_structural_event",
    "print_redacted",
    "print_structural_event",
    "redact_exception",
    "redact_text",
    "redact_value",
    "render_structural_event",
    "safe_event_fields",
    "secure_unlink",
    "structural_event",
    "write_redacted_json_report",
    "write_retention_metadata",
]
