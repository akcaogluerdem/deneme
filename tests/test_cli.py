import datetime as dt
import json
import os
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path

from harcama.cli import main


class AddTesti(unittest.TestCase):
    def setUp(self):
        self.dizin = tempfile.TemporaryDirectory()
        self.dosya = Path(self.dizin.name) / "harcamalar.json"
        os.environ["HARCAMA_DOSYASI"] = str(self.dosya)

    def tearDown(self):
        os.environ.pop("HARCAMA_DOSYASI", None)
        self.dizin.cleanup()

    def calistir(self, *argv):
        with redirect_stdout(StringIO()):
            return main(list(argv))

    def kayitlar(self):
        return json.loads(self.dosya.read_text(encoding="utf-8"))

    def test_tum_alanlarla_ekleme(self):
        kod = self.calistir(
            "add", "--tutar", "150.50", "--kategori", "market",
            "--tarih", "2026-10-20", "--aciklama", "haftalık alışveriş",
        )
        self.assertEqual(kod, 0)
        self.assertEqual(self.kayitlar(), [{
            "id": 1,
            "tutar": "150.50",
            "kategori": "market",
            "tarih": "2026-10-20",
            "aciklama": "haftalık alışveriş",
        }])

    def test_tarih_verilmezse_bugun(self):
        self.calistir("add", "--tutar", "10", "--kategori", "ulasim")
        kayit = self.kayitlar()[0]
        self.assertEqual(kayit["tarih"], dt.date.today().isoformat())
        self.assertEqual(kayit["tutar"], "10.00")

    def test_id_artar(self):
        self.calistir("add", "--tutar", "1", "--kategori", "a")
        self.calistir("add", "--tutar", "2", "--kategori", "b")
        self.assertEqual([k["id"] for k in self.kayitlar()], [1, 2])

    def test_gecersiz_girdiler_reddedilir(self):
        for argv in (
            ["add", "--tutar", "abc", "--kategori", "x"],
            ["add", "--tutar", "-5", "--kategori", "x"],
            ["add", "--tutar", "5", "--kategori", "x", "--tarih", "2026-13-01"],
            ["add", "--tutar", "5"],
        ):
            with self.subTest(argv=argv), redirect_stderr(StringIO()):
                with self.assertRaises(SystemExit) as cm:
                    self.calistir(*argv)
                self.assertNotEqual(cm.exception.code, 0)
        self.assertFalse(self.dosya.exists())


if __name__ == "__main__":
    unittest.main()
