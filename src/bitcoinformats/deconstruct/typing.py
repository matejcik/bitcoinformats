import typing as t
from types import SimpleNamespace


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

int8 = int
int16 = int
int32 = int
int64 = int

uint8 = int
uint16 = int
uint32 = int
uint64 = int

class _ints:
    int8 = int
    int16 = int
    int32 = int
    int64 = int
    uint8 = int
    uint16 = int
    uint32 = int
    uint64 = int

be = big = le = little = _ints
