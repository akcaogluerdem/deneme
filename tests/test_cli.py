import io
import os
import tempfile
import unittest

from harcama.cli import main


class CliTesti(unittest.TestCase):
    def setUp(self):
        self.dizin = tempfile.TemporaryDirectory()
        self.dosya = os.path.join(self.dizin.name, "h.json")

    def tearDown(self):
        self.dizin.cleanup()

    def calistir(self, *argv):
        cikti, hata = io.StringIO(), io.StringIO()
        kod = main(["--dosya", self.dosya, *argv], cikti, hata)
        return kod, cikti.getvalue(), hata.getvalue()

    def test_ekle_ve_listele(self):
        kod, cikti, _ = self.calistir("ekle", "12.50", "market", "--tarih", "2024-03-15")
        self.assertEqual(kod, 0)
        self.assertIn("1 numaralı kayıt eklendi", cikti)
        kod, cikti, _ = self.calistir("listele")
        self.assertIn("market", cikti)
        self.assertIn("Toplam: 12.50", cikti)

    def test_negatif_tutar(self):
        kod, _, hata = self.calistir("ekle", "-5", "market")
        self.assertEqual(kod, 1)
        self.assertIn("Tutar negatif olamaz", hata)

    def test_sifir_tutar(self):
        kod, _, hata = self.calistir("ekle", "0", "market")
        self.assertEqual(kod, 1)
        self.assertIn("Tutar sıfırdan büyük olmalı", hata)

    def test_sayi_olmayan_tutar(self):
        kod, _, hata = self.calistir("ekle", "abc", "market")
        self.assertEqual(kod, 1)
        self.assertIn("Tutar bir sayı olmalı", hata)

    def test_gecersiz_tarih(self):
        for tarih in ("2024-02-30", "15.03.2024", "yarın"):
            kod, _, hata = self.calistir("ekle", "10", "market", "--tarih", tarih)
            self.assertEqual(kod, 1)
            self.assertIn("Geçersiz tarih", hata)
        self.assertFalse(os.path.exists(self.dosya))

    def test_olmayan_id(self):
        self.calistir("ekle", "10", "market", "--tarih", "2024-03-15")
        kod, _, hata = self.calistir("sil", "42")
        self.assertEqual(kod, 1)
        self.assertIn("42 numaralı kayıt bulunamadı", hata)

    def test_gecersiz_id(self):
        kod, _, hata = self.calistir("sil", "abc")
        self.assertEqual(kod, 1)
        self.assertIn("Id pozitif bir tam sayı olmalı", hata)

    def test_sil(self):
        self.calistir("ekle", "10", "market", "--tarih", "2024-03-15")
        kod, cikti, _ = self.calistir("sil", "1")
        self.assertEqual(kod, 0)
        self.assertIn("1 numaralı kayıt silindi", cikti)


if __name__ == "__main__":
    unittest.main()
