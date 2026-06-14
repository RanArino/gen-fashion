from enum import Enum


class StyleSessionState(str, Enum):
    """State machine states for a styling session."""

    CREATED = "CREATED"
    IMAGE_RECEIVED = "IMAGE_RECEIVED"
    SOURCE_SELECTING = "SOURCE_SELECTING"
    ANALYZING = "ANALYZING"
    SEARCHING = "SEARCHING"
    PROPOSING = "PROPOSING"
    GENERATING = "GENERATING"
    COMPLETED = "COMPLETED"
    ERROR = "ERROR"
    TIMEOUT = "TIMEOUT"

    @staticmethod
    def transitions() -> dict:
        """Define valid state transitions."""
        return {
            StyleSessionState.CREATED: [
                StyleSessionState.IMAGE_RECEIVED,
                StyleSessionState.SOURCE_SELECTING,
                StyleSessionState.ERROR,
                StyleSessionState.TIMEOUT,
            ],
            StyleSessionState.IMAGE_RECEIVED: [
                StyleSessionState.ANALYZING,
                StyleSessionState.SOURCE_SELECTING,
                StyleSessionState.ERROR,
                StyleSessionState.TIMEOUT,
            ],
            StyleSessionState.SOURCE_SELECTING: [
                StyleSessionState.SEARCHING,
                StyleSessionState.ANALYZING,
                StyleSessionState.ERROR,
                StyleSessionState.TIMEOUT,
            ],
            StyleSessionState.ANALYZING: [
                StyleSessionState.SEARCHING,
                StyleSessionState.ERROR,
                StyleSessionState.TIMEOUT,
            ],
            StyleSessionState.SEARCHING: [
                StyleSessionState.PROPOSING,
                StyleSessionState.ERROR,
                StyleSessionState.TIMEOUT,
            ],
            StyleSessionState.PROPOSING: [
                StyleSessionState.GENERATING,
                StyleSessionState.COMPLETED,
                StyleSessionState.ERROR,
                StyleSessionState.TIMEOUT,
            ],
            StyleSessionState.GENERATING: [
                StyleSessionState.COMPLETED,
                StyleSessionState.ERROR,
                StyleSessionState.TIMEOUT,
            ],
            StyleSessionState.COMPLETED: [],
            StyleSessionState.ERROR: [],
            StyleSessionState.TIMEOUT: [],
        }

    def can_transition_to(self, next_state: "StyleSessionState") -> bool:
        """Check if transition is valid."""
        return next_state in self.transitions().get(self, [])
