# Makefile for plynt
#
# Targets:
#   make              - show help
#   make install      - create .venv and install all dev dependencies
#   make python-install - install .python-version interpreters using pyenv
#   make clean        - remove build artifacts
#   make purge        - remove build artifacts, .venv, and .tox
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
#   make salesforce-cdc-proto-generate - regenerate vendored Pub/Sub stub from the vendored .proto
#   make salesforce-cdc-proto-verify   - fail if regenerating would change committed stub files

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
	@echo "  python-install  Install local Python versions using existing pyenv"
	@echo "  clean         Remove build artifacts (keeps .venv)"
	@echo "  purge         Remove build artifacts, .venv, and .tox (full clean)"
	@echo "  lint          Run all linters (ruff, mypy)"
	@echo "  lint-fix      Auto-fix ruff lint issues"
	@echo "  format        Auto-format source code and markdown"
	@echo "  format-check  Verify formatting without modifying files"
	@echo "  markdown-format  Format markdown via pre-commit"
	@echo "  markdown-lint    Lint markdown via pre-commit"
	@echo "  check         Full local quality gate (format-check + lint + test)"
	@echo "  pre-commit-install  Install git pre-commit hooks"
	@echo "  test          Run linters + tests"
	@echo "  test-all      Run tests across Python 3.12-3.15 via tox"
	@echo "  unittests     Run pytest only"
	@echo "  coverage      Run tests with HTML coverage report"
	@echo "  build         Build sdist and wheel into dist/"
	@echo "  publish       Upload to PyPI  (set PYPI_TOKEN or use ~/.pypirc)"
	@echo "  publish-test  Upload to TestPyPI for validation"
	@echo "  version       Show current version from setuptools_scm"
	@echo "  salesforce-cdc-proto-generate  Regenerate vendored Salesforce Pub/Sub stub"
	@echo "  salesforce-cdc-proto-verify    Verify vendored stub matches the .proto"
	@echo ""

# ---------------------------------------------------------------------------
# Environment
# ---------------------------------------------------------------------------

.PHONY: python-install
python-install:
	@command -v pyenv >/dev/null 2>&1 || { \
		echo "pyenv is required; follow the Python bootstrap in CONTRIBUTING.md" >&2; \
		exit 1; \
	}
	@set -eu; while IFS= read -r version; do \
		pyenv install --skip-existing "$$version"; \
	done < .python-version
	pyenv rehash

.venv:
	$(PYTHON) -m venv $(VENV)
	$(PIP) install --upgrade 'pip>=26.2,<27'
	$(PIP) install -e '.[dev,httpx,grpc,salesforce,django,drf,fastapi]'

.PHONY: install
install:
	@if [ ! -d "$(VENV)" ]; then $(PYTHON) -m venv $(VENV); fi
	$(PIP) install --upgrade 'pip>=26.2,<27'
	$(PIP) install -e '.[dev,httpx,grpc,salesforce,django,drf,fastapi]'

# ---------------------------------------------------------------------------
# Salesforce CDC vendored Pub/Sub proto
#
# pubsub_api.proto is vendored, not hand-written (see _proto/SOURCE.md).
# Only re-run these targets after deliberately updating the vendored .proto;
# do not run this as part of every build/CI cycle.
# ---------------------------------------------------------------------------

PROTO_DIR := src/plynt/connectors/salesforce/cdc/_proto

.PHONY: salesforce-cdc-proto-generate
salesforce-cdc-proto-generate:
	$(VENV_BIN)/python -m grpc_tools.protoc \
		--proto_path=$(PROTO_DIR) \
		--python_out=$(PROTO_DIR) \
		--grpc_python_out=$(PROTO_DIR) \
		$(PROTO_DIR)/pubsub_api.proto
	@# protoc emits a bare `import pubsub_api_pb2`, which breaks once the file
	@# lives inside a package; rewrite it to a package-relative import.
	sed -i 's/^import pubsub_api_pb2 as pubsub__api__pb2$$/from . import pubsub_api_pb2 as pubsub__api__pb2/' \
		$(PROTO_DIR)/pubsub_api_pb2_grpc.py

.PHONY: salesforce-cdc-proto-verify
salesforce-cdc-proto-verify:
	@set -eu; \
	tmp=$$(mktemp -d); \
	trap 'rm -f "$$tmp/pubsub_api.proto" "$$tmp/pubsub_api_pb2.py" "$$tmp/pubsub_api_pb2_grpc.py"; rmdir "$$tmp"' EXIT; \
	cp $(PROTO_DIR)/pubsub_api.proto "$$tmp/"; \
	$(VENV_BIN)/python -m grpc_tools.protoc \
		--proto_path="$$tmp" --python_out="$$tmp" --grpc_python_out="$$tmp" \
		"$$tmp/pubsub_api.proto"; \
	sed -i 's/^import pubsub_api_pb2 as pubsub__api__pb2$$/from . import pubsub_api_pb2 as pubsub__api__pb2/' \
		"$$tmp/pubsub_api_pb2_grpc.py"; \
	if ! diff -q "$$tmp/pubsub_api_pb2.py" $(PROTO_DIR)/pubsub_api_pb2.py >/dev/null \
		|| ! diff -q "$$tmp/pubsub_api_pb2_grpc.py" $(PROTO_DIR)/pubsub_api_pb2_grpc.py >/dev/null; then \
		echo "Vendored Salesforce Pub/Sub stub is out of date; run 'make salesforce-cdc-proto-generate'"; \
		exit 1; \
	fi; \
	echo "Vendored Salesforce Pub/Sub stub is up to date."

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
	rm -rf .tox

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
	$(PYTEST) --cov=src/plynt --cov-report=html --cov-report=term-missing
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
