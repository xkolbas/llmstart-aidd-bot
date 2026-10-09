.PHONY: install run format lint test

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
