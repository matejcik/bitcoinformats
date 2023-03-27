from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass
from typing import TYPE_CHECKING

import construct as c
from ecdsa.curves import SECP256k1
from ecdsa.ellipticcurve import INFINITY, Point
from typing_extensions import Self

from . import digistruct as d
from .base58 import b58check_decode, b58check_encode
from .utils import hash160

if TYPE_CHECKING:
    from gmpy2 import mpz  # type: ignore  /mpz is an extra/

HARDENED_FLAG = 0x8000_0000


def _pub_encode(public_key: Point) -> bytes:
    return public_key.to_bytes("compressed")


def _pub_decode(data: bytes) -> Point:
    return Point.from_bytes(SECP256k1, "compressed")


def _prv_encode(private_key: int | mpz) -> bytes:
    return int(private_key).to_bytes(32, "big")


def _prv_decode(data: bytes) -> int:
    return int.from_bytes(data, "big")


def _calculate_pubkey(privkey: int | mpz) -> Point:
    """Calculate the public key from a private key."""
    return SECP256k1.generator * privkey


class Xpub(d.Struct):
    version: d.big.uint32
    depth: d.big.uint8
    fingerprint: bytes = d.size(4)
    child_num: d.big.uint32
    chain_code: bytes = d.size(32)
    key_bytes: bytes = d.size(33)

    @classmethod
    def decode(cls, xpub: str) -> ExtendedKey:
        node = cls.parse(b58check_decode(xpub))
        if node.key_bytes[0] == 0:
            return ExtendedPrivateKey.from_xprv(node)
        else:
            return ExtendedKey.from_xpub(node)

    def encode(self) -> str:
        return b58check_encode(self.build())


@dataclass(frozen=True)
class ExtendedKey:
    depth: int
    fingerprint: bytes
    child_num: int
    chain_code: bytes
    public_key: Point

    def to_xpub(self, version: int = 0x0488_B21E) -> Xpub:
        return Xpub(
            version=version,
            depth=self.depth,
            fingerprint=self.fingerprint,
            child_num=self.child_num,
            chain_code=self.chain_code,
            key_bytes=_pub_encode(self.public_key),
        )

    @staticmethod
    def from_xpub(node: Xpub) -> ExtendedKey:
        if node.key_bytes[0] == 0:
            raise ValueError("Xprv provided, use ExtendedPrivateKey.from_xprv()")
        return ExtendedKey(
            depth=node.depth,
            child_num=node.child_num,
            chain_code=node.chain_code,
            fingerprint=node.fingerprint,
            public_key=_pub_decode(node.key_bytes),
        )

    def public_child(self, i: int) -> ExtendedKey:
        if i & HARDENED_FLAG:
            raise ValueError("Cannot generate public child with hardened index")

        i_as_bytes = i.to_bytes(4, "big")

        pubkey_bytes = _pub_encode(self.public_key)

        # Public derivation
        data = pubkey_bytes + i_as_bytes

        I64 = hmac.HMAC(
            key=self.chain_code, msg=data, digestmod=hashlib.sha512
        ).digest()
        I_left_as_exponent = int.from_bytes(I64[:32], "big")
        if I_left_as_exponent >= SECP256k1.order:
            raise ValueError("Derivation results in invalid key (I_left >= order)")

        # point(parse256(I_left)) + Kpar
        result = I_left_as_exponent * SECP256k1.generator + self.public_key

        if result == INFINITY:
            raise ValueError(
                "Derivation results in invalid key (public key is infinity)"
            )

        return ExtendedKey(
            depth=self.depth + 1,
            child_num=i,
            chain_code=I64[32:],
            fingerprint=hash160(pubkey_bytes)[:4],
            public_key=result,
        )

    def derive(self, path: list[int]) -> Self:
        res = self
        for i in path:
            res = res.public_child(i)
        return res


@dataclass(frozen=True)
class ExtendedPrivateKey(ExtendedKey):
    private_key: int | mpz

    def _serialize_private_key(self) -> bytes:
        assert self.private_key is not None
        return b"\x00" + _prv_encode(self.private_key)

    def to_xprv(self, version: int = 0x0488_ADE4) -> Xpub:
        return Xpub(
            version=version,
            depth=self.depth,
            fingerprint=self.fingerprint,
            child_num=self.child_num,
            chain_code=self.chain_code,
            key_bytes=self._serialize_private_key(),
        )

    @staticmethod
    def from_xprv(node: Xpub) -> ExtendedPrivateKey:
        if node.key_bytes[0] != 0:
            raise ValueError("Xpub provided, use ExtendedKey.from_xpub()")
        private_key = _prv_decode(node.key_bytes[1:])
        return ExtendedPrivateKey(
            depth=node.depth,
            child_num=node.child_num,
            chain_code=node.chain_code,
            fingerprint=node.fingerprint,
            private_key=private_key,
            public_key=_calculate_pubkey(private_key),
        )

    def private_child(self, i: int) -> ExtendedPrivateKey:
        i_as_bytes = i.to_bytes(4, "big")
        pubkey_bytes = _pub_encode(self.public_key)
        if i & HARDENED_FLAG:
            data = self._serialize_private_key() + i_as_bytes
        else:
            data = pubkey_bytes + i_as_bytes
        I64 = hmac.HMAC(
            key=self.chain_code, msg=data, digestmod=hashlib.sha512
        ).digest()

        I_left = int.from_bytes(I64[:32], "big")
        if I_left >= SECP256k1.order:
            raise ValueError("Derivation results in invalid key (I_left >= order)")

        private_key = (self.private_key + I_left) % SECP256k1.order
        if private_key == 0:
            raise ValueError("Derivation results in invalid key (private key is zero)")

        return ExtendedPrivateKey(
            depth=self.depth + 1,
            child_num=i,
            chain_code=I64[32:],
            fingerprint=hash160(pubkey_bytes)[:4],
            private_key=private_key,
            public_key=_calculate_pubkey(private_key),
        )

    @classmethod
    def master_key(cls, seed: bytes, seed_salt: bytes = b"Bitcoin seed") -> Self:
        I64 = hmac.HMAC(key=seed_salt, msg=seed, digestmod=hashlib.sha512).digest()
        I_left = int.from_bytes(I64[:32], "big")
        if not 0 < I_left < SECP256k1.order:
            raise ValueError(
                "Derivation results in invalid key (either zero or greater than order)"
            )
        return cls(
            depth=0,
            child_num=0,
            chain_code=I64[32:],
            fingerprint=b"\x00\x00\x00\x00",
            private_key=I_left,
            public_key=_calculate_pubkey(I_left),
        )

    def derive(self, path: list[int]) -> Self:
        res = self
        for i in path:
            res = res.private_child(i)
        return res


def parse_path(nstr: str) -> list[int]:
    """
    Convert BIP32 path string to list of uint32 integers with hardened flags.
    Several conventions are supported to set the hardened flag: -1, 1', 1h

    e.g.: "0/1h/1" -> [0, 0x80000001, 1]

    :param nstr: path string
    :return: list of integers
    """
    if not nstr:
        return []

    n = nstr.split("/")

    # m/a/b/c => a/b/c
    if n[0] == "m":
        n = n[1:]

    def str_to_harden(x: str) -> int:
        if x.startswith("-"):
            return abs(int(x)) | HARDENED_FLAG
        elif x.endswith(("h", "'")):
            return int(x[:-1]) | HARDENED_FLAG
        else:
            return int(x)

    try:
        return [str_to_harden(x) for x in n]
    except Exception as e:
        raise ValueError("Invalid BIP32 path", nstr) from e


def unparse_path(path: list[int]) -> str:
    """
    Convert list of uint32 integers with hardened flags to BIP32 path string.
    """

    def unharden(x: int) -> str:
        if x & HARDENED_FLAG:
            return str(x & ~HARDENED_FLAG) + "'"
        else:
            return str(x)

    parts = ["m"] + [unharden(x) for x in path]
    return "/".join(parts)


def from_seed(
    seed: bytes, path: list[int], *, seed_salt: bytes = b"Bitcoin seed"
) -> ExtendedPrivateKey:
    """Derive the extended key from a seed and a BIP32 path."""
    return ExtendedPrivateKey.master_key(seed, seed_salt).derive(path)
