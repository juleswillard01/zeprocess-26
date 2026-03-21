.PHONY: install test test-cov lint typecheck format docker-build docker-run tree export export-txt export-all-txt export-all-pdf auth clean

install:
	uv sync --all-extras

test:
	uv run pytest -x --tb=short

test-cov:
	uv run pytest --cov=src --cov-report=term-missing --cov-fail-under=80

lint:
	uv run ruff check src tests
	uv run ruff format --check src tests

typecheck:
	uv run pyright src

format:
	uv run ruff format src tests
	uv run ruff check --fix src tests

docker-build:
	docker build -t onenote-exporter .

docker-run:
	docker-compose run --rm app

tree:
	uv run python -m src.cli tree

export:
	uv run python -m src.cli export

export-txt:
	uv run python -m src.cli export --format txt

export-all-txt:
	uv run python -m src.cli export --all --format txt

export-all-pdf:
	uv run python -m src.cli export --all --format pdf

auth:
	uv run python -m src.cli auth

clean:
	rm -rf io/exports/* .pytest_cache .ruff_cache __pycache__ .pyright
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
