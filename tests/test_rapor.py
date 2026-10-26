import csv
import os
import tempfile
import unittest
from decimal import Decimal

from harcama_takip import rapor
from harcama_takip.veri import Depo, HarcamaHatasi


class RaporTestTabani(unittest.TestCase):
    def setUp(self):
        self._dizin = tempfile.TemporaryDirectory()
        self.yol = os.path.join(self._dizin.name, "test.db")
        self.depo = Depo(self.yol)

    def tearDown(self):
        self.depo.kapat()
        self._dizin.cleanup()


class YardimciTesti(unittest.TestCase):
    def test_kurus_metni(self):
        self.assertEqual(rapor.kurus_metni(15050), "150.50")
        self.assertEqual(rapor.kurus_metni(5), "0.05")
        self.assertEqual(rapor.kurus_metni(100), "1.00")

    def test_yuzde_iki_ondaliga_yuvarlanir(self):
        self.assertEqual(rapor.yuzde_hesapla(1, 3), Decimal("33.33"))
        self.assertEqual(rapor.yuzde_hesapla(2, 3), Decimal("66.67"))

    def test_yuzde_yarim_yukari_yuvarlanir(self):
        self.assertEqual(rapor.yuzde_hesapla(1, 32), Decimal("3.13"))

    def test_toplam_sifirsa_yuzde_sifir(self):
        self.assertEqual(rapor.yuzde_hesapla(0, 0), Decimal("0.00"))


class AylikRaporTesti(RaporTestTabani):
    def setUp(self):
        super().setUp()
        self.depo.ekle("100", "market", "2026-10-20")
        self.depo.ekle("50", "market", "2026-10-03")
        self.depo.ekle("50", "kafe", "2026-10-05")
        self.depo.ekle("25.50", "ulasim", "2026-10-31")
        self.depo.ekle("30", "market", "2026-09-30")
        self.depo.ekle("999", "kira", "2026-11-01")

    def test_kategori_toplamlari_buyukten_kucuge(self):
        r = rapor.aylik_rapor(self.depo, "2026-10")
        self.assertEqual(
            [(s.kategori, s.toplam_kurus) for s in r.satirlar],
            [("market", 15000), ("kafe", 5000), ("ulasim", 2550)],
        )

    def test_genel_toplam_yalniz_o_ayi_kapsar(self):
        r = rapor.aylik_rapor(self.depo, "2026-10")
        self.assertEqual(r.genel_toplam_kurus, 22550)
        self.assertEqual(r.genel_toplam, Decimal("225.50"))

    def test_yuzdeler(self):
        r = rapor.aylik_rapor(self.depo, "2026-10")
        self.assertEqual(
            [s.yuzde for s in r.satirlar],
            [Decimal("66.52"), Decimal("22.17"), Decimal("11.31")],
        )
        self.assertEqual(r.satirlar[0].toplam, Decimal("150.00"))

    def test_bos_ay(self):
        r = rapor.aylik_rapor(self.depo, "2026-01")
        self.assertEqual(r.satirlar, [])
        self.assertEqual(r.genel_toplam_kurus, 0)
        self.assertIn("harcama yok", rapor.rapor_metni(r))

    def test_gecersiz_ay(self):
        with self.assertRaisesRegex(HarcamaHatasi, "Geçersiz ay"):
            rapor.aylik_rapor(self.depo, "2026-13")

    def test_rapor_metni(self):
        metin = rapor.rapor_metni(rapor.aylik_rapor(self.depo, "2026-10"))
        self.assertIn("2026-10", metin)
        self.assertIn("market", metin)
        self.assertIn("150.00", metin)
        self.assertIn("66.52%", metin)
        self.assertIn("GENEL TOPLAM", metin)
        self.assertIn("225.50", metin)
        self.assertNotIn("kira", metin)


class DisaAktarTesti(RaporTestTabani):
    def setUp(self):
        super().setUp()
        self.depo.ekle("150.50", "market", "2026-10-20", "haftalık alışveriş")
        self.depo.ekle("12", "kafe", "2026-09-01", 'çay, "simit"')
        self.cikti = os.path.join(self._dizin.name, "cikti.csv")

    def _oku(self):
        with open(self.cikti, newline="", encoding="utf-8") as f:
            return list(csv.reader(f))

    def test_csv_tum_kayitlar(self):
        sayi = rapor.disa_aktar(self.depo, self.cikti, "csv")
        self.assertEqual(sayi, 2)
        satirlar = self._oku()
        self.assertEqual(satirlar[0], rapor.CSV_BASLIKLARI)
        self.assertEqual(satirlar[1][1:], ["2026-09-01", "kafe", "12.00", 'çay, "simit"'])
        self.assertEqual(satirlar[2][1:], ["2026-10-20", "market", "150.50", "haftalık alışveriş"])

    def test_csv_filtreli(self):
        sayi = rapor.disa_aktar(self.depo, self.cikti, "csv", ay="2026-10")
        self.assertEqual(sayi, 1)
        self.assertEqual(len(self._oku()), 2)

    def test_bos_depo_yalniz_baslik(self):
        for h in self.depo.listele():
            self.depo.sil(h.id)
        self.assertEqual(rapor.disa_aktar(self.depo, self.cikti), 0)
        self.assertEqual(self._oku(), [rapor.CSV_BASLIKLARI])

    def test_desteklenmeyen_bicim(self):
        with self.assertRaisesRegex(HarcamaHatasi, "Desteklenmeyen biçim"):
            rapor.disa_aktar(self.depo, self.cikti, "xml")
        self.assertFalse(os.path.exists(self.cikti))

    def test_yazilamayan_dosya(self):
        yol = os.path.join(self._dizin.name, "olmayan", "cikti.csv")
        with self.assertRaisesRegex(HarcamaHatasi, "yazılamadı"):
            rapor.disa_aktar(self.depo, yol)


if __name__ == "__main__":
    unittest.main()
