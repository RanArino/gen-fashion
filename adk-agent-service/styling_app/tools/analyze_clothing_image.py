"""analyze_clothing_image tool (M4-5, req §6.1/§7.2)."""

from ..adapters import gemini, image_storage
from .registry import registry


def analyze_clothing_image(image_url: str) -> dict:
    """Analyze a clothing image and return its structured attributes.

    Args:
        image_url: http(s) URL or R2/MinIO object key of the garment photo.

    Returns:
        dict with keys: category, colors, tags, season, style.
    """
    image_bytes = image_storage.fetch_bytes(image_url)
    return gemini.analyze(image_bytes)


registry.register("analyze_clothing_image", analyze_clothing_image)
