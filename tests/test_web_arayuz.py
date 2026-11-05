import json
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


def test_bilinmeyen_yol_404_json(adres):
    with pytest.raises(urllib.error.HTTPError) as e:
        _al(adres + "/yok")
    assert e.value.code == 404
    assert "hata" in json.loads(e.value.read().decode("utf-8"))
