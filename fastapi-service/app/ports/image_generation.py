from abc import ABC, abstractmethod
from typing import List


class ImageGenerationPort(ABC):
    """Port for generating outfit images via AI models."""

    @abstractmethod
    async def generate_coordinate_image(
        self, clothing_item_ids: List[str], style_description: str
    ) -> str:
        """
        Generate a coordinate image showing the selected clothing items.
        Model choice determined in M1-2 (Imagen 4, Nano Banana 2, or collage fallback).
        Returns image URL.
        """
        raise NotImplementedError("Implement in M4-7: Image generation adapter (M1 PoC model)")

    @abstractmethod
    async def generate_fallback_collage(self, image_urls: List[str]) -> str:
        """Generate a simple collage of images as fallback."""
        raise NotImplementedError("Implement in M4-7: Image generation adapter (M1 PoC model)")
