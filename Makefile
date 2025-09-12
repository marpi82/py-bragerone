PY=python3
PIP=.venv/bin/pip
RUN=.venv/bin/python
ACT=. .venv/bin/activate

.PHONY: help
help:
	@echo "Targets:"
	@echo "  make venv          - create local venv"
	@echo "  make dev           - install dev+test+docs extras + pre-commit"
	@echo "  make lint          - ruff + isort + black --check + mypy"
	@echo "  make fmt           - ruff --fix + isort + black"
	@echo "  make test          - pytest (with coverage)"
	@echo "  make docs-serve    - sphinx-autobuild (optional, else just build)"
	@echo "  make docs-build    - build Sphinx docs (HTML)"
	@echo "  make dist          - build wheel+sdist"
	@echo "  make zip           - create source zip archive"
	@echo "  make publish-test  - upload to TestPyPI"
	@echo "  make publish       - upload to PyPI"
	@echo "  make all           - fmt + lint + test + dist"

.venv:
	$(PY) -m venv .venv
	$(PIP) install --upgrade pip build

venv: .venv

dev: venv
	$(PIP) install .[dev,test,docs]
	. .venv/bin/activate && pre-commit install

lint:
	. .venv/bin/activate && ruff check .
	. .venv/bin/activate && black --check .
	. .venv/bin/activate && isort --check-only .
	. .venv/bin/activate && mypy src

fmt:
	. .venv/bin/activate && ruff check . --fix
	. .venv/bin/activate && isort .
	. .venv/bin/activate && black .

test:
	. .venv/bin/activate && pytest

docs-build:
	. .venv/bin/activate && sphinx-build -b html docs docs/_build/html

# live-reload: pip install sphinx-autobuild
docs-serve:
	. .venv/bin/activate && sphinx-autobuild docs docs/_build/html

dist:
	. .venv/bin/activate && python -m build

zip:
	git ls-files > /tmp/_files && zip -@ bragerone-src.zip < /tmp/_files && rm /tmp/_files
	@echo "Created bragerone-src.zip"

publish-test: dist
	. .venv/bin/activate && $(PIP) install twine && twine upload --repository testpypi dist/*

publish: dist
	. .venv/bin/activate && $(PIP) install twine && twine upload dist/*
