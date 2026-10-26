"""Harcama kayıtlarını JSON dosyasında tutan basit komut satırı aracı.

Kullanıcı hataları (geçersiz tutar, tarih ya da id) argparse'ın İngilizce
mesajlarına bırakılmaz; burada doğrulanıp anlaşılır Türkçe mesajla
standart hataya yazılır ve çıkış kodu 1 döner.
"""

import argparse
import datetime
import json
import os
import sys
from decimal import Decimal, InvalidOperation

VARSAYILAN_DOSYA = "harcamalar.json"
TARIH_BICIMI = "%Y-%m-%d"


class HarcamaHatasi(Exception):
    """Kullanıcıya gösterilecek Türkçe hata mesajını taşır."""


def tutar_turu(deger):
    try:
        tutar = Decimal(str(deger).replace(",", "."))
    except InvalidOperation:
        raise HarcamaHatasi(
            f"Geçersiz tutar: '{deger}'. Tutar bir sayı olmalı (örnek: 12.50)."
        )
    if not tutar.is_finite():
        raise HarcamaHatasi(
            f"Geçersiz tutar: '{deger}'. Tutar bir sayı olmalı (örnek: 12.50)."
        )
    if tutar == 0:
        raise HarcamaHatasi("Geçersiz tutar: 0. Tutar sıfırdan büyük olmalı.")
    if tutar < 0:
        raise HarcamaHatasi(
            f"Geçersiz tutar: {deger}. Tutar negatif olamaz, sıfırdan büyük olmalı."
        )
    return tutar


def tarih_turu(deger):
    try:
        return datetime.datetime.strptime(deger, TARIH_BICIMI).date()
    except (ValueError, TypeError):
        raise HarcamaHatasi(
            f"Geçersiz tarih: '{deger}'. Tarih YYYY-AA-GG biçiminde ve "
            "takvimde var olan bir gün olmalı (örnek: 2024-03-15)."
        )


def ay_turu(deger):
    try:
        return datetime.datetime.strptime(deger, "%Y-%m").strftime("%Y-%m")
    except (ValueError, TypeError):
        raise HarcamaHatasi(
            f"Geçersiz ay: '{deger}'. Ay YYYY-AA biçiminde olmalı (örnek: 2024-03)."
        )


def id_turu(deger):
    try:
        kimlik = int(deger)
    except (ValueError, TypeError):
        raise HarcamaHatasi(
            f"Geçersiz id: '{deger}'. Id pozitif bir tam sayı olmalı."
        )
    if kimlik <= 0:
        raise HarcamaHatasi(f"Geçersiz id: {deger}. Id pozitif bir tam sayı olmalı.")
    return kimlik


def kayitlari_oku(dosya):
    if not os.path.exists(dosya):
        return []
    try:
        with open(dosya, encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError:
        raise HarcamaHatasi(
            f"Kayıt dosyası okunamadı: '{dosya}' geçerli bir JSON dosyası değil."
        )


def kayitlari_yaz(dosya, kayitlar):
    with open(dosya, "w", encoding="utf-8") as f:
        json.dump(kayitlar, f, ensure_ascii=False, indent=2)


def kayit_bul(kayitlar, kimlik):
    for kayit in kayitlar:
        if kayit["id"] == kimlik:
            return kayit
    raise HarcamaHatasi(
        f"{kimlik} numaralı kayıt bulunamadı. "
        "Mevcut kayıtları görmek için 'listele' komutunu kullanın."
    )


def filtrele(kayitlar, kategori=None, ay=None):
    sonuc = kayitlar
    if kategori:
        sonuc = [k for k in sonuc if k["kategori"] == kategori]
    if ay:
        sonuc = [k for k in sonuc if k["tarih"].startswith(ay)]
    return sonuc


def komut_ekle(args, cikti):
    tutar = tutar_turu(args.tutar)
    tarih = tarih_turu(args.tarih) if args.tarih else datetime.date.today()
    kayitlar = kayitlari_oku(args.dosya)
    yeni_id = max((k["id"] for k in kayitlar), default=0) + 1
    kayitlar.append(
        {
            "id": yeni_id,
            "tutar": str(tutar),
            "kategori": args.kategori,
            "tarih": tarih.strftime(TARIH_BICIMI),
            "aciklama": args.aciklama or "",
        }
    )
    kayitlari_yaz(args.dosya, kayitlar)
    print(f"{yeni_id} numaralı kayıt eklendi.", file=cikti)


def komut_list(args, cikti):
    ay = ay_turu(args.ay) if args.ay else None
    kayitlar = filtrele(kayitlari_oku(args.dosya), args.kategori, ay)
    if not kayitlar:
        print("Kayıt yok.", file=cikti)
        return
    toplam = Decimal(0)
    for k in kayitlar:
        print(
            f"{k['id']:>4}  {k['tarih']}  {k['tutar']:>10}  "
            f"{k['kategori']}  {k['aciklama']}",
            file=cikti,
        )
        toplam += Decimal(k["tutar"])
    print(f"Toplam: {toplam}", file=cikti)


def komut_sil(args, cikti):
    kimlik = id_turu(args.id)
    kayitlar = kayitlari_oku(args.dosya)
    kayit = kayit_bul(kayitlar, kimlik)
    kayitlar.remove(kayit)
    kayitlari_yaz(args.dosya, kayitlar)
    print(f"{kimlik} numaralı kayıt silindi.", file=cikti)


class TurkceArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        self.print_usage(sys.stderr)
        self.exit(2, f"Hata: komut satırı anlaşılamadı ({message}).\n")


def parser_olustur():
    parser = TurkceArgumentParser(prog="harcama", description="Harcama takibi")
    parser.add_argument(
        "--dosya",
        default=os.environ.get("HARCAMA_DOSYA", VARSAYILAN_DOSYA),
        help="kayıt dosyası (varsayılan: harcamalar.json)",
    )
    alt = parser.add_subparsers(dest="komut", required=True)

    ekle = alt.add_parser("ekle", help="yeni harcama ekle")
    ekle.add_argument("tutar", help="sıfırdan büyük tutar")
    ekle.add_argument("kategori")
    ekle.add_argument("--tarih", help="YYYY-AA-GG (varsayılan: bugün)")
    ekle.add_argument("--aciklama")
    ekle.set_defaults(islem=komut_ekle)

    listele = alt.add_parser("listele", help="harcamaları listele")
    listele.add_argument("--kategori")
    listele.add_argument("--ay", help="YYYY-AA")
    listele.set_defaults(islem=komut_list)

    sil = alt.add_parser("sil", help="harcama sil")
    sil.add_argument("id")
    sil.set_defaults(islem=komut_sil)

    return parser


def main(argv=None, cikti=None, hata_cikti=None):
    cikti = cikti or sys.stdout
    hata_cikti = hata_cikti or sys.stderr
    args = parser_olustur().parse_args(argv)
    try:
        args.islem(args, cikti)
    except HarcamaHatasi as e:
        print(f"Hata: {e}", file=hata_cikti)
        return 1
    return 0
