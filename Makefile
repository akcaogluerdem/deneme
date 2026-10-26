.PHONY: check

check:
	@test -f README.md
	@test -f Makefile
	@test -f .gitignore
	@test -f .context/index.yaml
	@echo "ok"
