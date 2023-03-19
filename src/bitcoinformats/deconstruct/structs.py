import io
import sys
import typing as t
import warnings

from .fields import Field
from .field_specifiers import _internal, field, InternalValue
from .exceptions import DeconstructError


if t.TYPE_CHECKING:
    from typing_extensions import Self, dataclass_transform
else:
    _identity = lambda x: x
    dataclass_transform = lambda *args, **kwargs: _identity


T = t.TypeVar("T")


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
        all_hints = t.get_type_hints(owner)
        # so we filter it out by looking into __annotations__
        return {k: v for k, v in all_hints.items() if k in owner.__annotations__}

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
            if getattr(field, "__origin__", None) is t.ClassVar:
                continue

            declared_value = getattr(owner, name, None)
            if isinstance(declared_value, InternalValue):
                setattr(owner, name, declared_value.value)
                continue

            if getattr(field, "__origin__", None) in (list, t.List):
                if declared_value is None:
                    raise DeconstructError(
                        f"Array spec for list field {name!r} not found."
                    )
                field = field.__args__[0]

            if not safe_issubclass(field, Field):
                raise DeconstructError(
                    f"Structs can only contain fields (found {field!r})."
                )
            fields[name] = field()

        return fields

    def decorate_owner(self) -> None:
        for name, field in self.fields.items():
            setattr(self.owner, name, field)
            field.__set_name__(self.owner, name)
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


U = t.TypeVar("U")

__all__ = ["Spec", "StructInfo", "Struct"]
