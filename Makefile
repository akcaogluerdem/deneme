PYTHON ?= python3

.PHONY: test run clean

test:
	$(PYTHON) -m unittest discover -s tests -t .

run:
	$(PYTHON) -m harcama $(ARGS)

clean:
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
