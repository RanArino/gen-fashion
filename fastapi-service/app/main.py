import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.handlers import health, closet_routes, session_routes


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
app.include_router(session_routes.router, prefix="/sessions", tags=["sessions"])


@app.on_event("startup")
async def startup():
    """Initialize on app startup."""
    agent_model = os.getenv("AGENT_MODEL", "gemini-2.0-flash")
    print(f"Using AGENT_MODEL={agent_model}")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
