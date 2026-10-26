PYTHON ?= python3

.PHONY: help test run clean

help:
	@echo "make test   - birim testlerini çalıştır"
	@echo "make run    - örnek bir harcama ekle"
	@echo "make clean  - önbellek dosyalarını sil"

test:
	$(PYTHON) -m unittest discover -s tests -t . -v

run:
	$(PYTHON) -m harcama add --tutar 150.50 --kategori market --tarih 2026-10-20 --aciklama "haftalık alışveriş"

clean:
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
