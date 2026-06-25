import asyncio

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.adapters import ElasticsearchEmbeddingRepository
from app.config import get_settings
from app.handlers import health, closet_routes, internal_routes, session_routes, shared_closet_routes


app = FastAPI(title="gen-fashion FastAPI Service", version="0.1.0")

# CORS middleware for Flutter Web
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # TODO: Restrict to known origins in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(health.router, tags=["health"])
app.include_router(closet_routes.router, prefix="/closet", tags=["closet"])
app.include_router(internal_routes.router, tags=["internal"])
app.include_router(session_routes.router, prefix="/sessions", tags=["sessions"])
app.include_router(shared_closet_routes.router, prefix="/shared-closets", tags=["shared-closets"])


@app.on_event("startup")
async def startup():
    """Initialize on app startup."""
    agent_model = get_settings().image_analysis_model
    print(f"Using AGENT_MODEL={agent_model}")
    for attempt in range(1, 6):
        try:
            await ElasticsearchEmbeddingRepository().ensure_index()
            print("[startup] Elasticsearch index ready.")
            return
        except Exception as exc:
            if attempt == 5:
                print(
                    f"[STARTUP ERROR] Elasticsearch index failed after 5 attempts. "
                    f"Shared closet and search will return errors until ES is reachable "
                    f"and you run `make seed`. Last error: {exc}"
                )
            else:
                wait = 2 ** attempt
                print(f"[startup] ES not ready (attempt {attempt}/5), retrying in {wait}s… ({exc})")
                await asyncio.sleep(wait)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
