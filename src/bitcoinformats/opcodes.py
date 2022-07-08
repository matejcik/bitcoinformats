from __future__ import annotations

import struct
from enum import IntEnum


class Opcode(IntEnum):
    # push value
    OP_0 = 0x00
    OP_FALSE = OP_0
    OP_PUSHDATA1 = 0x4C
    OP_PUSHDATA2 = 0x4D
    OP_PUSHDATA4 = 0x4E
    OP_1NEGATE = 0x4F
    OP_RESERVED = 0x50
    OP_1 = 0x51
    OP_TRUE = OP_1
    OP_2 = 0x52
    OP_3 = 0x53
    OP_4 = 0x54
    OP_5 = 0x55
    OP_6 = 0x56
    OP_7 = 0x57
    OP_8 = 0x58
    OP_9 = 0x59
    OP_10 = 0x5A
    OP_11 = 0x5B
    OP_12 = 0x5C
    OP_13 = 0x5D
    OP_14 = 0x5E
    OP_15 = 0x5F
    OP_16 = 0x60

    # control
    OP_NOP = 0x61
    OP_VER = 0x62
    OP_IF = 0x63
    OP_NOTIF = 0x64
    OP_VERIF = 0x65
    OP_VERNOTIF = 0x66
    OP_ELSE = 0x67
    OP_ENDIF = 0x68
    OP_VERIFY = 0x69
    OP_RETURN = 0x6A

    # stack ops
    OP_TOALTSTACK = 0x6B
    OP_FROMALTSTACK = 0x6C
    OP_2DROP = 0x6D
    OP_2DUP = 0x6E
    OP_3DUP = 0x6F
    OP_2OVER = 0x70
    OP_2ROT = 0x71
    OP_2SWAP = 0x72
    OP_IFDUP = 0x73
    OP_DEPTH = 0x74
    OP_DROP = 0x75
    OP_DUP = 0x76
    OP_NIP = 0x77
    OP_OVER = 0x78
    OP_PICK = 0x79
    OP_ROLL = 0x7A
    OP_ROT = 0x7B
    OP_SWAP = 0x7C
    OP_TUCK = 0x7D

    # splice ops
    OP_CAT = 0x7E
    OP_SUBSTR = 0x7F
    OP_LEFT = 0x80
    OP_RIGHT = 0x81
    OP_SIZE = 0x82

    # bit logic
    OP_INVERT = 0x83
    OP_AND = 0x84
    OP_OR = 0x85
    OP_XOR = 0x86
    OP_EQUAL = 0x87
    OP_EQUALVERIFY = 0x88
    OP_RESERVED1 = 0x89
    OP_RESERVED2 = 0x8A

    # numeric
    OP_1ADD = 0x8B
    OP_1SUB = 0x8C
    OP_2MUL = 0x8D
    OP_2DIV = 0x8E
    OP_NEGATE = 0x8F
    OP_ABS = 0x90
    OP_NOT = 0x91
    OP_0NOTEQUAL = 0x92

    OP_ADD = 0x93
    OP_SUB = 0x94
    OP_MUL = 0x95
    OP_DIV = 0x96
    OP_MOD = 0x97
    OP_LSHIFT = 0x98
    OP_RSHIFT = 0x99

    OP_BOOLAND = 0x9A
    OP_BOOLOR = 0x9B
    OP_NUMEQUAL = 0x9C
    OP_NUMEQUALVERIFY = 0x9D
    OP_NUMNOTEQUAL = 0x9E
    OP_LESSTHAN = 0x9F
    OP_GREATERTHAN = 0xA0
    OP_LESSTHANOREQUAL = 0xA1
    OP_GREATERTHANOREQUAL = 0xA2
    OP_MIN = 0xA3
    OP_MAX = 0xA4

    OP_WITHIN = 0xA5

    # crypto
    OP_RIPEMD160 = 0xA6
    OP_SHA1 = 0xA7
    OP_SHA256 = 0xA8
    OP_HASH160 = 0xA9
    OP_HASH256 = 0xAA
    OP_CODESEPARATOR = 0xAB
    OP_CHECKSIG = 0xAC
    OP_CHECKSIGVERIFY = 0xAD
    OP_CHECKMULTISIG = 0xAE
    OP_CHECKMULTISIGVERIFY = 0xAF

    # expansion
    OP_NOP1 = 0xB0
    OP_NOP2 = 0xB1
    OP_CHECKLOCKTIMEVERIFY = OP_NOP2
    OP_NOP3 = 0xB2
    OP_CHECKSEQUENCEVERIFY = OP_NOP3
    OP_NOP4 = 0xB3
    OP_NOP5 = 0xB4
    OP_NOP6 = 0xB5
    OP_NOP7 = 0xB6
    OP_NOP8 = 0xB7
    OP_NOP9 = 0xB8
    OP_NOP10 = 0xB9

    # template matching params
    OP_SMALLINTEGER = 0xFA
    OP_PUBKEYS = 0xFB
    OP_PUBKEYHASH = 0xFD
    OP_PUBKEY = 0xFE

    OP_INVALIDOPCODE = 0xFF


def op_push(datalen: int) -> bytes:
    """Generate OP_PUSH instruction and length of the appropriate size."""
    if datalen < Opcode.OP_PUSHDATA1:
        return struct.pack("<B", datalen)
    if datalen <= 0xFF:
        return struct.pack("<BB", Opcode.OP_PUSHDATA1, datalen)
    if datalen <= 0xFFFF:
        return struct.pack("<BS", Opcode.OP_PUSHDATA2, datalen)
    if datalen <= 0xFFFF_FFFF:
        return struct.pack("<BL", Opcode.OP_PUSHDATA4, datalen)

    raise ValueError("data too big for OP_PUSH")


def op_number(n: int) -> Opcode:
    if n == 0:
        return Opcode.OP_0
    if 1 <= n <= 16:
        opcode = Opcode.OP_1 + n - 1
        return Opcode(opcode)
    if n == -1:
        return Opcode.OP_1NEGATE
    raise ValueError("invalid OP_number")


def build_op_push(data: bytes) -> bytes:
    """Build an OP_PUSHed data by prefixing it with the appropriate OP_PUSH instruction."""
    return op_push(len(data)) + data


def extract_op_push(data: bytes) -> bytes:
    """Extract the data from an OP_PUSHed block."""
    if not data:
        raise ValueError("empty data")
    header = data[0]
    if header < Opcode.OP_PUSHDATA1:
        data_len = header
        offset = 1
    elif header == Opcode.OP_PUSHDATA1 and len(data) > 2:
        data_len = data[1]
        offset = 2
    elif header == Opcode.OP_PUSHDATA2 and len(data) > 3:
        data_len = int.from_bytes(data[1:3], "little")
        offset = 3
    elif header == Opcode.OP_PUSHDATA4 and len(data) > 5:
        data_len = int.from_bytes(data[1:5], "little")
        offset = 5
    else:
        raise ValueError("Invalid OP_PUSH header")

    if len(data) != offset + data_len:
        raise ValueError("Invalid OP_PUSH length")

    return data[offset:]
