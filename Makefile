.PHONY: install dev compile test lock migrate docker-up docker-build

install:
	uv sync --group dev

dev:
	uv run uvicorn app.main:app --reload

compile:
	uv run python -m compileall app

test:
	uv run pytest

lock:
	uv lock

migrate:
	uv run alembic upgrade head

docker-build:
	docker compose build

docker-up:
	docker compose up --build
