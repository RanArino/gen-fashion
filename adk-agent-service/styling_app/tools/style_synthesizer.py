"""style_synthesizer tool (M4-7, req §6.5/§7.2).

Nano Banana virtual try-on (M1-2). Each successful call writes a new UUID-named
object, so repeats never overwrite (M4 plan, Idempotence and Recovery).
"""

from uuid import uuid4

from ..adapters import image_generation, image_storage
from ..config import get_settings
from .registry import registry


def style_synthesizer(
    user_id: str,
    item_image_urls: list[str],
    style_description: str,
    gender: str = "common",
    wearer_age: str = "adult",
    language: str = "ja",
    item_categories: list[str] | None = None,
) -> dict:
    """Generate a coordinate (outfit) image from the selected garment images.

    Args:
        user_id: ID of the requesting user (owns the stored result).
        item_image_urls: Image URLs (or R2/MinIO keys) of the chosen garments.
        style_description: Desired styling direction for the generated photo.
        gender: Wearer's gender preference (male/female/common).
        wearer_age: Wearer's age group (adult/child).
        language: Natural-language output language code (ja/en).
        item_categories: Optional per-item category labels (e.g. from
            search_rakuten/search_closet), parallel to item_image_urls, used
            to tell the generation model which item to extract from each
            reference photo when the photo is not a plain garment shot.

    Returns:
        {coordinate_image_url, items, model_used}.
    """
    image_bytes_list = [image_storage.fetch_bytes(url) for url in item_image_urls]
    items = [
        {
            "bytes": data,
            "category": item_categories[i]
            if item_categories and i < len(item_categories)
            else None,
            "note": None,
        }
        for i, data in enumerate(image_bytes_list)
    ]

    settings = get_settings()
    wearer = f"{wearer_age} wearer"
    if gender != "common":
        wearer = f"{wearer_age} {gender} wearer"
    language_instruction = (
        "Write all natural-language descriptions in English."
        if language == "en"
        else "Write all natural-language descriptions in Japanese."
    )
    generation_prompt = (
        f"Outfit worn by a {wearer}. {language_instruction} {style_description}"
    )
    try:
        result_bytes = image_generation.generate(items, generation_prompt)
        model_used = settings.image_generation_model
    except Exception:
        try:
            result_bytes = image_generation.generate(
                items, generation_prompt, retry=True
            )
            model_used = settings.image_generation_model
        except Exception:
            raise RuntimeError("Coordinate image generation failed after retry.")

    coordinate_image_url = image_storage.put_bytes(
        f"{user_id}/coordinates/{uuid4().hex}.jpg", result_bytes
    )
    return {
        "coordinate_image_url": coordinate_image_url,
        "items": item_image_urls,
        "model_used": model_used,
        "generation_prompt": generation_prompt,
        "language": language,
    }


registry.register("style_synthesizer", style_synthesizer)
