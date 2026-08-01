lint:
	uv run ruff format . && uv run ruff format --check . && uv run ruff check .

test:
	uv run pytest

pulse:
	uv run pulse check