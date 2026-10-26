# harcama

Komut satırından harcama kaydetmek ve listelemek için küçük bir araç.
Yalnızca Python 3 standart kütüphanesini kullanır; ek bağımlılık yoktur.

## Kullanım

```sh
# Harcama ekle (tarih verilmezse bugün)
python3 -m harcama ekle 120 --kategori market --tarih 2026-10-01 --aciklama "haftalık alışveriş"

# Tümünü listele
python3 -m harcama list

# Aya ve/veya kategoriye göre süz
python3 -m harcama list --ay 2026-10
python3 -m harcama list --kategori market
python3 -m harcama list --ay 2026-10 --kategori market
```

- `--ay` biçimi `YYYY-AA` olmalıdır (örn. `2026-10`); geçersiz değer hata verir.
- `--kategori` büyük/küçük harf duyarsız eşleşir.
- Veriler varsayılan olarak `harcamalar.json` dosyasında tutulur; `--dosya` ya da
  `HARCAMA_DOSYA` ortam değişkeniyle değiştirilebilir.

## Geliştirme

```sh
make test   # birim testleri
make run    # kayıtları listele
make clean  # önbellekleri temizle
```
