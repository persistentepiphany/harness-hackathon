PY ?= .venv/bin/python

.PHONY: install check lint type test doctor

install:
	uv pip install --python $(PY) -e ".[all,dev]"

lint:
	$(PY) -m ruff check .
	$(PY) -m ruff format --check .

type:
	$(PY) -m mypy

test:
	$(PY) -m pytest -m "not network"

check: lint type test

doctor:
	.venv/bin/pah doctor
