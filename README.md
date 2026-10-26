# harcama

Yalnızca Python standart kütüphanesiyle yazılmış basit harcama takip aracı.
Kayıtlar CSV dosyasında tutulur (varsayılan `harcamalar.csv`; `--dosya` ya da
`HARCAMA_DOSYA` ile değiştirilebilir).

## Kullanım

```sh
python3 -m harcama add 120.50 market --tarih 2026-10-03 --aciklama "haftalık"
python3 -m harcama list --ay 2026-10
python3 -m harcama report --ay 2026-10
```

`report --ay YYYY-AA` kategori bazında toplamları, her kategorinin aylık
toplama oranını (yüzde) ve aylık genel toplamı yazar:

```
Rapor: 2026-10
Kategori              Toplam    Yüzde
market                 90.00    75.0%
kahve                  30.00    25.0%
GENEL TOPLAM          120.00   100.0%
```

## Geliştirme

```sh
make test
```
