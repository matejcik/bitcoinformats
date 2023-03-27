import typing as t

import construct as c
from typing_extensions import Self

from ..struct import Struct
from ..utils import BitcoinBytes, CompactUint


class Bip32Field(Struct):
    """BIP32 field."""

    fingerprint: bytes
    address_n: t.List[int]

    SUBCON = c.Struct(
        "fingerprint" / c.Bytes(4),
        "address_n" / c.GreedyRange(c.Int32ul),
    )


class TxModifiableBits(Struct):
    inputs_modifiable: bool
    outputs_modifiable: bool
    has_sighash_single: bool

    SUBCON = c.BitStruct(
        "inputs_modifiable" / c.Bit,
        "outputs_modifiable" / c.Bit,
        "has_sighash_single" / c.Bit,
        "_reserved" / c.Padding(5),
    )


class TapScriptSigKey(Struct):
    """Key of TAP_SCRIPT_SIG field.

    Consists of X-only public key and a hash of the leaf it is part of.
    """

    pubkey: bytes
    leafhash: bytes

    SUBCON = c.Struct(
        "pubkey" / c.Bytes(32),
        "leafhash" / c.Bytes(32),
    )


class TapLeafScript(Struct):
    """Value of TAP_LEAF_SCRIPT field.

    Consists of a script for the leaf, and a single byte leaf version.
    """

    script: bytes
    version: int

    SUBCON = c.Struct(
        "script" / c.GreedyBytes,
        "version" / c.Int8ul,
    )

    @classmethod
    def parse(cls, data: bytes) -> Self:
        # The chosen format is uniquely unsuited for Construct, because it cannot be
        # parsed from a stream.
        # Fortunately, it is trivial to "parse" by hand.
        return cls(script=data[:-1], version=data[-1])


class TapBip32Derivation(Struct):
    """Value of TAP_BIP32_DERIVATION field.

    Consists of a BIP32 derivation path and a single byte derivation version.
    """

    hashes: t.List[bytes]
    bip32: Bip32Field

    SUBCON = c.Struct(
        "path" / c.PrefixedArray(CompactUint, c.Bytes(32)),
        "version" / Bip32Field.SUBCON,
    )


class TapTreeLeaf(Struct):
    """Single entry in TAP_TREE field."""

    depth: int
    leaf_version: int
    leaf_script: bytes

    SUBCON = c.Struct(
        "depth" / c.Int8ul,
        "leaf_version" / c.Int8ul,
        "leaf_script" / BitcoinBytes,
    )


class TapTree(Struct):
    """Value of TAP_TREE field.

    Consists of a list of TapTreeLeaf.
    """

    nodes: t.List[TapTreeLeaf]

    SUBCON = c.Struct(
        "nodes" / c.PrefixedArray(CompactUint, TapTreeLeaf.SUBCON),
    )
