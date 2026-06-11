"""style_synthesizer tool (M4-7, req §6.5/§7.2).

Nano Banana virtual try-on (M1-2) with the ADL-005 collage fallback. Each call
writes a new UUID-named object, so repeats never overwrite (M4 plan,
Idempotence and Recovery).
"""

from uuid import uuid4

from ..adapters import image_generation, image_storage
from ..config import get_settings
from .registry import registry


def style_synthesizer(
    user_id: str, item_image_urls: list[str], style_description: str
) -> dict:
    """Generate a coordinate (outfit) image from the selected garment images.

    Args:
        user_id: ID of the requesting user (owns the stored result).
        item_image_urls: Image URLs (or R2/MinIO keys) of the chosen garments.
        style_description: Desired styling direction for the generated photo.

    Returns:
        {coordinate_image_url, items, model_used}; model_used is
        "collage-fallback" when generation failed and a collage was stored.
    """
    image_bytes_list = [image_storage.fetch_bytes(url) for url in item_image_urls]

    settings = get_settings()
    try:
        result_bytes = image_generation.generate(image_bytes_list, style_description)
        model_used = settings.image_generation_model
    except Exception:
        result_bytes = image_generation.build_collage(image_bytes_list)
        model_used = "collage-fallback"

    coordinate_image_url = image_storage.put_bytes(
        f"{user_id}/coordinates/{uuid4().hex}.jpg", result_bytes
    )
    return {
        "coordinate_image_url": coordinate_image_url,
        "items": item_image_urls,
        "model_used": model_used,
    }


registry.register("style_synthesizer", style_synthesizer)
