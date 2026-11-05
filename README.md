# harcama-takip

Python ile yazılmış, SQLite veritabanında veri tutan komut satırı harcama takip uygulaması.

- Tutarlar `Decimal` ile ayrıştırılır ve veritabanında tamsayı kuruş olarak saklanır; float kullanılmaz.
- Veritabanı yolu `--db` parametresi ya da `HARCAMA_DB` ortam değişkeni ile değiştirilebilir (varsayılan: `harcamalar.db`).

## Kurulum

Python 3.9 veya üzeri gerekir.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt   # pytest
pip install -e .                  # isteğe bağlı: paketi kurar
```

## Kullanım

Uygulama `python -m harcama_takip` ile çalışır.

```bash
# Harcama ekle (tarih verilmezse bugün kullanılır; ondalık ayracı nokta ya da virgül olabilir)
python -m harcama_takip add --tutar 150.50 --kategori market --tarih 2026-10-20 --aciklama "haftalık alışveriş"

# Listele, ay ve/veya kategoriye göre filtrele
python -m harcama_takip list
python -m harcama_takip list --ay 2026-10 --kategori market

# Sil (id ile)
python -m harcama_takip delete 3

# Aylık rapor: kategori toplamları, yüzdeler ve genel toplam
python -m harcama_takip report --ay 2026-10

# CSV'ye aktar
python -m harcama_takip export --format csv --dosya cikti.csv

# Yardım
python -m harcama_takip --help
```

Veritabanını geçici bir dosyaya yönlendirmek için:

```bash
HARCAMA_DB=/tmp/deneme.db python -m harcama_takip list
# veya
python -m harcama_takip --db /tmp/deneme.db list
```

Hatalı girdilerde (sıfır ya da negatif tutar, geçersiz tarih, olmayan id vb.) uygulama
Türkçe bir hata mesajı yazar ve sıfırdan farklı bir çıkış koduyla (`1`) sonlanır.

## Testler

Testler depo kökünden çalıştırılır:

```bash
python3 -m pytest -q
```

Testler geçici bir veritabanı dosyası kullanır; gerçek veritabanınıza dokunmaz.

## Proje yapısı

```
harcama_takip/
  __init__.py   sürüm bilgisi
  __main__.py   giriş noktası (python -m harcama_takip)
  cli.py        argparse tabanlı komutlar ve CSV dışa aktarımı
  veri.py       tutar/tarih/kategori doğrulama ve SQLite deposu
  rapor.py      aylık kategori raporu ve yüzde hesabı
tests/
  test_veri.py  veri katmanı ve uçtan uca akış testleri
  test_cli.py   komut satırı ve rapor testleri
```
