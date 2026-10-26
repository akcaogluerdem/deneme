# harcama

Komut satırından harcama kaydı tutan, bağımlılıksız (yalnızca Python 3.9+
standart kütüphanesi) küçük bir araç.

## Kullanım

```sh
python3 -m harcama add --tutar 150.50 --kategori market --tarih 2026-10-20 --aciklama "haftalık alışveriş"
```

| Seçenek      | Zorunlu | Açıklama                                   |
|--------------|---------|--------------------------------------------|
| `--tutar`    | evet    | Pozitif tutar; `150.50` ya da `150,50`     |
| `--kategori` | evet    | Serbest kategori adı (örn. `market`)       |
| `--tarih`    | hayır   | `YYYY-AA-GG`; verilmezse bugünün tarihi    |
| `--aciklama` | hayır   | Serbest açıklama                           |

Kayıtlar çalışma dizinindeki `harcamalar.json` dosyasına yazılır. Farklı bir
dosya için `HARCAMA_DOSYASI` ortam değişkenini kullanın.

## Geliştirme

```sh
make test   # birim testleri
make run    # örnek kayıt ekler
```
