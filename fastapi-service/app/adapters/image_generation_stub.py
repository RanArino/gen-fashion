from typing import List
from app.ports import ImageGenerationPort


class ImageGenerationStub(ImageGenerationPort):
    """Stub for image generation (M4-7, model chosen in M1-2)."""

    async def generate_coordinate_image(
        self, clothing_item_ids: List[str], style_description: str
    ) -> str:
        raise NotImplementedError(
            "Implement in M4-7: Image generation adapter (model chosen in M1-2)"
        )

    async def generate_fallback_collage(self, image_urls: List[str]) -> str:
        raise NotImplementedError(
            "Implement in M4-7: Fallback collage generation"
        )
