.PHONY: dev test clean build help web

help:
	@echo "gen-fashion local development commands:"
	@echo "  make dev      - Start all services with docker-compose"
	@echo "  make web      - Run the Flutter web client (http://localhost:8088)"
	@echo "  make test     - Run tests in FastAPI service"
	@echo "  make clean    - Stop and remove containers"
	@echo "  make build    - Build Docker images"

dev:
	docker-compose up

web:
	cd flutter-web-app && flutter run -d chrome --web-port 8088 \
	  --dart-define=API_BASE_URL=http://localhost:8000 \
	  --dart-define=USE_EMULATORS=true

test:
	docker-compose run --rm fastapi-service pytest

clean:
	docker-compose down -v

build:
	docker-compose build
