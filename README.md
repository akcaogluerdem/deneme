# harcama

Harcama tutarlarını **kuruş hassasiyetinde** toplayan küçük bir Python paketi.
Bağımlılık yoktur; yalnızca standart kütüphane kullanılır.

## Neden kuruş?

`float` ile `0.1 + 0.2` işlemi `0.30000000000000004` verir. Bu paket her
tutarı tam sayı kuruş (`int`) olarak tutar; böylece toplamlar her zaman
kesindir.

```python
from harcama import topla, bicimle

bicimle(topla(["0,10", "0,20"]))  # '0,30'
```

- `kurusa_cevir("12,50")` → `1250` (virgül ya da nokta ayırıcı; en çok 2 ondalık)
- `topla([...])` → toplam kuruş (`int`)
- `bicimle(1250)` → `"12,50"`

İkiden fazla ondalık basamaklı tutarlar ve `float` değerler sessizce
yuvarlanmaz, `TutarHatasi` ile reddedilir.

## Komutlar

```sh
make test     # birim testleri
make temizle  # __pycache__ temizliği
```
