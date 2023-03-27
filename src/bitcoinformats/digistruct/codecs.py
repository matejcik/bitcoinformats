import io
import struct
import typing as t

from . import exceptions
from .base import Codec, Context

T = t.TypeVar("T")


class BasicCodec(Codec[int]):
    def __init__(self, format: str) -> None:
        self.struct = struct.Struct(format)

    def build_value(self, context: Context, value: int) -> None:
        packed = self.struct.pack(value)
        context.write(packed)

    def parse_value(self, context: Context) -> int:
        data = context.read(self.struct.size)
        return self.struct.unpack(data)[0]

    def size_of(self, context: Context, value: int) -> int:
        return self.struct.size


class StrCodec(Codec[str]):
    def __init__(self, length: t.Optional[int] = None, encoding: str = "utf-8") -> None:
        self.length = length
        self.encoding = encoding

    def build_value(self, context: Context, value: str) -> None:
        encoded = value.encode(self.encoding)
        if self.length is not None and len(encoded) != self.length:
            raise ValueError(
                f"String length mismatch: expected {self.length}, got {len(encoded)}"
            )
        context.write(encoded)

    def parse_value(self, context: Context) -> str:
        if self.length is None:
            result = context.read()
        else:
            result = context.read(self.length)
            if len(result) != self.length:
                raise exceptions.EndOfStream

        return result.decode(self.encoding)

    def size_of(self, context: Context, value: str) -> int:
        if self.length is None:
            return len(value.encode(self.encoding))
        else:
            return self.length
