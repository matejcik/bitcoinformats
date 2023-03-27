import io
import typing as t

from . import exceptions
from .base import Codec, RecalcCodec, Field, Context, extract_codec_type

__all__ = ["size"]

T = t.TypeVar("T")


class ByteSize(Codec[T]):
    def __init__(self, codec: Codec[T]) -> None:
        self.codec = codec

    def get_length(self, ctx: Context) -> int:
        raise NotImplementedError

    def build_value(self, ctx: Context, value: T) -> None:
        start = ctx.tell()
        self.codec.build_value(ctx, value)
        end = ctx.tell()
        length = self.get_length(ctx)
        if end - start != length:
            raise exceptions.BuildError(
                f"Content length is {end - start}, expected {length}"
            )

    def parse_value(self, ctx: Context) -> T:
        length = self.get_length(ctx)
        data = ctx.read(length)
        if len(data) < length:
            raise exceptions.EndOfStream
        with ctx.push(f"subsequence of {len(data)} bytes", stream=io.BytesIO(data)):
            return self.codec.parse_value(ctx)

    def size_of(self, ctx: Context, value: T) -> int:
        return self.get_length(ctx)


class FixedByteSize(ByteSize[T]):
    def __init__(self, codec: Codec[T], length: int) -> None:
        super().__init__(codec)
        self.length = length

    def get_length(self, ctx: Context) -> int:
        return self.length


class ReferentByteSize(ByteSize[T]):
    def __init__(self, codec: Codec[T], length: Field[int]) -> None:
        super().__init__(codec)
        self.length_field = length

    def get_length(self, ctx: Context) -> int:
        return ctx.getvalue(self.length_field)

    def recalculate(self, ctx: Context, value: T) -> None:
        if isinstance(self.codec, RecalcCodec):
            self.codec.recalculate(ctx, value)
        ctx.setvalue(self.length_field, self.codec.size_of(ctx, value))


class PrefixedByteSize(ByteSize[T]):
    def __init__(self, codec: Codec[T], prefix: Codec[int]) -> None:
        super().__init__(codec)
        self.prefix = prefix

    def build_value(self, ctx: Context, value: T) -> None:
        length = self.codec.size_of(ctx, value)
        self.prefix.build_value(ctx, length)
        self.codec.build_value(ctx, value)

    def parse_value(self, ctx: Context) -> T:
        length = self.prefix.parse_value(ctx)
        data = ctx.read(length)
        if len(data) < length:
            raise exceptions.EndOfStream
        with ctx.push(f"subsequence of {len(data)} bytes", stream=io.BytesIO(data)):
            return self.codec.parse_value(ctx)


class BytesCodec(Codec[bytes]):
    def build_value(self, ctx: Context, value: bytes) -> None:
        ctx.write(value)

    def parse_value(self, ctx: Context) -> bytes:
        return ctx.read()

    def size_of(self, ctx: Context, value: bytes) -> int:
        return len(value)


class SizedField(Field[T]):
    def __init__(self, size: t.Union[int, Field[int], None], prefix: t.Any) -> None:
        self.size = size
        self.prefix = prefix

    def make_codec(self, field_type: t.Any) -> Codec[T]:
        inner_codec = super().make_codec(field_type)
        n_args = sum(arg is not None for arg in (self.size, self.prefix))
        if n_args == 0:
            return inner_codec
        if n_args > 1:
            raise ValueError("Cannot specify both size and prefix")

        if self.prefix is not None:
            prefix_codec = extract_codec_type(self.prefix)
            if prefix_codec is None:
                raise ValueError("Prefix must be a codec")
            return PrefixedByteSize(inner_codec, prefix_codec)
        if isinstance(self.size, int):
            return FixedByteSize(inner_codec, self.size)
        if isinstance(self.size, Field):
            return ReferentByteSize(inner_codec, self.size)

        raise NotImplementedError


def size(
    length: t.Union[int, Field[int], None] = None, *, prefix: t.Any = None
) -> t.Any:
    return SizedField(length, prefix)
