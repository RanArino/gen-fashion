import httpx
import google.auth.transport.requests
import google.oauth2.id_token

from app.config import get_settings
from app.ports import AgentRunPort, AgentRunRequest


def _fetch_oidc_token(audience: str) -> str:
    """Fetch a Google OIDC identity token for the given audience via ADC."""
    auth_req = google.auth.transport.requests.Request()
    return google.oauth2.id_token.fetch_id_token(auth_req, audience)


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
            "phase": request.phase,
            "selectedItems": request.selected_items,
        }
        headers = {}
        if settings.internal_task_secret:
            headers["X-Internal-Secret"] = settings.internal_task_secret
        # Production OIDC hardening: attach a Google identity token so the
        # adk-agent-service (deployed --no-allow-unauthenticated) can verify
        # that the caller is fastapi-sa (MD-8).
        if settings.internal_invoker_sa:
            audience = self.base_url
            token = _fetch_oidc_token(audience)
            headers["Authorization"] = f"Bearer {token}"
        # 60s covers Cloud Run cold-start (~26s observed) plus network overhead.
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                f"{self.base_url}/internal/run-session",
                json=payload,
                headers=headers,
            )
        response.raise_for_status()
