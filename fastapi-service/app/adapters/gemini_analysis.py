from google import genai
from google.genai import types
from app.config import get_settings
from app.ports import ClothingAnalysisResult, GeminiAnalysisPort


ANALYSIS_RESPONSE_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "category": {"type": "STRING"},
        "colors": {"type": "ARRAY", "items": {"type": "STRING"}},
        "tags": {"type": "ARRAY", "items": {"type": "STRING"}},
        "season": {"type": "STRING"},
        "style": {"type": "STRING"},
    },
    "required": ["category", "colors", "tags", "season", "style"],
}


class GeminiAnalysisAdapter(GeminiAnalysisPort):
    """Gemini adapter for clothing image analysis and best-effort embeddings."""

    def __init__(self) -> None:
        settings = get_settings()
        self._settings = settings
        if settings.google_genai_use_vertexai:
            self._client = genai.Client(vertexai=True, project=settings.project_id)
        else:
            self._client = genai.Client(api_key=settings.resolved_gemini_api_key)

    async def analyze(self, image_bytes: bytes) -> ClothingAnalysisResult:
        prompt = (
            "Analyze this clothing item image. Return JSON with category, colors, "
            "tags, season, and style. Use concise labels that work for Japanese "
            "fashion search as well as English search."
        )
        image_part = types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg")
        response = self._client.models.generate_content(
            model=self._settings.image_analysis_model,
            contents=[image_part, prompt],
            config={
                "response_mime_type": "application/json",
                "response_schema": ANALYSIS_RESPONSE_SCHEMA,
            },
        )
        if isinstance(response.parsed, ClothingAnalysisResult):
            return response.parsed
        if isinstance(response.parsed, dict):
            return ClothingAnalysisResult.model_validate(response.parsed)
        return ClothingAnalysisResult.model_validate_json(response.text or "{}")

    async def embed_text(self, text: str) -> list[float]:
        response = self._client.models.embed_content(
            model=self._settings.embedding_model,
            contents=[text],
            config={
                "task_type": "RETRIEVAL_DOCUMENT",
                "output_dimensionality": self._settings.embedding_dimensions,
            },
        )
        embedding = response.embeddings[0].values
        return list(embedding)
