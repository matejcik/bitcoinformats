from __future__ import annotations

import hmac
import hashlib
from dataclasses import dataclass, replace, asdict
from typing_extensions import Self

import construct as c
from fastecdsa.curve import secp256k1
from fastecdsa.keys import get_public_key
from fastecdsa.point import Point
from fastecdsa.encoding.sec1 import SEC1Encoder

from .struct import Struct
from .base58 import b58check_decode, b58check_encode
from .utils import hash160

HARDENED_FLAG = 0x8000_0000


def calculate_public_key(private_key: int) -> bytes:
    pubkey = get_public_key(private_key, secp256k1)
    return SEC1Encoder.encode_public_key(pubkey)


@dataclass
class Xpub(Struct):
    version: int
    depth: int
    fingerprint: bytes
    child_num: int
    chain_code: bytes
    key_bytes: bytes

    SUBCON = c.Struct(
        "version" / c.Int32ub,
        "depth" / c.Int8ub,
        "fingerprint" / c.Bytes(4),
        "child_num" / c.Int32ub,
        "chain_code" / c.Bytes(32),
        "key_bytes" / c.Bytes(33),
        c.Terminated,
    )

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
    public_key: bytes

    def to_xpub(self, version: int = 0x0488_B21E) -> Xpub:
        return Xpub(
            version=version,
            depth=self.depth,
            fingerprint=self.fingerprint,
            child_num=self.child_num,
            chain_code=self.chain_code,
            key_bytes=self.public_key,
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
            public_key=node.key_bytes,
        )

    def public_child(self, i: int) -> ExtendedKey:
        if i & HARDENED_FLAG:
            raise ValueError("Cannot generate public child with hardened index")

        i_as_bytes = i.to_bytes(4, "big")

        # Public derivation
        data = self.public_key + i_as_bytes

        I64 = hmac.HMAC(
            key=self.chain_code, msg=data, digestmod=hashlib.sha512
        ).digest()
        I_left_as_exponent = int.from_bytes(I64[:32], "big")
        if I_left_as_exponent >= secp256k1.q:
            raise ValueError("Derivation results in invalid key (I_left >= q)")

        k_par = SEC1Encoder.decode_public_key(self.public_key, secp256k1)
        # point(parse256(I_left)) + Kpar
        result = I_left_as_exponent * secp256k1.G + k_par

        if k_par == Point.IDENTITY_ELEMENT:
            raise ValueError(
                "Derivation results in invalid key (public key is infinity)"
            )

        # Convert public point to compressed public key
        public_key = SEC1Encoder.encode_public_key(result)

        return ExtendedKey(
            depth=self.depth + 1,
            child_num=i,
            chain_code=I64[32:],
            fingerprint=hash160(self.public_key)[:4],
            public_key=public_key,
        )

    def derive(self, path: list[int]) -> Self:
        res = self
        for i in path:
            res = res.public_child(i)
        return res


@dataclass(frozen=True)
class ExtendedPrivateKey(ExtendedKey):
    private_key: int

    def _serialize_private_key(self) -> bytes:
        assert self.private_key is not None
        return b"\x00" + self.private_key.to_bytes(32, "big")

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
        private_key = int.from_bytes(node.key_bytes[1:], "big")
        return ExtendedPrivateKey(
            depth=node.depth,
            child_num=node.child_num,
            chain_code=node.chain_code,
            fingerprint=node.fingerprint,
            private_key=private_key,
            public_key=calculate_public_key(private_key),
        )

    def private_child(self, i: int) -> ExtendedPrivateKey:
        i_as_bytes = i.to_bytes(4, "big")
        if i & HARDENED_FLAG:
            data = self._serialize_private_key() + i_as_bytes
        else:
            data = self.public_key + i_as_bytes
        I64 = hmac.HMAC(
            key=self.chain_code, msg=data, digestmod=hashlib.sha512
        ).digest()

        I_left = int.from_bytes(I64[:32], "big")
        if I_left >= secp256k1.q:
            raise ValueError("Derivation results in invalid key (I_left >= q)")

        private_key = (self.private_key + I_left) % secp256k1.q
        if private_key == 0:
            raise ValueError("Derivation results in invalid key (private key is zero)")

        return ExtendedPrivateKey(
            depth=self.depth + 1,
            child_num=i,
            chain_code=I64[32:],
            fingerprint=hash160(self.public_key)[:4],
            private_key=private_key,
            public_key=calculate_public_key(private_key),
        )

    @classmethod
    def master_key(cls, seed: bytes, seed_salt: bytes = b"Bitcoin seed") -> Self:
        I64 = hmac.HMAC(key=seed_salt, msg=seed, digestmod=hashlib.sha512).digest()
        I_left = int.from_bytes(I64[:32], "big")
        if not 0 < I_left < secp256k1.q:
            raise ValueError(
                "Derivation results in invalid key (either zero or greater than q)"
            )
        return cls(
            depth=0,
            child_num=0,
            chain_code=I64[32:],
            fingerprint=b"\x00\x00\x00\x00",
            private_key=I_left,
            public_key=calculate_public_key(I_left),
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


def from_seed(
    seed: bytes, path: list[int], *, seed_salt: bytes = b"Bitcoin seed"
) -> ExtendedPrivateKey:
    """Derive the extended key from a seed and a BIP32 path."""
    return ExtendedPrivateKey.master_key(seed, seed_salt).derive(path)
