"""Aylık rapor ve dışa aktarım: kategori toplamları, yüzdeler, genel toplam, CSV.

Hesaplar tamsayı kuruş üzerinden yapılır; yüzdeler Decimal ile iki ondalığa
yarım-yukarı yuvarlanır.
"""

import csv
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import List, Optional

from harcama_takip.veri import Depo, Harcama, HarcamaHatasi, ay_dogrula

DESTEKLENEN_BICIMLER = ("csv",)
CSV_BASLIKLARI = ["id", "tarih", "kategori", "tutar", "aciklama"]

_IKI_ONDALIK = Decimal("0.01")


def kurus_metni(kurus: int) -> str:
    """Kuruşu '150.50' biçiminde metne çevirir."""
    isaret = "-" if kurus < 0 else ""
    kurus = abs(kurus)
    return "{}{}.{:02d}".format(isaret, kurus // 100, kurus % 100)


def yuzde_hesapla(parca_kurus: int, toplam_kurus: int) -> Decimal:
    """Parçanın toplama oranını iki ondalıklı yüzde olarak döndürür."""
    if toplam_kurus <= 0:
        return Decimal("0.00")
    oran = Decimal(parca_kurus) * 100 / Decimal(toplam_kurus)
    return oran.quantize(_IKI_ONDALIK, rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class KategoriSatiri:
    kategori: str
    toplam_kurus: int
    yuzde: Decimal

    @property
    def toplam(self) -> Decimal:
        return Decimal(self.toplam_kurus) / Decimal(100)


@dataclass(frozen=True)
class AylikRapor:
    ay: str
    satirlar: List[KategoriSatiri]
    genel_toplam_kurus: int

    @property
    def genel_toplam(self) -> Decimal:
        return Decimal(self.genel_toplam_kurus) / Decimal(100)


def aylik_rapor(depo: Depo, ay: str) -> AylikRapor:
    """Verilen ay için kategori bazında toplam ve yüzdeleri hesaplar."""
    ay = ay_dogrula(ay)
    toplamlar = depo.kategori_toplamlari(ay)
    genel = sum(toplam for _, toplam in toplamlar)
    satirlar = [
        KategoriSatiri(kategori, toplam, yuzde_hesapla(toplam, genel))
        for kategori, toplam in toplamlar
    ]
    return AylikRapor(ay, satirlar, genel)


def rapor_metni(rapor: AylikRapor) -> str:
    """Raporu terminalde gösterilecek tablo metnine çevirir."""
    if not rapor.satirlar:
        return "{} ayında harcama yok.".format(rapor.ay)
    genislik = max(len("Kategori"), len("GENEL TOPLAM"), *(len(s.kategori) for s in rapor.satirlar))
    satirlar = [
        "{} ayı harcama raporu".format(rapor.ay),
        "{:<{g}}  {:>12}  {:>7}".format("Kategori", "Tutar", "Yüzde", g=genislik),
    ]
    for s in rapor.satirlar:
        satirlar.append(
            "{:<{g}}  {:>12}  {:>6}%".format(
                s.kategori, kurus_metni(s.toplam_kurus), str(s.yuzde), g=genislik
            )
        )
    satirlar.append(
        "{:<{g}}  {:>12}  {:>6}%".format(
            "GENEL TOPLAM", kurus_metni(rapor.genel_toplam_kurus), "100.00", g=genislik
        )
    )
    return "\n".join(satirlar)


def liste_metni(harcamalar: List[Harcama]) -> str:
    """Harcama listesini terminalde gösterilecek tablo metnine çevirir."""
    if not harcamalar:
        return "Kayıt bulunamadı."
    id_g = max(len("ID"), *(len(str(h.id)) for h in harcamalar))
    kat_g = max(len("Kategori"), *(len(h.kategori) for h in harcamalar))
    satirlar = [
        "{:>{i}}  {:<10}  {:<{k}}  {:>12}  {}".format(
            "ID", "Tarih", "Kategori", "Tutar", "Açıklama", i=id_g, k=kat_g
        )
    ]
    for h in harcamalar:
        satirlar.append(
            "{:>{i}}  {:<10}  {:<{k}}  {:>12}  {}".format(
                h.id, h.tarih, h.kategori, kurus_metni(h.tutar_kurus), h.aciklama, i=id_g, k=kat_g
            ).rstrip()
        )
    toplam = sum(h.tutar_kurus for h in harcamalar)
    satirlar.append("Toplam: {} ({} kayıt)".format(kurus_metni(toplam), len(harcamalar)))
    return "\n".join(satirlar)


def disa_aktar(
    depo: Depo,
    dosya: str,
    bicim: str = "csv",
    ay: Optional[str] = None,
    kategori: Optional[str] = None,
) -> int:
    """Harcamaları dosyaya yazar; yazılan kayıt sayısını döndürür."""
    bicim = (bicim or "").strip().lower()
    if bicim not in DESTEKLENEN_BICIMLER:
        raise HarcamaHatasi(
            "Desteklenmeyen biçim: '{}'. Desteklenenler: {}.".format(
                bicim, ", ".join(DESTEKLENEN_BICIMLER)
            )
        )
    if not dosya or not str(dosya).strip():
        raise HarcamaHatasi("Dışa aktarım için dosya yolu verilmelidir.")
    harcamalar = depo.listele(ay=ay, kategori=kategori)
    try:
        with open(dosya, "w", newline="", encoding="utf-8") as f:
            yazici = csv.writer(f)
            yazici.writerow(CSV_BASLIKLARI)
            for h in harcamalar:
                yazici.writerow([h.id, h.tarih, h.kategori, kurus_metni(h.tutar_kurus), h.aciklama])
    except OSError as hata:
        raise HarcamaHatasi("Dosyaya yazılamadı: '{}' ({}).".format(dosya, hata.strerror or hata))
    return len(harcamalar)
