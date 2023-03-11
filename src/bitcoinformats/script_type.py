from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256

from typing_extensions import Protocol, Self

from . import base58, bech32, utils
from .network import Network
from .opcodes import Opcode, build_op_push, extract_op_push, op_number


def version_to_bytes(version: int) -> bytes:
    vlen = max(1, (version.bit_length() + 7) // 8)
    return version.to_bytes(vlen, "big")


def parse_script_data(data: bytes) -> bytes:
    """Parse length-prefixed data in a Bitcoin script."""
    try:
        return extract_op_push(data)
    except ValueError as e:
        raise ValueError from e


class Script(Protocol):
    @classmethod
    def from_scriptpubkey(cls, script: bytes) -> Self:
        ...

    @classmethod
    def from_address(cls, address: str, network: Network) -> Self:
        ...

    def to_scriptpubkey(self) -> bytes:
        ...

    def to_address(self, network: Network) -> str:
        ...


@dataclass(frozen=True)
class Unknown(Script):
    script: bytes

    @classmethod
    def from_scriptpubkey(cls, script: bytes) -> Self:
        return cls(script)

    @classmethod
    def from_address(cls, address: str, network: Network) -> Self:
        raise ValueError("Unknown script")

    def to_scriptpubkey(self) -> bytes:
        return self.script

    def to_address(self, network: Network) -> str:
        raise ValueError("Unknown script")


@dataclass(frozen=True)
class OpReturn(Script):
    data: bytes

    BITCOIN_MAX_LENGTH = 80

    @classmethod
    def from_scriptpubkey(cls, script: bytes) -> Self:
        if script[0] != Opcode.OP_RETURN:
            raise ValueError("OpReturn must start with OP_RETURN")
        return cls(parse_script_data(script[1:]))

    @classmethod
    def from_address(cls, address: str, network: Network) -> Self:
        raise ValueError("Address cannot be OP_RETURN")

    def to_scriptpubkey(self) -> bytes:
        return bytes([Opcode.OP_RETURN]) + build_op_push(self.data)

    def to_address(self, network: Network) -> str:
        raise ValueError("Address cannot be OP_RETURN")


@dataclass(frozen=True)
class P2PK(Script):
    pubkey: bytes

    def __post_init__(self) -> None:
        """Validate public key."""
        if len(self.pubkey) != 33:
            raise ValueError("Invalid public key length")
        if self.pubkey[0] == 4:
            raise ValueError("Uncompressed public keys are not supported")

    @classmethod
    def from_scriptpubkey(cls, script: bytes) -> Self:
        if len(script) != 35:
            raise ValueError("P2PK must be 35 bytes long")
        if script[-1] != Opcode.OP_CHECKSIG:
            raise ValueError("P2PK must end with OP_CHECKSIG")
        return cls(parse_script_data(script[:34]))

    @classmethod
    def from_address(cls, address: str, network: Network) -> Self:
        raise ValueError("Address cannot be P2PK")

    def to_scriptpubkey(self) -> bytes:
        return build_op_push(self.pubkey) + bytes([Opcode.OP_CHECKSIG])

    def to_address(self, network: Network) -> str:
        raise ValueError("Address cannot be P2PK")


@dataclass(frozen=True)
class P2PKH(Script):
    pubkey_hash: bytes

    SCRIPT_PREFIX = bytes([Opcode.OP_DUP, Opcode.OP_HASH160])
    SCRIPT_SUFFIX = bytes([Opcode.OP_EQUALVERIFY, Opcode.OP_CHECKSIG])

    def __post_init__(self) -> None:
        """Validate public key hash."""
        if len(self.pubkey_hash) != 20:
            raise ValueError("Invalid public key hash length")

    @classmethod
    def from_pubkey(cls, pubkey: bytes) -> Self:
        if pubkey[0] == 4:
            raise ValueError("Uncompressed public keys are not supported")
        return cls(utils.hash160(pubkey))

    @classmethod
    def from_scriptpubkey(cls, script: bytes) -> Self:
        if len(script) != 25:
            raise ValueError("P2PKH must be 25 bytes long")
        if script[:2] != cls.SCRIPT_PREFIX:
            raise ValueError("P2PKH must start with OP_DUP OP_HASH160")
        if script[-2:] != cls.SCRIPT_SUFFIX:
            raise ValueError("P2PKH must end with OP_EQUALVERIFY OP_CHECKSIG")
        return cls(parse_script_data(script[2:-2]))

    @classmethod
    def from_address(cls, address: str, network: Network) -> Self:
        if network.p2pkh_version is None:
            raise ValueError("P2PKH not supported for this network")
        prefix_bytes = version_to_bytes(network.p2pkh_version)
        try:
            address_bytes = base58.b58check_decode(address)
            if not address_bytes.startswith(prefix_bytes):
                raise ValueError("Not a P2PKH address on this network")
            return cls(address_bytes[len(prefix_bytes) :])
        except ValueError as e:
            raise ValueError from e

    def to_scriptpubkey(self) -> bytes:
        return self.SCRIPT_PREFIX + build_op_push(self.pubkey_hash) + self.SCRIPT_SUFFIX

    def to_address(self, network: Network) -> str:
        if network.p2pkh_version is None:
            raise ValueError("P2PKH not supported for this network")
        prefix_bytes = version_to_bytes(network.p2pkh_version)
        return base58.b58check_encode(prefix_bytes + self.pubkey_hash)


@dataclass(frozen=True)
class P2SH(Script):
    script_hash: bytes

    SCRIPT_PREFIX = bytes([Opcode.OP_HASH160])
    SCRIPT_SUFFIX = bytes([Opcode.OP_EQUAL])

    def __post_init__(self) -> None:
        """Validate script hash."""
        if len(self.script_hash) != 20:
            raise ValueError("Invalid script hash length")

    @classmethod
    def from_script(cls, script: bytes) -> Self:
        return cls(utils.hash160(script))

    @classmethod
    def from_pubkey_p2wpkh(cls, pubkey: bytes) -> Self:
        assert pubkey[0] != 4, "uncompressed pubkey"
        return cls.from_script(P2WPKH.from_pubkey(pubkey).to_scriptpubkey())

    @classmethod
    def from_scriptpubkey(cls, script: bytes) -> Self:
        if len(script) != 23:
            raise ValueError("P2SH must be 23 bytes long")
        if script[:1] != cls.SCRIPT_PREFIX:
            raise ValueError("P2SH must start with OP_HASH160")
        if script[-1:] != cls.SCRIPT_SUFFIX:
            raise ValueError("P2SH must end with OP_EQUAL")
        return cls(parse_script_data(script[1:-1]))

    @classmethod
    def from_address(cls, address: str, network: Network) -> Self:
        if network.p2sh_version is None:
            raise ValueError("P2SH not supported for this network")
        prefix_bytes = version_to_bytes(network.p2sh_version)
        try:
            address_bytes = base58.b58check_decode(address)
            if not address_bytes.startswith(prefix_bytes):
                raise ValueError("Not a P2SH address on this network")
            return cls(address_bytes[len(prefix_bytes) :])
        except ValueError as e:
            raise ValueError from e

    def to_scriptpubkey(self) -> bytes:
        return self.SCRIPT_PREFIX + build_op_push(self.script_hash) + self.SCRIPT_SUFFIX

    def to_address(self, network: Network) -> str:
        if network.p2sh_version is None:
            raise ValueError("P2SH not supported for this network")
        prefix_bytes = version_to_bytes(network.p2sh_version)
        return base58.b58check_encode(prefix_bytes + self.script_hash)


@dataclass(frozen=True)
class P2WPKH(Script):
    pubkey_hash: bytes

    def __post_init__(self) -> None:
        """Validate public key hash."""
        if len(self.pubkey_hash) != 20:
            raise ValueError("Invalid public key hash length")

    @classmethod
    def from_pubkey(cls, pubkey: bytes) -> Self:
        assert pubkey[0] != 4, "uncompressed pubkey"
        return cls(utils.hash160(pubkey))

    @classmethod
    def from_scriptpubkey(cls, script: bytes) -> Self:
        if len(script) != 22:
            raise ValueError("P2WPKH must be 22 bytes long")
        if script[0] != Opcode.OP_0:
            raise ValueError("P2WPKH must start with OP_0 20")
        assert script[1] == 20
        return cls(parse_script_data(script[1:]))

    @classmethod
    def from_address(cls, address: str, network: Network) -> Self:
        if network.bech32_hrp is None:
            raise ValueError("P2WPKH not supported for this network")
        witver, witprog = bech32.decode(network.bech32_hrp, address)
        if witver != 0:
            raise ValueError("Invalid witness program version")
        return cls(witprog)

    def to_scriptpubkey(self) -> bytes:
        return bytes([Opcode.OP_0]) + build_op_push(self.pubkey_hash)

    def to_address(self, network: Network) -> str:
        if network.bech32_hrp is None:
            raise ValueError("P2WPKH not supported for this network")
        return bech32.encode(network.bech32_hrp, 0, self.pubkey_hash)


@dataclass(frozen=True)
class P2WSH(Script):
    script_hash: bytes

    WITNESS_VERSION = 0

    def __post_init__(self) -> None:
        """Validate script hash."""
        if len(self.script_hash) != 32:
            raise ValueError("Invalid script hash length")

    @classmethod
    def from_witness_script(cls, script: bytes) -> Self:
        return cls(sha256(script).digest())

    @classmethod
    def from_scriptpubkey(cls, script: bytes) -> Self:
        op_version = op_number(cls.WITNESS_VERSION)
        if len(script) != 34:
            raise ValueError(f"{cls.__name__} must be 34 bytes long")
        if script[0] != op_number(cls.WITNESS_VERSION):
            raise ValueError(f"{cls.__name__} must start with {op_version.name} 32")
        assert script[1] == 32
        return cls(parse_script_data(script[1:]))

    @classmethod
    def from_address(cls, address: str, network: Network) -> Self:
        if network.bech32_hrp is None:
            raise ValueError("P2WSH not supported for this network")
        witver, witprog = bech32.decode(network.bech32_hrp, address)
        if witver != cls.WITNESS_VERSION:
            raise ValueError("Invalid witness program version")
        return cls(witprog)

    def to_scriptpubkey(self) -> bytes:
        version_bytes = bytes([op_number(self.WITNESS_VERSION)])
        return version_bytes + build_op_push(self.script_hash)

    def to_address(self, network: Network) -> str:
        if network.bech32_hrp is None:
            raise ValueError("P2WSH not supported for this network")
        return bech32.encode(network.bech32_hrp, self.WITNESS_VERSION, self.script_hash)


class P2TR(P2WSH):
    """Pay to taproot.

    This is encoded the same way as a P2WSH script, except witness version
    is set to 1.
    """

    WITNESS_VERSION = 1


ALL_SCRIPTS = (P2PK, P2PKH, P2SH, P2WPKH, P2WSH, P2TR, OpReturn, Unknown)


def from_scriptpubkey(script_pubkey: bytes) -> Script:
    """Identify scriptPubKey and parse to the appropriate script subclass."""
    for cls in ALL_SCRIPTS:
        try:
            return cls.from_scriptpubkey(script_pubkey)
        except ValueError:
            pass
    # as long as the last script type is Unknown, we should never reach the end
    # of the for loop, because Unknown can parse any script type
    raise RuntimeError("This should not happen.")


def from_address(address: str, network: Network) -> Script:
    """Identify an address and parse to the appropriate script subclass."""
    for cls in ALL_SCRIPTS:
        try:
            return cls.from_address(address, network)
        except ValueError:
            pass
    # as long as the last script type is Unknown, we should never reach the end
    # of the for loop, because Unknown can parse any script type
    raise RuntimeError("This should not happen.")
