import io
import typing as t

import typing_extensions as tx

from .base import Field, get_type_hints, extract_codec_type, MISSING
from . import arrays
from .field_specifiers import field
from .exceptions import DeconstructError, BuildError


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
    def _make_field(field: t.Any, value: t.Any) -> t.Optional[Field]:
        if isinstance(value, Field):
            return value

        origin = tx.get_origin(field)
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

        annotations = get_type_hints(owner)
        for name, field_type in annotations.items():
            codec = extract_codec_type(field_type)
            if codec is None:
                continue
            value = getattr(owner, name, MISSING)
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
            if name not in self.fields or self.fields[name].is_dependent():
                raise TypeError(f"Unexpected keyword argument {name!r}")
            setattr(instance, name, value)
        for name, field in self.fields.items():
            if name not in kwargs:
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
        instance = cls.__new__(cls)
        for field in cls._spec.fields.values():
            field.parse_from(instance, stream)
        return instance

    @classmethod
    def parse(cls, data: bytes) -> tx.Self:
        inbuf = io.BytesIO(data)
        return cls.stream_parse(inbuf)

    def stream_build(self, stream: io.BufferedIOBase) -> None:
        for field in self._spec.fields.values():
            try:
                field.recalculate(self)
                field.build_into(self, stream)
            except Exception as e:
                raise BuildError(f"Failed to build field {field.name!r}", e) from e

    def build(self) -> bytes:
        outbuf = io.BytesIO()
        self.stream_build(outbuf)
        return outbuf.getvalue()

    # codec protocol methods
    @classmethod
    def build_into(cls, stream: io.BufferedIOBase, value: tx.Self) -> None:
        value.stream_build(stream)

    @classmethod
    def parse_from(cls, stream: io.BufferedIOBase) -> tx.Self:
        return cls.stream_parse(stream)

    @classmethod
    def sizeof(cls, value: tx.Self) -> int:
        # TODO calculate this without building
        return len(value.build())


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
