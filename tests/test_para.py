import unittest

from harcama.para import TutarHatasi, bicimle, kurusa_cevir, topla


class KurusaCevirTesti(unittest.TestCase):
    def test_bicimler(self):
        self.assertEqual(kurusa_cevir("12"), 1200)
        self.assertEqual(kurusa_cevir("12,5"), 1250)
        self.assertEqual(kurusa_cevir("12.05"), 1205)
        self.assertEqual(kurusa_cevir(" -0,01 "), -1)

    def test_gecersiz(self):
        for metin in ["", "abc", "1,234", "1.2.3", "--1"]:
            with self.assertRaises(TutarHatasi):
                kurusa_cevir(metin)

    def test_float_reddedilir(self):
        with self.assertRaises(TutarHatasi):
            kurusa_cevir(0.1)


class ToplaTesti(unittest.TestCase):
    def test_float_hatasi_yok(self):
        # float ile 0.1 + 0.2 == 0.30000000000000004 olur
        self.assertEqual(topla(["0,10", "0,20"]), 30)

    def test_cok_sayida_kucuk_tutar(self):
        self.assertEqual(topla(["0,01"] * 1000), 1000)
        self.assertEqual(topla(["0,10"] * 10), 100)

    def test_bos(self):
        self.assertEqual(topla([]), 0)


class BicimleTesti(unittest.TestCase):
    def test_bicimle(self):
        self.assertEqual(bicimle(30), "0,30")
        self.assertEqual(bicimle(123456), "1234,56")
        self.assertEqual(bicimle(-5), "-0,05")


if __name__ == "__main__":
    unittest.main()
