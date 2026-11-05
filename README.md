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

## Web arayüzü

Aynı veritabanını tarayıcıdan kullanmak için basit bir web arayüzü vardır. Yalnızca
Python standart kütüphanesi (`http.server` ve `json`) kullanır; ek bağımlılık gerektirmez.

```bash
python3 -m harcama_takip.web --port 8000
# veya veritabanını belirterek
python3 -m harcama_takip.web --port 8000 --db /tmp/deneme.db
```

Ardından tarayıcıdan **http://127.0.0.1:8000/** adresini açın. Varsayılan dinleme adresi
`127.0.0.1` (yalnızca bu makineden erişim) ve port `8000`'dir; `--host` ile değiştirilebilir.
Veritabanı yolu da CLI ile aynı kuralı izler: `--db`, yoksa `HARCAMA_DB`, yoksa `harcamalar.db`.
Sunucuyu durdurmak için terminalde `Ctrl+C` kullanın.

Arayüz üzerinden harcama ekleyebilir, ay ve kategoriye göre listeleyebilir, silebilir,
aylık raporu görebilir ve CSV dosyasını indirebilirsiniz.

API uç noktaları (JSON; tutarlar `tutar_kurus` tam sayısı ve `tutar` metni olarak döner):

| Yöntem   | Adres                                   | Açıklama                              |
|----------|-----------------------------------------|---------------------------------------|
| `GET`    | `/api/harcamalar[?ay=YYYY-AA&kategori=...]` | Harcamaları listeler            |
| `POST`   | `/api/harcamalar`                       | Harcama ekler (JSON gövde)            |
| `DELETE` | `/api/harcamalar/<id>`                  | Harcamayı siler                       |
| `GET`    | `/api/rapor?ay=YYYY-AA`                 | Aylık kategori raporu                 |
| `GET`    | `/export.csv[?ay=YYYY-AA&kategori=...]` | CSV dışa aktarma                      |

Rapor yüzdeleri `Decimal` metni olarak döner; API'de float kullanılmaz. Olmayan bir id
için `404` döner. Her istek kendi veritabanı bağlantısını açıp kapatır.

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
  web.py        standart kütüphane tabanlı web arayüzü ve JSON API'si
tests/
  test_veri.py          veri katmanı ve uçtan uca akış testleri
  test_cli.py           komut satırı ve rapor testleri
  test_web_api.py       web JSON API'si testleri
  test_web_arayuz.py    web arayüzü (HTML sayfası) testleri
```
