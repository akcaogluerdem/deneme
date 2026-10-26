import contextlib
import csv
import datetime
import io
import os
import subprocess
import sys
import tempfile
import unittest

from harcama_takip import cli
from harcama_takip.veri import DB_ORTAM_DEGISKENI, Depo

KOK_DIZIN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class CliTestTabani(unittest.TestCase):
    def setUp(self):
        self._dizin = tempfile.TemporaryDirectory()
        self.yol = os.path.join(self._dizin.name, "test.db")

    def tearDown(self):
        self._dizin.cleanup()

    def calistir(self, *argv):
        cikis, hata = io.StringIO(), io.StringIO()
        kod = cli.ana(["--db", self.yol] + list(argv), cikis=cikis, hata=hata)
        return kod, cikis.getvalue(), hata.getvalue()

    def kayitlar(self, **filtre):
        with Depo(self.yol) as depo:
            return depo.listele(**filtre)


class EkleTesti(CliTestTabani):
    def test_tum_alanlarla_ekler(self):
        kod, cikis, hata = self.calistir(
            "add", "--tutar", "150.50", "--kategori", "market",
            "--tarih", "2026-10-20", "--aciklama", "haftalık alışveriş",
        )
        self.assertEqual(kod, 0, hata)
        self.assertIn("150.50", cikis)
        kayitlar = self.kayitlar()
        self.assertEqual(len(kayitlar), 1)
        h = kayitlar[0]
        self.assertEqual((h.tutar_kurus, h.kategori, h.tarih, h.aciklama),
                         (15050, "market", "2026-10-20", "haftalık alışveriş"))

    def test_tarih_verilmezse_bugun(self):
        kod, _, hata = self.calistir("add", "--tutar", "10", "--kategori", "kafe")
        self.assertEqual(kod, 0, hata)
        self.assertEqual(self.kayitlar()[0].tarih, datetime.date.today().isoformat())

    def test_negatif_tutar_reddedilir(self):
        kod, _, hata = self.calistir("add", "--tutar=-5", "--kategori", "market")
        self.assertEqual(kod, 1)
        self.assertIn("Hata:", hata)
        self.assertEqual(self.kayitlar(), [])

    def test_sifir_tutar_reddedilir(self):
        kod, _, hata = self.calistir("add", "--tutar", "0", "--kategori", "market")
        self.assertEqual(kod, 1)
        self.assertIn("sıfırdan büyük", hata)

    def test_gecersiz_tutar_reddedilir(self):
        kod, _, hata = self.calistir("add", "--tutar", "abc", "--kategori", "market")
        self.assertEqual(kod, 1)
        self.assertIn("Geçersiz tutar", hata)

    def test_gecersiz_tarih_reddedilir(self):
        kod, _, hata = self.calistir("add", "--tutar", "5", "--kategori", "market", "--tarih", "2026-02-30")
        self.assertEqual(kod, 1)
        self.assertIn("Geçersiz tarih", hata)
        self.assertEqual(self.kayitlar(), [])

    def test_zorunlu_arguman_eksikse_argparse_cikar(self):
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as baglam:
                self.calistir("add", "--kategori", "market")
        self.assertEqual(baglam.exception.code, 2)


class ListeTesti(CliTestTabani):
    def setUp(self):
        super().setUp()
        self.calistir("add", "--tutar", "100", "--kategori", "market", "--tarih", "2026-10-01")
        self.calistir("add", "--tutar", "50.25", "--kategori", "ulasim", "--tarih", "2026-10-15")
        self.calistir("add", "--tutar", "70", "--kategori", "market", "--tarih", "2026-09-30")

    def test_tumunu_listeler(self):
        kod, cikis, _ = self.calistir("list")
        self.assertEqual(kod, 0)
        self.assertIn("2026-09-30", cikis)
        self.assertIn("2026-10-15", cikis)
        self.assertIn("Toplam: 220.25 (3 kayıt)", cikis)

    def test_ay_filtresi(self):
        kod, cikis, _ = self.calistir("list", "--ay", "2026-10")
        self.assertEqual(kod, 0)
        self.assertNotIn("2026-09-30", cikis)
        self.assertIn("Toplam: 150.25 (2 kayıt)", cikis)

    def test_kategori_ve_ay_filtresi(self):
        kod, cikis, _ = self.calistir("list", "--ay", "2026-10", "--kategori", "market")
        self.assertEqual(kod, 0)
        self.assertNotIn("ulasim", cikis)
        self.assertIn("Toplam: 100.00 (1 kayıt)", cikis)

    def test_bos_sonuc(self):
        kod, cikis, _ = self.calistir("list", "--kategori", "yok")
        self.assertEqual(kod, 0)
        self.assertIn("Kayıt bulunamadı.", cikis)

    def test_gecersiz_ay_reddedilir(self):
        kod, _, hata = self.calistir("list", "--ay", "2026-13")
        self.assertEqual(kod, 1)
        self.assertIn("Geçersiz ay", hata)


class SilTesti(CliTestTabani):
    def test_siler(self):
        self.calistir("add", "--tutar", "5", "--kategori", "kafe", "--tarih", "2026-10-01")
        kimlik = self.kayitlar()[0].id
        kod, cikis, hata = self.calistir("delete", str(kimlik))
        self.assertEqual(kod, 0, hata)
        self.assertIn("silindi", cikis)
        self.assertEqual(self.kayitlar(), [])

    def test_olmayan_kimlik(self):
        kod, _, hata = self.calistir("delete", "999")
        self.assertEqual(kod, 1)
        self.assertIn("bulunamadı", hata)

    def test_gecersiz_kimlik(self):
        kod, _, hata = self.calistir("delete", "abc")
        self.assertEqual(kod, 1)
        self.assertIn("Geçersiz kimlik", hata)


class RaporTesti(CliTestTabani):
    def test_kategori_toplam_yuzde_ve_genel_toplam(self):
        self.calistir("add", "--tutar", "300", "--kategori", "market", "--tarih", "2026-10-01")
        self.calistir("add", "--tutar", "100", "--kategori", "ulasim", "--tarih", "2026-10-02")
        self.calistir("add", "--tutar", "999", "--kategori", "kira", "--tarih", "2026-09-01")
        kod, cikis, hata = self.calistir("report", "--ay", "2026-10")
        self.assertEqual(kod, 0, hata)
        satirlar = cikis.splitlines()
        market = next(s for s in satirlar if s.startswith("market"))
        ulasim = next(s for s in satirlar if s.startswith("ulasim"))
        genel = next(s for s in satirlar if s.startswith("GENEL TOPLAM"))
        self.assertIn("300.00", market)
        self.assertIn("75.00%", market)
        self.assertIn("100.00", ulasim)
        self.assertIn("25.00%", ulasim)
        self.assertIn("400.00", genel)
        self.assertNotIn("kira", cikis)

    def test_bos_ay(self):
        kod, cikis, _ = self.calistir("report", "--ay", "2026-01")
        self.assertEqual(kod, 0)
        self.assertIn("harcama yok", cikis)

    def test_ay_zorunlu(self):
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as baglam:
                self.calistir("report")
        self.assertEqual(baglam.exception.code, 2)


class AktarTesti(CliTestTabani):
    def test_csv_aktarir(self):
        self.calistir("add", "--tutar", "150.50", "--kategori", "market",
                      "--tarih", "2026-10-20", "--aciklama", "haftalık alışveriş")
        dosya = os.path.join(self._dizin.name, "cikti.csv")
        kod, cikis, hata = self.calistir("export", "--format", "csv", "--dosya", dosya)
        self.assertEqual(kod, 0, hata)
        self.assertIn("1 kayıt", cikis)
        with open(dosya, newline="", encoding="utf-8") as f:
            satirlar = list(csv.reader(f))
        self.assertEqual(satirlar[0], ["id", "tarih", "kategori", "tutar", "aciklama"])
        self.assertEqual(satirlar[1][1:], ["2026-10-20", "market", "150.50", "haftalık alışveriş"])

    def test_desteklenmeyen_bicim(self):
        dosya = os.path.join(self._dizin.name, "cikti.json")
        kod, _, hata = self.calistir("export", "--format", "json", "--dosya", dosya)
        self.assertEqual(kod, 1)
        self.assertIn("Desteklenmeyen biçim", hata)
        self.assertFalse(os.path.exists(dosya))


class GirisNoktasiTesti(unittest.TestCase):
    def test_python_m_ile_calisir(self):
        with tempfile.TemporaryDirectory() as dizin:
            ortam = dict(os.environ)
            ortam[DB_ORTAM_DEGISKENI] = os.path.join(dizin, "m.db")
            ortam["PYTHONIOENCODING"] = "utf-8"
            komut = [sys.executable, "-m", "harcama_takip"]
            ekle = subprocess.run(
                komut + ["add", "--tutar", "12.30", "--kategori", "kafe", "--tarih", "2026-10-05"],
                cwd=KOK_DIZIN, env=ortam, capture_output=True, text=True, encoding="utf-8",
            )
            self.assertEqual(ekle.returncode, 0, ekle.stderr)
            liste = subprocess.run(
                komut + ["list"], cwd=KOK_DIZIN, env=ortam, capture_output=True, text=True, encoding="utf-8",
            )
            self.assertEqual(liste.returncode, 0, liste.stderr)
            self.assertIn("12.30", liste.stdout)
            hatali = subprocess.run(
                komut + ["add", "--tutar", "0", "--kategori", "kafe"],
                cwd=KOK_DIZIN, env=ortam, capture_output=True, text=True, encoding="utf-8",
            )
            self.assertEqual(hatali.returncode, 1)


if __name__ == "__main__":
    unittest.main()
