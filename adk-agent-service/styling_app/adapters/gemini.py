"""Gemini client calls for the M4 tools.

Thin local adapter (M4 Decision Log: no import of fastapi-service); the call
shapes, model IDs, and ANALYSIS_RESPONSE_SCHEMA are copied verbatim from
fastapi-service/app/adapters/gemini_analysis.py (M2-5) so M4 analysis matches M2.
"""

import json
from functools import lru_cache

from google import genai
from google.genai import types

from ..config import get_settings

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

_ANALYSIS_PROMPT = (
    "Analyze this clothing item image. Return JSON with category, colors, "
    "tags, season, and style. Use concise labels that work for Japanese "
    "fashion search as well as English search."
)


@lru_cache
def _client() -> genai.Client:
    settings = get_settings()
    if settings.google_genai_use_vertexai:
        return genai.Client(
            vertexai=True,
            project=settings.project_id,
            location=settings.google_cloud_location,
        )
    return genai.Client(api_key=settings.resolved_gemini_api_key)


def analyze(image_bytes: bytes) -> dict:
    """Structured clothing analysis: {category, colors, tags, season, style}."""
    settings = get_settings()
    image_part = types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg")
    response = _client().models.generate_content(
        model=settings.image_analysis_model,
        contents=[image_part, _ANALYSIS_PROMPT],
        config={
            "response_mime_type": "application/json",
            "response_schema": ANALYSIS_RESPONSE_SCHEMA,
        },
    )
    if isinstance(response.parsed, dict):
        return response.parsed
    return json.loads(response.text or "{}")


def embed_text(text: str) -> list[float]:
    """Embed a query description with the same model/dims as the M2-5 pipeline."""
    settings = get_settings()
    response = _client().models.embed_content(
        model=settings.embedding_model,
        contents=[text],
        config={
            "task_type": "RETRIEVAL_QUERY",
            "output_dimensionality": settings.embedding_dimensions,
        },
    )
    return list(response.embeddings[0].values)
