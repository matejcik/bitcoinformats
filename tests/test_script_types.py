import pytest

from bitcoinformats import network, script_type

ROUNDTRIP_VECTORS = (  # script class, attribute name, attribute value
    (script_type.P2PK, "pubkey", b"\x00" * 33),
    (script_type.P2PKH, "pubkey_hash", b"\x00" * 20),
    (script_type.P2SH, "script_hash", b"\x00" * 20),
    (script_type.P2WPKH, "pubkey_hash", b"\x00" * 20),
    (script_type.P2WSH, "script_hash", b"\x00" * 32),
    (script_type.P2TR, "script_hash", b"\x00" * 32),
    (script_type.OpReturn, "data", b"\x00" * 80),
)


@pytest.mark.parametrize(
    "script_class, attr_name, value",
    ROUNDTRIP_VECTORS,
    ids=(cls.__name__ for cls, _, _ in ROUNDTRIP_VECTORS),
)
def test_roundtrip(script_class, attr_name, value):
    script = script_class(value)
    spk = script.to_scriptpubkey()
    roundtrip = script_class.from_scriptpubkey(spk)
    assert roundtrip == script
    assert getattr(roundtrip, attr_name) == value


@pytest.mark.parametrize(
    "script_class, attr_name, value",
    ROUNDTRIP_VECTORS,
    ids=(cls.__name__ for cls, _, _ in ROUNDTRIP_VECTORS),
)
def test_roundtrip_address(script_class, attr_name, value):
    script = script_class(value)
    try:
        address = script.to_address(network.Bitcoin)
    except ValueError:
        pytest.skip("Address not supported")
    roundtrip = script_class.from_address(address, network.Bitcoin)
    assert roundtrip == script
    assert getattr(roundtrip, attr_name) == value


@pytest.mark.parametrize(
    "script_class, attr_name, value",
    ROUNDTRIP_VECTORS,
    ids=(cls.__name__ for cls, _, _ in ROUNDTRIP_VECTORS),
)
def test_parse_generic(script_class, attr_name, value):
    script = script_class(value)
    spk = script.to_scriptpubkey()
    roundtrip = script_type.from_scriptpubkey(spk)
    assert isinstance(roundtrip, script_class)
    assert roundtrip == script
    assert getattr(roundtrip, attr_name) == value


@pytest.mark.parametrize(
    "script_class, attr_name, value",
    ROUNDTRIP_VECTORS,
    ids=(cls.__name__ for cls, _, _ in ROUNDTRIP_VECTORS),
)
def test_parse_address_generic(script_class, attr_name, value):
    script = script_class(value)
    try:
        address = script.to_address(network.Bitcoin)
    except ValueError:
        pytest.skip("Address not supported")

    roundtrip = script_type.from_address(address, network.Bitcoin)
    assert isinstance(roundtrip, script_class)
    assert roundtrip == script
    assert getattr(roundtrip, attr_name) == value


@pytest.mark.parametrize(
    "data", (b"", b"\x00", b"\x00\x00", b"\x00\x00\x00", b"hello" * 10)
)
def test_op_return(data):
    script = script_type.OpReturn(data)
    spk = script.to_scriptpubkey()
    roundtrip = script_type.OpReturn.from_scriptpubkey(spk)
    assert roundtrip == script
    assert roundtrip.data == data
