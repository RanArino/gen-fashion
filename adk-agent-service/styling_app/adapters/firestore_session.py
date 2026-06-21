from datetime import datetime, timezone
from typing import Any

from ..config import get_settings


# req §8.1 lifecycle order. The writer enforces forward-only progression so a
# late/out-of-order ADK event (e.g. a stray search after synthesis started)
# cannot regress the persisted status to an earlier phase.
_STATUS_ORDER = {
    "CREATED": 0,
    "IMAGE_RECEIVED": 1,
    "SOURCE_SELECTING": 2,
    "ANALYZING": 3,
    "SEARCHING": 4,
    "PROPOSING": 5,
    "GENERATING": 6,
    "COMPLETED": 7,
}


class FirestoreSessionRepository:
    """Firestore writer for M5 session state and agentEvents."""

    def __init__(self, client: Any | None = None) -> None:
        if client is None:
            from google.cloud import firestore

            settings = get_settings()
            client = firestore.AsyncClient(
                project=settings.firestore_project_id,
                database=settings.firestore_database_id,
            )
        self._client = client
        self._status_rank = -1

    def _session_doc(self, session_id: str):
        return self._client.collection("sessions").document(session_id)

    async def update_status(self, session_id: str, status: str) -> None:
        # Advance only through the documented lifecycle: skip duplicates and
        # ignore any attempt to move back to an earlier phase. Terminal states
        # are written by write_style_result / mark_error, not here.
        rank = _STATUS_ORDER.get(status)
        if rank is not None:
            if rank <= self._status_rank:
                return
            self._status_rank = rank
        await self._session_doc(session_id).set(
            {"status": status, "updatedAt": datetime.now(timezone.utc)},
            merge=True,
        )

    async def write_event(self, session_id: str, event: dict[str, Any]) -> None:
        event_id = f"{int(event['seq']):06d}"
        await self._session_doc(session_id).collection("agentEvents").document(event_id).set(event)

    async def write_style_result(self, session_id: str, style_result: dict[str, Any]) -> None:
        self._status_rank = _STATUS_ORDER["COMPLETED"]
        await self._session_doc(session_id).set(
            {
                "status": "COMPLETED",
                "styleResult": style_result,
                "updatedAt": datetime.now(timezone.utc),
            },
            merge=True,
        )

    async def mark_error(self, session_id: str, message: str) -> None:
        await self._session_doc(session_id).set(
            {
                "status": "ERROR",
                "errorMessage": message,
                "updatedAt": datetime.now(timezone.utc),
            },
            merge=True,
        )
