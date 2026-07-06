"""Coordinate image generation (M4-7).

Ports the M1-2-approved Nano Banana virtual-try-on call and the ADL-005
collage fallback from poc/image_generation/run_poc.py.
"""

import io

from google.genai import types

from ..config import get_settings
from .gemini import _client

_TRYON_PROMPT = (
    "Generate a realistic full-body fashion photo of a single person wearing all of "
    "the provided clothing items together as one coordinated outfit. Keep each "
    "garment's color, pattern, and shape faithful to the reference photos. Studio "
    "background, soft even lighting, natural pose. Each reference photo is labeled "
    "with the item it represents. Use each photo only as a visual reference for "
    "the labeled garment or accessory; do not copy the original model, pose, "
    "background, text, logos, badges, catalog layout, or unrelated objects."
)

_RETRY_PROMPT = (
    "Create one realistic full-body outfit photo of a single person wearing the "
    "labeled clothing items. Preserve the visible color, fabric, pattern, and "
    "silhouette of each labeled item. Plain studio background, natural pose. "
    "Do not make a product collage or add written text."
)

def generate(
    items: list[dict],
    style_description: str,
    *,
    retry: bool = False,
) -> bytes:
    """Virtual try-on via Nano Banana: labeled garment photos + prompt -> outfit image.

    Each item is {"bytes": bytes, "category": str | None, "note": str | None}. A
    text label is inserted immediately before each image part so the model can
    be told, per photo, which item to extract from it (docs/local/20260704_
    styling_image_generation_issue.md, Phase 1).
    """
    settings = get_settings()
    parts: list[types.Part] = []
    for index, item in enumerate(items, start=1):
        label = f"Reference photo {index}: {item.get('category') or 'item'}."
        if item.get("note"):
            label += f" {item['note']}"
        parts.append(types.Part.from_text(text=label))
        parts.append(types.Part.from_bytes(data=item["bytes"], mime_type="image/jpeg"))
    prompt = _RETRY_PROMPT if retry else _TRYON_PROMPT
    if style_description:
        prompt += f" Desired style: {style_description}."
    parts.append(types.Part.from_text(text=prompt))

    response = _client().models.generate_content(
        model=settings.image_generation_model,
        contents=parts,
        config=types.GenerateContentConfig(response_modalities=["TEXT", "IMAGE"]),
    )
    for part in response.candidates[0].content.parts:
        if part.inline_data and part.inline_data.data:
            return part.inline_data.data
    raise RuntimeError("No image part in the model response.")


def build_collage(image_bytes_list: list[bytes]) -> bytes:
    """Lay the input garments side by side — the ADL-005 fallback."""
    from PIL import Image

    pics = [Image.open(io.BytesIO(data)).convert("RGB") for data in image_bytes_list]
    height = min(p.height for p in pics)
    pics = [p.resize((round(p.width * height / p.height), height)) for p in pics]
    canvas = Image.new("RGB", (sum(p.width for p in pics), height), "white")
    x = 0
    for p in pics:
        canvas.paste(p, (x, 0))
        x += p.width
    out = io.BytesIO()
    canvas.save(out, "JPEG", quality=90)
    return out.getvalue()
