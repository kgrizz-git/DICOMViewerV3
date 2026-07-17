"""Shared structural-event schema access for the local privacy scanner."""

from __future__ import annotations

import sys
from pathlib import Path

_SRC_ROOT = Path(__file__).resolve().parents[2] / "src"
if str(_SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(_SRC_ROOT))

from utils.privacy.structural_schema import (
    SCHEMA_RELATIVE_PATH,
    StructuralEventSchema,
    StructuralSchemaError,
    load_structural_event_schema,
)

__all__ = [
    "SCHEMA_RELATIVE_PATH",
    "StructuralEventSchema",
    "StructuralSchemaError",
    "load_structural_event_schema",
]
