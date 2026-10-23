
.PHONY: install test lint typecheck validate ci

install:
	python -m pip install -e ".[dev,market-demo,hmm]"

test:
	pytest

lint:
	ruff check .

typecheck:
	mypy src/macrosignal

validate:
	python scripts/validate_project.py

ci: lint test validate
