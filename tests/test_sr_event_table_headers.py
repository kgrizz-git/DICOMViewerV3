"""
Unit tests for SR dose-events table header ordering and empty-column detection.

**Purpose:** Verify :func:`core.rdsr_irradiation_events.ordered_irradiation_event_column_headers` and
:func:`core.rdsr_irradiation_events.irradiation_event_column_is_empty_for_all_rows` used by the
Structured Report browser **Dose events** tab (hide-empty-columns is a separate Qt wiring concern).

**Inputs:** Synthetic :class:`core.rdsr_irradiation_events.IrradiationEventRow` instances.

**Outputs:** Unittest assertions only.

**Requirements:** ``src`` on ``sys.path`` (see ``tests/conftest.py``), project imports.
"""

from __future__ import annotations

import unittest

from core.rdsr_irradiation_events import (
    IrradiationEventRow,
    irradiation_event_column_is_empty_for_all_rows,
    ordered_irradiation_event_column_headers,
)


def _row(node_id: int, columns: dict[str, str]) -> IrradiationEventRow:
    return IrradiationEventRow(node_id_placeholder=node_id, path_indices=(0,), event_concept="DCM", columns=columns)


class TestSrEventTableHeaders(unittest.TestCase):
    def test_ordered_event_headers_first_seen_order_and_union(self) -> None:
        rows = [
            _row(1, {"A": "1", "B": "2"}),
            _row(2, {"B": "x", "C": "y"}),
        ]
        self.assertEqual(ordered_irradiation_event_column_headers(rows), ["A", "B", "C"])

    def test_ordered_event_headers_empty_rows(self) -> None:
        self.assertEqual(ordered_irradiation_event_column_headers([]), [])

    def test_event_column_is_empty_for_all_rows(self) -> None:
        rows = [
            _row(1, {"filled": "a", "blank": "", "spaces": "   "}),
            _row(2, {"filled": "b"}),  # missing "blank" and "spaces" => treated blank
        ]
        self.assertIs(irradiation_event_column_is_empty_for_all_rows(rows, "filled"), False)
        self.assertIs(irradiation_event_column_is_empty_for_all_rows(rows, "blank"), True)
        self.assertIs(irradiation_event_column_is_empty_for_all_rows(rows, "spaces"), True)
        self.assertIs(irradiation_event_column_is_empty_for_all_rows(rows, "missing"), True)


if __name__ == "__main__":
    unittest.main()
