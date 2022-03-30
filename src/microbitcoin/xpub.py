from __future__ import annotations

from dataclasses import dataclass

import construct as c

from .struct import Struct
from .base58 import b58check_decode, b58check_encode

XpubPrivateKey = c.Array(c.Const(b"\0"), c.Bytes(32))
XpubPublicKey = c.Bytes(33)


@dataclass
class XpubStruct(Struct):
    version: int
    depth: int
    fingerprint: int
    child_num: int
    chain_code: bytes
    _key: bytes
    public_key: bytes | None = None
    private_key: bytes | None = None

    SUBCON = c.Struct(
        "version" / c.Int32ul,
        "depth" / c.Int8ul,
        "fingerprint" / c.Int32ul,
        "child_num" / c.Int32ul,
        "chain_code" / c.Bytes(32),
        "_key" / c.Bytes(33),
        c.Terminated,
    )

    def build(self) -> bytes:
        if self.public_key is None == self.private_key is None:
            raise ValueError("Please set exactly one of public_key or private_key")
        if self.public_key is not None:
            self._key = self.public_key
        else:
            self._key = b"\x00" + self.private_key
        return super().build()

    def encode(self) -> str:
        return b58check_encode(self.build())

    @classmethod
    def parse(cls: type[XpubStruct], data: bytes) -> XpubStruct:
        result = super().parse(data)
        if result._key[0] == 0:
            result.private_key = result._key[1:]
        else:
            result.public_key = result._key
        return result

    @classmethod
    def decode(cls: type[XpubStruct], data: str) -> XpubStruct:
        return cls.parse(b58check_decode(data))
