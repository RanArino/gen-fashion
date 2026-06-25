from abc import ABC, abstractmethod
from typing import List, Optional
from pydantic import BaseModel, Field


class ClothingAnalysisResult(BaseModel):
    category: Optional[str] = None
    colors: List[str] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)
    season: Optional[str] = None
    style: Optional[str] = None


class GeminiAnalysisPort(ABC):
    """Port for Gemini image analysis and optional image embeddings."""

    @abstractmethod
    async def analyze(self, image_bytes: bytes) -> ClothingAnalysisResult:
        raise NotImplementedError("Implement in M2-5: Gemini analysis adapter")

    @abstractmethod
    async def embed(self, image_bytes: bytes) -> List[float]:
        raise NotImplementedError("Implement in M2-5: Gemini embedding adapter")
