import hashlib
from dataclasses import asdict, field, replace
from enum import IntEnum

import construct as c

from .struct import Struct, subcon
from .utils import CompactUint, ConstFlag, hash256, BitcoinBytes, TxHash


class HashType(IntEnum):
    """Possible values of Bitcoin hashtypes."""

    SIGHASH_ALL = 0x01
    SIGHASH_NONE = 0x02
    SIGHASH_SINGLE = 0x03
    SIGHASH_ANYONECANPAY = 0x80


class TxInput(Struct):
    """Transaction input."""

    prev_tx: bytes
    index: int
    script_sig: bytes
    sequence: int

    SUBCON = c.Struct(
        "prev_tx" / TxHash,
        "index" / c.Int32ul,
        "script_sig" / BitcoinBytes,
        "sequence" / c.Int32ul,
    )


class TxOutput(Struct):
    """Transaction output."""

    amount: int
    script_pubkey: bytes

    SUBCON = c.Struct("amount" / c.Int64ul, "script_pubkey" / BitcoinBytes)


TxInputWitness = c.PrefixedArray(CompactUint, BitcoinBytes)
"""Array of witness records."""


class Transaction(Struct):
    """Bitcoin transaction.

    If the `segwit` flag is present (which would otherwise mean 0 inputs, 1 output),
    we expect a `witness` field with entries corresponding to each input.
    """

    version: int
    segwit: bool
    locktime: int
    inputs: list[TxInput] = subcon(TxInput)
    outputs: list[TxOutput] = subcon(TxOutput)
    witness: list[bytes] = field(default_factory=list)

    SUBCON = c.Struct(
        "version" / c.Int32ul,
        "segwit" / ConstFlag(b"\x00\x01"),
        "inputs" / c.PrefixedArray(CompactUint, TxInput.SUBCON),
        "outputs" / c.PrefixedArray(CompactUint, TxOutput.SUBCON),
        "witness" / c.If(c.this.segwit, TxInputWitness[c.len_(c.this.inputs)]),
        "locktime" / c.Int32ul,
        c.Terminated,
    )

    def get_txid(self) -> bytes:
        non_segwit = replace(self, segwit=False, witness=[])
        return non_segwit.get_txhash()

    def get_txhash(self) -> bytes:
        return hash256(self.SUBCON.build(asdict(self)))[::-1]

    def get_bip143_digest(
        self,
        input_idx: int,
        prevout: TxOutput,
        *,
        hash_type: HashType = HashType.SIGHASH_ALL
    ) -> bytes:
        if hash_type != HashType.SIGHASH_ALL:
            raise NotImplementedError

        selected_input = self.inputs[input_idx]

        hash = hashlib.sha256()
        # 1. nVersion
        hash.update(self.version.to_bytes(4, "little"))

        # 2. hashPrevouts
        hash_prevouts = hashlib.sha256()
        for inp in self.inputs:
            hash_prevouts.update(inp.build())
        hash.update(hash_prevouts.digest())

        # 3. hashSequence
        hash_sequence = hashlib.sha256()
        for inp in self.inputs:
            hash_sequence.update(inp.sequence.to_bytes(4, "little"))
        hash.update(hash_sequence.digest())

        # 4. outpoint
        hash.update(selected_input.prev_tx)
        hash.update(selected_input.index.to_bytes(4, "little"))

        # 5. scriptCode of the input
        hash.update(prevout.script_pubkey)

        # 6. amount of the output
        hash.update(prevout.amount.to_bytes(8, "little"))

        # 7. nSequence
        hash.update(selected_input.sequence.to_bytes(4, "little"))

        # 8. hashOutputs
        hash_outputs = hashlib.sha256()
        for out in self.outputs:
            hash_outputs.update(out.amount.to_bytes(8, "little"))
        hash.update(hash_outputs.digest())

        # 9. nLocktime
        hash.update(self.locktime.to_bytes(4, "little"))

        # 10. hashType
        hash.update(hash_type.value.to_bytes(4, "little"))

        return hash.digest()
