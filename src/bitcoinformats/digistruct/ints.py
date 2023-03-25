from typing_extensions import Annotated

from .codecs import BasicCodec

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


int8 = Annotated[int, BasicCodec("=b")]
int16 = Annotated[int, BasicCodec("=h")]
int32 = Annotated[int, BasicCodec("=i")]
int64 = Annotated[int, BasicCodec("=q")]

uint8 = Annotated[int, BasicCodec("=B")]
uint16 = Annotated[int, BasicCodec("=H")]
uint32 = Annotated[int, BasicCodec("=I")]
uint64 = Annotated[int, BasicCodec("=Q")]


class _BigEndian:
    int8 = Annotated[int, BasicCodec(">b")]
    int16 = Annotated[int, BasicCodec(">h")]
    int32 = Annotated[int, BasicCodec(">i")]
    int64 = Annotated[int, BasicCodec(">q")]

    uint8 = Annotated[int, BasicCodec(">B")]
    uint16 = Annotated[int, BasicCodec(">H")]
    uint32 = Annotated[int, BasicCodec(">I")]
    uint64 = Annotated[int, BasicCodec(">Q")]


class _LittleEndian:
    int8 = Annotated[int, BasicCodec("<b")]
    int16 = Annotated[int, BasicCodec("<h")]
    int32 = Annotated[int, BasicCodec("<i")]
    int64 = Annotated[int, BasicCodec("<q")]

    uint8 = Annotated[int, BasicCodec("<B")]
    uint16 = Annotated[int, BasicCodec("<H")]
    uint32 = Annotated[int, BasicCodec("<I")]
    uint64 = Annotated[int, BasicCodec("<Q")]


be = big = _BigEndian
le = little = _LittleEndian
