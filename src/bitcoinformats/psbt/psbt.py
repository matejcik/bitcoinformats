from dataclasses import dataclass, field
import typing as t

from construct import ConstructError
from typing_extensions import Self

from . import definitions as defs
from .error import PsbtError
from ._format import PsbtEnvelope, PsbtKeyValue


def _filter_forbidden_fields(
    sequence: t.Sequence[PsbtKeyValue], forbidden: t.Sequence[int]
) -> t.List[PsbtKeyValue]:
    return [keyvalue for keyvalue in sequence if keyvalue.key.type not in forbidden]


def _check_forbidden_fields(
    version: int,
    globals: t.Sequence[PsbtKeyValue],
    inputs: t.Sequence[t.Sequence[PsbtKeyValue]],
    outputs: t.Sequence[t.Sequence[PsbtKeyValue]],
) -> None:
    if version == 0:
        f_globals = _filter_forbidden_fields(globals, defs.V0_FORBIDDEN_KEYS_GLOBAL)
        f_inputs = [
            _filter_forbidden_fields(input, defs.V0_FORBIDDEN_KEYS_INPUT)
            for input in inputs
        ]
        f_outputs = [
            _filter_forbidden_fields(output, defs.V0_FORBIDDEN_KEYS_OUTPUT)
            for output in outputs
        ]
        if f_globals != globals or f_inputs != inputs or f_outputs != outputs:
            raise PsbtError(f"PSBT v0 contains forbidden fields")
    elif version == 2:
        f_globals = _filter_forbidden_fields(globals, defs.V2_FORBIDDEN_KEYS_GLOBAL)
        if f_globals != globals:
            raise PsbtError(f"PSBT v2 contains forbidden fields")
    else:
        assert False, "unhandled version"


@dataclass(kw_only=True)
class Psbt:
    """PSBT representation.

    Contains information about PSBT in a cross-version compatible format.
    That is, you can be sure that the globals field contains metainformation about
    the transaction (tx version, locktime, etc.), and inputs and outputs contain
    full information that would otherwise only be found in the `unsigned_tx` field.
    """

    globals: defs.PsbtGlobalMap
    inputs: t.List[defs.PsbtInputMap] = field(default_factory=list)
    outputs: t.List[defs.PsbtOutputMap] = field(default_factory=list)

    @staticmethod
    def _process_v0(main: defs.PsbtGlobalMap) -> None:
        """Process PSBT v0 format, check for required fields and fill in v2 data."""
        # Fill-in is done here and not in __post_init__ because this data is used
        # in parse() before object construction -- in particular, the parser needs to
        # know beforehand the version, number of inputs and outputs.
        if main.unsigned_tx is None:
            raise PsbtError("PSBT v0 does not contain a transaction")
        main.tx_version = main.unsigned_tx.version
        main.fallback_locktime = main.unsigned_tx.locktime or None
        main.input_count = len(main.unsigned_tx.inputs)
        main.output_count = len(main.unsigned_tx.outputs)
        main.version = 0

    @staticmethod
    def _process_v2(main: defs.PsbtGlobalMap) -> None:
        """Process PSBT v2 format, check for required fields."""
        if (
            main.tx_version is None
            or main.input_count is None
            or main.output_count is None
        ):
            raise PsbtError(
                "PSBT v2 does not contain enough information to create a transaction"
            )

    @classmethod
    def parse(cls, psbt_bytes: bytes) -> Self:
        """Parse an encoded PSBT byte sequence into a Psbt object.

        Validates the PSBT required fields according to BIP-174 and BIP-370.
        """
        try:
            psbt = PsbtEnvelope.parse(psbt_bytes)
            if not psbt:
                raise PsbtError("Empty PSBT envelope")
            main = defs.PsbtGlobalMap.from_sequence(psbt[0])
            if main.version == 2:
                cls._process_v2(main)
            elif main.version in (0, None):
                cls._process_v0(main)
            else:
                raise PsbtError("Unknown PSBT version")

            if len(psbt) != 1 + main.input_count + main.output_count:
                raise PsbtError("PSBT length does not match embedded transaction")

            input_seqs = psbt[1 : 1 + main.input_count]
            output_seqs = psbt[1 + main.input_count :]
            inputs = [defs.PsbtInputMap.from_sequence(s) for s in input_seqs]
            outputs = [defs.PsbtOutputMap.from_sequence(s) for s in output_seqs]
            _check_forbidden_fields(main.version, psbt[0], input_seqs, output_seqs)
            return cls(globals=main, inputs=inputs, outputs=outputs)

        except ConstructError as e:
            raise PsbtError("Could not parse PBST") from e

    def __post_init__(self) -> None:
        """Fill v2 required data from v0 inputs and outputs."""
        if self.globals.version == 0:
            assert self.globals.unsigned_tx is not None
            tx = self.globals.unsigned_tx
            for input, tx_in in zip(self.inputs, tx.inputs):
                input.previous_txid = tx_in.prev_tx
                input.output_index = tx_in.index

            for output, tx_out in zip(self.outputs, tx.outputs):
                output.amount = tx_out.amount
                output.script = tx_out.script_pubkey

    def build(self) -> bytes:
        """Encode PSBT as bytes."""
        global_seq = self.globals.to_sequence()
        input_seq = [i.to_sequence() for i in self.inputs]
        output_seq = [o.to_sequence() for o in self.outputs]
        if self.globals.version == 0:
            global_seq = _filter_forbidden_fields(
                global_seq, defs.V0_FORBIDDEN_KEYS_GLOBAL
            )
            input_seq = [
                _filter_forbidden_fields(input, defs.V0_FORBIDDEN_KEYS_INPUT)
                for input in input_seq
            ]
            output_seq = [
                _filter_forbidden_fields(output, defs.V0_FORBIDDEN_KEYS_OUTPUT)
                for output in output_seq
            ]
        elif self.globals.version == 2:
            global_seq = _filter_forbidden_fields(
                global_seq, defs.V2_FORBIDDEN_KEYS_GLOBAL
            )

        sequences = [global_seq] + input_seq + output_seq
        return PsbtEnvelope.build(sequences)
