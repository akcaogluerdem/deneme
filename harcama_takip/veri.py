"""Veri katmanı: tutar/tarih/kategori doğrulama ve SQLite depolama.

Tutarlar kuruş hassasiyetinde ``Decimal`` ile ayrıştırılır ve veritabanında
tamsayı kuruş olarak saklanır; hiçbir yerde float kullanılmaz.
"""

from __future__ import annotations

import os
import re
import sqlite3
from dataclasses import dataclass
from datetime import date, datetime
from decimal import MAX_PREC, Context, Decimal, InvalidOperation
from pathlib import Path
from typing import Optional

VARSAYILAN_DB = "harcamalar.db"
DB_ORTAM_DEGISKENI = "HARCAMA_DB"

_KURUS_BAGLAMI = Context(prec=MAX_PREC)

_AY_DESENI = re.compile(r"^\d{4}-\d{2}$")
_TARIH_DESENI = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class HarcamaHatasi(Exception):
    """Kullanıcıya gösterilebilir, Türkçe doğrulama hatası."""


class HarcamaBulunamadi(HarcamaHatasi):
    """Verilen id ile kayıt bulunamadı."""


@dataclass(frozen=True)
class Harcama:
    id: int
    tutar_kurus: int
    kategori: str
    tarih: str
    aciklama: str


def tutar_ayristir(deger: str) -> int:
    """Metin tutarı kuruş (tamsayı) olarak döndürür.

    Ondalık ayracı olarak nokta ya da virgül kabul edilir. Kuruştan fazla
    hassasiyet (ör. 1.234) sessizce yuvarlanmaz, hata verilir.
    """
    metin = str(deger).strip().replace(",", ".")
    try:
        tutar = Decimal(metin)
    except (InvalidOperation, ValueError):
        raise HarcamaHatasi(f"Geçersiz tutar: '{deger}'. Örnek: 150.50") from None
    if not tutar.is_finite():
        raise HarcamaHatasi(f"Geçersiz tutar: '{deger}'. Örnek: 150.50")
    if tutar <= 0:
        raise HarcamaHatasi("Tutar sıfırdan büyük olmalıdır.")
    # Varsayılan 28 basamaklık bağlam scaleb sırasında yuvarlayıp kuruş
    # farkını yutabilir; ölçekleme en yüksek hassasiyetle yapılır.
    kurus_ham = tutar.scaleb(2, context=_KURUS_BAGLAMI)
    if kurus_ham != kurus_ham.to_integral_value(context=_KURUS_BAGLAMI):
        raise HarcamaHatasi("Tutar en fazla 2 ondalık basamak içerebilir (kuruş).")
    return int(kurus_ham)


def kurus_metni(kurus: int) -> str:
    """Kuruş tamsayısını '1.234,50' biçiminde Türkçe metne çevirir."""
    isaret = "-" if kurus < 0 else ""
    kurus = abs(kurus)
    tl, k = divmod(kurus, 100)
    gruplu = f"{tl:,}".replace(",", ".")
    return f"{isaret}{gruplu},{k:02d}"


def tarih_dogrula(deger: Optional[str]) -> str:
    """YYYY-MM-DD biçimindeki geçerli bir tarihi döndürür; None ise bugün."""
    if deger is None:
        return date.today().isoformat()
    metin = str(deger).strip()
    if not _TARIH_DESENI.match(metin):
        raise HarcamaHatasi(f"Geçersiz tarih: '{deger}'. Biçim YYYY-AA-GG olmalı (ör. 2026-10-20).")
    try:
        return datetime.strptime(metin, "%Y-%m-%d").date().isoformat()
    except ValueError:
        raise HarcamaHatasi(f"Geçersiz tarih: '{deger}'. Böyle bir gün yok.") from None


def ay_dogrula(deger: Optional[str]) -> Optional[str]:
    """YYYY-AA biçimindeki ayı doğrular; None ise None döner."""
    if deger is None:
        return None
    metin = str(deger).strip()
    if not _AY_DESENI.match(metin):
        raise HarcamaHatasi(f"Geçersiz ay: '{deger}'. Biçim YYYY-AA olmalı (ör. 2026-10).")
    yil, ay = (int(p) for p in metin.split("-"))
    if not 1 <= ay <= 12:
        raise HarcamaHatasi(f"Geçersiz ay: '{deger}'. Ay 01 ile 12 arasında olmalı.")
    return f"{yil:04d}-{ay:02d}"


def kategori_dogrula(deger: Optional[str]) -> str:
    """Kategoriyi kırpıp küçük harfe çevirir; boş olamaz."""
    metin = (deger or "").strip().lower()
    if not metin:
        raise HarcamaHatasi("Kategori boş olamaz.")
    if len(metin) > 50:
        raise HarcamaHatasi("Kategori en fazla 50 karakter olabilir.")
    return metin


def varsayilan_db_yolu() -> str:
    return os.environ.get(DB_ORTAM_DEGISKENI) or VARSAYILAN_DB


class Veritabani:
    """SQLite üzerinde harcama kayıtlarını yöneten basit depo."""

    def __init__(self, yol: Optional[str] = None) -> None:
        self.yol = str(yol) if yol is not None else varsayilan_db_yolu()
        if self.yol != ":memory:":
            Path(self.yol).expanduser().parent.mkdir(parents=True, exist_ok=True)
        self._baglanti = sqlite3.connect(self.yol)
        self._baglanti.row_factory = sqlite3.Row
        self._sema_olustur()

    def _sema_olustur(self) -> None:
        with self._baglanti:
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

    def kapat(self) -> None:
        self._baglanti.close()

    def ekle(
        self,
        tutar: str,
        kategori: str,
        tarih: Optional[str] = None,
        aciklama: str = "",
    ) -> Harcama:
        kurus = tutar_ayristir(tutar)
        kat = kategori_dogrula(kategori)
        trh = tarih_dogrula(tarih)
        with self._baglanti:
            cur = self._baglanti.execute(
                "INSERT INTO harcamalar (tutar_kurus, kategori, tarih, aciklama) VALUES (?, ?, ?, ?)",
                (kurus, kat, trh, (aciklama or "").strip()),
            )
        return Harcama(cur.lastrowid, kurus, kat, trh, (aciklama or "").strip())

    def listele(
        self,
        ay: Optional[str] = None,
        kategori: Optional[str] = None,
    ) -> list[Harcama]:
        sorgu = "SELECT id, tutar_kurus, kategori, tarih, aciklama FROM harcamalar WHERE 1=1"
        parametreler: list[object] = []
        ay_d = ay_dogrula(ay)
        if ay_d is not None:
            sorgu += " AND substr(tarih, 1, 7) = ?"
            parametreler.append(ay_d)
        if kategori is not None:
            sorgu += " AND kategori = ?"
            parametreler.append(kategori_dogrula(kategori))
        sorgu += " ORDER BY tarih, id"
        satirlar = self._baglanti.execute(sorgu, parametreler).fetchall()
        return [Harcama(**dict(s)) for s in satirlar]

    def sil(self, harcama_id: int) -> None:
        with self._baglanti:
            cur = self._baglanti.execute("DELETE FROM harcamalar WHERE id = ?", (harcama_id,))
        if cur.rowcount == 0:
            raise HarcamaBulunamadi(f"{harcama_id} numaralı harcama bulunamadı.")
