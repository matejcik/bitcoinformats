from __future__ import annotations

import hashlib
import struct

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


CompactUintStruct = c.Struct(
    "base" / c.Int8ul,
    "ext" / c.Switch(c.this.base, {0xFD: c.Int16ul, 0xFE: c.Int32ul, 0xFF: c.Int64ul}),
)
"""Struct for Bitcoin's Compact uint / varint"""


class CompactUintAdapter(c.Adapter):
    """Adapter for Bitcoin's Compact uint / varint"""

    def _encode(self, obj, context, path):
        if obj < 0xFD:
            return {"base": obj, "ext": None}
        if obj < 2**16:
            return {"base": 0xFD, "ext": obj}
        if obj < 2**32:
            return {"base": 0xFE, "ext": obj}
        if obj < 2**64:
            return {"base": 0xFF, "ext": obj}
        raise ValueError("Value too big for compact uint")

    def _decode(self, obj, context, path):
        return obj["ext"] or obj["base"]


class ConstFlag(c.Adapter):
    """Constant value that might or might not be present.

    When parsing, if the appropriate value is found, it is consumed and
    this field set to True.
    When building, if True, the constant is inserted, otherwise it is omitted.
    """

    def __init__(self, const):
        self.const = const
        super().__init__(
            c.IfThenElse(
                c.this._building,
                c.Select(c.Bytes(len(self.const)), c.Pass),
                c.Optional(c.Const(const)),
            )
        )

    def _encode(self, obj, context, path):
        return self.const if obj else None

    def _decode(self, obj, context, path):
        return obj is not None


CompactUint = CompactUintAdapter(CompactUintStruct)
"""Bitcoin Compact uint construct.

Encodes an int as either:
- a single byte the value is smaller than 253 (0xFD)
- 0xFD + uint16 if the value fits into uint16
- 0xFE + uint32 if the value fits into uint32
- 0xFF + uint64 if the value is bigger.
"""


def op_push(data: bytes) -> bytes:
    """Generate OP_PUSH instruction and length of the appropriate size."""
    n = len(data)
    if n < 0x4C:
        return struct.pack("<B", n)
    if n <= 0xFF:
        return struct.pack("<BB", 0x4C, n)
    if n <= 0xFFFF:
        return struct.pack("<BS", 0x4D, n)
    if n <= 0xFFFF_FFFF:
        return struct.pack("<BL", 0x4E, n)
    
    raise ValueError("data too big for OP_PUSH")


def build_op_push(data: bytes) -> bytes:
    """Build an OP_PUSHed data by prefixing it with the appropriate OP_PUSH instruction."""
    return op_push(data) + data


def extract_op_push(data: bytes) -> bytes:
    """Extract the data from an OP_PUSHed block."""
    if not data:
        raise ValueError("empty data")
    header = data[0]
    if header < 0x4C:
        data_len = header
        offset = 1
    elif header == 0x4C and len(data) > 2:
        data_len = data[1]
        offset = 2
    elif header == 0x4D and len(data) > 3:
        data_len = int.from_bytes(data[1:3], "little")
        offset = 3
    elif header == 0x4E and len(data) > 5:
        data_len = int.from_bytes(data[1:5], "little")
        offset = 5
    else:
        raise ValueError("Invalid OP_PUSH header")

    if len(data) != offset + data_len:
        raise ValueError("Invalid OP_PUSH length")

    return data[offset:]
