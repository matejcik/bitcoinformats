import io
import typing as t

from .base import Codec, Field, extract_codec_type, DependentRelation
from . import exceptions

if t.TYPE_CHECKING:
    from typing_extensions import Self

T = t.TypeVar("T")


__all__ = ["array"]


@t.overload
def array(length: t.Union[int, Field[int], None] = None) -> t.List:
    ...


@t.overload
def array(*, prefix: t.Type[int]) -> t.List:
    ...


@t.overload
def array(*, byte_size: int) -> t.List:
    ...


def array(
    length: t.Union[int, Field[int], None] = None,
    *,
    prefix: t.Optional[t.Type[int]] = None,
    byte_size: t.Optional[int] = None,
) -> t.Any:
    n_args = sum(arg is not None for arg in (length, prefix, byte_size))
    if n_args == 0:
        return GreedyArray()

    if n_args > 1:
        raise ValueError("Only one of length, prefix, or byte_size may be specified")

    if isinstance(length, int):
        return FixedSizeArray(length)

    if isinstance(length, Field):
        return ReferentArray(length)

    if prefix is not None:
        codec = extract_codec_type(prefix)
        if codec is None:
            raise TypeError("prefix must be a codec")
        return PrefixedArray(codec)

    raise NotImplementedError


class Array(Field[T]):
    _default: t.Iterable[T] = ()

    @property
    def default(self) -> t.List[T]:
        return list(self._default)

    @default.setter
    def default(self, value: t.Any) -> None:
        if value is None:
            self._default = ()
        elif isinstance(value, t.Iterable):
            # TODO does this actually work?
            self._default = value
        else:
            raise TypeError("array default must be an iterable")

    def get_length(self, instance: t.Any) -> int:
        raise NotImplementedError

    def setvalue(self, instance: t.Any, value: t.Iterable[T]) -> None:
        super().setvalue(instance, list(value))  # type: ignore

    if t.TYPE_CHECKING:

        def getvalue(self, instance: t.Any) -> t.List[T]:
            ...

        def __get__(
            self, instance: t.Any, owner: t.Type[t.Any]
        ) -> t.Union["Self", t.List[T]]:
            ...

        def __set__(self, instance: t.Any, value: t.Iterable[T]) -> None:
            ...

    def _check_length(self, instance: t.Any) -> None:
        length = self.get_length(instance)
        value = self.getvalue(instance)
        if len(value) != length:
            raise exceptions.BuildError(
                f"Array length mismatch: expected a length of {length}, "
                f"but got a length of {len(value)}"
            )

    def build_into(self, instance: t.Any, stream: io.BufferedIOBase) -> None:
        assert self.codec is not None
        self._check_length(instance)
        for item in self.getvalue(instance):
            # TODO support nested arrays?
            self.codec.build_into(stream, item)

    def parse_from(self, instance: t.Any, stream: io.BufferedIOBase) -> None:
        assert self.codec is not None
        length = self.get_length(instance)
        value = []
        for _ in range(length):
            value.append(self.codec.parse_from(stream))
        self.setvalue(instance, value)

    def sizeof(self, instance: t.Any) -> int:
        assert self.codec is not None
        self._check_length(instance)
        return sum(self.codec.sizeof(item) for item in self.getvalue(instance))


class GreedyArray(Array[T]):
    def get_length(self, instance: t.Any) -> int:
        return len(self.getvalue(instance))

    def parse_from(self, instance: t.Any, stream: io.BufferedIOBase) -> None:
        assert self.codec is not None
        value = []
        while True:
            start_pos = stream.tell()
            try:
                value.append(self.codec.parse_from(stream))
            except exceptions.EndOfStream:
                end_pos = stream.tell()
                if end_pos != start_pos:
                    # partially parsed array element
                    raise
                # eof after fully parsing the previous element
                self.setvalue(instance, value)


class FixedSizeArray(Array[T]):
    def __init__(self, length: int) -> None:
        super().__init__()
        self.length = length

    def get_length(self, instance: t.Any) -> int:
        return self.length


class ReferentArray(Array[T], DependentRelation[int]):
    def __init__(self, length_field: Field[int]) -> None:
        super().__init__()
        self.length_field = length_field
        self.length_field.depend_on(self)

    def get_length(self, instance: t.Any) -> int:
        return self.length_field.getvalue(instance)

    def update(self, instance: t.Any, referent: "Field[int]") -> int:
        return len(self.getvalue(instance))


class PrefixedArray(Array[T]):
    def __init__(self, prefix: Codec[int]) -> None:
        super().__init__()
        self.prefix = prefix

    def get_length(self, instance: t.Any) -> int:
        return len(self.getvalue(instance))

    def build_into(self, instance: t.Any, stream: io.BufferedIOBase) -> None:
        assert self.codec is not None
        length = self.get_length(instance)
        self.prefix.build_into(stream, length)
        super().build_into(instance, stream)

    def parse_from(self, instance: t.Any, stream: io.BufferedIOBase) -> None:
        assert self.codec is not None
        length = self.prefix.parse_from(stream)
        value = []
        for _ in range(length):
            value.append(self.codec.parse_from(stream))
        self.setvalue(instance, value)

    def sizeof(self, instance: t.Any) -> int:
        assert self.codec is not None
        return self.prefix.sizeof(self.get_length(instance)) + sum(
            self.codec.sizeof(item) for item in self.getvalue(instance)
        )
