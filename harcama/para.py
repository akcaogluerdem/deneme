"""Kuruş hassasiyetinde para işlemleri.

Tutarlar bellekte her zaman tam sayı KURUŞ olarak tutulur; float hiçbir
aşamada kullanılmaz. Böylece 0,10 + 0,20 tam olarak 0,30 eder.
"""

import re

_TUTAR_DESENI = re.compile(r"^(-?)(\d+)(?:[.,](\d{1,2}))?$")


class TutarHatasi(ValueError):
    """Geçersiz tutar metni."""


def kurusa_cevir(metin):
    """'12,50' / '12.5' / '12' biçimindeki metni tam sayı kuruşa çevirir.

    İkiden fazla ondalık basamak reddedilir (sessiz yuvarlama yapılmaz).
    """
    if not isinstance(metin, str):
        raise TutarHatasi(f"tutar metin olmalı, {type(metin).__name__} verildi")
    eslesme = _TUTAR_DESENI.match(metin.strip())
    if not eslesme:
        raise TutarHatasi(f"geçersiz tutar: {metin!r}")
    isaret, lira, kurus = eslesme.groups()
    deger = int(lira) * 100 + int((kurus or "0").ljust(2, "0"))
    return -deger if isaret else deger


def topla(tutarlar):
    """Metin tutarları toplayıp sonucu tam sayı kuruş olarak döndürür."""
    return sum(kurusa_cevir(t) for t in tutarlar)


def bicimle(kurus):
    """Kuruşu '1234,56' biçiminde metne çevirir."""
    isaret = "-" if kurus < 0 else ""
    lira, kalan = divmod(abs(kurus), 100)
    return f"{isaret}{lira},{kalan:02d}"
