# ──────────────────────────────────────────────────────────────────────────────
# VulnForge Makefile — Developer Workflow Automation
# ──────────────────────────────────────────────────────────────────────────────

.PHONY: help dev prod test lint format type-check migrate migrate-create \
        seed clean logs shell db-shell celery-worker celery-flower \
        docker-build docker-clean secret

# Default target
.DEFAULT_GOAL := help

# Load .env if it exists
ifneq (,$(wildcard ./.env))
    include .env
    export
endif

PYTHON        := python3.13
PIP           := pip
DOCKER_COMPOSE := docker compose
BACKEND_DIR   := backend
ALEMBIC       := cd $(BACKEND_DIR) && alembic

# ── Help ──────────────────────────────────────────────────────────────────────
help:  ## Show this help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
	  awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-25s\033[0m %s\n", $$1, $$2}'

# ── Development ───────────────────────────────────────────────────────────────
dev:  ## Start full development stack (hot reload)
	$(DOCKER_COMPOSE) -f docker/docker-compose.yml \
	  -f docker/docker-compose.dev.yml up --build

dev-backend:  ## Start only backend services (db, redis, celery, api)
	$(DOCKER_COMPOSE) -f docker/docker-compose.yml \
	  -f docker/docker-compose.dev.yml up --build db redis celery-worker api

dev-detach:  ## Start development stack in background
	$(DOCKER_COMPOSE) -f docker/docker-compose.yml \
	  -f docker/docker-compose.dev.yml up -d --build

# ── Production ────────────────────────────────────────────────────────────────
prod:  ## Start production stack
	$(DOCKER_COMPOSE) -f docker/docker-compose.yml up -d --build

prod-down:  ## Stop production stack
	$(DOCKER_COMPOSE) -f docker/docker-compose.yml down

# ── Testing ───────────────────────────────────────────────────────────────────
test:  ## Run full test suite (unit + integration)
	$(DOCKER_COMPOSE) -f docker/docker-compose.test.yml up --build --abort-on-container-exit
	$(DOCKER_COMPOSE) -f docker/docker-compose.test.yml down -v

test-unit:  ## Run only unit tests (no external services needed)
	cd $(BACKEND_DIR) && pytest tests/unit -m unit -v

test-integration:  ## Run integration tests (requires running services)
	cd $(BACKEND_DIR) && pytest tests/integration -m integration -v

test-cov:  ## Run tests with HTML coverage report
	cd $(BACKEND_DIR) && pytest --cov=app --cov-report=html:coverage_html

# ── Code Quality ──────────────────────────────────────────────────────────────
lint:  ## Run ruff linter
	cd $(BACKEND_DIR) && ruff check .

format:  ## Run ruff formatter
	cd $(BACKEND_DIR) && ruff format .

format-check:  ## Check formatting without changes
	cd $(BACKEND_DIR) && ruff format --check .

type-check:  ## Run mypy type checker
	cd $(BACKEND_DIR) && mypy app plugins reports

quality: lint format-check type-check  ## Run all quality checks

# ── Database ──────────────────────────────────────────────────────────────────
migrate:  ## Apply all pending migrations
	$(ALEMBIC) upgrade head

migrate-down:  ## Rollback one migration
	$(ALEMBIC) downgrade -1

migrate-create:  ## Create a new migration (usage: make migrate-create MSG="add users table")
	$(ALEMBIC) revision --autogenerate -m "$(MSG)"

migrate-history:  ## Show migration history
	$(ALEMBIC) history --verbose

migrate-current:  ## Show current migration revision
	$(ALEMBIC) current

seed:  ## Seed development database with test data
	cd $(BACKEND_DIR) && $(PYTHON) -m scripts.seed_db

db-shell:  ## Open psql shell in running DB container
	$(DOCKER_COMPOSE) -f docker/docker-compose.yml exec db \
	  psql -U $${POSTGRES_USER} -d $${POSTGRES_DB}

# ── Workers ───────────────────────────────────────────────────────────────────
celery-worker:  ## Start Celery worker locally
	cd $(BACKEND_DIR) && celery -A app.celery_app worker --loglevel=info

celery-flower:  ## Start Celery Flower monitoring UI
	cd $(BACKEND_DIR) && celery -A app.celery_app flower --port=5555

# ── Utilities ─────────────────────────────────────────────────────────────────
secret:  ## Generate a new SECRET_KEY
	cd $(BACKEND_DIR) && $(PYTHON) ../scripts/generate_secret.py

shell:  ## Open Python shell in backend container
	$(DOCKER_COMPOSE) -f docker/docker-compose.yml exec api python

logs:  ## Tail all service logs
	$(DOCKER_COMPOSE) -f docker/docker-compose.yml logs -f

logs-api:  ## Tail API logs only
	$(DOCKER_COMPOSE) -f docker/docker-compose.yml logs -f api

# ── Cleanup ───────────────────────────────────────────────────────────────────
clean:  ## Remove all containers, volumes, and caches
	$(DOCKER_COMPOSE) -f docker/docker-compose.yml down -v --remove-orphans
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	rm -rf $(BACKEND_DIR)/coverage_html $(BACKEND_DIR)/.coverage

docker-build:  ## Build all Docker images without starting
	$(DOCKER_COMPOSE) -f docker/docker-compose.yml build

docker-clean:  ## Remove all VulnForge Docker images
	docker images | grep vulnforge | awk '{print $$3}' | xargs docker rmi -f

install-dev:  ## Install backend dev dependencies locally
	cd $(BACKEND_DIR) && $(PIP) install -e ".[dev]"

install-hooks:  ## Install pre-commit hooks
	cd $(BACKEND_DIR) && pre-commit install
