"""Veri katmanı ve doğrulama testleri."""

from datetime import date
from decimal import Decimal

import pytest

from harcama_takip.rapor import yuzde_hesapla
from harcama_takip.veri import (
    HarcamaBulunamadi,
    HarcamaHatasi,
    Veritabani,
    ay_dogrula,
    kategori_dogrula,
    kurus_metni,
    tarih_dogrula,
    tutar_ayristir,
    varsayilan_db_yolu,
)


@pytest.fixture
def db(tmp_path):
    veritabani = Veritabani(tmp_path / "test.db")
    yield veritabani
    veritabani.kapat()


# --- tutar ---------------------------------------------------------------


def test_tutar_noktali_metin_kurus_olarak_ayristirilir():
    assert tutar_ayristir("150.50") == 15050


def test_tutar_virgullu_metin_de_kabul_edilir():
    assert tutar_ayristir("150,5") == 15050


def test_tutar_en_kucuk_pozitif_kurus_sinirinda_calisir():
    assert tutar_ayristir("0.01") == 1


def test_tutar_sondaki_sifirli_kurus_tamsayi_kalir():
    assert tutar_ayristir("0.010") == 1


@pytest.mark.parametrize("girdi", ["0", "0.00", "-5", "-0.01"])
def test_sifir_ve_negatif_tutar_reddedilir(girdi):
    with pytest.raises(HarcamaHatasi, match="sıfırdan büyük"):
        tutar_ayristir(girdi)


def test_kurustan_fazla_hassasiyet_sessizce_yuvarlanmaz():
    with pytest.raises(HarcamaHatasi, match="2 ondalık"):
        tutar_ayristir("1.234")


def test_cok_hassas_ondalik_sessizce_yuvarlanmaz():
    # 30 anlamlı basamak: varsayılan 28 basamaklık bağlamda kuruş farkı yutulurdu.
    with pytest.raises(HarcamaHatasi, match="2 ondalık"):
        tutar_ayristir("1.00000000000000000000000000001")


def test_cok_hassas_ama_sondasi_sifir_olan_tutar_kabul_edilir():
    assert tutar_ayristir("1.00000000000000000000000000000") == 100


@pytest.mark.parametrize("girdi", ["abc", "", "NaN", "Infinity", "12,3,4"])
def test_bozuk_tutar_metinleri_reddedilir(girdi):
    with pytest.raises(HarcamaHatasi, match="Geçersiz tutar"):
        tutar_ayristir(girdi)


def test_kuruş_metni_turkce_biçimlenir():
    assert kurus_metni(123450) == "1.234,50"
    assert kurus_metni(5) == "0,05"
    assert kurus_metni(0) == "0,00"


def test_onluk_toplamlar_float_hatasi_olmadan_tam_toplanir(db):
    # 0.10 + 0.10 + 0.10 float'ta 0.30000000000000004 verir; kuruşta tam 30 olmalı.
    for _ in range(3):
        db.ekle("0.10", "market")
    toplam = sum(k.tutar_kurus for k in db.listele())
    assert toplam == 30
    assert kurus_metni(toplam) == "0,30"


# --- tarih, ay, kategori --------------------------------------------------


def test_tarih_verilmezse_bugun_doner():
    assert tarih_dogrula(None) == date.today().isoformat()


def test_gecerli_tarih_oldugu_gibi_doner():
    assert tarih_dogrula("2026-10-20") == "2026-10-20"


@pytest.mark.parametrize("girdi", ["2026-02-30", "2026-13-01", "20261020", "20.10.2026"])
def test_gecersiz_tarih_reddedilir(girdi):
    with pytest.raises(HarcamaHatasi, match="tarih"):
        tarih_dogrula(girdi)


def test_ay_dogrulama_sinirlari():
    assert ay_dogrula("2026-10") == "2026-10"
    assert ay_dogrula(None) is None
    with pytest.raises(HarcamaHatasi, match="Ay 01 ile 12"):
        ay_dogrula("2026-13")
    with pytest.raises(HarcamaHatasi, match="Geçersiz ay"):
        ay_dogrula("2026/10")


def test_kategori_kirpilir_ve_kucuk_harfe_cevrilir():
    assert kategori_dogrula("  Market ") == "market"


@pytest.mark.parametrize("girdi", [None, "", "   "])
def test_bos_kategori_reddedilir(girdi):
    with pytest.raises(HarcamaHatasi, match="boş olamaz"):
        kategori_dogrula(girdi)


# --- depo ----------------------------------------------------------------


def test_ekle_ve_ay_ile_kategori_filtreleri(db):
    db.ekle("150.50", "market", "2026-10-20", "haftalık alışveriş")
    db.ekle("80", "ulaşım", "2026-10-21")
    db.ekle("42.00", "market", "2026-09-30")

    ekim = db.listele(ay="2026-10")
    assert [k.tutar_kurus for k in ekim] == [15050, 8000]

    marketler = db.listele(kategori="market")
    assert len(marketler) == 2
    assert db.listele(ay="2026-10", kategori="market")[0].aciklama == "haftalık alışveriş"


def test_tarih_verilmezse_bugun_kaydedilir(db):
    kayit = db.ekle("10", "kahve")
    assert kayit.tarih == date.today().isoformat()


def test_olmayan_id_silinince_hata_verilir(db):
    with pytest.raises(HarcamaBulunamadi, match="999 numaralı"):
        db.sil(999)


def test_var_olan_kayit_silinir(db):
    kayit = db.ekle("10", "kahve", "2026-10-01")
    db.sil(kayit.id)
    assert db.listele() == []


def test_veritabani_yolu_ortam_degiskeninden_okunur(monkeypatch, tmp_path):
    hedef = tmp_path / "ortam.db"
    monkeypatch.setenv("HARCAMA_DB", str(hedef))
    assert varsayilan_db_yolu() == str(hedef)
    veritabani = Veritabani()
    veritabani.ekle("5", "test", "2026-01-01")
    veritabani.kapat()
    assert hedef.exists()


# --- rapor ---------------------------------------------------------------


def test_yuzde_iki_ondalikla_yuvarlanir():
    assert yuzde_hesapla(1, 3) == Decimal("33.33")
    assert yuzde_hesapla(2, 3) == Decimal("66.67")


def test_sifir_toplamda_yuzde_sifir_doner():
    assert yuzde_hesapla(0, 0) == Decimal("0.00")


def test_cok_cumleli_uctan_uca_akis(tmp_path, capsys):
    from harcama_takip.cli import ana

    veritabani_yolu = str(tmp_path / "akis.db")
    csv_yolu = tmp_path / "cikti.csv"

    def calistir(*argv):
        return ana(["--db", veritabani_yolu, *argv])

    assert calistir("add", "--tutar", "150.50", "--kategori", "market",
                    "--tarih", "2026-10-20", "--aciklama", "haftalık alışveriş") == 0
    assert calistir("add", "--tutar", "349.50", "--kategori", "fatura",
                    "--tarih", "2026-10-05", "--aciklama", "elektrik faturası. Ödendi.") == 0
    assert calistir("add", "--tutar", "0.50", "--kategori", "market",
                    "--tarih", "2026-10-22") == 0
    capsys.readouterr()

    assert calistir("report", "--ay", "2026-10") == 0
    rapor_ciktisi = capsys.readouterr().out
    # 349.50 / 500.50 = %69.83 ; 151.00 / 500.50 = %30.17
    assert "fatura" in rapor_ciktisi and "69.83%" in rapor_ciktisi
    assert "market" in rapor_ciktisi and "30.17%" in rapor_ciktisi
    assert "Genel toplam: 500,50 TL" in rapor_ciktisi

    assert calistir("export", "--format", "csv", "--dosya", str(csv_yolu)) == 0
    satirlar = csv_yolu.read_text(encoding="utf-8").splitlines()
    assert satirlar[0] == "id,tarih,kategori,tutar,aciklama"
    assert len(satirlar) == 4
