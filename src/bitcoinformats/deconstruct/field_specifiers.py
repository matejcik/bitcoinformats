import typing as t


__all__ = [
    "field",
    "auto",
]


class FieldPlaceholder:
    pass


class InternalValue:
    def __init__(self, value: t.Any) -> None:
        self.value = value


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


def _internal(init: t.Literal[False] = False, default: t.Any = None) -> t.Any:
    return InternalValue(default)
