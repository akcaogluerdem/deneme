from __future__ import annotations

import csv
import io
import json
import threading
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Optional, Tuple

import pytest

from harcama_takip.cli import csv_yaz
from harcama_takip.veri import Veritabani
from harcama_takip.web import sunucu_olustur


@pytest.fixture
def sunucu(tmp_path: Path):
    s = sunucu_olustur("127.0.0.1", 0, str(tmp_path / "test.db"))
    thread = threading.Thread(target=s.serve_forever, daemon=True)
    thread.start()
    yield s
    s.shutdown()
    s.server_close()
    thread.join(5)


def _url(s, yol: str) -> str:
    host, port = s.server_address[:2]
    return f"http://{host}:{port}{yol}"


def _ham_istek(
    s, yontem: str, yol: str, govde: Optional[bytes] = None
) -> Tuple[int, Any, bytes]:
    basliklar = {}
    if govde is not None:
        basliklar["Content-Type"] = "application/json"
    istek = urllib.request.Request(_url(s, yol), data=govde, method=yontem, headers=basliklar)
    try:
        with urllib.request.urlopen(istek, timeout=5) as yanit:
            return yanit.status, yanit.headers, yanit.read()
    except urllib.error.HTTPError as hata:
        return hata.code, hata.headers, hata.read()


def _json_istek(s, yontem: str, yol: str, veri: Any = None) -> Tuple[int, Any]:
    govde = None if veri is None else json.dumps(veri).encode("utf-8")
    durum, _, ham = _ham_istek(s, yontem, yol, govde)
    return durum, json.loads(ham.decode("utf-8"))


def _ekle(s, tutar: str, kategori: str, tarih: str, aciklama: str = "") -> dict:
    durum, veri = _json_istek(
        s,
        "POST",
        "/api/harcamalar",
        {"tutar": tutar, "kategori": kategori, "tarih": tarih, "aciklama": aciklama},
    )
    assert durum == 201, veri
    return veri


def test_ekle_ve_listele_turkce_bicim(sunucu):
    durum, veri = _json_istek(
        sunucu,
        "POST",
        "/api/harcamalar",
        {"tutar": "150.50", "kategori": " Market ", "tarih": "2026-10-05", "aciklama": "  haftalık alışveriş  "},
    )
    assert durum == 201
    assert veri["tutar_kurus"] == 15050
    assert veri["tutar"] == "150,50"
    assert veri["kategori"] == "market"
    assert veri["aciklama"] == "haftalık alışveriş"

    durum, liste = _json_istek(sunucu, "GET", "/api/harcamalar")
    assert durum == 200
    assert [h["id"] for h in liste["harcamalar"]] == [veri["id"]]


def test_liste_ay_ve_kategori_filtresi(sunucu):
    _ekle(sunucu, "10", "market", "2026-10-01")
    _ekle(sunucu, "20", "ulasim", "2026-10-02")
    _ekle(sunucu, "30", "market", "2026-11-01")

    _, ekim = _json_istek(sunucu, "GET", "/api/harcamalar?ay=2026-10")
    assert len(ekim["harcamalar"]) == 2

    _, ulasim = _json_istek(sunucu, "GET", "/api/harcamalar?kategori=ulasim")
    assert [h["kategori"] for h in ulasim["harcamalar"]] == ["ulasim"]

    durum, hata = _json_istek(sunucu, "GET", "/api/harcamalar?ay=2026-13")
    assert durum == 400
    assert "Ay 01 ile 12" in hata["hata"]


def test_sil_ve_olmayan_id_404(sunucu):
    kayit = _ekle(sunucu, "12.34", "kira", "2026-10-03")

    durum, veri = _json_istek(sunucu, "DELETE", f"/api/harcamalar/{kayit['id']}")
    assert durum == 200
    assert veri == {"silindi": kayit["id"]}

    durum, hata = _json_istek(sunucu, "DELETE", f"/api/harcamalar/{kayit['id']}")
    assert durum == 404
    assert "bulunamadı" in hata["hata"]

    durum, _ = _json_istek(sunucu, "DELETE", "/api/harcamalar/abc")
    assert durum == 400


def test_rapor_yuzdeleri_metin_olarak_doner(sunucu):
    _ekle(sunucu, "100.00", "market", "2026-10-01")
    _ekle(sunucu, "50.00", "ulasim", "2026-10-02")

    durum, rapor = _json_istek(sunucu, "GET", "/api/rapor?ay=2026-10")
    assert durum == 200
    assert rapor["ay"] == "2026-10"
    assert rapor["genel_toplam_kurus"] == 15000
    assert rapor["genel_toplam"] == "150,00"
    assert [s["kategori"] for s in rapor["satirlar"]] == ["market", "ulasim"]
    assert [s["yuzde"] for s in rapor["satirlar"]] == ["66.67", "33.33"]
    assert all(isinstance(s["yuzde"], str) for s in rapor["satirlar"])


def test_rapor_ay_eksik_ve_gecersiz_400(sunucu):
    durum, hata = _json_istek(sunucu, "GET", "/api/rapor")
    assert durum == 400
    assert "zorunlu" in hata["hata"]

    durum, hata = _json_istek(sunucu, "GET", "/api/rapor?ay=2026-1")
    assert durum == 400


@pytest.mark.parametrize("tutar", ["1.234", "-5", "abc", "0"])
def test_gecersiz_tutar_400_ve_kayit_olusmaz(sunucu, tutar):
    durum, hata = _json_istek(
        sunucu, "POST", "/api/harcamalar", {"tutar": tutar, "kategori": "market"}
    )
    assert durum == 400
    assert hata["hata"]

    _, liste = _json_istek(sunucu, "GET", "/api/harcamalar")
    assert liste["harcamalar"] == []


def test_ondalikli_json_sayisi_ve_eksik_alan_400(sunucu):
    durum, hata = _json_istek(sunucu, "POST", "/api/harcamalar", {"tutar": 150.5, "kategori": "market"})
    assert durum == 400
    assert "metin" in hata["hata"]

    durum, hata = _json_istek(sunucu, "POST", "/api/harcamalar", {"kategori": "market"})
    assert durum == 400
    assert "zorunlu" in hata["hata"]

    durum, hata = _json_istek(sunucu, "POST", "/api/harcamalar", {"tutar": "10", "kategori": ""})
    assert durum == 400
    assert "boş" in hata["hata"]


def test_bozuk_veya_bos_govde_400(sunucu):
    durum, _, ham = _ham_istek(sunucu, "POST", "/api/harcamalar", b"{bozuk")
    assert durum == 400
    assert "JSON" in json.loads(ham)["hata"]

    durum, _, ham = _ham_istek(sunucu, "POST", "/api/harcamalar", b"[1, 2]")
    assert durum == 400

    durum, _, _ = _ham_istek(sunucu, "POST", "/api/harcamalar")
    assert durum == 400


def test_bilinmeyen_yol_404(sunucu):
    durum, hata = _json_istek(sunucu, "GET", "/api/yok")
    assert durum == 404
    assert "Bulunamadı" in hata["hata"]


def test_export_csv_cli_ile_ayni_bicimde(sunucu, tmp_path: Path):
    _ekle(sunucu, "150.50", "market", "2026-10-05", "haftalık, alışveriş")
    _ekle(sunucu, "1234", "kira", "2026-10-01")

    durum, basliklar, ham = _ham_istek(sunucu, "GET", "/export.csv")
    assert durum == 200
    assert basliklar.get_content_type() == "text/csv"
    assert "attachment" in basliklar.get("Content-Disposition", "")

    cli_dosya = tmp_path / "cli.csv"
    veritabani = Veritabani(str(tmp_path / "test.db"))
    try:
        csv_yaz(veritabani, str(cli_dosya))
    finally:
        veritabani.kapat()
    assert ham == cli_dosya.read_bytes()

    satirlar = list(csv.reader(io.StringIO(ham.decode("utf-8"), newline="")))
    assert satirlar[0] == ["id", "tarih", "kategori", "tutar", "aciklama"]
    assert satirlar[1][2:] == ["kira", "1.234,00", ""]
    assert satirlar[2][2:] == ["market", "150,50", "haftalık, alışveriş"]


def test_csv_ay_filtresi_ve_bos_sonuc(sunucu):
    durum, basliklar, ham = _ham_istek(sunucu, "GET", "/export.csv?ay=2026-10")
    assert durum == 200
    assert ham.decode("utf-8").strip() == "id,tarih,kategori,tutar,aciklama"

    _ekle(sunucu, "5", "market", "2026-09-30")
    durum, _, ham = _ham_istek(sunucu, "GET", "/export.csv?ay=2026-10")
    assert ham.decode("utf-8").strip() == "id,tarih,kategori,tutar,aciklama"
