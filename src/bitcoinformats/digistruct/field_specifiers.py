import typing as t

from . import structs


__all__ = [
    "field",
    "auto",
]

INTERNAL_VALUE = object()


def field(**kwargs) -> t.Any:
    return structs.Field()


@t.overload
def auto(init: t.Literal[False] = False) -> t.Any:
    ...


@t.overload
def auto(init: bool) -> t.Any:
    ...


def auto(init: bool = False) -> t.Any:
    return structs.Field()
