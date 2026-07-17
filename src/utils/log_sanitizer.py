"""
Log Sanitization Utility

Provides functions to redact sensitive information from log messages and exceptions
before output. This prevents accidental exposure of:
- Patient PII (name, ID, DOB, age)
- File paths that may contain user/patient identifiers
- Exception details that may leak system information

Usage:
    from utils.log_sanitizer import sanitize_message, sanitize_exception
    
    # Sanitize a generic message
    safe_msg = sanitize_message(f"Error for patient {patient_name}")
    
    # Sanitize an exception traceback
    safe_traceback = sanitize_exception(traceback.format_exc())
"""

import re

from utils.privacy.classification import PATIENT_PII_FIELDS
from utils.privacy.redaction import redact_exception, redact_text


def sanitize_message(message: str, redact_paths: bool = False) -> str:
    """
    Redact sensitive information from a log message.
    
    Args:
        message: The message to sanitize
        redact_paths: If True, also redact file paths (slower, use sparingly)
        
    Returns:
        Sanitized message with PII replaced with [REDACTED]
    """
    # ``redact_paths`` is retained for source compatibility.  Runtime output may
    # not opt out of full-path and basename protection, so the shared redactor
    # always removes absolute user paths.
    return redact_text(message, redact_paths=redact_paths)


def sanitize_exception(traceback_str: str) -> str:
    """
    Redact sensitive information from an exception traceback.
    
    Args:
        traceback_str: The full traceback string
        
    Returns:
        Sanitized traceback with paths and PII redacted
    """
    return redact_exception(traceback_str)


def sanitized_format_exc() -> str:
    """
    Return the current exception traceback as a redacted string for logging.

    Prefer this over ``traceback.print_exc()`` in application code so paths and
    PHI-like patterns are not written raw to stderr or logs.
    """
    import traceback

    return sanitize_exception(traceback.format_exc())


def create_safe_exception_handler(func_name: str = "") -> str:
    """
    Template for a safe exception handler that logs without leaking PII.
    
    Usage:
        try:
            risky_operation()
        except Exception as e:
            safe_msg = create_safe_exception_message(exc, "operation_name")
            logger.error(safe_msg)
    
    Args:
        func_name: Name of the function where error occurred
        
    Returns:
        Code template for safe exception handling
    """
    _ = func_name
    return """
try:
    # Your code here
    pass
except Exception as e:
    error_msg = f"Error in {func_name}: {{type(e).__name__}}: {{str(e)[:100]}}"
    safe_msg = sanitize_message(error_msg)
    # Use logger instead of print for production
    logger.error(safe_msg)
    # Debug mode only (not in production builds):
    if DEBUG_MODE:
        logger.debug(f"Full traceback: {{sanitize_exception(traceback.format_exc())}}")
"""


def validate_no_pii_in_output(message: str) -> tuple[bool, list[str]]:
    """
    Validate that a message doesn't contain obvious PII before logging.
    
    Args:
        message: The message to validate
        
    Returns:
        Tuple of (is_safe: bool, issues: list of found PII patterns)
    """
    issues = []

    # Check for patient fields
    for field in PATIENT_PII_FIELDS:
        if field in message:
            issues.append(f"Contains patient field name: {field}")

    # Check for date patterns with context clues
    date_pattern = r"\d{1,2}[/-]\d{1,2}[/-]\d{2,4}"
    if re.search(date_pattern, message):
        # Check if preceded by date-related keywords
        if any(kw in message.lower() for kw in ["dob", "birth", "date", "age"]):
            issues.append("Potential date of birth or age information")

    # Check for common ID patterns
    if re.search(r"(?:mrn|patient.?id|pid)[:\s=]+[A-Z0-9\-]{5,}", message, re.IGNORECASE):
        issues.append("Potential patient ID or MRN")

    return len(issues) == 0, issues


# Example production-ready exception handler
class SafeExceptionLogger:
    """Wrapper to log exceptions safely without leaking PII."""

    def __init__(self, logger, debug_enabled: bool = False):
        """
        Args:
            logger: Logger instance (e.g., from logging module)
            debug_enabled: If True, include full traceback in debug logs only
        """
        self.logger = logger
        self.debug_enabled = debug_enabled

    def log_exception(self, exc: Exception, context: str = ""):
        """
        Log an exception with automatic PII redaction.
        
        Args:
            exc: The exception to log
            context: Brief context about what was happening
        """
        msg = "Error"
        if context:
            msg += f" ({context})"
        msg += f": {type(exc).__name__}: {str(exc)[:150]}"

        safe_msg = sanitize_message(msg)
        self.logger.error(sanitize_message(safe_msg))

        if self.debug_enabled:
            # Only log full traceback in debug mode
            import traceback
            safe_trace = sanitize_exception(traceback.format_exc())
            self.logger.debug(sanitize_message(f"Debug traceback:\n{safe_trace}"))
