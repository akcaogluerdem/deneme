import json
import re
import threading
import urllib.error
import urllib.request

import pytest

from harcama_takip.web import sunucu_olustur


@pytest.fixture()
def adres(tmp_path):
    sunucu = sunucu_olustur("127.0.0.1", 0, str(tmp_path / "t.db"))
    t = threading.Thread(target=sunucu.serve_forever, daemon=True)
    t.start()
    yield "http://127.0.0.1:%d" % sunucu.server_address[1]
    sunucu.shutdown()
    sunucu.server_close()


def _al(url):
    with urllib.request.urlopen(url) as y:
        return y.status, y.headers, y.read().decode("utf-8")


def test_ana_sayfa_html_doner(adres):
    durum, basliklar, govde = _al(adres + "/")
    assert durum == 200
    assert basliklar["Content-Type"].startswith("text/html")
    assert '<html lang="tr">' in govde
    assert "<style>" in govde and "<script>" in govde


def test_mobil_ve_tema(adres):
    govde = _al(adres + "/")[2]
    assert 'name="viewport"' in govde
    assert "prefers-color-scheme: dark" in govde
    assert "@media (max-width" in govde


def test_api_uclarina_baglanir(adres):
    govde = _al(adres + "/")[2]
    for parca in ("/api/harcamalar", "/api/rapor", "/export.csv"):
        assert parca in govde


def test_ozet_kartlari_var(adres):
    govde = _al(adres + "/")[2]
    for kimlik in ("ozet-toplam", "ozet-adet", "ozet-kategori", "ozet-ay"):
        assert 'id="%s"' % kimlik in govde
    assert govde.count('class="ozet-kart') == 3


def test_kategori_renk_paleti(adres):
    govde = _al(adres + "/")[2]
    eslesme = re.search(r"PALET=\[([^\]]*)\]", govde)
    assert eslesme is not None
    assert eslesme.group(1).count("#") == 8
    assert "function kategoriRenk(" in govde
    assert "kategori-renk" in govde


def test_tema_tokenlari_ve_cubuk(adres):
    govde = _al(adres + "/")[2]
    assert ":root{" in govde
    assert "--vurgu:" in govde and "--tehlike:" in govde
    assert 'class="cubuk"' in govde or '"cubuk"' in govde


def test_tasarim_tokenlari_ve_palet(adres):
    govde = _al(adres + "/")[2]
    assert "#4338CA" in govde
    assert "--birincil:" in govde and "--hata:" in govde
    eslesme = re.search(r"PALET=\[([^\]]*)\]", govde)
    assert eslesme is not None
    assert eslesme.group(1).count("#") == 8


def test_tasarim_kararli_idler(adres):
    govde = _al(adres + "/")[2]
    for kimlik in ("harcama-tablo", "dagilim-yigin", "sil-diyalog", "ozet-kategori", "ozet-toplam"):
        assert 'id="%s"' % kimlik in govde
    assert "<dialog" in govde


def test_linear_gradient_yok(adres):
    govde = _al(adres + "/")[2]
    assert "linear-gradient" not in govde


def test_bilinmeyen_yol_404_json(adres):
    with pytest.raises(urllib.error.HTTPError) as e:
        _al(adres + "/yok")
    assert e.value.code == 404
    assert "hata" in json.loads(e.value.read().decode("utf-8"))
