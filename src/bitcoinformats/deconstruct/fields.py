import io
import struct
import typing as t

from . import exceptions
from .field_specifiers import _internal

if t.TYPE_CHECKING:
    from typing_extensions import Self

    from .structs import Struct


T = t.TypeVar("T")

__all__ = [
    "Field",
    "FormatField",
    "BytesField",
    "StrField",
]


class Field(t.Generic[T]):
    _internal_name: str = _internal()

    def __set_name__(self, _owner: t.Any, name: str) -> None:
        self._internal_name = name

    @t.overload
    def __get__(self, instance: None, _owner: t.Any = None) -> "Self":
        ...

    @t.overload
    def __get__(self, instance: "Struct", _owner: t.Any = None) -> T:
        ...

    def __get__(self, instance: t.Any, _owner: t.Any = None) -> t.Union[T, "Self"]:
        if instance is None:
            return self
        return self.get(instance)

    def get(self, instance: t.Any) -> T:
        return instance.__dict__[self._internal_name]

    def __set__(self, instance: t.Any, value: T) -> None:
        if instance is None:
            raise AttributeError("can't set attribute")
        return self.set(instance, value)

    def set(self, instance: t.Any, value: T) -> None:
        instance.__dict__[self._internal_name] = value

    def build_into(self, stream: io.BufferedIOBase, value: T) -> None:
        raise exceptions.UnsupportedError(
            f"Cannot build field of type {type(self).__name__}."
        )

    def parse_from(self, stream: io.BufferedIOBase) -> T:
        raise exceptions.UnsupportedError(
            f"Cannot parse field of type {type(self).__name__}."
        )

    def sizeof(self, value: T) -> int:
        raise NotImplementedError


class FormatField(Field[int]):
    struct: t.ClassVar[struct.Struct]

    @classmethod
    def make(cls: t.Type, format: str) -> t.Type["FormatField"]:
        class _FormatField(cls):
            struct = struct.Struct(format)

        return _FormatField

    def build_into(self, stream: io.BufferedIOBase, value: int) -> None:
        packed = self.struct.pack(value)
        stream.write(packed)

    def parse_from(self, stream: io.BufferedIOBase) -> int:
        data = stream.read(self.struct.size)
        return self.struct.unpack(data)[0]

    def sizeof(self, value: int) -> int:
        return self.struct.size


class LimitedField(Field[T]):
    def __init__(self, inner: Field[T], length: int) -> None:
        self.inner = inner
        self.length = length

    def build_into(self, stream: io.BufferedIOBase, value: T) -> None:
        buf = io.BytesIO()
        self.inner.build_into(buf, value)
        if buf.tell() != self.length:
            raise ValueError(
                f"Field length mismatch: expected {self.length}, got {buf.tell()}"
            )
        stream.write(buf.getvalue())

    def parse_from(self, stream: io.BufferedIOBase) -> T:
        data = stream.read(self.length)
        if len(data) != self.length:
            raise exceptions.EndOfStream
        buf = io.BytesIO(data)
        result = self.inner.parse_from(buf)
        if buf.tell() != self.length:
            raise exceptions.ParseError(
                f"Unparsed data at end of field: {self.length - buf.tell()} bytes"
            )
        return result

    def sizeof(self, value: T) -> int:
        return self.length


class BytesField(Field[bytes]):
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


class StrField(Field[str]):
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


class Referent(t.Generic[T]):
    def __init__(self, field: Field[T], instance: t.Any) -> None:
        self.field = field
        self.instance = instance

    def get(self) -> T:
        return self.field.get(self.instance)

    def set(self, value: T) -> None:
        self.field.set(self.instance, value)

    def sizeof(self, value: T) -> int:
        return self.field.sizeof(value)
