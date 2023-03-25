import io
import typing as t

from . import codecs, exceptions, structs

if t.TYPE_CHECKING:
    from typing_extensions import Self

T = t.TypeVar("T")


__all__ = [
    "Array",
    "array",
]


def array(
    length: t.Union[int, codecs.Codec[int], None] = None,
    *,
    prefix: t.Optional[t.Type[int]] = None,
    byte_size: t.Optional[int] = None,
) -> t.Any:
    if length is None and prefix is None and byte_size is None:
        return GreedyArray()
    elif isinstance(length, int):
        return FixedSizeArray(length)
    elif isinstance(length, structs.Field):
        return ReferentArray(length)
    else:
        raise NotImplementedError


class Array(structs.Field[T]):
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

    def get_length(self) -> int:
        return self.length


class ReferentArray(Array[T]):
    def __init__(self, length_field: structs.Field[int]) -> None:
        super().__init__()
        self.length_field = length_field

    def get_length(self, instance: t.Any) -> int:
        return self.length_field.getvalue(instance)

    def setvalue(self, instance: t.Any, value: t.Iterable[T]) -> None:
        value = list(value)
        self.length_field.setvalue(instance, len(value))
        super().setvalue(instance, value)
