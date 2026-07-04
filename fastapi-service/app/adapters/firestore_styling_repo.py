from datetime import datetime
from typing import Any, Optional
from uuid import UUID
from google.cloud import firestore
from app.ports import StylingRepositoryPort
from app.config import get_settings
from app.domain.styling import (
    ClothingSource,
    CoordinationMode,
    StyleResult,
    StyleSession,
    StyleSessionId,
    StyleSessionState,
    UserPreference,
)


class FirestoreStylingRepository(StylingRepositoryPort):
    """Firestore adapter for styling session persistence (M5-2)."""

    def __init__(self) -> None:
        settings = get_settings()
        self._client = firestore.AsyncClient(
            project=settings.firestore_project_id,
            database=settings.firestore_database_id,
        )

    def _collection(self):
        return self._client.collection("sessions")

    def _document(self, session_id: StyleSessionId):
        return self._collection().document(str(session_id))

    @staticmethod
    def _parse_datetime(value):
        if isinstance(value, datetime) or value is None:
            return value
        if hasattr(value, "datetime"):
            return value.datetime
        return value

    @staticmethod
    def _preference_to_document(preference: UserPreference | None) -> dict[str, Any] | None:
        if preference is None:
            return None
        return {
            "occasion": preference.occasion,
            "season": preference.season,
            "style": preference.style,
            "colorPreference": preference.color_preference,
            "gender": preference.gender,
            "language": preference.language,
        }

    @staticmethod
    def _preference_from_document(data: dict[str, Any] | None) -> UserPreference | None:
        if not data:
            return None
        return UserPreference(
            occasion=data.get("occasion"),
            season=data.get("season"),
            style=data.get("style"),
            color_preference=data.get("colorPreference"),
            gender=data.get("gender"),
            language=data.get("language"),
        )

    @staticmethod
    def _result_to_document(result: StyleResult | None) -> dict[str, Any] | None:
        if result is None:
            return None
        if result.raw_payload is not None:
            return result.raw_payload
        return {
            "coordinateImageUrl": result.coordinate_image_url,
            "modelUsed": result.model_used,
        }

    @staticmethod
    def _result_from_document(data: dict[str, Any] | None) -> StyleResult | None:
        if not data:
            return None
        return StyleResult(
            coordinate_image_url=data.get("coordinateImageUrl", ""),
            model_used=data.get("modelUsed"),
            raw_payload=data,
        )

    @staticmethod
    def _to_document(session: StyleSession) -> dict[str, Any]:
        return {
            "sessionId": str(session.id),
            "userId": session.user_id,
            "status": session.state.value,
            "source": session.clothing_source.value,
            "coordinationMode": session.coordination_mode.value,
            "anchorItems": session.anchor_items,
            "sharedClosetId": session.shared_closet_id,
            "analysisResult": session.analysis_result,
            "userPreference": FirestoreStylingRepository._preference_to_document(
                session.user_preference
            ),
            "selectedItems": session.selected_items,
            "proposedCandidates": session.proposed_candidates,
            "styleResult": FirestoreStylingRepository._result_to_document(session.final_result),
            "createdAt": session.created_at,
            "updatedAt": session.updated_at,
            "completedAt": session.completed_at,
            "expiresAt": session.expires_at,
        }

    @staticmethod
    def _from_snapshot(snapshot) -> StyleSession | None:
        if not snapshot.exists:
            return None
        data = snapshot.to_dict() or {}
        return StyleSession(
            id=StyleSessionId(UUID(snapshot.id)),
            user_id=data["userId"],
            state=StyleSessionState(data.get("status", StyleSessionState.SOURCE_SELECTING)),
            clothing_source=ClothingSource(data.get("source", ClothingSource.UNSET)),
            coordination_mode=CoordinationMode(
                data.get("coordinationMode", CoordinationMode.STANDARD)
            ),
            anchor_items=data.get("anchorItems", []),
            shared_closet_id=data.get("sharedClosetId"),
            analysis_result=data.get("analysisResult"),
            selected_items=data.get("selectedItems", []),
            proposed_candidates=data.get("proposedCandidates", []),
            user_preference=FirestoreStylingRepository._preference_from_document(
                data.get("userPreference")
            ),
            final_result=FirestoreStylingRepository._result_from_document(data.get("styleResult")),
            created_at=FirestoreStylingRepository._parse_datetime(data.get("createdAt")),
            updated_at=FirestoreStylingRepository._parse_datetime(data.get("updatedAt")),
            completed_at=FirestoreStylingRepository._parse_datetime(data.get("completedAt")),
            expires_at=FirestoreStylingRepository._parse_datetime(data.get("expiresAt")),
        )

    async def create(self, session: StyleSession) -> None:
        await self._document(session.id).set(self._to_document(session))

    async def get_by_id(self, user_id: str, session_id: StyleSessionId) -> Optional[StyleSession]:
        snapshot = await self._document(session_id).get()
        session = self._from_snapshot(snapshot)
        if session is None or session.user_id != user_id:
            return None
        return session

    async def update(self, session: StyleSession) -> None:
        await self._document(session.id).set(self._to_document(session), merge=True)

    async def list_completed(self, user_id: str, limit: int = 20) -> list[StyleSession]:
        query = (
            self._collection()
            .where("userId", "==", user_id)
            .where("status", "==", StyleSessionState.COMPLETED.value)
            .order_by("completedAt", direction=firestore.Query.DESCENDING)
            .limit(limit)
        )
        sessions: list[StyleSession] = []
        async for snapshot in query.stream():
            session = self._from_snapshot(snapshot)
            if session is not None:
                sessions.append(session)
        return sessions

    async def count_completed_today(self, user_id: str, since: datetime) -> int:
        settings = get_settings()
        cap = max(settings.max_daily_generations_per_user + 1, 2)
        query = (
            self._collection()
            .where("userId", "==", user_id)
            .where("status", "==", StyleSessionState.COMPLETED.value)
            .where("completedAt", ">=", since)
            .limit(cap)
        )
        count = 0
        async for _ in query.stream():
            count += 1
        return count

    async def list_events(
        self, user_id: str, session_id: StyleSessionId, after_seq: int = 0
    ) -> list[dict[str, Any]]:
        query = (
            self._document(session_id)
            .collection("agentEvents")
            .where("seq", ">", after_seq)
            .order_by("seq")
        )
        events: list[dict[str, Any]] = []
        async for snapshot in query.stream():
            data = snapshot.to_dict() or {}
            data["eventId"] = snapshot.id
            events.append(data)
        return events

    async def delete(self, user_id: str, session_id: StyleSessionId) -> None:
        session = await self.get_by_id(user_id, session_id)
        if session is not None:
            await self._document(session_id).delete()
