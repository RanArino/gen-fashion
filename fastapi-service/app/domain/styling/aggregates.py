from uuid import UUID
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional
from app.domain.shared.base_models import AggregateRoot
from app.domain.styling.state_machine import StyleSessionState
from app.domain.styling.value_objects import (
    StyleSessionId,
    UserPreference,
    CoordinateProposal,
    StyleResult,
    ClothingSource,
)


@dataclass
class StyleSession(AggregateRoot):
    """
    Aggregate root for a styling session.
    Manages the full coordination workflow from image selection to result.
    """

    id: StyleSessionId
    user_id: str
    state: StyleSessionState
    uploaded_image_url: Optional[str] = None
    clothing_source: ClothingSource = ClothingSource.UNSET
    shared_closet_id: Optional[str] = None
    analysis_result: Optional[dict[str, Any]] = None
    selected_items: list[dict[str, Any]] = None
    proposed_candidates: list[dict[str, Any]] = None
    user_preference: Optional[UserPreference] = None
    proposed_coordinate: Optional[CoordinateProposal] = None
    final_result: Optional[StyleResult] = None
    created_at: datetime = None
    updated_at: datetime = None
    completed_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None

    def __post_init__(self):
        """Validate invariants."""
        if not self.user_id:
            raise ValueError("user_id must not be empty")
        if self.created_at is None:
            object.__setattr__(self, 'created_at', datetime.utcnow())
        if self.updated_at is None:
            object.__setattr__(self, 'updated_at', datetime.utcnow())
        if self.selected_items is None:
            object.__setattr__(self, 'selected_items', [])
        if self.proposed_candidates is None:
            object.__setattr__(self, 'proposed_candidates', [])

    def select_source(
        self,
        source: ClothingSource,
        preference: Optional[UserPreference] = None,
        shared_closet_id: Optional[str] = None,
    ) -> None:
        """Store source selection and advance the Web flow to SEARCHING."""
        if self.state != StyleSessionState.SOURCE_SELECTING:
            raise ValueError(f"Cannot select source from {self.state}")
        object.__setattr__(self, 'clothing_source', source)
        object.__setattr__(self, 'shared_closet_id', shared_closet_id)
        if preference is not None:
            object.__setattr__(self, 'user_preference', preference)
        self._transition_to(StyleSessionState.SEARCHING)

    def upload_image(self, image_url: str) -> None:
        """Store the uploaded image for analysis."""
        if not image_url:
            raise ValueError("image_url must not be empty")
        object.__setattr__(self, 'uploaded_image_url', image_url)

    def analyze(self) -> None:
        """Transition to ANALYZING state."""
        if not self.state.can_transition_to(StyleSessionState.ANALYZING):
            raise ValueError(f"Cannot transition from {self.state} to ANALYZING")
        self._transition_to(StyleSessionState.ANALYZING)

    def search(self) -> None:
        """Transition to SEARCHING state."""
        if not self.state.can_transition_to(StyleSessionState.SEARCHING):
            raise ValueError(f"Cannot transition from {self.state} to SEARCHING")
        self._transition_to(StyleSessionState.SEARCHING)

    def set_preference(self, preference: UserPreference) -> None:
        """Set user styling preferences."""
        object.__setattr__(self, 'user_preference', preference)
        self._mark_updated()

    def set_analysis_result(self, result: dict[str, Any]) -> None:
        """Store image analysis output."""
        object.__setattr__(self, 'analysis_result', result)
        self._mark_updated()

    def set_selected_items(self, items: list[dict[str, Any]]) -> None:
        """Store selected candidate items."""
        object.__setattr__(self, 'selected_items', items)
        self._mark_updated()

    def select_candidates(self, items: list[dict[str, Any]]) -> None:
        """Accept an explicit, non-empty selection while awaiting approval."""
        if self.state != StyleSessionState.PROPOSING:
            raise ValueError(f"Cannot select candidates from {self.state.value}")
        if not items:
            raise ValueError("At least one candidate must be selected")
        object.__setattr__(self, 'selected_items', items)
        self._mark_updated()

    def propose(self, proposal: CoordinateProposal) -> None:
        """Transition to PROPOSING with a coordinate proposal."""
        if not self.state.can_transition_to(StyleSessionState.PROPOSING):
            raise ValueError(f"Cannot transition from {self.state} to PROPOSING")
        object.__setattr__(self, 'proposed_coordinate', proposal)
        self._transition_to(StyleSessionState.PROPOSING)

    def complete(self, result: StyleResult) -> None:
        """Transition to COMPLETED with the final result."""
        if not self.state.can_transition_to(StyleSessionState.COMPLETED):
            raise ValueError(f"Cannot transition from {self.state} to COMPLETED")
        object.__setattr__(self, 'final_result', result)
        object.__setattr__(self, 'completed_at', datetime.utcnow())
        self._transition_to(StyleSessionState.COMPLETED)

    def timeout(self) -> None:
        """Transition to TIMEOUT state."""
        object.__setattr__(self, 'state', StyleSessionState.TIMEOUT)
        self._mark_updated()

    def mark_error(self) -> None:
        """Transition to ERROR state."""
        if not self.state.can_transition_to(StyleSessionState.ERROR):
            raise ValueError(f"Cannot transition from {self.state} to ERROR")
        self._transition_to(StyleSessionState.ERROR)

    def _transition_to(self, next_state: StyleSessionState) -> None:
        """Safely transition to next state."""
        if not self.state.can_transition_to(next_state):
            raise ValueError(f"Invalid transition from {self.state} to {next_state}")
        object.__setattr__(self, 'state', next_state)
        self._mark_updated()

    def _mark_updated(self) -> None:
        """Mark the session as updated."""
        object.__setattr__(self, 'updated_at', datetime.utcnow())
