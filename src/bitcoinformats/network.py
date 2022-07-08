from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Network:
    p2pkh_version: int | None
    p2sh_version: int | None
    bech32_hrp: str | None

    xpub_version: int | None
    xprv_version: int | None


Bitcoin = Network(
    p2pkh_version=0,
    p2sh_version=5,
    bech32_hrp="bc",
    xpub_version=0x0488_B21E,
    xprv_version=0x0488_ADE4,
)

BitcoinTestnet = Network(
    p2pkh_version=111,
    p2sh_version=196,
    bech32_hrp="tb",
    xpub_version=0x0435_87CF,
    xprv_version=0x0435_8394,
)
