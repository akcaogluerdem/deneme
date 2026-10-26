# deneme

Yeni başlatılmış bir proje iskeleti. Dil ve çatı henüz seçilmedi; ortak
işler `Makefile` hedefleri üzerinden yürür.

## Gereksinimler

- `git`
- `make` (macOS'ta Xcode Command Line Tools ile gelir: `xcode-select --install`)

## Kurulum

```sh
git clone <depo-adresi> deneme
cd deneme
make setup
```

## Çalıştırma

```sh
make run
```

## Doğrulama

İskeletin eksiksiz olduğunu denetler:

```sh
make check
```

## Make hedefleri

| Hedef   | Açıklama                                   |
|---------|--------------------------------------------|
| `help`  | Kullanılabilir hedefleri listeler (varsayılan) |
| `setup` | Geliştirme ortamını hazırlar               |
| `run`   | Projeyi çalıştırır                         |
| `check` | Proje iskeletini doğrular                  |
| `clean` | Üretilmiş geçici dosyaları siler           |

## Dizin yapısı

```
.
├── .context/index.yaml   # Proje bağlam dizini
├── .gitignore
├── Makefile
└── README.md
```
