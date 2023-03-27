import dataclasses
import io
import logging
import typing as t

import typing_extensions as tx

from .exceptions import BuildError, EndOfStream

if t.TYPE_CHECKING:
    from .structs import Struct

T = t.TypeVar("T")

LOG = logging.getLogger(__name__)


MISSING = object()


@dataclasses.dataclass
class ContextItem:
    instance: "Struct"
    label: str
    stream: io.BufferedIOBase


class Context:
    def __init__(self, stream: io.BufferedIOBase) -> None:
        self.stream = stream
        self.stack: t.List[ContextItem] = []
        self.stack_top: t.Optional[ContextItem] = None

    def write(self, data: bytes) -> None:
        assert self.stack_top is not None
        self.stack_top.stream.write(data)

    def read(self, length: t.Optional[int] = None) -> bytes:
        assert self.stack_top is not None
        result = self.stack_top.stream.read(length)
        if length is not None and len(result) != length:
            raise EndOfStream
        return result

    def skip(self, length: int) -> None:
        assert self.stack_top is not None
        self.stack_top.stream.seek(length, io.SEEK_CUR)

    def seek(self, offset: int) -> None:
        assert self.stack_top is not None
        self.stack_top.stream.seek(offset)

    def tell(self) -> int:
        assert self.stack_top is not None
        return self.stack_top.stream.tell()

    def getvalue(self, field: "Field[T]") -> T:
        assert self.stack_top is not None
        return getattr(self.stack_top.instance, field.name)

    def setvalue(self, field: "Field[T]", value: T) -> None:
        assert self.stack_top is not None
        setattr(self.stack_top.instance, field.name, value)

    def push(self, instance: "Struct", label: str) -> tx.Self:
        if self.stack_top is not None:
            stream = self.stack_top.stream
        else:
            stream = self.stream
        self.stack_top = ContextItem(instance, label, stream)
        self.stack.append(self.stack_top)
        return self

    def pop(self) -> None:
        self.stack.pop()
        if self.stack:
            self.stack_top = self.stack[-1]
        else:
            self.stack_top = None

    def __enter__(self) -> tx.Self:
        return self

    def __exit__(self, exc_type: t.Any, exc_value: t.Any, traceback: t.Any) -> None:
        self.pop()


@t.runtime_checkable
class Codec(t.Protocol[T]):
    def build_value(self, context: Context, value: T) -> None:
        ...

    def parse_value(self, context: Context) -> T:
        ...

    def size_of(self, context: Context, value: T) -> int:
        ...


class DependentRelation(t.Protocol[T]):
    def update(self, instance: t.Any, referent: "Field[T]") -> T:
        ...


class Field(t.Generic[T]):
    _name: t.Optional[str] = None
    _codec: t.Optional[Codec[T]] = None

    default: t.Any = MISSING

    def __init__(self) -> None:
        self.dependent_relations: t.List[DependentRelation[T]] = []

    @property
    def name(self) -> str:
        assert self._name is not None
        return self._name

    @property
    def codec(self) -> Codec[T]:
        assert self._codec is not None
        return self._codec

    def make_codec(self, field_type: t.Any) -> Codec[T]:
        return extract_codec_type(field_type)

    def fill(self, name: str, field_type: t.Any, value: t.Any) -> None:
        self._name = name
        self._codec = self.make_codec(field_type)
        if value is not self:
            self.default = value

    def __get__(self, instance: t.Any, owner: t.Type[t.Any]) -> t.Union[tx.Self, T]:
        if instance is None:
            return self
        if self.name not in instance.__dict__:
            if self.default is MISSING:
                raise AttributeError(f"Field {self.name!r} is not set")
            return self.default
        return instance.__dict__[self.name]

    def __set__(self, instance: t.Any, value: T) -> None:
        instance.__dict__[self.name] = value

    def depend_on(self, relation: DependentRelation[T]) -> None:
        self.dependent_relations.append(relation)

    def is_dependent(self) -> bool:
        return bool(self.dependent_relations)

    def recalculate(self, ctx: Context) -> None:
        if not self.is_dependent():
            return

        values = [rel.update(ctx, self) for rel in self.dependent_relations]
        # all values must be the same
        if any(v != values[0] for v in values):
            raise BuildError(f"Inconsistent values for field {self.name!r}")

        ctx.setvalue(self, values[0])


def get_type_hints(owner: type) -> t.Dict[str, t.Any]:
    # get_type_hints dumbly returns all hints for all baseclasses ever
    # but we only want this one class
    all_hints = tx.get_type_hints(owner, include_extras=True)
    # so we filter it out by looking into __annotations__
    return {k: v for k, v in all_hints.items() if k in owner.__annotations__}


def extract_codec_type(field: t.Any) -> Codec:
    origin = tx.get_origin(field)
    args = tx.get_args(field)
    if origin is t.Annotated:
        return extract_codec_type(args[1])
    if origin in (list, t.List):
        return extract_codec_type(args[0])
    if isinstance(field, Codec):
        return field
    print("at field: ", field)
    raise TypeError("Unrecognized field type")