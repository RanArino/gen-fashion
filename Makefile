.PHONY: dev test clean reset build help web seed firestore-export

FIREBASE_PROJECT_ID ?= gen-fashion-local

help:
	@echo "gen-fashion local development commands:"
	@echo "  make dev                       - Start all services with persisted Firestore data, attach logs"
	@echo "  make web                       - Run the Flutter web client (http://localhost:8088)"
	@echo "  make test                      - Run tests in FastAPI service"
	@echo "  make clean                     - Stop containers without deleting local data"
	@echo "  make reset                     - Remove containers and volumes (re-seed required)"
	@echo "  make build                     - Build Docker images"
	@echo "  make seed SOURCE_DIR=<path>    - Manually (re)seed shared closet"

dev:
	docker-compose up -d
	@echo "Waiting for Elasticsearch…" && until docker-compose exec -T elasticsearch curl -sf http://localhost:9200/_cluster/health > /dev/null 2>&1; do sleep 3; done && echo "  ES ready"
	@echo "Waiting for Firestore…"     && until docker-compose exec -T firestore-emulator curl -sf http://localhost:8080 > /dev/null 2>&1; do sleep 3; done && echo "  Firestore ready"
	@echo "Waiting for MinIO…"         && until docker-compose exec -T minio mc ready local > /dev/null 2>&1; do sleep 3; done && echo "  MinIO ready"
	docker-compose logs -f

web:
	cd flutter-web-app && flutter run -d chrome --web-port 8088 \
	  --dart-define=API_BASE_URL=http://localhost:8000 \
	  --dart-define=USE_EMULATORS=true \
	  --dart-define=FIREBASE_PROJECT_ID=gen-fashion-local \
	  --dart-define=FIREBASE_API_KEY=AIzaSyDLocalEmulatorOnlyKey00000000000 \
	  --dart-define=FIREBASE_APP_ID=1:000000000000:web:0000000000000000 \
	  --dart-define=FIREBASE_MESSAGING_SENDER_ID=000000000000 \
	  --dart-define=FIREBASE_AUTH_DOMAIN=gen-fashion-local.firebaseapp.com \
	  --dart-define=FIREBASE_STORAGE_BUCKET=gen-fashion-local.appspot.com \
	  --dart-define=AUTH_EMULATOR_HOST=localhost \
	  --dart-define=AUTH_EMULATOR_PORT=9099 \
	  --dart-define=FIRESTORE_EMULATOR_HOST=localhost \
	  --dart-define=FIRESTORE_EMULATOR_PORT=8080

test:
	docker-compose run --rm fastapi-service pytest

clean:
	@$(MAKE) firestore-export
	docker-compose stop

reset:
	docker-compose down -v

build:
	docker-compose build

seed:
	@test -n "$(SOURCE_DIR)" || (echo "Usage: make seed SOURCE_DIR=/path/to/clothing-dataset/images_original" && exit 1)
	@echo "Waiting for Elasticsearch…" && until curl -sf http://localhost:9200/_cluster/health > /dev/null 2>&1; do sleep 2; done
	@echo "Waiting for Firestore…" && until curl -sf http://localhost:8080 > /dev/null 2>&1; do sleep 2; done
	@echo "Waiting for MinIO…" && until curl -sf http://localhost:9000/minio/health/ready > /dev/null 2>&1; do sleep 2; done
	cd scripts/seed_shared_closet && \
	  (test -d .venv || python3 -m venv .venv) && \
	  .venv/bin/pip install -q -r requirements.txt && \
	  .venv/bin/python run_seed.py --purge && \
	  .venv/bin/python run_seed.py --source-dir "$(SOURCE_DIR)"
	@$(MAKE) firestore-export

firestore-export:
	@if docker-compose ps --status running --services | grep -qx firestore-emulator; then \
	  export_dir="/firestore-data/snapshot-$$(date +%s)" && \
	  docker-compose exec -T firestore-emulator mkdir -p "$$export_dir" && \
	  curl -fsS -X POST \
	    "http://localhost:8080/emulator/v1/projects/$(FIREBASE_PROJECT_ID):export" \
	    -H 'Content-Type: application/json' \
	    -d "{\"database\":\"projects/$(FIREBASE_PROJECT_ID)/databases/(default)\",\"export_directory\":\"$$export_dir\"}" \
	    > /dev/null && \
	  echo "Firestore emulator data exported to gen-fashion_firestore-data"; \
	else \
	  echo "Firestore emulator is not running; skipping export"; \
	fi
