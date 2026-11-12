.PHONY: install run format lint test docker-build docker-up docker-down docker-logs \
	docker-format docker-lint docker-test

install:
	uv sync --locked

run:
	uv run --locked bot

format:
	uv run --locked ruff format .

lint:
	uv run --locked ruff check .
	uv run --locked ruff format --check .

test:
	uv run --locked pytest

docker-build:
	docker compose build

docker-up:
	docker compose up --build --detach

docker-down:
	docker compose down

docker-logs:
	docker compose logs --follow bot

docker-format:
	docker compose run --rm bot uv run --locked ruff format .

docker-lint:
	docker compose run --rm bot uv run --locked ruff check .
	docker compose run --rm bot uv run --locked ruff format --check .

docker-test:
	docker compose run --rm bot uv run --locked pytest
