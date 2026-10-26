.DEFAULT_GOAL := help

.PHONY: help setup run check clean

help: ## Kullanılabilir hedefleri listeler
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-8s %s\n", $$1, $$2}'

setup: ## Geliştirme ortamını hazırlar (henüz bağımlılık yok)
	@echo "Kurulacak bağımlılık yok; ortam hazır."

run: ## Projeyi çalıştırır (henüz uygulama kodu yok)
	@echo "deneme: çalıştırılacak uygulama henüz tanımlanmadı."

check: ## Proje iskeletinin eksiksiz olduğunu doğrular
	@test -f README.md && test -f Makefile && test -f .gitignore && test -f .context/index.yaml
	@echo "İskelet tamam."

clean: ## Üretilmiş geçici dosyaları siler
	@rm -rf build dist tmp
