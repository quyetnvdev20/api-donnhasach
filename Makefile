.PHONY: help build up down restart logs clean test

# Default target
help:
	@echo "Available commands:"
	@echo "  build      - Build API Docker image"
	@echo "  up         - Start API service"
	@echo "  down       - Stop API service"
	@echo "  restart    - Restart API service"
	@echo "  logs       - Show logs from API service"
	@echo "  clean      - Remove containers and images"
	@echo "  test       - Run tests"
	@echo "  shell      - Access API container shell"
	@echo "  dev-setup  - Setup development environment"

# Build API image
build:
	docker-compose build --no-cache api

# Start API service
up:
	docker-compose up -d api

# Stop API service
down:
	docker-compose down

# Restart API service
restart:
	docker-compose restart api

# Show logs
logs:
	docker-compose logs -f api

# Clean everything
clean:
	docker-compose down --remove-orphans
	docker system prune -af

# Run tests
test:
	docker-compose exec api python -m pytest

# Access API container shell
shell:
	docker-compose exec api /bin/bash

# Development setup
dev-setup:
	@echo "Setting up development environment..."
	@if [ ! -f .env ]; then cp env.example .env; echo "Created .env file from env.example"; fi
	@echo "⚠️  IMPORTANT: Please edit .env file with your external database and Redis configuration:"
	@echo "   - DATABASE_URL=postgresql://username:password@host:port/database_name"
	@echo "   - REDIS_URL=redis://host:port"
	@echo "   - ODOO_URL=http://your-odoo-server:8069"
	@echo "   - ODOO_TOKEN=your_odoo_token"
	@echo ""
	@echo "Then run: make build && make up"

# Check status
status:
	docker-compose ps

# View resource usage
stats:
	docker stats

# Test API connection
test-api:
	@echo "Testing API connection..."
	curl -f http://localhost:8000/docs || echo "API not accessible"

# Test external connections
test-connections:
	@echo "Testing external database and Redis connections..."
	docker-compose exec api python -c "from app.utils.erp_db import PostgresDB; import asyncio; asyncio.run(PostgresDB.execute_query('SELECT 1'))" || echo "Database connection failed" 