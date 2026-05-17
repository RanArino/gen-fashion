.PHONY: dev test clean build help

help:
	@echo "gen-fashion local development commands:"
	@echo "  make dev      - Start all services with docker-compose"
	@echo "  make test     - Run tests in FastAPI service"
	@echo "  make clean    - Stop and remove containers"
	@echo "  make build    - Build Docker images"

dev:
	docker-compose up

test:
	docker-compose run --rm fastapi-service pytest

clean:
	docker-compose down -v

build:
	docker-compose build
