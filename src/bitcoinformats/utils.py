from __future__ import annotations

import hashlib

import construct as c


def hash256(data: bytes) -> bytes:
    """Perform OP_HASH256.

    Hashes the data with SHA256 twice.
    """
    return hashlib.sha256(hashlib.sha256(data).digest()).digest()


def hash160(data: bytes) -> bytes:
    """Perform OP_HASH160.

    Hashes the data with SHA256 and then RIPEMD160.
    """
    return hashlib.new("ripemd160", hashlib.sha256(data).digest()).digest()


def ConstFlag(const: bytes) -> c.Construct:
    """Constant value that might or might not be present.

    When parsing, if the appropriate value is found, it is consumed and
    this field set to True.
    When building, if True, the constant is inserted, otherwise it is omitted.
    """

    class Adapter(c.Adapter):
        def _encode(self, obj, context, path):
            return const if obj else None

        def _decode(self, obj, context, path):
            return obj is not None

    subcon = c.IfThenElse(
        c.this._building,
        c.Select(c.Bytes(len(const)), c.Pass),
        c.Optional(c.Const(const)),  # type: ignore /mismatch of Const type to the outer type?/
    )

    return Adapter(subcon)


_CompactUintStruct = c.Struct(
    "base" / c.Int8ul,
    "ext" / c.Switch(c.this.base, {0xFD: c.Int16ul, 0xFE: c.Int32ul, 0xFF: c.Int64ul}),
)
"""Struct for Bitcoin's Compact uint / varint"""


class _CompactUintAdapter(c.Adapter):
    """Adapter for Bitcoin's Compact uint / varint"""

    def _encode(self, obj: int, context, path):
        if obj < 0xFD:
            return {"base": obj, "ext": None}
        if obj < 2**16:
            return {"base": 0xFD, "ext": obj}
        if obj < 2**32:
            return {"base": 0xFE, "ext": obj}
        if obj < 2**64:
            return {"base": 0xFF, "ext": obj}
        raise ValueError("Value too big for compact uint")

    def _decode(self, obj: c.Container, context, path):
        return obj["ext"] or obj["base"]


CompactUint = _CompactUintAdapter(_CompactUintStruct)
"""Bitcoin Compact uint construct.

Encodes an int as either:
- a single byte the value is smaller than 253 (0xFD)
- 0xFD + uint16 if the value fits into uint16
- 0xFE + uint32 if the value fits into uint32
- 0xFF + uint64 if the value is bigger.
"""

BitcoinBytes = c.Prefixed(CompactUint, c.GreedyBytes)
"""Bitcoin string of bytes.

Encoded as a CompactUint length followed by that many bytes.
"""

TxHash = c.Transformed(c.Bytes(32), lambda b: b[::-1], 32, lambda b: b[::-1], 32)
"""Transaction hash, encoded as a reversed sequence of bytes."""
