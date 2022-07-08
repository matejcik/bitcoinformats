import typing as t
import warnings
from typing_extensions import dataclass_transform, Self

import construct as c

from .transaction import Transaction, TxOutput
from .utils import CompactUint
from .struct import Struct, subcon


PSBT_PROPRIETARY_BYTE = 0xFC


class PsbtError(Exception):
    pass


class PsbtKey(Struct):
    """Key for a PSBT entry."""

    type: int
    data: bytes

    SUBCON = c.Struct(
        "type" / CompactUint,
        "key" / c.GreedyBytes,
    )


class PsbtKeyValue(Struct):
    """Key-value pair in a PSBT entry."""

    value: bytes
    key: PsbtKey = subcon(PsbtKey)

    SUBCON = c.Struct(
        "key" / c.Prefixed(CompactUint, PsbtKey.SUBCON),
        "value" / c.Prefixed(CompactUint, c.GreedyBytes),
    )


class PsbtProprietaryKey(Struct):
    """Proprietary key in a PSBT entry."""

    prefix: str
    subtype: int
    data: bytes

    SUBCON = c.Struct(
        "prefix" / c.CString("utf-8"),
        "subtype" / CompactUint,
        "data" / c.Optional(c.GreedyBytes),
    )


# fmt: off
PsbtSequence = c.FocusedSeq("content",
    "content" / c.GreedyRange(PsbtKeyValue.SUBCON),
    c.Const(b"\0"),
)

PsbtEnvelope = c.FocusedSeq("sequences",
    "magic" / c.Const(b"psbt\xff"),
    "sequences" / c.GreedyRange(PsbtSequence),
    c.Terminated,
)
# fmt: on


class Bip32Field(Struct):
    """BIP32 field."""

    fingerprint: bytes
    address_n: list[int]

    SUBCON = c.Struct(
        "fingerprint" / c.Bytes(4),
        "address_n" / c.GreedyRange(c.Int32ul),
    )


class Field:
    def __init__(
        self,
        id: int,
        *,
        key: type[bytes] | type[Struct] | c.Construct | None = None,
        value: type[bytes] | type[Struct] | c.Construct = bytes,
    ) -> None:
        self.id = id
        self.key = key
        self.value = value


def field(
    id: int,
    *,
    key: type[bytes] | type[Struct] | c.Construct | None = None,
    value: type[bytes] | type[Struct] | c.Construct = bytes,
) -> t.Any:
    return Field(id, key=key, value=value)


@dataclass_transform(field_specifiers=(field,))
class PsbtMapType:
    _fields: dict[int, tuple[str, Field]] = {}

    def __init__(self, **kwargs: t.Any) -> None:
        self._proprietary: dict[str, dict[tuple[int, bytes], t.Any]] = {}
        self._unknown: list[PsbtKeyValue] = []
        self._collect_fields()
        names = {name: field for name, field in self._fields.values()}

        # process values specified in kwargs
        for arg, value in kwargs.items():
            if arg not in names:
                raise TypeError(f"Unknown field: {arg}")
            if names[arg].key is not None and not isinstance(value, dict):
                raise PsbtError("must supply dict for multi-key fields")
            setattr(self, arg, value)

        # process rest of fields
        for name, field in names.items():
            if name in kwargs:
                continue
            elif field.key is None:
                setattr(self, name, None)
            else:
                setattr(self, name, {})

    @classmethod
    def _collect_fields(cls) -> dict[int, tuple[str, Field]]:
        if not cls._fields:
            for key, value in cls.__dict__.items():
                if not isinstance(value, Field):
                    continue
                cls._fields[value.id] = (key, value)
        return cls._fields

    def __repr__(self) -> str:
        d = {}
        for key, value in self.__dict__.items():
            if value.startswith("_"):
                continue
            if value is None or value == {}:
                continue
            d[key] = value
        return "<%s: %s>" % (self.__class__.__name__, d)

    def __bool__(self) -> bool:
        """Return False if no fields are set, True otherwise"""
        return any(v is not None and v != {} for v in self.__dict__.values())

    @staticmethod
    def _decode_field(
        field_type: type[bytes] | type[Struct] | c.Construct | None, field_bytes: bytes
    ) -> t.Any:
        if field_type is None:
            return None
        if field_type is bytes:
            return field_bytes
        if isinstance(field_type, type) and issubclass(field_type, Struct):
            return field_type.parse(field_bytes)
        if isinstance(field_type, c.Construct):
            return field_type.parse(field_bytes)
        raise RuntimeError("Unknown field type")

    @staticmethod
    def _encode_field(
        field_type: type[bytes] | type[Struct] | c.Construct, field_value: t.Any
    ) -> bytes:
        if field_type is bytes:
            return field_value
        if (
            isinstance(field_type, type)
            and issubclass(field_type, Struct)
            and isinstance(field_value, field_type)
        ):
            return field_value.build()
        if isinstance(field_type, c.Construct):
            return field_type.build(field_value)
        raise RuntimeError("Unknown field type")

    @classmethod
    def from_sequence(cls, sequence: list[PsbtKeyValue]) -> Self:
        cls._collect_fields()
        psbt = cls()
        seen_keys = set()
        for v in sequence:
            key = v.key.type
            if (key, v.key.data) in seen_keys:
                raise PsbtError(f"Duplicate key type 0x{key:02x}")
            seen_keys.add((key, v.key.data))

            if key == PSBT_PROPRIETARY_BYTE:
                prop_key = PsbtProprietaryKey.parse(v.key.data)
                prop_dict = psbt._proprietary.setdefault(prop_key.prefix, {})
                prop_dict[prop_key.subtype, prop_key.data] = v.value
                continue

            if key not in cls._fields:
                warnings.warn(f"Unknown field type 0x{key:02x}")
                psbt._unknown.append(v)
                continue

            name, field = cls._fields[key]
            if field.key is None and v.key.data:
                raise PsbtError(f"Key data not allowed on '{name}'")
            if field.key is not None and not v.key.data:
                raise PsbtError(f"Key data missing on '{name}'")

            parsed_key = cls._decode_field(field.key, v.key.data)
            parsed_value = cls._decode_field(field.value, v.value)
            if field.key:
                getattr(psbt, name)[parsed_key] = parsed_value
            else:
                setattr(psbt, name, parsed_value)
        return psbt

    def to_sequence(self):
        sequence: list[PsbtKeyValue] = []
        for key, (name, field) in self._fields.items():
            if field.key is None:
                value = getattr(self, name)
                if value is None:
                    continue
                value_bytes = self._encode_field(field.value, value)
                sequence.append(
                    PsbtKeyValue(key=PsbtKey(type=key, data=b""), value=value_bytes)
                )
            else:
                values = getattr(self, name)
                if values == {}:
                    continue
                for keydata, value in values.items():
                    keydata_bytes = self._encode_field(field.key, keydata)
                    value_bytes = self._encode_field(field.value, value)
                    sequence.append(
                        PsbtKeyValue(
                            key=PsbtKey(type=key, data=keydata_bytes), value=value_bytes
                        )
                    )

        for prefix, proprietary in self._proprietary.items():
            for (subtype, data), value in proprietary.items():
                data = PsbtProprietaryKey(prefix=prefix, subtype=subtype, data=data)
                key = PsbtKey(type=PSBT_PROPRIETARY_BYTE, data=data.build())
                sequence.append(PsbtKeyValue(key=key, value=value))

        sequence.extend(self._unknown)
        return sequence


class PsbtGlobalType(PsbtMapType):
    transaction: Transaction = field(0x00, value=Transaction)
    global_xpub: bytes = field(0x01, value=bytes)
    version: int = field(0x02, value=c.Int32ul)


class PsbtInputType(PsbtMapType):
    non_witnes_utxo: Transaction = field(0x00, value=Transaction)
    witness_utxo: TxOutput = field(0x01, value=TxOutput)
    signature: bytes = field(0x02, key=bytes, value=bytes)
    sighash_type: int = field(0x03, value=c.Int32ul)
    redeem_script: bytes = field(0x04, value=bytes)
    witness_script: bytes = field(0x05, value=bytes)
    bip32_path: Bip32Field = field(0x06, key=bytes, value=Bip32Field)
    script_sig: bytes = field(0x07, value=bytes)
    witness: bytes = field(0x08, value=bytes)
    por_commitment: str = field(0x09, value=c.GreedyString("utf8"))


class PsbtOutputType(PsbtMapType):
    redeem_script: bytes = field(0x00, value=bytes)
    witness: bytes = field(0x01, value=bytes)
    bip32_path: Bip32Field = field(0x02, key=bytes, value=Bip32Field)


def read_psbt(
    psbt_bytes: bytes,
) -> tuple[PsbtGlobalType, list[PsbtInputType], list[PsbtOutputType]]:
    try:
        psbt = PsbtEnvelope.parse(psbt_bytes)
        if not psbt:
            raise PsbtError("Empty PSBT envelope")
        main = PsbtGlobalType.from_sequence(psbt[0])
        tx = main.transaction
        if len(psbt) != 1 + len(tx.inputs) + len(tx.outputs):
            raise PsbtError("PSBT length does not match embedded transaction")

        input_seqs = psbt[1 : 1 + len(tx.inputs)]
        output_seqs = psbt[1 + len(tx.inputs) :]
        inputs = [PsbtInputType.from_sequence(s) for s in input_seqs]
        outputs = [PsbtOutputType.from_sequence(s) for s in output_seqs]
        return main, inputs, outputs

    except c.ConstructError as e:
        raise PsbtError("Could not parse PBST") from e


def write_psbt(
    main: PsbtGlobalType,
    inputs: t.Sequence[PsbtInputType],
    outputs: t.Sequence[PsbtOutputType],
) -> bytes:
    sequences = (
        [main.to_sequence()]
        + [inp.to_sequence() for inp in inputs]
        + [out.to_sequence() for out in outputs]
    )
    return PsbtEnvelope.build(sequences)
