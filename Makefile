quality:
	uv run mypy src

format:
	uv run ruff format . && uv run ruff format --check .

check:
	uv run ruff check . && uv run ruff check --fix .

test:
	uv run pytest

pulse:
	uv run pulse check

HOURS ?= 24
availability:
	uv run pulse availability --hours $(HOURS)