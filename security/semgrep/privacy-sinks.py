import logging
import socket
import sys
import traceback
import urllib.request

import requests

from utils.log_sanitizer import sanitize_message
from utils.privacy.redaction import redact_text


def unsafe_sinks(value, logger, debug_log):
    # ruleid: dicomviewer-privacy-forbidden-traceback-output
    traceback.print_exc()
    # ruleid: dicomviewer-privacy-forbidden-traceback-output
    traceback.print_stack()
    # ruleid: dicomviewer-privacy-forbidden-logging-exception
    logging.exception("failed")
    # ruleid: dicomviewer-privacy-forbidden-logging-exception
    logger.exception("failed")
    # ruleid: dicomviewer-privacy-forbidden-exc-info
    logger.error("failed", exc_info=True)
    # ruleid: dicomviewer-privacy-unsafe-dynamic-output
    print(value)
    # ruleid: dicomviewer-privacy-unsafe-dynamic-output
    sys.stderr.write(value)
    # ruleid: dicomviewer-privacy-unsafe-dynamic-output
    debug_log("module:1", "event", value)


def unsafe_network(sock):
    # ruleid: dicomviewer-privacy-unapproved-outbound-network
    requests.post("https://example.invalid")
    # ruleid: dicomviewer-privacy-unapproved-outbound-network
    urllib.request.urlopen("https://example.invalid")
    # ruleid: dicomviewer-privacy-unapproved-outbound-network
    socket.create_connection(("example.invalid", 443))
    # ruleid: dicomviewer-privacy-unapproved-outbound-network
    sock.connect(("example.invalid", 443))


def reviewed_safe_output(value):
    # ok: dicomviewer-privacy-unsafe-dynamic-output
    print(sanitize_message(value))
    # ok: dicomviewer-privacy-unsafe-dynamic-output
    sys.stderr.write(redact_text(value))
