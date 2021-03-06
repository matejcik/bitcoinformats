from __future__ import annotations

import typing as t
import dataclasses
from typing_extensions import Self, dataclass_transform

import construct as c


def subcon(cls: type[Struct]) -> t.Any:
    return dataclasses.field(metadata={"substruct": cls})


@dataclass_transform(field_specifiers=(subcon,))
class _StructMeta(type):
    def __new__(
        cls, name: str, bases: tuple[type, ...], namespace: dict[str, t.Any]
    ) -> type:
        new_cls = super().__new__(cls, name, bases, namespace)
        return dataclasses.dataclass()(new_cls)


class Struct(metaclass=_StructMeta):
    SUBCON: t.ClassVar[c.Struct]

    def build(self) -> bytes:
        return self.SUBCON.build(dataclasses.asdict(self))

    @staticmethod
    def _decontainerize(item: t.Any) -> t.Any:
        if isinstance(item, c.ListContainer):
            return [Struct._decontainerize(i) for i in item]
        return item

    @classmethod
    def from_parsed(cls: type[Self], data: c.Container) -> Self:
        del data["_io"]
        for field in dataclasses.fields(cls):
            subcls = field.metadata.get("substruct")
            if subcls is None:
                continue

            field_data = data.get(field.name)
            if isinstance(field_data, c.ListContainer):
                data[field.name] = [subcls.from_parsed(d) for d in field_data]
            elif isinstance(field_data, c.Container):
                data[field.name] = subcls.from_parsed(field_data)
            elif field_data is None:
                continue
            else:
                raise ValueError(
                    f"Mismatched type for field {field.name}: expected a struct, found {type(field_data)}"
                )

        for key in data:
            data[key] = cls._decontainerize(data[key])
        return cls(**data)

    @classmethod
    def parse(cls: type[Self], data: bytes) -> Self:
        result = cls.SUBCON.parse(data)
        return cls.from_parsed(result)
