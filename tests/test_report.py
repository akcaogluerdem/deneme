import contextlib
import io
import os
import tempfile
import unittest
from decimal import Decimal

from harcama.cli import kayitlari_oku, main, rapor_hesapla


class RaporTesti(unittest.TestCase):
    def setUp(self):
        self.gecici = tempfile.TemporaryDirectory()
        self.dosya = os.path.join(self.gecici.name, "h.csv")

    def tearDown(self):
        self.gecici.cleanup()

    def calistir(self, *argv):
        cikti = io.StringIO()
        with contextlib.redirect_stdout(cikti):
            kod = main(["--dosya", self.dosya, *argv])
        return kod, cikti.getvalue()

    def test_kategori_toplamlari_ve_yuzdeler(self):
        self.calistir("add", "75", "market", "--tarih", "2026-10-03")
        self.calistir("add", "25", "market", "--tarih", "2026-10-15")
        self.calistir("add", "100", "kira", "--tarih", "2026-10-01")
        self.calistir("add", "999", "kira", "--tarih", "2026-09-30")

        kayitlar = kayitlari_oku(self.dosya)
        satirlar, genel = rapor_hesapla(kayitlar, "2026-10")
        self.assertEqual(genel, Decimal("200.00"))
        self.assertEqual(
            satirlar,
            [("kira", Decimal("100.00"), Decimal("50.0")),
             ("market", Decimal("100.00"), Decimal("50.0"))],
        )

    def test_report_ciktisi(self):
        self.calistir("add", "30", "ulasim", "--tarih", "2026-10-05")
        self.calistir("add", "10", "kahve", "--tarih", "2026-10-06")
        kod, cikti = self.calistir("report", "--ay", "2026-10")
        self.assertEqual(kod, 0)
        self.assertIn("ulasim", cikti)
        self.assertIn("75.0%", cikti)
        self.assertIn("25.0%", cikti)
        self.assertIn("GENEL TOPLAM", cikti)
        self.assertIn("40.00", cikti)

    def test_bos_ay(self):
        kod, cikti = self.calistir("report", "--ay", "2026-10")
        self.assertEqual(kod, 0)
        self.assertIn("kayıt yok", cikti)


if __name__ == "__main__":
    unittest.main()
