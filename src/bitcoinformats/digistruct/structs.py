import io
import typing as t
import dataclasses

from . import arrays, codecs
from .field_specifiers import _internal, field, INTERNAL_VALUE
from .exceptions import DeconstructError

from typing_extensions import (
    Self,
    dataclass_transform,
    get_origin,
    get_args,
    get_type_hints,
)


T = t.TypeVar("T")

__all__ = ["Spec", "StructInfo", "Struct", "Adapter"]


@dataclasses.dataclass(init=False)
class Field(t.Generic[T]):
    name: t.Optional[str]
    codec: t.Optional[codecs.Codec[T]]
    default: t.Optional[T]

    def getvalue(self, instance: t.Any) -> T:
        assert self.name is not None
        return instance.__dict__[self.name]

    def setvalue(self, instance: t.Any, value: T) -> None:
        assert self.name is not None
        instance.__dict__[self.name] = value

    def build_into(self, instance: t.Any, stream: io.BufferedIOBase) -> None:
        assert self.codec is not None
        self.codec.build_into(stream, self.getvalue(instance))

    def parse_from(self, instance: t.Any, stream: io.BufferedIOBase) -> None:
        assert self.codec is not None
        self.setvalue(instance, self.codec.parse_from(stream))

    def __get__(self, instance: t.Any, owner: t.Type[t.Any]) -> t.Union[Self, T]:
        if instance is None:
            return self
        return self.getvalue(instance)

    def __set__(self, instance: t.Any, value: T) -> None:
        self.setvalue(instance, value)

    def sizeof(self, instance: t.Any) -> int:
        assert self.codec is not None
        return self.codec.sizeof(self.getvalue(instance))


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
    def _get_type_hints(owner: type) -> t.Dict[str, t.Any]:
        # get_type_hints dumbly returns all hints for all baseclasses ever
        # but we only want this one class
        all_hints = get_type_hints(owner, include_extras=True)
        # so we filter it out by looking into __annotations__
        return {k: v for k, v in all_hints.items() if k in owner.__annotations__}

    @staticmethod
    def _extract_codec_type(field: t.Any) -> t.Optional[codecs.Codec]:
        origin = get_origin(field)
        args = get_args(field)
        if origin is t.ClassVar:
            return None
        if origin is t.Annotated:
            return Spec._extract_codec_type(args[1])
        if origin in (list, t.List):
            return Spec._extract_codec_type(args[0])
        if isinstance(field, codecs.Codec):
            return field
        raise TypeError("Unrecognized field type")

    @staticmethod
    def _make_field(field: t.Any, value: t.Any) -> t.Optional[Field]:
        if isinstance(value, Field):
            return value

        origin = get_origin(field)
        if origin in (list, t.List):
            return arrays.GreedyArray()
        else:
            return Field()

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

        annotations = cls._get_type_hints(owner)
        for name, field_type in annotations.items():
            codec = cls._extract_codec_type(field_type)
            if codec is None:
                continue
            value = getattr(owner, name, None)
            if value is INTERNAL_VALUE:
                continue
            field = cls._make_field(field_type, value)
            if field is None:
                continue

            field.name = name
            field.codec = codec
            if not isinstance(value, Field):
                field.default = value

            fields[name] = field

        return fields

    def decorate_owner(self) -> None:
        for name, field in self.fields.items():
            setattr(self.owner, name, field)
        setattr(self.owner, "_spec", self)

    def populate(self, instance: "Struct", kwargs: t.Dict[str, t.Any]) -> None:
        # TODO handle defaults
        for name, value in kwargs.items():
            if name not in self.fields:
                raise TypeError(f"Unexpected keyword argument {name!r}")
            setattr(instance, name, value)

    def as_dict(self, instance: "Struct") -> t.Dict[str, t.Any]:
        return {name: getattr(instance, name) for name in self.fields}


class StructInfo:
    pass


@dataclass_transform(kw_only_default=True, field_specifiers=(field, _internal))
class Struct:
    _spec: t.ClassVar[Spec]
    _struct: StructInfo = _internal()

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
    def stream_parse(cls, stream: io.BufferedIOBase) -> "Self":
        instance = cls.__new__(cls)
        for field in cls._spec.fields.values():
            field.parse_from(instance, stream)
        return instance

    @classmethod
    def parse(cls, data: bytes) -> "Self":
        inbuf = io.BytesIO(data)
        return cls.stream_parse(inbuf)

    def stream_build(self, stream: io.BufferedIOBase) -> None:
        for field in self._spec.fields.values():
            field.build_into(self, stream)

    def build(self) -> bytes:
        outbuf = io.BytesIO()
        self.stream_build(outbuf)
        return outbuf.getvalue()

    # codec protocol methods
    @classmethod
    def build_into(cls, stream: io.BufferedIOBase, value: "Self") -> None:
        value.stream_build(stream)

    @classmethod
    def parse_from(cls, stream: io.BufferedIOBase) -> "Self":
        return cls.stream_parse(stream)

    @classmethod
    def sizeof(cls, value: "Self") -> int:
        # TODO calculate this without building
        return len(value.build())


S = t.TypeVar("S", bound=Struct)


class Adapter(Struct, t.Generic[T]):
    if t.TYPE_CHECKING:

        def __get__(self, instance: t.Any, owner: t.Any) -> "t.Union[Self, T]":
            ...

        def __set__(self, instance: t.Any, value: T) -> None:
            ...

    @classmethod
    def encode(cls, value: T) -> "Self":
        raise NotImplementedError

    def decode(self) -> T:
        raise NotImplementedError

    @classmethod
    def build_into(cls, stream: io.BufferedIOBase, value: T) -> None:
        actual_type = cls.encode(value)
        actual_type.stream_build(stream)

    @classmethod
    def parse_from(cls, stream: io.BufferedIOBase) -> T:
        actual_type = cls.stream_parse(stream)
        return actual_type.decode()

    @classmethod
    def sizeof(cls, value: T) -> int:
        return cls.sizeof(cls.encode(value))
