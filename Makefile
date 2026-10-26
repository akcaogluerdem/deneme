.PHONY: help check clean

help:
	@echo "Hedefler:"
	@echo "  help   - bu yardımı gösterir"
	@echo "  check  - iskeletin temel dosyalarını doğrular"
	@echo "  clean  - üretilmiş çıktıları siler"

check:
	@test -f README.md && test -f Makefile && test -f .gitignore && test -f .context/index.yaml
	@echo "iskelet tamam"

clean:
	rm -rf build dist
