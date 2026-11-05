"""Komut satırı arayüzü: add, list, delete, report, export."""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path
from typing import Optional, Sequence

from harcama_takip.rapor import aylik_rapor, rapor_metni
from harcama_takip.veri import (
    HarcamaHatasi,
    Veritabani,
    ay_dogrula,
    kurus_metni,
    varsayilan_db_yolu,
)


def ayristirici_olustur() -> argparse.ArgumentParser:
    ana = argparse.ArgumentParser(
        prog="harcama-takip",
        description="Kişisel harcamalarınızı SQLite veritabanında takip edin.",
    )
    ana.add_argument(
        "--db",
        default=None,
        help="Veritabanı dosya yolu (varsayılan: HARCAMA_DB ortam değişkeni ya da harcamalar.db)",
    )
    altkomutlar = ana.add_subparsers(dest="komut", required=True, metavar="KOMUT")

    ekle = altkomutlar.add_parser("add", help="Yeni harcama ekle")
    ekle.add_argument("--tutar", required=True, help="Pozitif tutar, ör. 150.50")
    ekle.add_argument("--kategori", required=True, help="Kategori, ör. market")
    ekle.add_argument("--tarih", default=None, help="YYYY-AA-GG (verilmezse bugün)")
    ekle.add_argument("--aciklama", default="", help="Serbest açıklama")

    listele = altkomutlar.add_parser("list", help="Harcamaları listele")
    listele.add_argument("--ay", default=None, help="Ay filtresi, YYYY-AA")
    listele.add_argument("--kategori", default=None, help="Kategori filtresi")

    sil = altkomutlar.add_parser("delete", help="Bir harcamayı id ile sil")
    sil.add_argument("id", type=int, help="Silinecek harcamanın id'si")

    rapor = altkomutlar.add_parser("report", help="Aylık kategori raporu")
    rapor.add_argument("--ay", required=True, help="Ay, YYYY-AA")

    aktar = altkomutlar.add_parser("export", help="Harcamaları dosyaya aktar")
    aktar.add_argument("--format", choices=["csv"], default="csv", help="Çıktı biçimi (yalnız csv)")
    aktar.add_argument("--dosya", required=True, help="Çıktı dosyası yolu")

    return ana


def csv_yaz(veritabani: Veritabani, dosya: str) -> int:
    """Tüm harcamaları CSV dosyasına yazar; yazılan kayıt sayısını döndürür."""
    kayitlar = veritabani.listele()
    yol = Path(dosya)
    if yol.parent and not yol.parent.exists():
        raise HarcamaHatasi(f"Çıktı klasörü bulunamadı: {yol.parent}")
    with yol.open("w", newline="", encoding="utf-8") as f:
        yazici = csv.writer(f)
        yazici.writerow(["id", "tarih", "kategori", "tutar", "aciklama"])
        for k in kayitlar:
            yazici.writerow([k.id, k.tarih, k.kategori, kurus_metni(k.tutar_kurus), k.aciklama])
    return len(kayitlar)


def _calistir(args: argparse.Namespace, veritabani: Veritabani) -> int:
    if args.komut == "add":
        h = veritabani.ekle(args.tutar, args.kategori, args.tarih, args.aciklama)
        print(f"Eklendi: #{h.id} {h.tarih} {h.kategori} {kurus_metni(h.tutar_kurus)} TL")
        return 0

    if args.komut == "list":
        kayitlar = veritabani.listele(args.ay, args.kategori)
        if not kayitlar:
            print("Kayıt bulunamadı.")
            return 0
        print(f"{'id':>5}  {'tarih':<10}  {'kategori':<15}  {'tutar (TL)':>12}  açıklama")
        for k in kayitlar:
            print(
                f"{k.id:>5}  {k.tarih:<10}  {k.kategori:<15}  "
                f"{kurus_metni(k.tutar_kurus):>12}  {k.aciklama}"
            )
        return 0

    if args.komut == "delete":
        veritabani.sil(args.id)
        print(f"Silindi: #{args.id}")
        return 0

    if args.komut == "report":
        ay = ay_dogrula(args.ay)
        print(rapor_metni(aylik_rapor(veritabani, ay)))
        return 0

    if args.komut == "export":
        sayi = csv_yaz(veritabani, args.dosya)
        print(f"{sayi} kayıt {args.dosya} dosyasına aktarıldı.")
        return 0

    raise HarcamaHatasi(f"Bilinmeyen komut: {args.komut}")


def ana(argv: Optional[Sequence[str]] = None) -> int:
    ayristirici = ayristirici_olustur()
    args = ayristirici.parse_args(argv)
    yol = args.db or varsayilan_db_yolu()
    try:
        veritabani = Veritabani(yol)
    except OSError as hata:
        print(f"Hata: veritabanı açılamadı ({yol}): {hata}", file=sys.stderr)
        return 1
    try:
        return _calistir(args, veritabani)
    except HarcamaHatasi as hata:
        print(f"Hata: {hata}", file=sys.stderr)
        return 1
    finally:
        veritabani.kapat()
