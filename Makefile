.PHONY: help up down build rebuild logs test seed clean

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-15s\033[0m %s\n", $$1, $$2}'

up: ## Start all services
	docker compose up -d

down: ## Stop all services
	docker compose down

build: ## Build all services
	docker compose build

rebuild: ## Rebuild and restart all services
	docker compose down
	docker compose build
	docker compose up -d

logs: ## Show logs (use: make logs s=backend)
	docker compose logs -f $(s)

test: ## Run tests
	docker compose exec backend pytest tests/ -v

test-unit: ## Run unit tests only
	docker compose exec backend pytest tests/unit/ -v

test-int: ## Run integration tests only
	docker compose exec backend pytest tests/integration/ -v

seed: ## Seed the database
	docker compose exec backend python -m app.db.seed

clean: ## Remove all containers and volumes
	docker compose down -v
	docker system prune -f

status: ## Show service status
	docker compose ps
