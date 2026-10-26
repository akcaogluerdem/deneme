import datetime
import os
import tempfile
import unittest
from decimal import Decimal
from unittest import mock

from harcama_takip import veri
from harcama_takip.veri import Depo, HarcamaBulunamadi, HarcamaHatasi


class DepoTestTabani(unittest.TestCase):
    def setUp(self):
        self._dizin = tempfile.TemporaryDirectory()
        self.yol = os.path.join(self._dizin.name, "test.db")
        self.depo = Depo(self.yol)

    def tearDown(self):
        self.depo.kapat()
        self._dizin.cleanup()


class EkleTesti(DepoTestTabani):
    def test_ekle_kaydi_dondurur(self):
        h = self.depo.ekle("150.50", "market", "2026-10-20", "haftalık alışveriş")
        self.assertEqual(h.tutar_kurus, 15050)
        self.assertEqual(h.kategori, "market")
        self.assertEqual(h.tarih, "2026-10-20")
        self.assertEqual(h.aciklama, "haftalık alışveriş")
        self.assertIsInstance(h.id, int)

    def test_tarih_verilmezse_bugun(self):
        h = self.depo.ekle("10", "kafe")
        self.assertEqual(h.tarih, datetime.date.today().isoformat())

    def test_kurus_hassasiyeti_korunur(self):
        for _ in range(10):
            self.depo.ekle("0.10", "market", "2026-10-01")
        toplam = sum(h.tutar_kurus for h in self.depo.listele())
        self.assertEqual(toplam, 100)
        self.assertEqual(self.depo.listele()[0].tutar, Decimal("0.10"))

    def test_virgullu_tutar_kabul_edilir(self):
        h = self.depo.ekle("12,75", "market", "2026-10-01")
        self.assertEqual(h.tutar_kurus, 1275)

    def test_veri_kalici(self):
        self.depo.ekle("5", "ulasim", "2026-10-02")
        self.depo.kapat()
        self.depo = Depo(self.yol)
        self.assertEqual(len(self.depo.listele()), 1)


class HataTesti(DepoTestTabani):
    def test_sifir_tutar_reddedilir(self):
        with self.assertRaisesRegex(HarcamaHatasi, "sıfırdan büyük"):
            self.depo.ekle("0", "market", "2026-10-01")

    def test_negatif_tutar_reddedilir(self):
        with self.assertRaisesRegex(HarcamaHatasi, "sıfırdan büyük"):
            self.depo.ekle("-5", "market", "2026-10-01")

    def test_sayi_olmayan_tutar_reddedilir(self):
        with self.assertRaisesRegex(HarcamaHatasi, "Geçersiz tutar"):
            self.depo.ekle("abc", "market", "2026-10-01")

    def test_uc_ondalikli_tutar_reddedilir(self):
        with self.assertRaisesRegex(HarcamaHatasi, "iki ondalık"):
            self.depo.ekle("1.005", "market", "2026-10-01")

    def test_gecersiz_tarih_bicimi(self):
        with self.assertRaisesRegex(HarcamaHatasi, "Geçersiz tarih"):
            self.depo.ekle("10", "market", "20-10-2026")

    def test_var_olmayan_gun(self):
        with self.assertRaisesRegex(HarcamaHatasi, "Geçersiz tarih"):
            self.depo.ekle("10", "market", "2026-02-30")

    def test_bos_kategori(self):
        with self.assertRaisesRegex(HarcamaHatasi, "Kategori boş"):
            self.depo.ekle("10", "  ", "2026-10-01")

    def test_gecersiz_ay_filtresi(self):
        with self.assertRaisesRegex(HarcamaHatasi, "Geçersiz ay"):
            self.depo.listele(ay="2026-13")

    def test_hatali_kayit_eklenmez(self):
        with self.assertRaises(HarcamaHatasi):
            self.depo.ekle("-1", "market", "2026-10-01")
        self.assertEqual(self.depo.listele(), [])


class ListeleTesti(DepoTestTabani):
    def setUp(self):
        super().setUp()
        self.depo.ekle("100", "market", "2026-10-20")
        self.depo.ekle("50", "kafe", "2026-10-05")
        self.depo.ekle("30", "market", "2026-09-30")

    def test_tumunu_tarihe_gore_listeler(self):
        tarihler = [h.tarih for h in self.depo.listele()]
        self.assertEqual(tarihler, ["2026-09-30", "2026-10-05", "2026-10-20"])

    def test_aya_gore_filtre(self):
        sonuc = self.depo.listele(ay="2026-10")
        self.assertEqual({h.tarih for h in sonuc}, {"2026-10-05", "2026-10-20"})

    def test_kategoriye_gore_filtre(self):
        sonuc = self.depo.listele(kategori="market")
        self.assertEqual(len(sonuc), 2)
        self.assertTrue(all(h.kategori == "market" for h in sonuc))

    def test_ay_ve_kategori_birlikte(self):
        sonuc = self.depo.listele(ay="2026-10", kategori="market")
        self.assertEqual(len(sonuc), 1)
        self.assertEqual(sonuc[0].tutar_kurus, 10000)


class SilTesti(DepoTestTabani):
    def test_sil(self):
        h = self.depo.ekle("10", "market", "2026-10-01")
        self.depo.sil(h.id)
        self.assertEqual(self.depo.listele(), [])

    def test_olmayan_kayit_silinemez(self):
        with self.assertRaisesRegex(HarcamaBulunamadi, "bulunamadı"):
            self.depo.sil(999)

    def test_gecersiz_kimlik(self):
        with self.assertRaisesRegex(HarcamaHatasi, "Geçersiz kimlik"):
            self.depo.sil("abc")


class DbYoluTesti(unittest.TestCase):
    def test_ortam_degiskeni_kullanilir(self):
        with mock.patch.dict(os.environ, {"HARCAMA_TAKIP_DB": "/tmp/ozel.db"}):
            self.assertEqual(veri.varsayilan_db_yolu(), "/tmp/ozel.db")

    def test_ortam_degiskeni_yoksa_ev_dizini(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            os.environ["HOME"] = "/tmp/ev"
            self.assertEqual(
                veri.varsayilan_db_yolu(), os.path.join("/tmp/ev", veri.VARSAYILAN_DB_ADI)
            )


if __name__ == "__main__":
    unittest.main()
