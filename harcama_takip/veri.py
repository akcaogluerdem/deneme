"""SQLite veri katmanı: harcama ekleme, listeleme, filtreleme ve silme.

Tutarlar veritabanında tamsayı kuruş olarak saklanır; girişte Decimal ile
ayrıştırılır, böylece kayan nokta yuvarlama hataları oluşmaz.
"""

import datetime
import os
import re
import sqlite3
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import List, Optional, Tuple, Union

DB_ORTAM_DEGISKENI = "HARCAMA_TAKIP_DB"
VARSAYILAN_DB_ADI = ".harcama_takip.db"

_AY_DESENI = re.compile(r"^\d{4}-\d{2}$")
_TARIH_DESENI = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class HarcamaHatasi(ValueError):
    """Kullanıcıya gösterilecek Türkçe hata mesajı taşıyan temel hata."""


class HarcamaBulunamadi(HarcamaHatasi):
    """Verilen kimlikte harcama yok."""


@dataclass(frozen=True)
class Harcama:
    id: int
    tutar_kurus: int
    kategori: str
    tarih: str
    aciklama: str

    @property
    def tutar(self) -> Decimal:
        return Decimal(self.tutar_kurus) / Decimal(100)


def tutar_ayristir(deger: Union[str, int, Decimal]) -> int:
    """Tutarı kuruşa çevirir; sıfır, negatif ya da geçersiz tutarı reddeder."""
    if isinstance(deger, float):
        deger = repr(deger)
    metin = str(deger).strip().replace(",", ".")
    try:
        sayi = Decimal(metin)
    except InvalidOperation:
        raise HarcamaHatasi("Geçersiz tutar: '{}'. Sayı girmelisiniz (örn. 150.50).".format(deger))
    if not sayi.is_finite():
        raise HarcamaHatasi("Geçersiz tutar: '{}'. Sayı girmelisiniz (örn. 150.50).".format(deger))
    if sayi <= 0:
        raise HarcamaHatasi("Tutar sıfırdan büyük olmalıdır: {}".format(deger))
    kurus = sayi * 100
    if kurus != kurus.to_integral_value():
        raise HarcamaHatasi("Tutar en fazla iki ondalık basamak içerebilir: {}".format(deger))
    return int(kurus)


def tarih_dogrula(deger: Optional[str]) -> str:
    """YYYY-AA-GG biçimindeki tarihi doğrular; boşsa bugünü döndürür."""
    if deger is None or str(deger).strip() == "":
        return datetime.date.today().isoformat()
    metin = str(deger).strip()
    if not _TARIH_DESENI.match(metin):
        raise HarcamaHatasi("Geçersiz tarih: '{}'. Biçim YYYY-AA-GG olmalıdır.".format(deger))
    try:
        return datetime.date.fromisoformat(metin).isoformat()
    except ValueError:
        raise HarcamaHatasi("Geçersiz tarih: '{}'. Böyle bir gün yok.".format(deger))


def ay_dogrula(deger: str) -> str:
    """YYYY-AA biçimindeki ayı doğrular."""
    metin = str(deger).strip()
    if not _AY_DESENI.match(metin):
        raise HarcamaHatasi("Geçersiz ay: '{}'. Biçim YYYY-AA olmalıdır.".format(deger))
    ay = int(metin[5:7])
    if not 1 <= ay <= 12:
        raise HarcamaHatasi("Geçersiz ay: '{}'. Ay 01 ile 12 arasında olmalıdır.".format(deger))
    return metin


def kategori_dogrula(deger: Optional[str]) -> str:
    metin = (deger or "").strip()
    if not metin:
        raise HarcamaHatasi("Kategori boş olamaz.")
    return metin


def varsayilan_db_yolu() -> str:
    """HARCAMA_TAKIP_DB ayarlıysa onu, değilse ev dizinindeki dosyayı döndürür."""
    yol = os.environ.get(DB_ORTAM_DEGISKENI)
    if yol:
        return yol
    return os.path.join(os.path.expanduser("~"), VARSAYILAN_DB_ADI)


class Depo:
    """Harcamaları SQLite veritabanında tutan depo."""

    def __init__(self, yol: Optional[str] = None):
        self.yol = yol or varsayilan_db_yolu()
        self._baglanti = sqlite3.connect(self.yol)
        self._baglanti.execute(
            """
            CREATE TABLE IF NOT EXISTS harcamalar (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tutar_kurus INTEGER NOT NULL CHECK (tutar_kurus > 0),
                kategori TEXT NOT NULL,
                tarih TEXT NOT NULL,
                aciklama TEXT NOT NULL DEFAULT ''
            )
            """
        )
        self._baglanti.commit()

    def kapat(self) -> None:
        self._baglanti.close()

    def __enter__(self) -> "Depo":
        return self

    def __exit__(self, *_) -> None:
        self.kapat()

    def ekle(
        self,
        tutar: Union[str, int, Decimal],
        kategori: str,
        tarih: Optional[str] = None,
        aciklama: Optional[str] = None,
    ) -> Harcama:
        tutar_kurus = tutar_ayristir(tutar)
        kategori = kategori_dogrula(kategori)
        tarih = tarih_dogrula(tarih)
        aciklama = (aciklama or "").strip()
        imlec = self._baglanti.execute(
            "INSERT INTO harcamalar (tutar_kurus, kategori, tarih, aciklama) VALUES (?, ?, ?, ?)",
            (tutar_kurus, kategori, tarih, aciklama),
        )
        self._baglanti.commit()
        return Harcama(imlec.lastrowid, tutar_kurus, kategori, tarih, aciklama)

    def listele(self, ay: Optional[str] = None, kategori: Optional[str] = None) -> List[Harcama]:
        kosullar = []
        parametreler = []
        if ay is not None:
            kosullar.append("substr(tarih, 1, 7) = ?")
            parametreler.append(ay_dogrula(ay))
        if kategori is not None:
            kosullar.append("kategori = ?")
            parametreler.append(kategori_dogrula(kategori))
        sorgu = "SELECT id, tutar_kurus, kategori, tarih, aciklama FROM harcamalar"
        if kosullar:
            sorgu += " WHERE " + " AND ".join(kosullar)
        sorgu += " ORDER BY tarih, id"
        return [Harcama(*satir) for satir in self._baglanti.execute(sorgu, parametreler)]

    def kategori_toplamlari(self, ay: str) -> List[Tuple[str, int]]:
        """Verilen aydaki kategori toplamlarını (kuruş) büyükten küçüğe döndürür."""
        sorgu = (
            "SELECT kategori, SUM(tutar_kurus) AS toplam FROM harcamalar"
            " WHERE substr(tarih, 1, 7) = ?"
            " GROUP BY kategori ORDER BY toplam DESC, kategori"
        )
        return [(k, int(t)) for k, t in self._baglanti.execute(sorgu, (ay_dogrula(ay),))]

    def sil(self, harcama_id: int) -> None:
        try:
            kimlik = int(harcama_id)
        except (TypeError, ValueError):
            raise HarcamaHatasi("Geçersiz kimlik: '{}'. Tamsayı girmelisiniz.".format(harcama_id))
        imlec = self._baglanti.execute("DELETE FROM harcamalar WHERE id = ?", (kimlik,))
        self._baglanti.commit()
        if imlec.rowcount == 0:
            raise HarcamaBulunamadi("{} numaralı harcama bulunamadı.".format(kimlik))
