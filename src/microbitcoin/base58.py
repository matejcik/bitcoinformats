from __future__ import annotations

import typing as t

from .utils import hash256

__b58chars = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
__b58base = len(__b58chars)


def b58encode(v: bytes) -> str:
    """encode v, which is a string of bytes, to base58."""

    long_value = 0
    for c in v:
        long_value = long_value * 256 + c

    chars = []
    while long_value >= __b58base:
        div, mod = divmod(long_value, __b58base)
        chars.append(__b58chars[mod])
        long_value = div
    chars.append(long_value)

    # Bitcoin does a little leading-zero-compression:
    # leading 0-bytes in the input become leading-1s
    nPad = 0
    for c in v:
        if c == 0:
            nPad += 1
        else:
            break

    return (__b58chars[0] * nPad) + "".join(chars[::-1])


def b58decode(v: t.AnyStr, length: int | None = None) -> bytes:
    """decode v into a string of length bytes."""
    str_v = v.decode() if isinstance(v, bytes) else v

    for c in str_v:
        if c not in __b58chars:
            raise ValueError("invalid Base58 string")

    long_value = 0
    for i, c in enumerate(str_v[::-1]):
        long_value += __b58chars.find(c) * (__b58base**i)

    byte_data = []
    while long_value >= 256:
        div, mod = divmod(long_value, 256)
        byte_data.append(mod)
        long_value = div
    byte_data.append(long_value)

    nPad = 0
    for c in str_v:
        if c == __b58chars[0]:
            nPad += 1
        else:
            break

    result = b"\x00" * nPad + bytes(byte_data[::-1])
    if length is not None and len(result) != length:
        raise ValueError("Result length does not match expected_length")

    return result


def b58check_encode(v: bytes, *, digest: t.Callable[[bytes], bytes] = hash256) -> str:
    checksum = digest(v)[:4]
    return b58encode(v + checksum)


def b58check_decode(
    v: t.AnyStr,
    length: int | None = None,
    *,
    digest: t.Callable[[bytes], bytes] = hash256,
) -> bytes:
    dec = b58decode(v, length)
    data, checksum = dec[:-4], dec[-4:]
    if digest(data)[:4] != checksum:
        raise ValueError("invalid checksum")
    return data
