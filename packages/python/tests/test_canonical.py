from __future__ import annotations

import hashlib
import math

from datamonger._canonical import canonical_bytes, canonical_sha256
from datamonger._models import LogicalComponent


def test_int64_vector_has_exact_provisional_encoding() -> None:
    component = LogicalComponent(
        name="count",
        logical_type="int64",
        values=(1, 999, -2),
        valid=(True, False, True),
    )

    expected = bytes.fromhex(
        "444d4346"  # DMCF
        "0100"  # version
        "01000000"  # component count
        "05000000"  # name length
        "636f756e74"  # count
        "01"  # vector
        "02"  # int64
        "01"  # rank
        "0300000000000000"  # length
        "05"  # validity
        "0100000000000000"
        "0000000000000000"
        "feffffffffffffff"
    )

    assert canonical_bytes((component,)) == expected
    assert canonical_sha256((component,)) == hashlib.sha256(expected).hexdigest()


def test_float_encoding_normalizes_negative_zero_nan_and_invalid_storage() -> None:
    component = LogicalComponent(
        name="x",
        logical_type="float64",
        values=(-0.0, math.nan, 123.0),
        valid=(True, True, False),
    )

    encoded = canonical_bytes((component,))

    assert encoded[-24:] == bytes.fromhex(
        "0000000000000000"  # normalized negative zero
        "000000000000f87f"  # canonical quiet NaN
        "0000000000000000"  # invalid storage
    )


def test_bool_padding_and_invalid_bits_are_zero() -> None:
    component = LogicalComponent(
        name="flag",
        logical_type="bool",
        values=(True, True, True, True, True),
        valid=(True, False, True, True, True),
    )

    encoded = canonical_bytes((component,))

    assert encoded[-2:] == bytes((0b00011101, 0b00011101))
