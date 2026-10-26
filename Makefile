PYTHON ?= python3

.PHONY: test calistir

test:
	$(PYTHON) -m unittest discover -s tests -t .

calistir:
	$(PYTHON) -m harcama listele
