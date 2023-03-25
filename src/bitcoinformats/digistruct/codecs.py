import io
import struct
import typing as t

from . import exceptions

T = t.TypeVar("T")

__all__ = [
    "Codec",
    "BasicCodec",
    "BytesCodec",
    "StrCodec",
]


@t.runtime_checkable
class Codec(t.Protocol[T]):
    def build_into(self, stream: io.BufferedIOBase, value: T) -> None:
        ...

    def parse_from(self, stream: io.BufferedIOBase) -> T:
        ...

    def sizeof(self, value: T) -> int:
        ...


class BasicCodec(Codec[int]):
    def __init__(self, format: str) -> None:
        self.struct = struct.Struct(format)

    def build_into(self, stream: io.BufferedIOBase, value: int) -> None:
        packed = self.struct.pack(value)
        stream.write(packed)

    def parse_from(self, stream: io.BufferedIOBase) -> int:
        data = stream.read(self.struct.size)
        return self.struct.unpack(data)[0]

    def sizeof(self, value: int) -> int:
        return self.struct.size


class BytesCodec(Codec[bytes]):
    def __init__(self, length: t.Optional[int] = None) -> None:
        self.length = length

    def build_into(self, stream: io.BufferedIOBase, value: bytes) -> None:
        stream.write(value)

    def parse_from(self, stream: io.BufferedIOBase) -> bytes:
        if self.length is None:
            return stream.read()

        result = stream.read(self.length)
        if len(result) != self.length:
            raise exceptions.EndOfStream
        return result

    def sizeof(self, value: bytes) -> int:
        return len(value)


class StrCodec(Codec[str]):
    def __init__(self, length: t.Optional[int] = None, encoding: str = "utf-8") -> None:
        self.length = length
        self.encoding = encoding

    def build_into(self, stream: io.BufferedIOBase, value: str) -> None:
        encoded = value.encode(self.encoding)
        if self.length is not None and len(encoded) != self.length:
            raise ValueError(
                f"String length mismatch: expected {self.length}, got {len(encoded)}"
            )
        stream.write(encoded)

    def parse_from(self, stream: io.BufferedIOBase) -> str:
        if self.length is None:
            result = stream.read()
        else:
            result = stream.read(self.length)
            if len(result) != self.length:
                raise exceptions.EndOfStream

        return result.decode(self.encoding)

    def sizeof(self, value: str) -> int:
        if self.length is None:
            return len(value.encode(self.encoding))
        else:
            return self.length
