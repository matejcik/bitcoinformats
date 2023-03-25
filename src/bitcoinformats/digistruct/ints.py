from typing_extensions import Annotated

from .fields import FormatField

__all__ = [
    "int8",
    "int16",
    "int32",
    "int64",
    "uint8",
    "uint16",
    "uint32",
    "uint64",
    "be",
    "big",
    "le",
    "little",
]


int8 = Annotated[int, FormatField("=b")]
int16 = Annotated[int, FormatField("=h")]
int32 = Annotated[int, FormatField("=i")]
int64 = Annotated[int, FormatField("=q")]

uint8 = Annotated[int, FormatField("=B")]
uint16 = Annotated[int, FormatField("=H")]
uint32 = Annotated[int, FormatField("=I")]
uint64 = Annotated[int, FormatField("=Q")]


class _BigEndian:
    int8 = Annotated[int, FormatField(">b")]
    int16 = Annotated[int, FormatField(">h")]
    int32 = Annotated[int, FormatField(">i")]
    int64 = Annotated[int, FormatField(">q")]

    uint8 = Annotated[int, FormatField(">B")]
    uint16 = Annotated[int, FormatField(">H")]
    uint32 = Annotated[int, FormatField(">I")]
    uint64 = Annotated[int, FormatField(">Q")]


class _LittleEndian:
    int8 = Annotated[int, FormatField("<b")]
    int16 = Annotated[int, FormatField("<h")]
    int32 = Annotated[int, FormatField("<i")]
    int64 = Annotated[int, FormatField("<q")]

    uint8 = Annotated[int, FormatField("<B")]
    uint16 = Annotated[int, FormatField("<H")]
    uint32 = Annotated[int, FormatField("<I")]
    uint64 = Annotated[int, FormatField("<Q")]


be = big = _BigEndian
le = little = _LittleEndian
