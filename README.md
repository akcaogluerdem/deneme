# harcama

Komut satırından harcama takibi. Yalnızca Python standart kütüphanesi kullanılır (Python 3.8+).

## Kullanım

```sh
python3 -m harcama ekle 12.50 market --tarih 2024-03-15 --aciklama "süt"
python3 -m harcama listele --kategori market --ay 2024-03
python3 -m harcama sil 1
```

Kayıtlar varsayılan olarak `harcamalar.json` dosyasında tutulur; `--dosya` seçeneği
ya da `HARCAMA_DOSYA` ortam değişkeniyle değiştirilebilir.

## Hata mesajları

Hatalı girişte araç Türkçe bir mesaj yazar ve 1 koduyla çıkar:

| Durum | Örnek mesaj |
|---|---|
| Negatif tutar | `Hata: Geçersiz tutar: -5. Tutar negatif olamaz, sıfırdan büyük olmalı.` |
| Sıfır tutar | `Hata: Geçersiz tutar: 0. Tutar sıfırdan büyük olmalı.` |
| Geçersiz tarih | `Hata: Geçersiz tarih: '2024-02-30'. Tarih YYYY-AA-GG biçiminde ve takvimde var olan bir gün olmalı (örnek: 2024-03-15).` |
| Olmayan id | `Hata: 42 numaralı kayıt bulunamadı. Mevcut kayıtları görmek için 'listele' komutunu kullanın.` |

## Test

```sh
make test
```
