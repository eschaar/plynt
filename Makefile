# Makefile for plynth
#
# Targets:
#   make              - show help
#   make install      - create .venv and install all dev dependencies
#   make clean        - remove build artifacts
#   make lint         - run all linters
#   make lint-fix     - auto-fix ruff lint issues
#   make format       - auto-format code and markdown
#   make format-check - verify formatting without modifying files
#   make markdown-format - format markdown via pre-commit
#   make markdown-lint   - lint markdown via pre-commit
#   make check        - full local quality gate (format-check + lint + test)
#   make pre-commit-install - install git pre-commit hooks
#   make test         - run all linters + unit tests
#   make test-all     - run tests across all Python versions via tox
#   make coverage     - run tests with HTML coverage report
#   make build        - build sdist and wheel into dist/
#   make publish      - upload to PyPI (requires PYPI_TOKEN or ~/.pypirc)
#   make publish-test - upload to TestPyPI for validation
#   make version      - show current version from setuptools_scm

PYTHON     := python
VENV       := .venv
VENV_BIN   := $(VENV)/bin
PIP        := $(VENV_BIN)/pip
PYTEST     := $(VENV_BIN)/pytest
RUFF       := $(VENV_BIN)/ruff
MYPY       := $(VENV_BIN)/mypy
TWINE      := $(VENV_BIN)/twine
BUILD      := $(VENV_BIN)/python -m build
TOX        := $(VENV_BIN)/tox

SRC        := src tests

# ---------------------------------------------------------------------------
# Default target
# ---------------------------------------------------------------------------

.PHONY: help
help:
	@echo ""
	@echo "Usage: make <target>"
	@echo ""
	@echo "  install       Create .venv and install all dev dependencies"
	@echo "  clean         Remove build artifacts (keeps .venv)"
	@echo "  purge         Remove build artifacts and .venv (full clean)"
	@echo "  lint          Run all linters (ruff, mypy)"
	@echo "  lint-fix      Auto-fix ruff lint issues"
	@echo "  format        Auto-format source code and markdown"
	@echo "  format-check  Verify formatting without modifying files"
	@echo "  markdown-format  Format markdown via pre-commit"
	@echo "  markdown-lint    Lint markdown via pre-commit"
	@echo "  check         Full local quality gate (format-check + lint + test)"
	@echo "  pre-commit-install  Install git pre-commit hooks"
	@echo "  test          Run linters + tests"
	@echo "  test-all      Run tests across Python 3.11, 3.12, 3.13 via tox"
	@echo "  unittests     Run pytest only"
	@echo "  coverage      Run tests with HTML coverage report"
	@echo "  build         Build sdist and wheel into dist/"
	@echo "  publish       Upload to PyPI  (set PYPI_TOKEN or use ~/.pypirc)"
	@echo "  publish-test  Upload to TestPyPI for validation"
	@echo "  version       Show current version from setuptools_scm"
	@echo ""

# ---------------------------------------------------------------------------
# Environment
# ---------------------------------------------------------------------------

.venv:
	$(PYTHON) -m venv $(VENV)
	$(PIP) install --upgrade pip
	$(PIP) install -e .[dev]

.PHONY: install
install:
	@if [ ! -d "$(VENV)" ]; then $(PYTHON) -m venv $(VENV); fi
	$(PIP) install --upgrade pip
	$(PIP) install -e .[dev]

.PHONY: pre-commit-install
pre-commit-install: .venv
	$(VENV_BIN)/pre-commit install

# ---------------------------------------------------------------------------
# Cleaning
# ---------------------------------------------------------------------------

.PHONY: pyclean
pyclean:
	find . -name "*.pyc" -delete
	find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
	rm -rf *.egg-info src/*.egg-info
	rm -rf build dist
	rm -rf coverage*.xml .coverage .coverage.* htmlcov
	rm -rf junit*.xml .pytest_cache
	rm -rf .mypy_cache .ruff_cache

.PHONY: clean
clean: pyclean

.PHONY: purge
purge: clean
	rm -rf $(VENV)

# ---------------------------------------------------------------------------
# Linting
# ---------------------------------------------------------------------------

.PHONY: lint
lint: lint/ruff lint/mypy

.PHONY: lint/ruff
lint/ruff: .venv
	$(RUFF) check $(SRC)

.PHONY: lint/mypy
lint/mypy: .venv
	$(MYPY) $(SRC)

# ---------------------------------------------------------------------------
# Formatting
# ---------------------------------------------------------------------------

.PHONY: format
format: format/ruff markdown-format

.PHONY: format/ruff
format/ruff: .venv
	$(RUFF) format $(SRC)

.PHONY: format-check
format-check: .venv
	$(RUFF) format --check $(SRC)

.PHONY: lint-fix
lint-fix: .venv
	$(RUFF) check --fix $(SRC)

.PHONY: markdown-format
markdown-format: .venv
	$(VENV_BIN)/pre-commit run mdformat --all-files || true

.PHONY: markdown-lint
markdown-lint: .venv
	$(VENV_BIN)/pre-commit run markdownlint --all-files
# ---------------------------------------------------------------------------
# Testing
# ---------------------------------------------------------------------------

.PHONY: check
check: format-check markdown-lint lint unittests

.PHONY: test
test: pyclean lint unittests

.PHONY: test-all
test-all: .venv
	$(TOX)

.PHONY: unittests
unittests: .venv
	$(PYTEST)

.PHONY: coverage
coverage: .venv
	$(PYTEST) --cov=src/plynth --cov-report=html --cov-report=term-missing
	@echo ""
	@echo "Coverage report: htmlcov/index.html"

# ---------------------------------------------------------------------------
# Build and release
# ---------------------------------------------------------------------------

.PHONY: build
build: clean .venv
	$(BUILD)
	$(TWINE) check dist/*

.PHONY: version
version: .venv
	$(VENV_BIN)/python -m setuptools_scm

# NOTE: Releases are intended to be triggered via GitHub Actions.
# Use 'make publish' for manual releases to PyPI only when needed.
# Set PYPI_TOKEN env var or configure ~/.pypirc before publishing.

.PHONY: publish
publish: build
	@echo "Publishing to PyPI..."
ifdef PYPI_TOKEN
	$(TWINE) upload --username __token__ --password $(PYPI_TOKEN) dist/*
else
	$(TWINE) upload dist/*
endif

# NOTE: Use publish-test to validate packaging against TestPyPI first.
# Register at https://test.pypi.org and set TEST_PYPI_TOKEN.

.PHONY: publish-test
publish-test: build
	@echo "Publishing to TestPyPI..."
ifdef TEST_PYPI_TOKEN
	$(TWINE) upload --repository testpypi --username __token__ --password $(TEST_PYPI_TOKEN) dist/*
else
	$(TWINE) upload --repository testpypi dist/*
endif
