"""Aylık rapor: kategori bazında toplamlar, yüzdeler ve genel toplam.

Tüm toplamlar tamsayı kuruş üzerinde yapılır; yüzdeler Decimal ile hesaplanır.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Optional

from harcama_takip.veri import Veritabani, ay_dogrula, kurus_metni


@dataclass(frozen=True)
class KategoriSatiri:
    kategori: str
    tutar_kurus: int
    yuzde: Decimal


@dataclass(frozen=True)
class AylikRapor:
    ay: str
    satirlar: list[KategoriSatiri]
    genel_toplam_kurus: int


def yuzde_hesapla(parca_kurus: int, toplam_kurus: int) -> Decimal:
    """parca / toplam oranını yüzde olarak, iki ondalık basamakla döndürür."""
    if toplam_kurus == 0:
        return Decimal("0.00")
    oran = Decimal(parca_kurus) * Decimal(100) / Decimal(toplam_kurus)
    return oran.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def aylik_rapor(veritabani: Veritabani, ay: Optional[str]) -> AylikRapor:
    ay_d = ay_dogrula(ay)
    if ay_d is None:
        raise ValueError("aylik_rapor için ay zorunludur.")
    kayitlar = veritabani.listele(ay=ay_d)

    toplamlar: dict[str, int] = {}
    for k in kayitlar:
        toplamlar[k.kategori] = toplamlar.get(k.kategori, 0) + k.tutar_kurus

    genel = sum(toplamlar.values())
    satirlar = [
        KategoriSatiri(kat, tutar, yuzde_hesapla(tutar, genel))
        for kat, tutar in sorted(toplamlar.items(), key=lambda p: (-p[1], p[0]))
    ]
    return AylikRapor(ay=ay_d, satirlar=satirlar, genel_toplam_kurus=genel)


def rapor_metni(rapor: AylikRapor) -> str:
    satirlar = [f"Aylık rapor: {rapor.ay}"]
    if not rapor.satirlar:
        satirlar.append("Bu ayda kayıt bulunamadı.")
        satirlar.append(f"Genel toplam: {kurus_metni(0)} TL")
        return "\n".join(satirlar)

    satirlar.append(f"{'kategori':<15}  {'tutar (TL)':>12}  {'yüzde':>7}")
    for s in rapor.satirlar:
        satirlar.append(
            f"{s.kategori:<15}  {kurus_metni(s.tutar_kurus):>12}  {s.yuzde:>6}%"
        )
    satirlar.append(f"Genel toplam: {kurus_metni(rapor.genel_toplam_kurus)} TL")
    return "\n".join(satirlar)
