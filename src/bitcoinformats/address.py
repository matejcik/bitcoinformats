from . import bech32
from .utils import hash160
from .base58 import b58check_encode


def version_to_bytes(version):
    vlen = max(1, (version.bit_length() + 7) // 8)
    return version.to_bytes(vlen, "big")


def address_p2pkh(version, pubkey):
    assert pubkey[0] != 4, "uncompressed pubkey"
    prefix_bytes = version_to_bytes(version)
    pubkey_bytes = hash160(pubkey)
    return b58check_encode(prefix_bytes + pubkey_bytes)


def address_p2sh_p2wpkh(version, pubkey):
    assert pubkey[0] != 4, "uncompressed pubkey"
    prefix_bytes = version_to_bytes(version)
    pubkey_bytes = hash160(pubkey)
    witness = b"\x00\x14" + pubkey_bytes
    witness_bytes = hash160(witness)
    return b58check_encode(prefix_bytes + witness_bytes)


def address_p2wpkh(version, pubkey):
    assert pubkey[0] != 4, "uncompressed pubkey"
    witver = 0
    witprog = hash160(pubkey)
    return bech32.encode(version, witver, witprog)
