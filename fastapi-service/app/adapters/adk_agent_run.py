import httpx

from app.config import get_settings
from app.ports import AgentRunPort, AgentRunRequest


class HttpAgentRunAdapter(AgentRunPort):
    """HTTP adapter for starting ADK session runs."""

    def __init__(self, base_url: str | None = None) -> None:
        self.base_url = (base_url or get_settings().adk_internal_base_url).rstrip("/")

    async def start_session_run(self, request: AgentRunRequest) -> None:
        settings = get_settings()
        payload = {
            "sessionId": request.session_id,
            "userId": request.user_id,
            "source": request.source,
            "userPreference": request.user_preference,
            "sharedClosetId": request.shared_closet_id,
        }
        headers = {}
        if settings.internal_task_secret:
            headers["X-Internal-Secret"] = settings.internal_task_secret
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(
                f"{self.base_url}/internal/run-session",
                json=payload,
                headers=headers,
            )
        response.raise_for_status()
