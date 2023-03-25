import typing as t


__all__ = [
    "field",
    "auto",
]

INTERNAL_VALUE = object()


class FieldPlaceholder:
    pass


def field(**kwargs) -> t.Any:
    return FieldPlaceholder()


@t.overload
def auto(init: t.Literal[False] = False) -> t.Any:
    ...


@t.overload
def auto(init: bool) -> t.Any:
    ...


def auto(init: bool = False) -> t.Any:
    return FieldPlaceholder()


def _internal(init: t.Literal[False] = False) -> t.Any:
    return INTERNAL_VALUE
