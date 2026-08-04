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

RECENT_HOURS ?= 2
BASELINE_HOURS ?= 168
regression:
	uv run pulse regression --recent-hours $(RECENT_HOURS) --baseline-hours $(BASELINE_HOURS)