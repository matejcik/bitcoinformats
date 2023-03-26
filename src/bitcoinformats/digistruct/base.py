import io
import logging
import typing as t

import typing_extensions as tx

from .exceptions import BuildError

T = t.TypeVar("T")

LOG = logging.getLogger(__name__)


MISSING = object()


@t.runtime_checkable
class Codec(t.Protocol[T]):
    def build_into(self, stream: io.BufferedIOBase, value: T) -> None:
        ...

    def parse_from(self, stream: io.BufferedIOBase) -> T:
        ...

    def sizeof(self, value: T) -> int:
        ...


class DependentRelation(t.Protocol[T]):
    def update(self, instance: t.Any, referent: "Field[T]") -> T:
        ...


class Field(t.Generic[T]):
    name: t.Optional[str] = None
    codec: t.Optional[Codec[T]] = None
    default: t.Union[T, object, None] = MISSING

    def __init__(self) -> None:
        self.dependent_relations: t.List[DependentRelation[T]] = []

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

    def __get__(self, instance: t.Any, owner: t.Type[t.Any]) -> t.Union[tx.Self, T]:
        if instance is None:
            return self
        return self.getvalue(instance)

    def __set__(self, instance: t.Any, value: T) -> None:
        self.setvalue(instance, value)

    def sizeof(self, instance: t.Any) -> int:
        assert self.codec is not None
        return self.codec.sizeof(self.getvalue(instance))

    def depend_on(self, relation: DependentRelation[T]) -> None:
        self.dependent_relations.append(relation)

    def is_dependent(self) -> bool:
        return bool(self.dependent_relations)

    def recalculate(self, instance: t.Any) -> None:
        if not self.is_dependent():
            return

        values = [rel.update(instance, self) for rel in self.dependent_relations]
        # all values must be the same
        if any(v != values[0] for v in values):
            raise BuildError(f"Inconsistent values for field {self.name!r}")
        self.setvalue(instance, values[0])
        LOG.warning("Recalculated field %r, using value %r", self.name, values[0])


def get_type_hints(owner: type) -> t.Dict[str, t.Any]:
    # get_type_hints dumbly returns all hints for all baseclasses ever
    # but we only want this one class
    all_hints = tx.get_type_hints(owner, include_extras=True)
    # so we filter it out by looking into __annotations__
    return {k: v for k, v in all_hints.items() if k in owner.__annotations__}


def extract_codec_type(field: t.Any) -> t.Optional[Codec]:
    origin = tx.get_origin(field)
    args = tx.get_args(field)
    if origin is t.ClassVar:
        return None
    if origin is t.Annotated:
        return extract_codec_type(args[1])
    if origin in (list, t.List):
        return extract_codec_type(args[0])
    if isinstance(field, Codec):
        return field
    raise TypeError("Unrecognized field type")
