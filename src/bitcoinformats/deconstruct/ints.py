from types import SimpleNamespace

from .fields import FormatField

__all__ = [
    "int8",
    "int16",
    "int32",
    "int64",
    "uint8",
    "uint16",
    "uint32",
    "uint64",
    "be",
    "big",
    "le",
    "little",
]


int8 = FormatField.make("=b")
int16 = FormatField.make("=h")
int32 = FormatField.make("=i")
int64 = FormatField.make("=q")

uint8 = FormatField.make("=B")
uint16 = FormatField.make("=H")
uint32 = FormatField.make("=I")
uint64 = FormatField.make("=Q")

be = big = SimpleNamespace(
    int8=FormatField.make(">b"),
    int16=FormatField.make(">h"),
    int32=FormatField.make(">i"),
    int64=FormatField.make(">q"),
    uint8=FormatField.make(">B"),
    uint16=FormatField.make(">H"),
    uint32=FormatField.make(">I"),
    uint64=FormatField.make(">Q"),
)

le = little = SimpleNamespace(
    int8=FormatField.make("<b"),
    int16=FormatField.make("<h"),
    int32=FormatField.make("<i"),
    int64=FormatField.make("<q"),
    uint8=FormatField.make("<B"),
    uint16=FormatField.make("<H"),
    uint32=FormatField.make("<I"),
    uint64=FormatField.make("<Q"),
)
