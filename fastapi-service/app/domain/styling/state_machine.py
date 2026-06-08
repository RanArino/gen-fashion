from enum import Enum


class StyleSessionState(str, Enum):
    """State machine states for a styling session."""

    CREATED = "CREATED"
    SOURCE_SELECTING = "SOURCE_SELECTING"
    ANALYZING = "ANALYZING"
    SEARCHING = "SEARCHING"
    PROPOSING = "PROPOSING"
    COMPLETED = "COMPLETED"
    TIMEOUT = "TIMEOUT"

    @staticmethod
    def transitions() -> dict:
        """Define valid state transitions."""
        return {
            StyleSessionState.CREATED: [StyleSessionState.SOURCE_SELECTING],
            StyleSessionState.SOURCE_SELECTING: [StyleSessionState.ANALYZING],
            StyleSessionState.ANALYZING: [StyleSessionState.SEARCHING],
            StyleSessionState.SEARCHING: [StyleSessionState.PROPOSING],
            StyleSessionState.PROPOSING: [StyleSessionState.COMPLETED],
            StyleSessionState.COMPLETED: [],
            StyleSessionState.TIMEOUT: [],
        }

    def can_transition_to(self, next_state: "StyleSessionState") -> bool:
        """Check if transition is valid."""
        return next_state in self.transitions().get(self, [])
