"""pyproject.toml komut girişini ve README'deki kurulum/kullanım belgesini doğrular."""

import importlib
import io
import os
import re
import shlex
import tempfile
import unittest

from harcama_takip import __version__
from harcama_takip.cli import ana, ayristirici_olustur, main

try:  # Python 3.11+
    import tomllib
except ImportError:  # pragma: no cover - eski Python'lar
    tomllib = None

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PYPROJECT = os.path.join(KOK, "pyproject.toml")
README = os.path.join(KOK, "README.md")
KOMUTLAR = ("add", "list", "delete", "report", "export")


def _oku(yol):
    with open(yol, encoding="utf-8") as f:
        return f.read()


def _pyproject_oku():
    """pyproject.toml'dan proje adı, sürüm ve betikleri döndürür."""
    metin = _oku(PYPROJECT)
    if tomllib is not None:
        veri = tomllib.loads(metin)
        proje = veri["project"]
        return proje["name"], proje["version"], proje.get("scripts", {})
    # tomllib yoksa yalnız ihtiyaç duyulan alanları basitçe ayrıştır.
    bolumler = {}
    bolum = None
    for satir in metin.splitlines():
        satir = satir.strip()
        if not satir or satir.startswith("#"):
            continue
        m = re.match(r"^\[([^\]]+)\]$", satir)
        if m:
            bolum = bolumler.setdefault(m.group(1), {})
            continue
        m = re.match(r'^"?([\w.-]+)"?\s*=\s*"([^"]*)"$', satir)
        if m and bolum is not None:
            bolum[m.group(1)] = m.group(2)
    proje = bolumler.get("project", {})
    return proje.get("name"), proje.get("version"), bolumler.get("project.scripts", {})


def _kullanim_ornekleri():
    """README'deki `harcama-takip add` içeren kod bloğunun komut satırları."""
    bloklar = re.findall(r"```[^\n]*\n(.*?)```", _oku(README), flags=re.S)
    for blok in bloklar:
        if "harcama-takip add" in blok:
            return [s.strip() for s in blok.splitlines() if s.strip().startswith("harcama-takip ")]
    return []


class PyprojectTesti(unittest.TestCase):
    def test_dosya_var(self):
        self.assertTrue(os.path.isfile(PYPROJECT))

    def test_ad_ve_surum(self):
        ad, surum, _ = _pyproject_oku()
        self.assertEqual(ad, "harcama-takip")
        self.assertEqual(surum, __version__)

    def test_komut_girisi_tanimli(self):
        _, _, betikler = _pyproject_oku()
        self.assertEqual(betikler.get("harcama-takip"), "harcama_takip.cli:main")

    def test_komut_girisi_cagrilabilir(self):
        _, _, betikler = _pyproject_oku()
        modul_adi, _, nitelik = betikler["harcama-takip"].partition(":")
        hedef = getattr(importlib.import_module(modul_adi), nitelik)
        self.assertIs(hedef, main)

    def test_main_cikis_kodu_dondurur(self):
        with tempfile.TemporaryDirectory() as dizin:
            db = os.path.join(dizin, "h.db")
            self.assertEqual(main(["--db", db, "add", "--tutar", "10", "--kategori", "market"]), 0)
            self.assertEqual(main(["--db", db, "add", "--tutar", "0", "--kategori", "market"]), 1)


class ReadmeTesti(unittest.TestCase):
    def setUp(self):
        self.metin = _oku(README)

    def test_baslik(self):
        self.assertTrue(self.metin.startswith("# harcama-takip"))

    def test_kurulum_anlatiliyor(self):
        self.assertIn("pip install .", self.metin)
        self.assertIn("python3 -m harcama_takip", self.metin)

    def test_veritabani_ayari_anlatiliyor(self):
        self.assertIn("HARCAMA_TAKIP_DB", self.metin)
        self.assertIn("--db", self.metin)

    def test_tum_komutlar_belgelenmis(self):
        alt = next(
            e for e in ayristirici_olustur()._actions if e.__class__.__name__ == "_SubParsersAction"
        )
        self.assertEqual(set(alt.choices), set(KOMUTLAR))
        for komut in KOMUTLAR:
            self.assertIn("harcama-takip " + komut, self.metin, komut)

    def test_tum_secenekler_belgelenmis(self):
        for secenek in ("--tutar", "--kategori", "--tarih", "--aciklama", "--ay", "--format", "--dosya"):
            self.assertIn(secenek, self.metin, secenek)

    def test_ornekler_calisiyor(self):
        ornekler = _kullanim_ornekleri()
        self.assertGreaterEqual(len(ornekler), len(KOMUTLAR))
        eski_dizin = os.getcwd()
        with tempfile.TemporaryDirectory() as dizin:
            os.chdir(dizin)
            try:
                db = os.path.join(dizin, "ornek.db")
                for satir in ornekler:
                    argv = shlex.split(satir)[1:]
                    cikis, hata = io.StringIO(), io.StringIO()
                    kod = ana(["--db", db] + argv, cikis=cikis, hata=hata)
                    self.assertEqual(kod, 0, "{} -> {}".format(satir, hata.getvalue()))
                self.assertTrue(os.path.isfile(os.path.join(dizin, "cikti.csv")))
            finally:
                os.chdir(eski_dizin)


if __name__ == "__main__":
    unittest.main()
