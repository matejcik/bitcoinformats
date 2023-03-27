import typing as t

import construct as c

from ..transaction import Transaction, TxOutput
from ..utils import CompactUint
from ._format import PsbtMapType, keytype
from .fields import (
    Bip32Field,
    TapBip32Derivation,
    TapLeafScript,
    TapScriptSigKey,
    TapTree,
    TxModifiableBits,
)

String = c.GreedyString("utf-8")


class PsbtGlobalMap(PsbtMapType):
    unsigned_tx: t.Optional[Transaction] = keytype(0x00, value=Transaction)
    xpub: t.Dict[str, t.List[int]] = keytype(
        0x01, key=String, value=c.GreedyRange(c.Int32ul)
    )
    tx_version: int = keytype(0x02, value=c.Int32ul)
    fallback_locktime: t.Optional[int] = keytype(0x03, value=c.Int32ul)
    input_count: int = keytype(0x04, value=CompactUint)
    output_count: int = keytype(0x05, value=CompactUint)
    tx_modifiable: t.Optional[TxModifiableBits] = keytype(0x06, value=TxModifiableBits)
    version: int = keytype(0xFB, value=c.Int32ul)


class PsbtInputMap(PsbtMapType):
    non_witnes_utxo: t.Optional[Transaction] = keytype(0x00, value=Transaction)
    witness_utxo: t.Optional[TxOutput] = keytype(0x01, value=TxOutput)
    partial_sig: t.Dict[bytes, bytes] = keytype(0x02, key=bytes, value=bytes)
    sighash_type: t.Optional[int] = keytype(0x03, value=c.Int32ul)
    redeem_script: t.Optional[bytes] = keytype(0x04, value=bytes)
    witness_script: t.Optional[bytes] = keytype(0x05, value=bytes)
    bip32_derivation: t.Dict[bytes, Bip32Field] = keytype(
        0x06, key=bytes, value=Bip32Field
    )
    final_scriptsig: t.Optional[bytes] = keytype(0x07, value=bytes)
    final_scriptwitness: t.Optional[bytes] = keytype(0x08, value=bytes)
    por_commitment: t.Optional[str] = keytype(0x09, value=c.GreedyString("utf8"))
    ripemd160: t.Optional[bytes] = keytype(0x0A, value=c.Bytes(20))
    sha256: t.Optional[bytes] = keytype(0x0B, value=c.Bytes(32))
    hash160: t.Optional[bytes] = keytype(0x0C, value=c.Bytes(20))
    hash256: t.Optional[bytes] = keytype(0x0D, value=c.Bytes(32))
    previous_txid: bytes = keytype(0x0E, value=c.Bytes(32))
    output_index: int = keytype(0x0F, value=CompactUint)
    sequence: t.Optional[int] = keytype(0x10, value=c.Int32ul)
    required_time_locktime: t.Optional[int] = keytype(0x11, value=c.Int32ul)
    required_height_locktime: t.Optional[int] = keytype(0x12, value=c.Int32ul)
    tap_key_sig: t.Dict[TapScriptSigKey, bytes] = keytype(
        0x13, key=TapScriptSigKey, value=bytes
    )
    tap_leaf_script: t.Dict[bytes, TapLeafScript] = keytype(
        0x14, key=bytes, value=TapLeafScript
    )
    tap_bip32_derivation: t.Dict[bytes, TapBip32Derivation] = keytype(
        0x15, key=c.Bytes(32), value=TapBip32Derivation
    )
    tap_internal_key: t.Optional[bytes] = keytype(0x16, value=c.Bytes(32))
    tap_merkle_root: t.Optional[bytes] = keytype(0x17, value=c.Bytes(32))


class PsbtOutputMap(PsbtMapType):
    redeem_script: t.Optional[bytes] = keytype(0x00, value=bytes)
    witness: t.Optional[bytes] = keytype(0x01, value=bytes)
    bip32_derivation: t.Optional[Bip32Field] = keytype(
        0x02, key=bytes, value=Bip32Field
    )
    amount: int = keytype(0x03, value=c.Int64sl)
    script: bytes = keytype(0x04, value=bytes)
    tap_internal_key: t.Optional[bytes] = keytype(0x05, value=c.Bytes(32))
    tap_tree: t.Optional[TapTree] = keytype(0x06, value=TapTree)
    tap_bip32_derivation: t.Optional[TapBip32Derivation] = keytype(
        0x07, key=c.Bytes(32), value=TapBip32Derivation
    )


V0_FORBIDDEN_KEYS_GLOBAL: t.List[int] = [
    field.id  # type: ignore /I know what I'm doing/
    for field in (
        PsbtGlobalMap.tx_version,
        PsbtGlobalMap.fallback_locktime,
        PsbtGlobalMap.input_count,
        PsbtGlobalMap.output_count,
        PsbtGlobalMap.tx_modifiable,
    )
]

V0_FORBIDDEN_KEYS_INPUT: t.List[int] = [
    field.id  # type: ignore /I know what I'm doing/
    for field in (
        PsbtInputMap.previous_txid,
        PsbtInputMap.output_index,
        PsbtInputMap.sequence,
        PsbtInputMap.required_time_locktime,
        PsbtInputMap.required_height_locktime,
    )
]

V0_FORBIDDEN_KEYS_OUTPUT: t.List[int] = [
    field.id  # type: ignore /I know what I'm doing/
    for field in (
        PsbtOutputMap.amount,
        PsbtOutputMap.script,
    )
]

V2_FORBIDDEN_KEYS_GLOBAL: t.List[int] = [
    PsbtGlobalMap.unsigned_tx.id  # type: ignore /I know what I'm doing/
]
