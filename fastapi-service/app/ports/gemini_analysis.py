from abc import ABC, abstractmethod
from typing import List, Optional
from pydantic import BaseModel, Field


class ClothingAnalysisResult(BaseModel):
    category: Optional[str] = None
    colors: List[str] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)
    season: Optional[str] = None
    style: Optional[str] = None
    gender: Optional[str] = None


class GeminiAnalysisPort(ABC):
    """Port for Gemini image analysis and text embeddings."""

    @abstractmethod
    async def analyze(self, image_bytes: bytes) -> ClothingAnalysisResult:
        raise NotImplementedError("Implement in M2-5: Gemini analysis adapter")

    @abstractmethod
    async def embed_text(self, text: str) -> List[float]:
        # Embeds the item's analyzed text (category/colors/tags/season) so index
        # vectors share the embedding space with the text query used at search
        # time. gemini-embedding-001 is text-only; image embeddings would live in
        # a different space and never match the query.
        raise NotImplementedError("Implement in M2-5: Gemini embedding adapter")
