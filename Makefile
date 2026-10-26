.PHONY: help check

help:
	@echo "Hedefler:"
	@echo "  check  - iskelet dosyalarinin varligini dogrular"

check:
	test -f README.md && test -f Makefile && test -f .gitignore && test -f .context/index.yaml
