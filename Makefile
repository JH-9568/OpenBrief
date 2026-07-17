.PHONY: install test lint up migrate

install:
	python -m pip install -e '.[dev]'

test:
	pytest -q

lint:
	ruff check .

up:
	docker compose up --build

migrate:
	alembic upgrade head

