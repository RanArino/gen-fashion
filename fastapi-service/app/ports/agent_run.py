from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class AgentRunRequest:
    session_id: str
    user_id: str
    source: str
    user_preference: dict
    shared_closet_id: str | None = None


class AgentRunPort(ABC):
    """Port for starting an ADK styling run."""

    @abstractmethod
    async def start_session_run(self, request: AgentRunRequest) -> None:
        """Ask adk-agent-service to run a styling session asynchronously."""
        raise NotImplementedError("Implement in M5-1: ADK run adapter")
