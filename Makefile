.DEFAULT_GOAL := help
PYTHON ?= python3
VENV ?= .venv
HOST ?= 0.0.0.0
PORT ?= 5000
PY := $(VENV)/bin/python
FLASK := $(PY) -m flask --app run:app

.PHONY: help setup env install run upgrade migrate current test check
help:
	@echo "make setup   — окружение, зависимости, .env и миграции"
	@echo "make run     — запуск приложения"
	@echo "make upgrade — применить миграции"
	@echo 'make migrate MESSAGE="описание" — создать миграцию'
	@echo "make current — версия базы; make test — тесты; make check — сверка схемы"

env:
	@test -f .env || cp .env.example .env
	@echo "Для автоперевода задайте DEEPL_API_KEY в .env"

$(PY):
	$(PYTHON) -m venv $(VENV)

install: $(PY)
	$(PY) -m pip install -r requirements.txt

setup: install env
	$(MAKE) upgrade

run: env $(PY)
	$(FLASK) run --host "$(HOST)" --port "$(PORT)" --no-debugger --no-reload

upgrade: env $(PY)
	$(FLASK) db upgrade

migrate: env $(PY)
	@test -n "$(MESSAGE)" || (echo 'Укажите MESSAGE="описание"'; exit 1)
	$(FLASK) db migrate -m "$(MESSAGE)"

current: $(PY)
	$(FLASK) db current

test: $(PY)
	$(PY) -m pytest

check: $(PY)
	$(FLASK) db check
