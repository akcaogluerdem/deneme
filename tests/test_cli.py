"""Komut satırı ve rapor testleri."""

from decimal import Decimal

import pytest

from harcama_takip.cli import ana
from harcama_takip.rapor import aylik_rapor, rapor_metni
from harcama_takip.veri import Veritabani


@pytest.fixture
def db_yolu(tmp_path):
    return str(tmp_path / "cli.db")


def _calistir(db_yolu, *argv):
    return ana(["--db", db_yolu, *argv])


def test_help_basarili_cikar(capsys):
    with pytest.raises(SystemExit) as cikis:
        ana(["--help"])
    assert cikis.value.code == 0
    assert "add" in capsys.readouterr().out


def test_add_negatif_tutarda_sifirdan_farkli_cikar(db_yolu, capsys):
    assert _calistir(db_yolu, "add", "--tutar", "-10", "--kategori", "market") == 1
    assert "sıfırdan büyük" in capsys.readouterr().err


def test_add_gecersiz_tarihte_hata_verir(db_yolu, capsys):
    assert _calistir(db_yolu, "add", "--tutar", "10", "--kategori", "market",
                     "--tarih", "2026-02-30") == 1
    assert "Geçersiz tarih" in capsys.readouterr().err


def test_olmayan_id_silinmeye_calisilinca_hata(db_yolu, capsys):
    assert _calistir(db_yolu, "delete", "424242") == 1
    assert "bulunamadı" in capsys.readouterr().err


def test_list_ay_ve_kategori_filtresini_uygular(db_yolu, capsys):
    _calistir(db_yolu, "add", "--tutar", "12.25", "--kategori", "market", "--tarih", "2026-10-02")
    _calistir(db_yolu, "add", "--tutar", "7", "--kategori", "kahve", "--tarih", "2026-10-03")
    _calistir(db_yolu, "add", "--tutar", "9", "--kategori", "market", "--tarih", "2026-11-01")
    capsys.readouterr()

    assert _calistir(db_yolu, "list", "--ay", "2026-10", "--kategori", "market") == 0
    cikti = capsys.readouterr().out
    assert "12,25" in cikti
    assert "kahve" not in cikti
    assert "2026-11-01" not in cikti


def test_delete_kaydi_kaldirir(db_yolu, capsys):
    _calistir(db_yolu, "add", "--tutar", "3", "--kategori", "simit", "--tarih", "2026-10-04")
    assert _calistir(db_yolu, "delete", "1") == 0
    assert _calistir(db_yolu, "list") == 0
    assert "Kayıt bulunamadı" in capsys.readouterr().out


def test_export_csv_kuruş_metni_ile_yazar(db_yolu, tmp_path):
    _calistir(db_yolu, "add", "--tutar", "1234.5", "--kategori", "kira", "--tarih", "2026-10-01",
              "--aciklama", "ekim, kirası")
    hedef = tmp_path / "cikti.csv"
    assert _calistir(db_yolu, "export", "--format", "csv", "--dosya", str(hedef)) == 0
    satirlar = hedef.read_text(encoding="utf-8").splitlines()
    assert satirlar[0] == "id,tarih,kategori,tutar,aciklama"
    assert satirlar[1] == '1,2026-10-01,kira,"1.234,50","ekim, kirası"'


def test_export_bilinmeyen_klasorde_hata_verir(db_yolu, tmp_path, capsys):
    hedef = tmp_path / "yok" / "cikti.csv"
    assert _calistir(db_yolu, "export", "--format", "csv", "--dosya", str(hedef)) == 1
    assert "Çıktı klasörü bulunamadı" in capsys.readouterr().err


def test_bos_ay_raporu_kayit_bulunamadi_der(db_yolu):
    db = Veritabani(db_yolu)
    rapor = aylik_rapor(db, "2026-05")
    db.kapat()
    assert rapor.genel_toplam_kurus == 0
    assert "Bu ayda kayıt bulunamadı" in rapor_metni(rapor)


def test_rapor_kategori_yuzde_ve_genel_toplam_hesaplar(db_yolu):
    db = Veritabani(db_yolu)
    db.ekle("100", "market", "2026-10-01")
    db.ekle("50", "market", "2026-10-02")
    db.ekle("50", "ulaşım", "2026-10-03")
    rapor = aylik_rapor(db, "2026-10")
    db.kapat()

    assert rapor.genel_toplam_kurus == 20000
    yuzdeler = {s.kategori: s.yuzde for s in rapor.satirlar}
    assert yuzdeler == {"market": Decimal("75.00"), "ulaşım": Decimal("25.00")}
    assert rapor.satirlar[0].kategori == "market"


def test_rapor_ayi_gecersizse_hata_verir(db_yolu, capsys):
    assert _calistir(db_yolu, "report", "--ay", "2026-00") == 1
    assert "Geçersiz ay" in capsys.readouterr().err
