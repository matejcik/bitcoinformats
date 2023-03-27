import io
import typing as t

import typing_extensions as tx

from . import exceptions
from .base import Codec, Context, Field, RecalcCodec, extract_codec_type

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
    return ArrayField(length=length, prefix=prefix, byte_size=byte_size)


class ArrayField(Field[t.List[T]]):
    _default: t.Iterable[T] = ()

    def __init__(
        self,
        length: t.Union[int, Field[int], None] = None,
        prefix: t.Optional[t.Type[int]] = None,
        byte_size: t.Optional[int] = None,
    ) -> None:
        super().__init__()
        self.length = length
        self.prefix = prefix
        self.byte_size = byte_size

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

    def __set__(self, instance: t.Any, value: t.Iterable[T]) -> None:
        super().__set__(instance, list(value))

    def make_codec(self, field_type: t.Any) -> Codec[t.List[T]]:
        assert tx.get_origin(field_type) in (list, t.List)
        inner_codec = extract_codec_type(tx.get_args(field_type)[0])

        n_args = sum(
            arg is not None for arg in (self.length, self.prefix, self.byte_size)
        )
        if n_args == 0:
            return GreedyArray(inner_codec)

        if n_args > 1:
            raise ValueError(
                "Only one of length, prefix, or byte_size may be specified"
            )

        if isinstance(self.length, int):
            return FixedSizeArray(inner_codec, self.length)

        if isinstance(self.length, Field):
            return ReferentArray(inner_codec, self.length)

        if self.prefix is not None:
            prefix_codec = extract_codec_type(self.prefix)
            if prefix_codec is None:
                raise TypeError("prefix must be a codec")
            return PrefixedArray(inner_codec, prefix_codec)

        raise NotImplementedError


class Array(Codec[t.List[T]]):
    def __init__(self, inner_codec: Codec[T]) -> None:
        self.inner_codec = inner_codec

    def get_length(self, ctx: Context) -> int:
        raise NotImplementedError

    def _check_length(self, ctx: Context, value: t.Collection[T]) -> None:
        length = self.get_length(ctx)
        if len(value) != length:
            raise exceptions.BuildError(
                f"Array length mismatch: expected a length of {length}, "
                f"but got a length of {len(value)}"
            )

    def build_value(self, ctx: Context, value: t.Collection[T]) -> None:
        self._check_length(ctx, value)
        for item in value:
            self.inner_codec.build_value(ctx, item)

    def parse_value(self, ctx: Context) -> t.List[T]:
        return self.parse_with_length(ctx, self.get_length(ctx))

    def parse_with_length(self, ctx: Context, length: int) -> t.List[T]:
        value = []
        for _ in range(length):
            value.append(self.inner_codec.parse_value(ctx))
        return value

    def size_of(self, ctx: Context, value: t.Collection[T]) -> int:
        self._check_length(ctx, value)
        return sum(self.inner_codec.size_of(ctx, item) for item in value)

    def recalculate(self, ctx: Context, value: t.Collection[T]) -> None:
        self._check_length(ctx, value)
        if isinstance(self.inner_codec, RecalcCodec):
            for item in value:
                self.inner_codec.recalculate(ctx, item)


class GreedyArray(Array[T]):
    def _check_length(self, ctx: Context, value: t.Collection[T]) -> None:
        pass

    def parse_value(self, ctx: Context) -> t.List[T]:
        value = []
        while True:
            start_pos = ctx.tell()
            try:
                value.append(self.inner_codec.parse_value(ctx))
            except exceptions.EndOfStream:
                end_pos = ctx.tell()
                if end_pos != start_pos:
                    # partially parsed array element
                    ctx.seek(start_pos)

                # end of (parseable part of) stream
                return value


class FixedSizeArray(Array[T]):
    def __init__(self, inner_codec: Codec[T], length: int) -> None:
        super().__init__(inner_codec)
        self.length = length

    def get_length(self, ctx: Context) -> int:
        return self.length


class ReferentArray(Array[T]):
    def __init__(self, inner_codec: Codec[T], length_field: Field[int]) -> None:
        super().__init__(inner_codec)
        self.length_field = length_field

    def get_length(self, ctx: Context) -> int:
        return ctx.getvalue(self.length_field)

    def recalculate(self, ctx: Context, value: t.Collection[T]) -> None:
        ctx.setvalue(self.length_field, len(value))
        super().recalculate(ctx, value)


class PrefixedArray(Array[T]):
    def __init__(self, inner_codec: Codec[T], prefix_codec: Codec[int]) -> None:
        super().__init__(inner_codec)
        self.prefix_codec = prefix_codec

    def _check_length(self, ctx: Context, value: t.Collection[T]) -> None:
        pass

    def build_value(self, ctx: Context, value: t.Collection[T]) -> None:
        self.prefix_codec.build_value(ctx, len(value))
        return super().build_value(ctx, value)

    def parse_value(self, ctx: Context) -> t.List[T]:
        length = self.prefix_codec.parse_value(ctx)
        return self.parse_with_length(ctx, length)

    def size_of(self, ctx: Context, value: t.Collection[T]) -> int:
        return self.prefix_codec.size_of(ctx, len(value)) + sum(
            self.inner_codec.size_of(ctx, item) for item in value
        )
