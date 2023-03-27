import typing as t

from .base import Field

__all__ = [
    "field",
    "auto",
]

INTERNAL_VALUE = object()


def field(**kwargs) -> t.Any:
    return Field()


def auto(init: t.Literal[False] = False) -> t.Any:
    field = Field()
    field.default = None
    return field
