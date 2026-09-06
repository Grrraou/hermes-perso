# Hermes lifecycle. Data in ./data is never removed by these targets
# except `make destroy` (you must type "destroy" to confirm).
#
#   make up        start (creates ./data if missing)
#   make down      stop containers and network — keeps ./data
#   make build     pull image and recreate container — keeps ./data
#   make restart   restart the running container — keeps ./data
#   make destroy   wipe ./data after confirmation

SHELL := /bin/bash
.SHELLFLAGS := -eu -o pipefail -c

# Docker Desktop (same engine as citlog/erp/…) speaks API 1.43.
# Ubuntu's docker 29 client otherwise errors: "client version 1.52 is too new".
export DOCKER_API_VERSION ?= 1.43

# Use Compose v2 plugin, then the standalone binary. Override with COMPOSE=...
ifndef COMPOSE
COMPOSE := $(shell \
	if docker compose version >/dev/null 2>&1; then echo 'docker compose'; \
	elif command -v docker-compose >/dev/null && docker-compose version >/dev/null 2>&1; then echo docker-compose; \
	fi)
endif

.DEFAULT_GOAL := help

.PHONY: help init setup up down build restart logs chat ps voice destroy ensure-compose ensure-env ensure-data

help:
	@echo "make init      create .env and ./data (secrets printed once)"
	@echo "make setup     first-time Hermes wizard (writes into ./data)"
	@echo "make up        start gateway + dashboard + webui"
	@echo "make down      stop stack (keeps ./data)"
	@echo "make build     pull image and recreate (keeps ./data)"
	@echo "make restart   restart container (keeps ./data)"
	@echo "make logs      follow logs"
	@echo "make chat      interactive CLI inside the container"
	@echo "make ps        show status"
	@echo "make voice     reinstall local STT/TTS packages into ./data"
	@echo "make destroy   DELETE ./data (type destroy to confirm)"

init:
	@./scripts/init.sh

setup: ensure-compose ensure-data
	@test -f .env || ./scripts/init.sh
	$(COMPOSE) run --rm hermes setup

up: ensure-compose ensure-env ensure-data
	$(COMPOSE) up -d --remove-orphans

# Never pass --volumes / -v here. That flag is only used by `make destroy`.
down: ensure-compose
	$(COMPOSE) down --remove-orphans

# Official image has no local Dockerfile; "build" means refresh the image.
# --force-recreate replaces the container only. The ./data bind mount stays.
build: ensure-compose ensure-env ensure-data
	$(COMPOSE) pull
	$(COMPOSE) up -d --force-recreate --remove-orphans

restart: ensure-compose ensure-env ensure-data
	$(COMPOSE) up -d --no-recreate --remove-orphans
	$(COMPOSE) restart

logs: ensure-compose
	$(COMPOSE) logs -f

chat: ensure-compose
	$(COMPOSE) exec hermes hermes

ps: ensure-compose
	$(COMPOSE) ps

# Official post-setup needs pip; the image is sealed. Install into ./data so
# it survives recreate. Models download on first use into ./data/cache.
voice: ensure-compose
	$(COMPOSE) exec -u hermes -e HOME=/opt/data hermes \
		uv pip install --python /opt/hermes/.venv/bin/python3 \
		--target /opt/data/lazy-packages -U faster-whisper piper-tts
	$(COMPOSE) exec -u hermes hermes hermes tools enable stt --platform cli

destroy: ensure-compose
	@echo "This deletes sessions, memories, skills, and API keys in ./data"
	@echo "Containers are stopped first. .env is kept."
	@printf 'Type destroy to continue: '
	@read -r ans && [[ "$$ans" == "destroy" ]]
	$(COMPOSE) down --remove-orphans
	rm -rf -- data
	@echo "Volume ./data removed."

ensure-compose:
	@if [[ -z "$(COMPOSE)" ]]; then \
		echo "Docker Compose is not installed."; \
		echo "The 'docker compose' plugin is missing, so Make cannot start Hermes."; \
		echo "Ubuntu/Debian:  sudo apt install docker-compose-v2"; \
		echo "Then retry:     make setup"; \
		exit 1; \
	fi

ensure-env:
	@if [[ ! -f .env ]]; then \
		echo "Missing .env — run: make init"; \
		exit 1; \
	fi

ensure-data:
	@mkdir -p data/workspace
	@chmod 700 data || true
