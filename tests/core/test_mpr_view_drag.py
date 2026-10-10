"""Versioned MPR tile drag payload: encode/decode, bounds, origin token and rejection."""

from __future__ import annotations

import json

import pytest

from core.mpr_view_drag import (
    MAX_PAYLOAD_BYTES,
    MAX_VIEW_ID,
    MPR_VIEW_MIME,
    OP_MOVE,
    ViewDragPayload,
    decode_view_drag,
    encode_view_drag,
    new_drag_origin,
    same_origin,
)

ORIGIN = "AbCdEfGhIjKlMnOpQr_-12"


def test_round_trip_carries_view_id_operation_and_origin_only() -> None:
    raw = encode_view_drag(321, ORIGIN, OP_MOVE)
    assert decode_view_drag(raw) == ViewDragPayload(view_id=321, operation=OP_MOVE, origin=ORIGIN)
    assert set(json.loads(raw)) == {"v", "op", "view", "origin"}  # no pane index in the schema
    assert len(raw) <= MAX_PAYLOAD_BYTES


def test_mime_type_is_distinct_from_the_retired_bare_integer_one() -> None:
    assert MPR_VIEW_MIME == "application/x-dv3-mpr-view"
    assert MPR_VIEW_MIME != "application/x-dv3-mpr-assign"


@pytest.mark.parametrize("bad", [0, -1, True, 1.0, "3", None, MAX_VIEW_ID + 1])
def test_encode_rejects_invalid_ids(bad) -> None:
    with pytest.raises(ValueError):
        encode_view_drag(bad, ORIGIN)


@pytest.mark.parametrize("bad", ["", "short", "x" * 33, "has space 1234567890", "bad/char/12345678", None, 5])
def test_encode_rejects_invalid_origin_tokens(bad) -> None:
    with pytest.raises(ValueError):
        encode_view_drag(1, bad)  # type: ignore[arg-type]


def test_encode_rejects_unknown_operation() -> None:
    with pytest.raises(ValueError):
        encode_view_drag(1, ORIGIN, "duplicate")


def test_largest_valid_payload_round_trips_within_the_size_bound() -> None:
    raw = encode_view_drag(MAX_VIEW_ID, "A" * 32)
    assert len(raw) <= MAX_PAYLOAD_BYTES
    assert decode_view_drag(raw).view_id == MAX_VIEW_ID  # type: ignore[union-attr]


def test_generated_tokens_are_valid_opaque_and_distinct() -> None:
    tokens = {new_drag_origin() for _ in range(50)}
    assert len(tokens) == 50  # 128 bits of randomness: no collisions
    for token in tokens:
        assert decode_view_drag(encode_view_drag(1, token)) is not None
        assert 16 <= len(token) <= 32


def test_same_origin_matches_only_the_identical_token() -> None:
    own = new_drag_origin()
    assert same_origin(own, own) is True
    assert same_origin(new_drag_origin(), own) is False
    assert same_origin(own + "x", own) is False


def _body(**overrides) -> bytes:
    body = {"v": 1, "op": "move", "view": 1, "origin": ORIGIN}
    body.update(overrides)
    return json.dumps(body).encode()


@pytest.mark.parametrize(
    "raw",
    [
        b"",
        b"1",
        b"-1",
        b"null",
        b"[]",
        b"{",
        b'{"v":1,"op":"move","view":1}',  # missing origin (an older/foreign producer)
        _body(origin=None),
        _body(origin=""),
        _body(origin="short"),
        _body(origin="has spaces in it!!"),
        _body(origin="x" * 33),
        _body(origin=12345678901234567890),
        _body(extra=1),  # extra key
        _body(v=2),  # foreign version
        _body(v="1"),
        _body(v=True),
        _body(op="swap"),
        _body(op=1),
        _body(view=0),
        _body(view=-5),
        _body(view=1.5),
        _body(view="1"),
        _body(view=False),
        _body(view=2147483648),
        b'{"v":1,"op":"move","view":NaN,"origin":"AbCdEfGhIjKlMnOpQr_-12"}',
        "é".encode(),  # non-ASCII
        b"\xff\xfe",
    ],
)
def test_decode_rejects_malformed_missing_origin_or_foreign_payloads(raw: bytes) -> None:
    assert decode_view_drag(raw) is None


def test_decode_rejects_oversized_payload_before_parsing() -> None:
    padded = _body() + b" " * MAX_PAYLOAD_BYTES
    assert decode_view_drag(padded) is None
    assert decode_view_drag(b"{" + b"[" * 100000) is None


@pytest.mark.parametrize("raw", ["text", 5, None, object()])
def test_decode_rejects_non_bytes_input(raw) -> None:
    assert decode_view_drag(raw) is None


def test_decode_accepts_bytearray_and_memoryview() -> None:
    raw = encode_view_drag(9, ORIGIN)
    assert decode_view_drag(bytearray(raw)).view_id == 9  # type: ignore[union-attr]
    assert decode_view_drag(memoryview(raw)).view_id == 9  # type: ignore[union-attr]
