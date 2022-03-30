from dataclasses import dataclass, field

import construct as c

from . import CompactUint, ConstFlag
from .struct import Struct, subcon

BitcoinBytes = c.Prefixed(CompactUint, c.GreedyBytes)
"""Bitcoin string of bytes.

Encoded as a CompactUint length followed by that many bytes.
"""

TxHash = c.Transformed(c.Bytes(32), lambda b: b[::-1], 32, lambda b: b[::-1], 32)
"""Transaction hash, encoded as a reversed sequence of bytes."""


@dataclass
class TxInput(Struct):
    """Transaction input."""

    tx: bytes
    index: int
    script_sig: bytes
    sequence: int

    SUBCON = c.Struct(
        "tx" / TxHash,
        "index" / c.Int32ul,
        "script_sig" / BitcoinBytes,
        "sequence" / c.Int32ul,
    )


@dataclass
class TxOutput(Struct):
    """Transaction output."""

    value: int
    script_pubkey: bytes

    SUBCON = c.Struct("value" / c.Int64ul, "script_pubkey" / BitcoinBytes)


TxInputWitness = c.PrefixedArray(CompactUint, BitcoinBytes)
"""Array of witness records."""


@dataclass
class Transaction(Struct):
    """Bitcoin transaction.

    If the `segwit` flag is present (which would otherwise mean 0 inputs, 1 output),
    we expect a `witness` field with entries corresponding to each input.
    """

    version: int
    lock_time: int
    witness: list[TxInputWitness] = field(default_factory=list)
    inputs: list[TxInput] = subcon(TxInput)
    outputs: list[TxOutput] = subcon(TxOutput)

    SUBCON = c.Struct(
        "version" / c.Int32ul,
        "segwit" / ConstFlag(b"\x00\x01"),
        "inputs" / c.PrefixedArray(CompactUint, TxInput.SUBCON),
        "outputs" / c.PrefixedArray(CompactUint, TxOutput.SUBCON),
        "witness" / c.If(c.this.segwit, TxInputWitness[c.len_(c.this.inputs)]),
        "lock_time" / c.Int32ul,
        c.Terminated,
    )
