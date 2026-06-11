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
    "background, soft even lighting, natural pose."
)


def generate(image_bytes_list: list[bytes], style_description: str) -> bytes:
    """Virtual try-on via Nano Banana: garment photos + prompt -> outfit image."""
    settings = get_settings()
    parts = [
        types.Part.from_bytes(data=data, mime_type="image/jpeg")
        for data in image_bytes_list
    ]
    prompt = _TRYON_PROMPT
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
