import io
import sys
import typing as t
import warnings

from .arrays import ArraySpec
from .fields import Field
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
    def _get_field_type(field: t.Any, value: t.Any) -> t.Optional[Field]:
        if value is INTERNAL_VALUE:
            return None

        origin = get_origin(field)
        args = get_args(field)
        if origin is t.ClassVar:
            return None
        if origin is t.Annotated:
            return Spec._get_field_type(args[1], value)
        if origin in (list, t.List):
            assert isinstance(value, ArraySpec)
            return value.make_field(args[0])
        if safe_issubclass(field, Adapter):
            return AdapterField(field)
        elif safe_issubclass(field, Struct):
            return StructField(field)
        if isinstance(field, Field):
            return field
        raise TypeError("Unrecognized field type")

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
        for name, field in annotations.items():
            value = getattr(owner, name, None)
            field_type = cls._get_field_type(field, value)
            if field_type is None:
                continue

            fields[name] = field_type

        return fields

    def decorate_owner(self) -> None:
        for name, _ in self.fields.items():
            if hasattr(self.owner, name):
                delattr(self.owner, name)
        setattr(self.owner, "_spec", self)

    def populate(self, instance: "Struct", kwargs: t.Dict[str, t.Any]) -> None:
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
        for name, field in cls._spec.fields.items():
            setattr(instance, name, field.parse_from(stream))
        return instance

    @classmethod
    def parse(cls, data: bytes) -> "Self":
        inbuf = io.BytesIO(data)
        return cls.stream_parse(inbuf)

    def stream_build(self, stream: io.BufferedIOBase) -> None:
        for name, field in self._spec.fields.items():
            field.build_into(stream, getattr(self, name))

    def build(self) -> bytes:
        outbuf = io.BytesIO()
        self.stream_build(outbuf)
        return outbuf.getvalue()

    def sizeof(self) -> int:
        total = 0
        for name, field in self._spec.fields.items():
            value = getattr(self, name)
            total += field.sizeof(value)
        return total


S = t.TypeVar("S", bound=Struct)


class StructField(Field[S]):
    def __init__(self, struct: t.Type[S]) -> None:
        self.struct = struct

    def parse_from(self, stream: io.BufferedIOBase) -> S:
        return self.struct.stream_parse(stream)

    def build_into(self, stream: io.BufferedIOBase, value: S) -> None:
        value.stream_build(stream)

    def sizeof(self, value: S) -> int:
        return value.sizeof()


class Adapter(Struct, t.Generic[T]):
    def __get__(self, instance: t.Any, owner: t.Any) -> "t.Union[Self, T]":
        raise RuntimeError("Adapter should not be used as a descriptor.")

    def __set__(self, instance: t.Any, value: T) -> None:
        raise RuntimeError("Adapter should not be used as a descriptor.")

    @classmethod
    def encode(cls, value: T) -> "Self":
        raise NotImplementedError

    def decode(self) -> T:
        raise NotImplementedError


class AdapterField(Field[T]):
    def __init__(self, adapter: t.Type[Adapter[T]]) -> None:
        self.adapter = adapter

    def build_into(self, stream: io.BufferedIOBase, value: T) -> None:
        actual_type = self.adapter.encode(value)
        actual_type.stream_build(stream)

    def parse_from(self, stream: io.BufferedIOBase) -> T:
        actual_type = self.adapter.stream_parse(stream)
        return actual_type.decode()

    def sizeof(self, value: T) -> int:
        return self.adapter.encode(value).sizeof()
