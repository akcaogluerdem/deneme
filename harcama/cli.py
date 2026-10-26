"""Komut satırı arayüzü: `ekle` ve `list` alt komutları."""

import argparse
import json
import os
import re
import sys
from datetime import date

VARSAYILAN_DOSYA = "harcamalar.json"
AY_DESENI = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")


def ay_turu(deger):
    """`--ay` değerini YYYY-AA biçiminde doğrular."""
    if not AY_DESENI.match(deger):
        raise argparse.ArgumentTypeError(
            f"geçersiz ay: {deger!r} (beklenen biçim YYYY-AA, örn. 2026-10)"
        )
    return deger


def tarih_turu(deger):
    """`--tarih` değerini YYYY-AA-GG biçiminde doğrular."""
    try:
        return date.fromisoformat(deger).isoformat()
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"geçersiz tarih: {deger!r} (beklenen biçim YYYY-AA-GG)"
        )


def kayitlari_oku(yol):
    if not os.path.exists(yol):
        return []
    with open(yol, encoding="utf-8") as f:
        return json.load(f)


def kayitlari_yaz(yol, kayitlar):
    with open(yol, "w", encoding="utf-8") as f:
        json.dump(kayitlar, f, ensure_ascii=False, indent=2)
        f.write("\n")


def filtrele(kayitlar, ay=None, kategori=None):
    """Kayıtları aya (YYYY-AA) ve kategoriye (büyük/küçük harf duyarsız) göre süzer."""
    sonuc = []
    for k in kayitlar:
        if ay and not k["tarih"].startswith(ay + "-"):
            continue
        if kategori and k["kategori"].casefold() != kategori.casefold():
            continue
        sonuc.append(k)
    return sonuc


def komut_ekle(args):
    kayitlar = kayitlari_oku(args.dosya)
    kayitlar.append(
        {
            "tarih": args.tarih,
            "tutar": args.tutar,
            "kategori": args.kategori,
            "aciklama": args.aciklama,
        }
    )
    kayitlari_yaz(args.dosya, kayitlar)
    print(f"Eklendi: {args.tarih} {args.kategori} {args.tutar:.2f}")
    return 0


def komut_list(args):
    kayitlar = filtrele(kayitlari_oku(args.dosya), args.ay, args.kategori)
    kayitlar.sort(key=lambda k: k["tarih"])
    if not kayitlar:
        print("Kayıt bulunamadı.")
        return 0
    for k in kayitlar:
        print(f"{k['tarih']}  {k['kategori']:<12}  {k['tutar']:>10.2f}  {k['aciklama']}")
    toplam = sum(k["tutar"] for k in kayitlar)
    print(f"Toplam: {toplam:.2f} ({len(kayitlar)} kayıt)")
    return 0


def parser_olustur():
    parser = argparse.ArgumentParser(prog="harcama", description="Harcama kaydı ve listeleme")
    parser.add_argument(
        "--dosya",
        default=os.environ.get("HARCAMA_DOSYA", VARSAYILAN_DOSYA),
        help=f"veri dosyası (varsayılan: $HARCAMA_DOSYA ya da {VARSAYILAN_DOSYA})",
    )
    alt = parser.add_subparsers(dest="komut", required=True)

    ekle = alt.add_parser("ekle", help="yeni harcama ekle")
    ekle.add_argument("tutar", type=float)
    ekle.add_argument("--kategori", required=True)
    ekle.add_argument("--tarih", type=tarih_turu, default=date.today().isoformat())
    ekle.add_argument("--aciklama", default="")
    ekle.set_defaults(islev=komut_ekle)

    lst = alt.add_parser("list", help="harcamaları listele")
    lst.add_argument("--ay", type=ay_turu, help="yalnızca bu ay (YYYY-AA, örn. 2026-10)")
    lst.add_argument("--kategori", help="yalnızca bu kategori")
    lst.set_defaults(islev=komut_list)

    return parser


def main(argv=None):
    args = parser_olustur().parse_args(argv)
    return args.islev(args)


if __name__ == "__main__":
    sys.exit(main())
