"""Tool modules; importing this package populates the registry (M4-4)."""

from . import (  # noqa: F401
    analyze_clothing_image,
    ask_preference,
    search_closet,
    style_synthesizer,
)
from .registry import registry  # noqa: F401
