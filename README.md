# harcama-takip

SQLite tabanlı, komut satırından kullanılan basit bir harcama takip uygulaması.
Dış bağımlılığı yoktur; yalnızca Python 3.8+ standart kütüphanesini kullanır.

## Kurulum

Depo kökünde:

```sh
pip install .
```

Geliştirme için düzenlenebilir kurulum:

```sh
pip install -e .
```

Kurulum `harcama-takip` komutunu tanımlar. Kurmadan da çalıştırabilirsiniz:

```sh
python3 -m harcama_takip --help
```

## Veritabanı

Veriler varsayılan olarak `~/.harcama_takip.db` SQLite dosyasında saklanır.
Yolu `HARCAMA_TAKIP_DB` ortam değişkeniyle ya da her komuttan önce verilen
`--db` seçeneğiyle değiştirebilirsiniz:

```sh
HARCAMA_TAKIP_DB=/tmp/harcamalar.db harcama-takip list
harcama-takip --db /tmp/harcamalar.db list
```

Tutarlar veritabanında tamsayı kuruş olarak tutulur; yuvarlama hatası olmaz.

## Kullanım

```sh
harcama-takip add --tutar 150.50 --kategori market --tarih 2026-10-20 --aciklama "haftalık alışveriş"
harcama-takip add --tutar 45 --kategori ulasim --aciklama "taksi"
harcama-takip list
harcama-takip list --ay 2026-10 --kategori market
harcama-takip report --ay 2026-10
harcama-takip export --format csv --dosya cikti.csv
harcama-takip delete 1
```

### Komutlar

| Komut | Açıklama |
|-------|----------|
| `add` | Yeni harcama ekler. `--tutar` ve `--kategori` zorunludur; `--tarih` (YYYY-AA-GG) verilmezse bugünün tarihi kullanılır; `--aciklama` isteğe bağlıdır. |
| `list` | Harcamaları listeler. `--ay` (YYYY-AA) ve `--kategori` ile filtrelenebilir. |
| `delete` | Verilen kimlikteki (`id`) harcamayı siler. |
| `report` | `--ay` için kategori bazında toplamları, yüzdeleri ve aylık genel toplamı gösterir. |
| `export` | Harcamaları `--dosya` ile verilen dosyaya `--format csv` biçiminde aktarır; `--ay` ve `--kategori` filtreleri de kullanılabilir. |

### Doğrulama ve çıkış kodları

- Negatif ya da sıfır tutar, ikiden fazla ondalık basamak, geçersiz tarih/ay,
  boş kategori, bulunamayan kayıt ve desteklenmeyen biçim anlaşılır bir
  `Hata: ...` mesajıyla reddedilir.
- Çıkış kodları: başarıda `0`, kullanıcı hatasında `1`, komut satırı sözdizimi
  hatasında `2`.

## Testler

```sh
python3 -m pytest -q
# ya da
python3 -m unittest discover -s tests -t . -v
```
