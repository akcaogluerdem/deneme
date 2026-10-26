import contextlib
import io
import os
import tempfile
import unittest

from harcama.cli import filtrele, main

KAYITLAR = [
    {"tarih": "2026-09-30", "tutar": 50.0, "kategori": "market", "aciklama": "a"},
    {"tarih": "2026-10-01", "tutar": 120.0, "kategori": "market", "aciklama": "b"},
    {"tarih": "2026-10-15", "tutar": 300.0, "kategori": "kira", "aciklama": "c"},
]


class FiltreleTest(unittest.TestCase):
    def test_filtresiz(self):
        self.assertEqual(len(filtrele(KAYITLAR)), 3)

    def test_ay(self):
        sonuc = filtrele(KAYITLAR, ay="2026-10")
        self.assertEqual([k["aciklama"] for k in sonuc], ["b", "c"])

    def test_kategori_harf_duyarsiz(self):
        sonuc = filtrele(KAYITLAR, kategori="MARKET")
        self.assertEqual([k["aciklama"] for k in sonuc], ["a", "b"])

    def test_ay_ve_kategori(self):
        sonuc = filtrele(KAYITLAR, ay="2026-10", kategori="market")
        self.assertEqual([k["aciklama"] for k in sonuc], ["b"])


class CliTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dosya = os.path.join(self.tmp.name, "h.json")

    def tearDown(self):
        self.tmp.cleanup()

    def calistir(self, *argv):
        cikti = io.StringIO()
        with contextlib.redirect_stdout(cikti):
            kod = main(["--dosya", self.dosya, *argv])
        return kod, cikti.getvalue()

    def test_ekle_ve_list(self):
        self.calistir("ekle", "120", "--kategori", "market", "--tarih", "2026-10-01")
        self.calistir("ekle", "300", "--kategori", "kira", "--tarih", "2026-10-15")
        self.calistir("ekle", "50", "--kategori", "market", "--tarih", "2026-09-30")

        kod, cikti = self.calistir("list", "--ay", "2026-10", "--kategori", "market")
        self.assertEqual(kod, 0)
        self.assertIn("2026-10-01", cikti)
        self.assertNotIn("2026-09-30", cikti)
        self.assertNotIn("kira", cikti)
        self.assertIn("Toplam: 120.00 (1 kayıt)", cikti)

    def test_bos_list(self):
        kod, cikti = self.calistir("list")
        self.assertEqual(kod, 0)
        self.assertIn("Kayıt bulunamadı.", cikti)

    def test_gecersiz_ay(self):
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                self.calistir("list", "--ay", "2026-13")


if __name__ == "__main__":
    unittest.main()
