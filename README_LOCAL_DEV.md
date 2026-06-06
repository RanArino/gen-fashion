# Local Development Setup

This guide walks you through setting up gen-fashion for local development using Docker Compose.

## Prerequisites

- Docker and Docker Compose installed
- Python 3.11+ (for local FastAPI development without Docker)
- Node 20+ (for local ADK development without Docker)
- Git

## Quick Start

1. **Clone the repository**

```bash
git clone <repo-url>
cd gen-fashion
```

2. **Set up environment variables**

```bash
cp .env.example .env
```

Edit `.env` if needed (defaults work for local development).

3. **Start all services**

```bash
make dev
```

This command:
- Builds Docker images for both FastAPI and ADK services
- Starts Elasticsearch 8.x on port 9200
- Starts Firestore Emulator on port 8080
- Starts Firebase Auth Emulator on port 9099
- Starts MinIO S3-compatible storage on ports 9000 and 9001
- Starts FastAPI service on port 8000
- Starts ADK Agent service on port 3000

Wait 30-60 seconds for all services to become healthy.

4. **Verify services are running**

In another terminal, test the endpoints:

```bash
# Health check
curl http://localhost:8000/health

# Elasticsearch cluster health
curl http://localhost:9200/_cluster/health

# Firestore emulator UI
open http://localhost:8080/

# Firebase Auth emulator
curl http://localhost:9099/

# MinIO console
open http://localhost:9001/
```

Expected responses:
- FastAPI: `{"status":"ok"}`
- Elasticsearch: JSON object with `"status":"green"` or `"yellow"`
- Firestore: Web UI loads
- Firebase Auth: emulator responds on port 9099
- MinIO: console loads; local credentials are `minioadmin` / `minioadmin`

## Development Workflow

### Running Tests

```bash
make test
```

This runs pytest on the FastAPI service.

### Stopping Services

```bash
make clean
```

This stops all containers and removes volumes.

### Rebuilding Images

```bash
make build
```

This rebuilds Docker images (useful if dependencies change).

## Local Development Without Docker

For faster iteration during development, you can run services locally:

### FastAPI Service

```bash
cd fastapi-service
pip install -r requirements.txt
python -m uvicorn app.main:app --reload
```

(Still need Elasticsearch and Firestore Emulator running; see Docker Compose alternatives below.)

### ADK Agent Service

```bash
cd adk-agent-service
npm install
npm run build
npm start
```

## Troubleshooting

### Port Already in Use

If ports 8000, 9200, 8080, or 3000 are already in use:

```bash
# Find and kill process on port (e.g., 8000)
lsof -i :8000
kill -9 <PID>

# Or adjust docker-compose.yml ports
```

### Services Won't Start

```bash
# Check logs
docker-compose logs -f fastapi-service

# Force rebuild
make clean && make build && make dev
```

### Firestore Emulator Issues

The Google Cloud SDK emulator is large. First run may take a while. If it fails:

```bash
# Use lighter Firebase emulator alternative for development
# (Fall back to Cloud Firestore if needed)
```

### Local Auth Token

With `make dev` running, create a Firebase Auth emulator user and capture an ID token:

```bash
TOKEN=$(curl -s -X POST \
  "http://localhost:9099/identitytoolkit.googleapis.com/v1/accounts:signUp?key=fake-api-key" \
  -H "Content-Type: application/json" \
  -d '{"returnSecureToken":true}' | python3 -c 'import json,sys; print(json.load(sys.stdin)["idToken"])')
```

Use it with authenticated API calls:

```bash
curl "http://localhost:8000/closet/upload-url?item_id=<uuid>" \
  -H "Authorization: Bearer $TOKEN"
```

## Service Endpoints

| Service | URL | Purpose |
|---------|-----|---------|
| FastAPI | http://localhost:8000 | REST API for closet & session management |
| Elasticsearch | http://localhost:9200 | Vector search for clothing items |
| Firestore Emulator | http://localhost:8080 | Database emulator for local dev |
| Firebase Auth Emulator | http://localhost:9099 | Local Firebase ID tokens |
| MinIO | http://localhost:9001 | Local R2/S3-compatible object storage console |
| ADK Agent | http://localhost:3000 | Agent orchestrator (internal) |

## Environment Variables

See `.env.example` for all available options. Key variables:

- `FIRESTORE_EMULATOR_HOST`: Firestore Emulator address
- `FIREBASE_AUTH_EMULATOR_HOST`: Firebase Auth Emulator address
- `ELASTICSEARCH_URL`: Elasticsearch URL
- `GEMINI_API_KEY` / `GOOGLE_GENAI_API_KEY`: Gemini developer API key for local image analysis
- `IMAGE_ANALYSIS_MODEL`: Gemini model for clothing image analysis; local dev defaults to `gemini-2.5-flash`
- `R2_ENDPOINT_URL`: R2 or MinIO S3-compatible endpoint URL used by the API container
- `R2_PUBLIC_ENDPOINT_URL`: public endpoint embedded in signed URLs for browser/curl uploads
- `TASK_QUEUE_MODE`: `local` for local HTTP worker calls, `cloud_tasks` for production queueing
- `AGENT_MODEL`: LLM model (default: gemini-2.0-flash)
- `MAX_CLOSET_IMAGES_PER_USER`: Max items per user (default: 20)

## Next Steps

- [Architecture overview](../docs/req-phase01.md)
- [Feature matrix & progress](../docs/feature-matrix-phase01.md)
- [Implementation M0 ExecPlan](../docs/plans/20260517-m0-project-foundation.md)
