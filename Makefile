PYTHON ?= python3

.PHONY: test temizle

test:
	$(PYTHON) -m unittest discover -s tests -t .

temizle:
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
