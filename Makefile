PYTHON ?= python
INFRA ?= infra.yml
OUTPUT ?= .gitlab-ci-generated.yml

.DEFAULT_GOAL := all

.PHONY: all install install-dev validate generate lint lint-ruff pylint lint-fix format format-check typecheck check help

all: install
	$(MAKE) generate

install:
	$(PYTHON) -m pip install -e .

install-dev:
	$(PYTHON) -m pip install -r requirements-dev.txt -e .

lint: lint-ruff pylint

lint-ruff:
	$(PYTHON) -m ruff check .

pylint:
	$(PYTHON) -m pylint infra_to_gitlab.py infra_actions

lint-fix:
	$(PYTHON) -m ruff check --fix .

format:
	$(PYTHON) -m ruff format .

format-check:
	$(PYTHON) -m ruff format --check .

typecheck:
	$(PYTHON) -m mypy

check: lint format-check typecheck validate

validate:
	$(PYTHON) -m infra_to_gitlab validate "$(INFRA)"

generate: validate
	$(PYTHON) -m infra_to_gitlab generate "$(INFRA)" --output "$(OUTPUT)"

help:
	@echo "make          - Installer les dependances et generer GitLab CI"
	@echo "make install  - Installer les dependances Python"
	@echo "make install-dev - Installer les outils de developpement"
	@echo "make lint     - Verifier le code avec Ruff et Pylint"
	@echo "make lint-ruff - Verifier le code avec Ruff"
	@echo "make pylint   - Verifier le code avec Pylint"
	@echo "make lint-fix - Corriger les erreurs Ruff corrigeables"
	@echo "make format   - Formater le code avec Ruff"
	@echo "make format-check - Verifier le formatage"
	@echo "make typecheck - Verifier les types avec mypy"
	@echo "make check    - Lint, formatage, types et validation du manifeste"
	@echo "make validate - Valider le manifeste avec Pydantic"
	@echo "make generate - Convertir infra.yml en .gitlab-ci-generated.yml"
	@echo "Variables     - PYTHON=python INFRA=infra.yml OUTPUT=.gitlab-ci-generated.yml"
