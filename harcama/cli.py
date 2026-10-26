"""Harcama takip komut satırı arayüzü (yalnızca standart kütüphane)."""

import argparse
import csv
import datetime
import os
import sys
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

ALANLAR = ["tarih", "kategori", "tutar", "aciklama"]
VARSAYILAN_DOSYA = os.environ.get("HARCAMA_DOSYA", "harcamalar.csv")
KURUS = Decimal("0.01")


def tarih_turu(deger):
    try:
        return datetime.date.fromisoformat(deger).isoformat()
    except ValueError:
        raise argparse.ArgumentTypeError(f"geçersiz tarih (YYYY-AA-GG bekleniyor): {deger}")


def ay_turu(deger):
    try:
        return datetime.datetime.strptime(deger, "%Y-%m").strftime("%Y-%m")
    except ValueError:
        raise argparse.ArgumentTypeError(f"geçersiz ay (YYYY-AA bekleniyor): {deger}")


def tutar_turu(deger):
    try:
        tutar = Decimal(deger)
    except InvalidOperation:
        raise argparse.ArgumentTypeError(f"geçersiz tutar: {deger}")
    if not tutar.is_finite() or tutar <= 0:
        raise argparse.ArgumentTypeError(f"tutar pozitif olmalı: {deger}")
    return tutar.quantize(KURUS, rounding=ROUND_HALF_UP)


def kayitlari_oku(yol):
    if not os.path.exists(yol):
        return []
    with open(yol, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def kayitlari_yaz(yol, kayitlar):
    with open(yol, "w", newline="", encoding="utf-8") as f:
        yazici = csv.DictWriter(f, fieldnames=ALANLAR)
        yazici.writeheader()
        yazici.writerows(kayitlar)


def filtrele(kayitlar, ay=None, kategori=None):
    sonuc = kayitlar
    if ay:
        sonuc = [k for k in sonuc if k["tarih"].startswith(ay + "-")]
    if kategori:
        sonuc = [k for k in sonuc if k["kategori"] == kategori]
    return sonuc


def rapor_hesapla(kayitlar, ay):
    """Ayın kayıtlarını kategori bazında toplar.

    (satırlar, genel_toplam) döndürür; satırlar (kategori, toplam, yüzde)
    üçlüleridir ve toplama göre azalan, eşitlikte ada göre sıralıdır.
    """
    toplamlar = {}
    for k in filtrele(kayitlar, ay=ay):
        toplamlar[k["kategori"]] = toplamlar.get(k["kategori"], Decimal("0")) + Decimal(k["tutar"])
    genel = sum(toplamlar.values(), Decimal("0"))
    satirlar = []
    for kategori, toplam in sorted(toplamlar.items(), key=lambda x: (-x[1], x[0])):
        yuzde = (toplam * 100 / genel).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
        satirlar.append((kategori, toplam.quantize(KURUS), yuzde))
    return satirlar, genel.quantize(KURUS)


def komut_ekle(args):
    kayitlar = kayitlari_oku(args.dosya)
    kayitlar.append({
        "tarih": args.tarih,
        "kategori": args.kategori,
        "tutar": str(args.tutar),
        "aciklama": args.aciklama,
    })
    kayitlari_yaz(args.dosya, kayitlar)
    print(f"Eklendi: {args.tarih} {args.kategori} {args.tutar}")
    return 0


def komut_list(args):
    kayitlar = filtrele(kayitlari_oku(args.dosya), ay=args.ay, kategori=args.kategori)
    for k in sorted(kayitlar, key=lambda k: k["tarih"]):
        print(f"{k['tarih']}  {k['kategori']:<15} {k['tutar']:>12}  {k['aciklama']}")
    return 0


def komut_report(args):
    satirlar, genel = rapor_hesapla(kayitlari_oku(args.dosya), args.ay)
    print(f"Rapor: {args.ay}")
    if not satirlar:
        print("Bu ay için kayıt yok.")
        return 0
    print(f"{'Kategori':<15} {'Toplam':>12} {'Yüzde':>8}")
    for kategori, toplam, yuzde in satirlar:
        print(f"{kategori:<15} {toplam:>12} {str(yuzde) + '%':>8}")
    print(f"{'GENEL TOPLAM':<15} {genel:>12} {'100.0%':>8}")
    return 0


def parser_olustur():
    parser = argparse.ArgumentParser(prog="harcama", description="Basit harcama takibi")
    parser.add_argument("--dosya", default=VARSAYILAN_DOSYA, help="CSV veri dosyası")
    alt = parser.add_subparsers(dest="komut", required=True)

    ekle = alt.add_parser("add", help="harcama ekle")
    ekle.add_argument("tutar", type=tutar_turu)
    ekle.add_argument("kategori")
    ekle.add_argument("--tarih", type=tarih_turu, default=datetime.date.today().isoformat())
    ekle.add_argument("--aciklama", default="")
    ekle.set_defaults(fonk=komut_ekle)

    listele = alt.add_parser("list", help="harcamaları listele")
    listele.add_argument("--ay", type=ay_turu)
    listele.add_argument("--kategori")
    listele.set_defaults(fonk=komut_list)

    rapor = alt.add_parser("report", help="aylık kategori raporu")
    rapor.add_argument("--ay", type=ay_turu, required=True)
    rapor.set_defaults(fonk=komut_report)

    return parser


def main(argv=None):
    args = parser_olustur().parse_args(argv)
    return args.fonk(args)


if __name__ == "__main__":
    sys.exit(main())
