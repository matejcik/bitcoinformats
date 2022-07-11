import pytest

from bitcoinformats import bech32, opcodes
from bitcoinformats.bech32 import Encoding

# fmt: off
VECTORS_VALID = (
    (Encoding.BECH32, "A12UEL5L"),
    (Encoding.BECH32, "a12uel5l"),
    (Encoding.BECH32, "an83characterlonghumanreadablepartthatcontainsthenumber1andtheexcludedcharactersbio1tt5tgs"),
    (Encoding.BECH32, "abcdef1qpzry9x8gf2tvdw0s3jn54khce6mua7lmqqqxw"),
    (Encoding.BECH32, "11qqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqc8247j"),
    (Encoding.BECH32, "split1checkupstagehandshakeupstreamerranterredcaperred2y9e3w"),
    (Encoding.BECH32, "?1ezyfcl"),
    (Encoding.BECH32M, "A1LQFN3A"),
    (Encoding.BECH32M, "a1lqfn3a"),
    (Encoding.BECH32M, "an83characterlonghumanreadablepartthatcontainsthetheexcludedcharactersbioandnumber11sg7hg6"),
    (Encoding.BECH32M, "abcdef1l7aum6echk45nj3s0wdvt2fg8x9yrzpqzd3ryx"),
    (Encoding.BECH32M, "11llllllllllllllllllllllllllllllllllllllllllllllllllllllllllllllllllllllllllllllllllludsr8"),
    (Encoding.BECH32M, "split1checkupstagehandshakeupstreamerranterredcaperredlc445v"),
    (Encoding.BECH32M, "?1v759aa"),
)
# fmt: on

VECTORS_INVALID = (
    "\x201nwldj5",  # HRP character out of range
    "\x7f1axkwrx",  # HRP character out of range
    "\x801eym55h",  # HRP character out of range
    # "an84characterslonghumanreadablepartthatcontainsthenumber1andtheexcludedcharactersbio1569pvx": overall max length exceeded
    "pzry9x0s0muk",  # No separator character
    "1pzry9x0s0muk",  # Empty HRP
    "x1b4n0q5v",  # Invalid data character
    "li1dgmt3",  # Too short checksum
    "de1lg7wt\xff",  # Invalid character in checksum
    "A1G7SGD8",  # checksum calculated with uppercase form of HRP
)

VECTORS_ADDRESS_VALID = (
    (
        "bc",
        "BC1QW508D6QEJXTDG4Y5R3ZARVARY0C5XW7KV8F3T4",
        "0014751e76e8199196d454941c45d1b3a323f1433bd6",
    ),
    (
        "tb",
        "tb1qrp33g0q5c5txsp9arysrx4k6zdkfs4nce4xj0gdcccefvpysxf3q0sl5k7",
        "00201863143c14c5166804bd19203356da136c985678cd4d27a1b8c6329604903262",
    ),
    (
        "bc",
        "bc1pw508d6qejxtdg4y5r3zarvary0c5xw7kw508d6qejxtdg4y5r3zarvary0c5xw7kt5nd6y",
        "5128751e76e8199196d454941c45d1b3a323f1433bd6751e76e8199196d454941c45d1b3a323f1433bd6",
    ),
    ("bc", "BC1SW50QGDZ25J", "6002751e"),
    (
        "bc",
        "bc1zw508d6qejxtdg4y5r3zarvaryvaxxpcs",
        "5210751e76e8199196d454941c45d1b3a323",
    ),
    (
        "tb",
        "tb1qqqqqp399et2xygdj5xreqhjjvcmzhxw4aywxecjdzew6hylgvsesrxh6hy",
        "0020000000c4a5cad46221b2a187905e5266362b99d5e91c6ce24d165dab93e86433",
    ),
    (
        "tb",
        "tb1pqqqqp399et2xygdj5xreqhjjvcmzhxw4aywxecjdzew6hylgvsesf3hn0c",
        "5120000000c4a5cad46221b2a187905e5266362b99d5e91c6ce24d165dab93e86433",
    ),
    (
        "bc",
        "bc1p0xlxvlhemja6c4dqv22uapctqupfhlxm9h8z3k2e72q4k9hcz7vqzk5jj0",
        "512079be667ef9dcbbac55a06295ce870b07029bfcdb2dce28d959f2815b16f81798",
    ),
)

VECTORS_ADDRESS_INVALID = (
    (
        "bc",
        "tb1qqqqqp399et2xygdj5xreqhjjvcmzhxw4aywxecjdzew6hylgvsesrxh6hy",
    ),  # HRP mismatch
    (
        "bc",
        "tc1qw508d6qejxtdg4y5r3zarvary0c5xw7kg3g4ty",
    ),  # Invalid human-readable part
    ("bc", "bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t5"),  # Invalid checksum
    ("bc", "BC13W508D6QEJXTDG4Y5R3ZARVARY0C5XW7KN40WF2"),  # Invalid witness version
    ("bc", "bc1rw5uspcuh"),  # Invalid program length
    (
        "bc",
        "bc10w508d6qejxtdg4y5r3zarvary0c5xw7kw508d6qejxtdg4y5r3zarvary0c5xw7kw5rljs90",
    ),  # Invalid program length
    (
        "bc",
        "BC1QR508D6QEJXTDG4Y5R3ZARVARYV98GJ9P",
    ),  # Invalid program length for witness version 0 (per BIP141)
    (
        "tb",
        "tb1qrp33g0q5c5txsp9arysrx4k6zdkfs4nce4xj0gdcccefvpysxf3q0sL5k7",
    ),  # Mixed case
    (
        "bc",
        "bc1zw508d6qejxtdg4y5r3zarvaryvqyzf3du",
    ),  # zero padding of more than 4 bits
    (
        "tb",
        "tb1qrp33g0q5c5txsp9arysrx4k6zdkfs4nce4xj0gdcccefvpysxf3pjxtptv",
    ),  # Non-zero padding in 8-to-5 conversion
    ("bc", "bc1gmk9yu"),  # Empty data section
    (
        "bc",
        "bc1p0xlxvlhemja6c4dqv22uapctqupfhlxm9h8z3k2e72q4k9hcz7vqh2y7hd",
    ),  # invalid checksum - bech32 instead of bech32m
    (
        "bc",
        "bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kemeawh",
    ),  # invalid checksum - bech32m instead of bech32
    (
        "bc",
        "BC130XLXVLHEMJA6C4DQV22UAPCTQUPFHLXM9H8Z3K2E72Q4K9HCZ7VQ7ZWS8R",
    ),  # invalid witness version
)


@pytest.mark.parametrize("encoding, string", VECTORS_VALID)
def test_valid_bech32(encoding, string):
    _, _, encoding_got = bech32.bech32_decode(string)
    assert encoding == encoding_got


@pytest.mark.parametrize("string", VECTORS_INVALID)
def test_invalid_bech23(string):
    with pytest.raises(ValueError):
        bech32.bech32_decode(string)


@pytest.mark.parametrize("hrp, string, pubkey", VECTORS_ADDRESS_VALID)
def test_valid_address(hrp, string, pubkey):
    version, data = bech32.decode(hrp, string)
    assert 0 <= version <= 16
    script_pubkey = bytes([opcodes.op_number(version)]) + opcodes.build_op_push(data)
    assert script_pubkey == bytes.fromhex(pubkey)


@pytest.mark.parametrize("hrp, string", VECTORS_ADDRESS_INVALID)
def test_invalid_address(hrp, string):
    with pytest.raises(ValueError):
        bech32.decode(hrp, string)
