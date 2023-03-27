import io
import typing as t

import typing_extensions as tx

from .base import Field, get_type_hints, MISSING, Context
from . import arrays
from .field_specifiers import field
from .exceptions import DeconstructError, BuildError, ParseError


T = t.TypeVar("T")

__all__ = ["Spec", "StructInfo", "Struct", "Adapter"]


def safe_issubclass(
    cls: type, class_or_tuple: t.Union[type, t.Tuple[type, ...]]
) -> bool:
    return isinstance(cls, type) and issubclass(cls, class_or_tuple)


class Spec:
    def __init__(self, owner: t.Type["Struct"]) -> None:
        self.owner = owner
        self.fields = self._extract_fields(owner)
        self.decorate_owner()

    @staticmethod
    def _make_field(field_type: t.Any, value: t.Any) -> Field:
        if isinstance(value, Field):
            return value

        origin = tx.get_origin(field_type)
        if origin in (list, t.List):
            return arrays.ArrayField()
        else:
            return Field()

    @staticmethod
    def _should_skip(field_type: t.Any) -> bool:
        origin = tx.get_origin(field_type)
        return origin is t.ClassVar

    @classmethod
    def _extract_fields(cls, owner: t.Type["Struct"]) -> t.Dict[str, Field]:
        parents = [
            p for p in owner.__bases__ if issubclass(p, Struct) and p is not Struct
        ]
        fields = {}

        for parent in parents:
            common_keys = fields.keys() & parent._spec.fields.keys()
            if common_keys:
                raise DeconstructError(
                    f"Duplicate field(s) ({', '.join(common_keys)}) found in {parent.__name__}"
                )
            # TODO: is it ok that we use the preexisting instances?
            fields.update(parent._spec.fields)

        annotations = get_type_hints(owner)
        for name, field_type in annotations.items():
            if cls._should_skip(field_type):
                continue
            value = getattr(owner, name, MISSING)
            field = cls._make_field(field_type, value)
            field.fill(name, field_type, value)
            fields[name] = field

        return fields

    def decorate_owner(self) -> None:
        for name, field in self.fields.items():
            setattr(self.owner, name, field)
        setattr(self.owner, "_spec", self)

    def populate(self, instance: "Struct", kwargs: t.Dict[str, t.Any]) -> None:
        # provided arguments
        for name, value in kwargs.items():
            if name not in self.fields or self.fields[name].is_dependent():
                raise TypeError(f"Unexpected keyword argument {name!r}")
            setattr(instance, name, value)

        # remaining fields
        for name, field in self.fields.items():
            if name in kwargs:
                continue
            if field.is_dependent():
                continue
            if field.default is MISSING:
                raise TypeError(f"Missing required argument {name!r}")
            setattr(instance, name, field.default)

    def as_dict(self, instance: "Struct") -> t.Dict[str, t.Any]:
        return {name: getattr(instance, name) for name in self.fields}


class StructInfo:
    pass


@tx.dataclass_transform(kw_only_default=True, field_specifiers=(field,))
class Struct:
    _spec: t.ClassVar[Spec]
    _struct: StructInfo

    def __init_subclass__(cls, **kwargs: t.Any) -> None:
        super().__init_subclass__(**kwargs)
        cls._spec = Spec(cls)

    def __init__(self, **kwargs: t.Any) -> None:
        self._spec.populate(self, kwargs)

    def __eq__(self, other: t.Any) -> bool:
        if not isinstance(other, type(self)):
            return NotImplemented
        return self._spec.as_dict(self) == other._spec.as_dict(other)

    @classmethod
    def stream_parse(cls, stream: io.BufferedIOBase) -> tx.Self:
        ctx = Context(stream)
        result = cls.parse_value(ctx)
        if stream.read(1):
            raise ParseError("Unparsed data at end of stream")
        return result

    @classmethod
    def parse(cls, data: bytes) -> tx.Self:
        inbuf = io.BytesIO(data)
        return cls.stream_parse(inbuf)

    def stream_build(self, stream: io.BufferedIOBase) -> None:
        ctx = Context(stream)
        self.build_value(ctx, self)

    def build(self) -> bytes:
        outbuf = io.BytesIO()
        self.stream_build(outbuf)
        return outbuf.getvalue()

    # codec protocol methods
    @classmethod
    def build_value(cls, ctx: Context, self: tx.Self) -> None:
        with ctx.push(self, f"struct {cls.__name__!r}"):
            for field in cls._spec.fields.values():
                try:
                    field.recalculate(ctx)
                    value = getattr(self, field.name)
                    field.codec.build_value(ctx, value)
                except Exception as e:
                    raise BuildError(f"Failed to build field {field.name!r}", e) from e

    @classmethod
    def parse_value(cls, ctx: Context) -> tx.Self:
        instance = cls.__new__(cls)
        with ctx.push(instance, f"struct {cls.__name__!r}"):
            for field in cls._spec.fields.values():
                value = field.codec.parse_value(ctx)
                setattr(instance, field.name, value)

        return instance

    @classmethod
    def size_of(cls, ctx: Context, value: tx.Self) -> int:
        return sum(
            field.codec.size_of(ctx, getattr(value, field.name))
            for field in cls._spec.fields.values()
        )

    def size(self) -> int:
        # TODO: is it OK to use an empty context like this?
        return self.size_of(Context(io.BytesIO()), self)


S = t.TypeVar("S", bound=Struct)


class Adapter(Struct, t.Generic[T]):
    if t.TYPE_CHECKING:

        def __get__(self, instance: t.Any, owner: t.Any) -> t.Union[tx.Self, T]:
            ...

        def __set__(self, instance: t.Any, value: T) -> None:
            ...

    @classmethod
    def encode(cls, value: T) -> tx.Self:
        raise NotImplementedError

    def decode(self) -> T:
        raise NotImplementedError

    @classmethod
    def build_value(cls, ctx: Context, value: T) -> None:
        actual = cls.encode(value)
        super().build_value(ctx, actual)

    @classmethod
    def parse_value(cls, ctx: Context) -> T:
        actual = super().parse_value(ctx)
        return actual.decode()

    @classmethod
    def size_of(cls, ctx: Context, value: T) -> int:
        return super().size_of(ctx, cls.encode(value))

    def stream_build(self, stream: io.BufferedIOBase) -> None:
        # skip our override of build_value
        super().build_value(Context(stream), self)

    @classmethod
    def stream_parse(cls, stream: io.BufferedIOBase) -> tx.Self:
        # skip our override of parse_value
        return super().parse_value(Context(stream))
