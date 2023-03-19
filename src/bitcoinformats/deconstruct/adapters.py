import io
import typing as t

from .fields import Field
from .structs import Struct
from .field_specifiers import _internal

_NO_ARGUMENT = object()

__all__ = ["Adapter"]

T = t.TypeVar("T")

if t.TYPE_CHECKING:
    from typing_extensions import Self


class Adapter(Struct, Field[T]):
    _is_descriptor_instance: bool = _internal(default=True)

    def __init__(self, **kwargs: t.Any) -> None:
        super().__init__(**kwargs)
        self._is_descriptor_instance = False

    def build_into(self, stream: io.BufferedIOBase, value: T) -> None:
        self.encode(value).stream_build(stream)

    def parse_from(self, stream: io.BufferedIOBase) -> T:
        return self.stream_parse(stream).decode()

    def sizeof(self, value: t.Union[T, object] = _NO_ARGUMENT) -> int:
        if value is not _NO_ARGUMENT:
            return self.encode(value).sizeof()
        elif self._is_descriptor_instance:
            raise TypeError("Called sizeof() without a valid self")
        else:
            return super().sizeof()

    def stream_build(self, stream: io.BufferedIOBase) -> None:
        if self._is_descriptor_instance:
            raise TypeError("Called stream_build() without a valid self")
        return super().stream_build(stream)

    @classmethod
    def encode(cls, value: T) -> "Self":
        raise NotImplementedError

    def decode(self) -> T:
        raise NotImplementedError
