"""Harcama takipçisinin komut satırı arayüzü.

Örnek:
    python -m harcama add --tutar 150.50 --kategori market \
        --tarih 2026-10-20 --aciklama "haftalık alışveriş"
"""

import argparse
import datetime as dt
import json
import os
import sys
from decimal import Decimal, InvalidOperation
from pathlib import Path

VARSAYILAN_DOSYA = "harcamalar.json"


def veri_dosyasi() -> Path:
    return Path(os.environ.get("HARCAMA_DOSYASI", VARSAYILAN_DOSYA))


def tutar_tipi(deger: str) -> Decimal:
    try:
        tutar = Decimal(deger.replace(",", "."))
    except InvalidOperation:
        raise argparse.ArgumentTypeError(f"geçersiz tutar: {deger!r}")
    if not tutar.is_finite() or tutar <= 0:
        raise argparse.ArgumentTypeError(f"tutar pozitif olmalı: {deger!r}")
    return tutar.quantize(Decimal("0.01"))


def tarih_tipi(deger: str) -> dt.date:
    try:
        return dt.date.fromisoformat(deger)
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"geçersiz tarih (YYYY-AA-GG bekleniyor): {deger!r}"
        )


def kayitlari_oku(yol: Path) -> list:
    if not yol.exists():
        return []
    with yol.open(encoding="utf-8") as f:
        return json.load(f)


def kayitlari_yaz(yol: Path, kayitlar: list) -> None:
    gecici = yol.with_name(yol.name + ".tmp")
    with gecici.open("w", encoding="utf-8") as f:
        json.dump(kayitlar, f, ensure_ascii=False, indent=2)
        f.write("\n")
    gecici.replace(yol)


def komut_add(args: argparse.Namespace) -> int:
    yol = veri_dosyasi()
    kayitlar = kayitlari_oku(yol)
    kayit = {
        "id": max((k["id"] for k in kayitlar), default=0) + 1,
        "tutar": str(args.tutar),
        "kategori": args.kategori,
        "tarih": (args.tarih or dt.date.today()).isoformat(),
        "aciklama": args.aciklama,
    }
    kayitlar.append(kayit)
    kayitlari_yaz(yol, kayitlar)
    print(
        f"Eklendi #{kayit['id']}: {kayit['tarih']} {kayit['kategori']} "
        f"{kayit['tutar']} {kayit['aciklama']}".rstrip()
    )
    return 0


def parser_olustur() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="harcama", description="Harcama takipçisi")
    alt = parser.add_subparsers(dest="komut", required=True)

    add = alt.add_parser("add", help="yeni harcama ekle")
    add.add_argument("--tutar", type=tutar_tipi, required=True, help="harcama tutarı (örn. 150.50)")
    add.add_argument("--kategori", required=True, help="harcama kategorisi (örn. market)")
    add.add_argument("--tarih", type=tarih_tipi, default=None, help="YYYY-AA-GG; verilmezse bugün")
    add.add_argument("--aciklama", default="", help="serbest açıklama")
    add.set_defaults(fonksiyon=komut_add)

    return parser


def main(argv=None) -> int:
    args = parser_olustur().parse_args(argv)
    return args.fonksiyon(args)


if __name__ == "__main__":
    sys.exit(main())
