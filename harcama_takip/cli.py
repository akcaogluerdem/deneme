"""argparse tabanlı komut satırı arayüzü: add, list, delete, report, export.

Başarıda 0, kullanıcı hatasında (geçersiz tutar/tarih, bulunamayan kayıt vb.)
1 döner; argparse sözdizimi hatalarında 2 ile çıkar.
"""

import argparse
import sys
from typing import List, Optional, TextIO

from harcama_takip import __version__
from harcama_takip.rapor import DESTEKLENEN_BICIMLER, aylik_rapor, disa_aktar, kurus_metni, liste_metni, rapor_metni
from harcama_takip.veri import DB_ORTAM_DEGISKENI, Depo, HarcamaHatasi

PROG = "harcama-takip"


def ayristirici_olustur() -> argparse.ArgumentParser:
    ayristirici = argparse.ArgumentParser(
        prog=PROG,
        description="SQLite tabanlı harcama takip uygulaması.",
    )
    ayristirici.add_argument("--version", action="version", version="%(prog)s " + __version__)
    ayristirici.add_argument(
        "--db",
        help="Veritabanı dosyası (varsayılan: ${} ya da ~/.harcama_takip.db).".format(DB_ORTAM_DEGISKENI),
    )
    alt = ayristirici.add_subparsers(dest="komut", metavar="KOMUT")
    alt.required = True

    ekle = alt.add_parser("add", help="Yeni harcama ekle.")
    ekle.add_argument("--tutar", required=True, help="Tutar, örn. 150.50 (sıfırdan büyük).")
    ekle.add_argument("--kategori", required=True, help="Kategori, örn. market.")
    ekle.add_argument("--tarih", help="YYYY-AA-GG; verilmezse bugün.")
    ekle.add_argument("--aciklama", default="", help="Serbest açıklama.")
    ekle.set_defaults(isleyici=_ekle)

    listele = alt.add_parser("list", help="Harcamaları listele.")
    listele.add_argument("--ay", help="YYYY-AA ile aya göre filtrele.")
    listele.add_argument("--kategori", help="Kategoriye göre filtrele.")
    listele.set_defaults(isleyici=_listele)

    sil = alt.add_parser("delete", help="Harcamayı kimliğiyle sil.")
    sil.add_argument("id", help="Silinecek harcamanın kimliği.")
    sil.set_defaults(isleyici=_sil)

    rapor = alt.add_parser("report", help="Aylık kategori raporu.")
    rapor.add_argument("--ay", required=True, help="YYYY-AA biçiminde ay.")
    rapor.set_defaults(isleyici=_rapor)

    aktar = alt.add_parser("export", help="Harcamaları dosyaya aktar.")
    aktar.add_argument("--format", dest="bicim", default="csv", help="Biçim: {}.".format(", ".join(DESTEKLENEN_BICIMLER)))
    aktar.add_argument("--dosya", required=True, help="Çıktı dosyasının yolu.")
    aktar.add_argument("--ay", help="YYYY-AA ile aya göre filtrele.")
    aktar.add_argument("--kategori", help="Kategoriye göre filtrele.")
    aktar.set_defaults(isleyici=_aktar)

    return ayristirici


def _ekle(depo: Depo, args: argparse.Namespace, cikis: TextIO) -> None:
    h = depo.ekle(args.tutar, args.kategori, args.tarih, args.aciklama)
    cikis.write("Harcama eklendi: #{} {} {} {}\n".format(h.id, h.tarih, h.kategori, kurus_metni(h.tutar_kurus)))


def _listele(depo: Depo, args: argparse.Namespace, cikis: TextIO) -> None:
    cikis.write(liste_metni(depo.listele(ay=args.ay, kategori=args.kategori)) + "\n")


def _sil(depo: Depo, args: argparse.Namespace, cikis: TextIO) -> None:
    depo.sil(args.id)
    cikis.write("{} numaralı harcama silindi.\n".format(args.id))


def _rapor(depo: Depo, args: argparse.Namespace, cikis: TextIO) -> None:
    cikis.write(rapor_metni(aylik_rapor(depo, args.ay)) + "\n")


def _aktar(depo: Depo, args: argparse.Namespace, cikis: TextIO) -> None:
    adet = disa_aktar(depo, args.dosya, bicim=args.bicim, ay=args.ay, kategori=args.kategori)
    cikis.write("{} kayıt '{}' dosyasına aktarıldı.\n".format(adet, args.dosya))


def ana(
    argv: Optional[List[str]] = None,
    cikis: Optional[TextIO] = None,
    hata: Optional[TextIO] = None,
) -> int:
    """CLI giriş noktası; çıkış kodunu döndürür."""
    cikis = cikis if cikis is not None else sys.stdout
    hata = hata if hata is not None else sys.stderr
    args = ayristirici_olustur().parse_args(argv)
    try:
        with Depo(args.db) as depo:
            args.isleyici(depo, args, cikis)
    except HarcamaHatasi as e:
        hata.write("Hata: {}\n".format(e))
        return 1
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    """pyproject.toml'daki `harcama-takip` konsol betiğinin hedefi."""
    return ana(argv)


if __name__ == "__main__":
    sys.exit(main())
