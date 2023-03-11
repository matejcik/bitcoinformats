import io
import struct
import sys
import typing as t

if t.TYPE_CHECKING:
    from typing_extensions import Self, dataclass_transform

else:
    _identity = lambda x: x
    dataclass_transform = lambda *args, **kwargs: _identity


T = t.TypeVar("T")


class DeconstructError(Exception):
    pass


class UnsupportedError(DeconstructError):
    pass


class ParseError(DeconstructError):
    pass


class BuildError(DeconstructError):
    pass


class SizeofError(DeconstructError):
    pass


class Field(t.Generic[T]):
    private_name: str

    def __init__(self) -> None:
        pass

    def __set_name__(self, _owner: t.Any, name: str) -> None:
        self.private_name = "_" + name

    def __get__(self, instance: t.Any, _owner: t.Any = None) -> t.Union[T, Self]:
        if instance is None:
            return self
        return getattr(instance, self.private_name)

    def __set__(self, instance: t.Any, value: T) -> None:
        if instance is None:
            raise AttributeError("can't set attribute")
        setattr(instance, self.private_name, value)

    def __getitem__(self, key: t.Union[int, "Field[int]"]) -> "Array[T]":
        if not isinstance(key, int):
            raise TypeError("Array size must be an integer")
        return Array(self, key)

    def build(self, stream: io.IOBase, value: T) -> None:
        raise UnsupportedError(f"Cannot build field of type {type(self).__name__}.")

    def parse(self, stream: io.IOBase) -> T:
        raise UnsupportedError(f"Cannot parse field of type {type(self).__name__}.")

    def sizeof(self, instance: t.Any = None) -> int:
        raise NotImplementedError


class Array(Field[t.List[T]]):
    def __init__(self, inner_type: Field[T], length: int) -> None:
        self.length = length
        self.inner_type = inner_type

    def build(self, stream: io.IOBase, value: t.List[T]) -> None:
        if len(value) != self.length:
            raise BuildError(
                f"Array length mismatch: expected {self.length}, got {len(value)}"
            )
        for item in value:
            self.inner_type.build(stream, item)

    def parse(self, stream: io.IOBase) -> t.List[T]:
        value = []
        for _ in range(self.length):
            value.append(self.inner_type.parse(stream))
        return value


class FormatField(Field[T]):
    _format: str

    @classmethod
    def make(cls, name: str, format: str, value_type: t.Type[T]) -> t.Type[Field[T]]:
        return type(name, (cls,), {"_format": format})

    def build(self, stream: io.IOBase, value: T) -> None:
        packed = struct.pack(self._format, value)
        stream.write(packed)

    def parse(self, stream: io.IOBase) -> T:
        size = self.sizeof()
        data = stream.read(size)
        return struct.unpack(self._format, data)[0]

    def sizeof(self, instance: t.Any = None) -> int:
        return struct.calcsize(self._format)


int8ul = FormatField.make("int8ul", "<B", int)
int8ub = FormatField.make("int8ub", ">B", int)
int16ul = FormatField.make("int16ul", "<H", int)
int16ub = FormatField.make("int16ub", ">H", int)
int32ul = FormatField.make("int32ul", "<I", int)
int32ub = FormatField.make("int32ub", ">I", int)
int64ul = FormatField.make("int64ul", "<Q", int)
int64ub = FormatField.make("int64ub", ">Q", int)

int8sl = FormatField.make("int8sl", "<b", int)
int8sb = FormatField.make("int8sb", ">b", int)
int16sl = FormatField.make("int16sl", "<h", int)
int16sb = FormatField.make("int16sb", ">h", int)
int32sl = FormatField.make("int32sl", "<i", int)
int32sb = FormatField.make("int32sb", ">i", int)
int64sl = FormatField.make("int64sl", "<q", int)
int64sb = FormatField.make("int64sb", ">q", int)


def field() -> t.Any:
    pass


@dataclass_transform(kw_only_default=True, field_specifiers=(field,))
class StructMeta(type):
    @staticmethod
    def _is_field(value: t.Any) -> bool:
        return isinstance(value, type) and issubclass(value, Field)

    def __new__(
        cls, name: str, bases: t.Tuple[t.Type, ...], namespace: t.Dict[str, t.Any]
    ) -> "Self":
        # temporary class object to get the nice behavior of get_type_hints
        _tmpcls = super().__new__(cls, name, bases, namespace)
        annotations = t.get_type_hints(_tmpcls)

        fields = {}

        for name, field in annotations.items():
            if getattr(field, "__origin__", None) is t.ClassVar:
                continue
            if not StructMeta._is_field(field):
                raise DeconstructError(
                    f"Structs can only contain fields (found {field!r})."
                )
            field_instance = field()
            namespace[name] = field_instance
            fields[name] = field_instance

        namespace["__struct_info__"] = fields
        return super().__new__(cls, name, bases, namespace)


class Struct(metaclass=StructMeta):
    __struct_info__: t.ClassVar[t.Dict[str, t.Any]]

    def __init__(self, **kwargs: t.Any) -> None:
        for name, value in kwargs.items():
            if name not in self.__struct_info__:
                raise TypeError(f"Unexpected keyword argument {name!r}")
            setattr(self, name, value)

    def __eq__(self, other: t.Any) -> bool:
        if not isinstance(other, type(self)):
            return NotImplemented
        for name in self.__struct_info__:
            if getattr(self, name) != getattr(other, name):
                return False
        return True

    @classmethod
    def parse(cls, data: bytes) -> "Self":
        inbuf = io.BytesIO(data)
        kwargs = {}
        for name, field in cls.__struct_info__.items():
            kwargs[name] = field.parse(inbuf)
        return cls(**kwargs)

    def build(self) -> bytes:
        outbuf = io.BytesIO()
        for name, field in self.__struct_info__.items():
            field.build(outbuf, getattr(self, name))
        return outbuf.getvalue()

    def sizeof(self) -> int:
        return sum(field.sizeof(self) for field in self.__struct_info__.values())
