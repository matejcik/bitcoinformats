import io
import typing as t

from . import exceptions
from .fields import Field
from .field_specifiers import FieldPlaceholder

if t.TYPE_CHECKING:
    from .structs import Struct

T = t.TypeVar("T")


__all__ = [
    "Array",
    "array",
]


class ArraySpec:
    def __init__(
        self,
        array_type: t.Type["Array"],
        *,
        referent_placeholder: t.Optional[FieldPlaceholder] = None,
        fixed_length: t.Optional[int] = None,
        is_byte_size: bool = False,
    ) -> None:
        self.array_type = array_type
        self.referent_placeholder = referent_placeholder
        self.fixed_length = fixed_length
        self.is_byte_size = is_byte_size


def array(
    length: t.Union[int, Field[int], None] = None,
    *,
    prefix: t.Optional[t.Type[int]] = None,
    byte_size: t.Optional[int] = None,
) -> t.Any:
    if length is None and prefix is None and byte_size is None:
        return ArraySpec(GreedyArray)
    elif isinstance(length, int):
        return ArraySpec(FixedSizeArray, fixed_length=length)
    elif isinstance(length, FieldPlaceholder):
        return ArraySpec(ReferentArray, referent_placeholder=length)
    else:
        raise NotImplementedError


class Array(Field[t.List[T]]):
    def __init__(self, inner_type: Field[T]) -> None:
        self.inner_type = inner_type

    def get_length(self) -> int:
        raise NotImplementedError

    def build_into(self, stream: io.BufferedIOBase, value: t.Sequence[T]) -> None:
        for item in value:
            self.inner_type.build_into(stream, item)

    def parse_from(self, stream: io.BufferedIOBase) -> t.List[T]:
        length = self.get_length()
        value = []
        for _ in range(length):
            value.append(self.inner_type.parse_from(stream))
        return value

    def sizeof(self, value: t.Sequence[T]) -> int:
        return sum(self.inner_type.sizeof(item) for item in value)


class GreedyArray(Array[T]):
    def parse_from(self, stream: io.BufferedIOBase) -> t.List[T]:
        value = []
        while True:
            start_pos = stream.tell()
            try:
                value.append(self.inner_type.parse_from(stream))
            except exceptions.EndOfStream:
                end_pos = stream.tell()
                if end_pos != start_pos:
                    # partially parsed array element
                    raise
                # eof after fully parsing the previous element
                return value


class SizedArray(Array[T]):
    def build_into(self, stream: io.BufferedIOBase, value: t.Sequence[T]) -> None:
        length = self.get_length()
        if len(value) != length:
            raise ValueError(
                f"Array length mismatch: expected {length}, got {len(value)}"
            )
        return super().build_into(stream, value)

    def sizeof(self, value: t.Sequence[T]) -> int:
        length = self.get_length()
        if len(value) != length:
            raise ValueError(
                f"Array length mismatch: expected {length}, got {len(value)}"
            )
        return super().sizeof(value)


class FixedSizeArray(SizedArray[T]):
    def __init__(self, inner_type: Field[T], length: int) -> None:
        super().__init__(inner_type)
        self.length = length

    def get_length(self) -> int:
        return self.length


class ReferentArray(SizedArray[T]):
    def __init__(self, inner_type: Field[T], length_field: Referent[int]) -> None:
        super(SizedArray).__init__(inner_type)
        self.length_field = length_field

    def get_length(self) -> int:
        return self.length_field.get()
