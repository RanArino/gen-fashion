"""ask_preference tool (M4-8, req §6.4).

Web (Phase 1a) variant: preferences are collected by the pre-session Flutter
form and passed in the initial agent context, so this tool just normalizes
and echoes the UserPreference fields for StylingAgent to reason over.
The LINE interactive multi-turn variant is deferred to M6
(AskUserPreferenceUseCase, M6-7).
"""

from .registry import registry


def ask_preference(
    occasion: str | None = None,
    season: str | None = None,
    style: str | None = None,
    color_preference: str | None = None,
    gender: str | None = None,
) -> dict:
    """Normalize the user's styling preferences for this session.

    Args:
        occasion: e.g. "office", "date", "casual outing".
        season: e.g. "spring", "summer".
        style: e.g. "casual", "formal", "street".
        color_preference: e.g. "earth tones", "monochrome".
        gender: "male", "female", or "common".

    Returns:
        UserPreference-shaped dict including gender, with blank values
        normalized to null.
    """

    def _clean(value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None

    return {
        "occasion": _clean(occasion),
        "season": _clean(season),
        "style": _clean(style),
        "color_preference": _clean(color_preference),
        "gender": _clean(gender),
    }


registry.register("ask_preference", ask_preference)
