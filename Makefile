.PHONY: install lint format typecheck test test-unit coverage up down seed health clean

# --- Setup ---

install:
	uv sync

# --- Quality ---

lint:
	uv run ruff check .

format:
	uv run ruff format .

typecheck:
	uv run mypy packages/

# --- Tests ---

test:
	uv run pytest -v --tb=short

test-unit:
	uv run pytest tests/test_edge_cases.py tests/test_pii.py tests/test_risk.py tests/test_hook.py tests/test_codex_parser.py tests/test_mcp.py -v --tb=short

coverage:
	uv run pytest --cov=packages --cov-report=term-missing --cov-fail-under=80

# --- Docker ---

up:
	docker compose up -d
	@echo "Waiting for services..."
	@sleep 8
	@curl -sf http://localhost:8000/health | python3 -m json.tool

down:
	docker compose down

seed:
	docker compose exec api sh -c "cd /app/packages/api && uv run python -m agentaudit_api.seed"

health:
	curl -sf http://localhost:8000/health | python3 -m json.tool

# --- Utilities ---

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .mypy_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	rm -rf .coverage htmlcov/

check: lint format typecheck test-unit
	@echo "All checks passed."
