.PHONY: dev test lint eval up down

dev:
	pip install -e ".[dev]"

up:
	docker compose up -d --build

down:
	docker compose down -v

test:
	pytest -q

lint:
	ruff check . && ruff format --check . && mypy src

eval:
	python -m evals.run_review_eval --cases evals/cases --out evals/results
