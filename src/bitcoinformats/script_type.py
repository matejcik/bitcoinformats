from dataclasses import dataclass
from enum import Enum
from typing_extensions import Protocol, Self

from construct import ConstructError

from .opcodes import Opcode, build_op_push, extract_op_push


class ScriptError(Exception):
    pass


def parse_script_data(data: bytes) -> bytes:
    """Parse length-prefixed data in a Bitcoin script."""
    try:
        return extract_op_push(data)
    except ValueError as e:
        raise ScriptError from e


class Script(Protocol):
    @classmethod
    def parse_script_pubkey(cls, script: bytes) -> Self:
        ...

    def compile_script_pubkey(self) -> bytes:
        ...


@dataclass(frozen=True)
class Unknown(Script):
    script: bytes

    @classmethod
    def parse_script_pubkey(cls, script: bytes) -> Self:
        return cls(script)

    def compile_script_pubkey(self) -> bytes:
        return self.script


@dataclass(frozen=True)
class OpReturn(Script):
    data: bytes

    @classmethod
    def parse_script_pubkey(cls, script: bytes) -> Self:
        if script[0] != Opcode.OP_RETURN:
            raise ScriptError("OpReturn must start with OP_RETURN")
        return cls(parse_script_data(script[1:]))

    def compile_script_pubkey(self) -> bytes:
        return bytes([Opcode.OP_RETURN]) + build_op_push(self.data)


@dataclass(frozen=True)
class P2PK(Script):
    pubkey: bytes

    @classmethod
    def parse_script_pubkey(cls, script: bytes) -> Self:
        if len(script) != 35:
            raise ScriptError("P2PK must be 35 bytes long")
        if script[-1] != Opcode.OP_CHECKSIG:
            raise ScriptError("P2PK must end with OP_CHECKSIG")
        return cls(parse_script_data(script[:34]))

    def compile_script_pubkey(self) -> bytes:
        return build_op_push(self.pubkey) + bytes([Opcode.OP_CHECKSIG])


@dataclass(frozen=True)
class P2PKH(Script):
    pubkey_hash: bytes

    SCRIPT_PREFIX = bytes([Opcode.OP_DUP, Opcode.OP_HASH160])
    SCRIPT_SUFFIX = bytes([Opcode.OP_EQUALVERIFY, Opcode.OP_CHECKSIG])

    @classmethod
    def parse_script_pubkey(cls, script: bytes) -> Self:
        if len(script) != 25:
            raise ScriptError("P2PKH must be 25 bytes long")
        if script[:2] != cls.SCRIPT_PREFIX:
            raise ScriptError("P2PKH must start with OP_DUP OP_HASH160")
        if script[-2:] != cls.SCRIPT_SUFFIX:
            raise ScriptError("P2PKH must end with OP_EQUALVERIFY OP_CHECKSIG")
        return cls(parse_script_data(script[2:-2]))

    def compile_script_pubkey(self) -> bytes:
        return self.SCRIPT_PREFIX + build_op_push(self.pubkey_hash) + self.SCRIPT_SUFFIX


@dataclass(frozen=True)
class P2SH(Script):
    script_hash: bytes

    SCRIPT_PREFIX = bytes([Opcode.OP_HASH160])
    SCRIPT_SUFFIX = bytes([Opcode.OP_EQUAL])

    @classmethod
    def parse_script_pubkey(cls, script: bytes) -> Self:
        if len(script) != 23:
            raise ScriptError("P2SH must be 23 bytes long")
        if script[:1] != cls.SCRIPT_PREFIX:
            raise ScriptError("P2SH must start with OP_HASH160")
        if script[-1] != cls.SCRIPT_SUFFIX:
            raise ScriptError("P2SH must end with OP_EQUAL")
        return cls(parse_script_data(script[1:-1]))

    def compile_script_pubkey(self) -> bytes:
        return self.SCRIPT_PREFIX + build_op_push(self.script_hash) + self.SCRIPT_SUFFIX


@dataclass(frozen=True)
class P2WPKH(Script):
    pubkey_hash: bytes

    @classmethod
    def parse_script_pubkey(cls, script: bytes) -> Self:
        if len(script) != 22:
            raise ScriptError("P2WPKH must be 22 bytes long")
        if script[0] != Opcode.OP_0:
            raise ScriptError("P2WPKH must start with OP_0 20")
        assert script[1] == 20
        return cls(parse_script_data(script[1:]))

    def compile_script_pubkey(self) -> bytes:
        return bytes([Opcode.OP_0]) + build_op_push(self.pubkey_hash)


@dataclass(frozen=True)
class P2WSH(Script):
    script_hash: bytes

    @classmethod
    def parse_script_pubkey(cls, script: bytes) -> Self:
        if len(script) != 34:
            raise ScriptError("P2WSH must be 34 bytes long")
        if script[0] != Opcode.OP_0:
            raise ScriptError("P2WSH must start with OP_0 32")
        assert script[1] == 32
        return cls(parse_script_data(script[1:]))

    def compile_script_pubkey(self) -> bytes:
        return bytes([Opcode.OP_0]) + build_op_push(self.script_hash)


class ScriptType(Enum):
    UNKNOWN = None
    OP_RETURN = "op_return"
    P2PK = "p2pk"
    P2PKH = "p2pkh"
    P2SH = "p2sh"
    P2WPKH = "p2wpkh"
    P2WSH = "p2wsh"
    P2SH_P2WPKH = "p2sh_p2wpkh"
    P2SH_P2WSH = "p2sh_p2wsh"
