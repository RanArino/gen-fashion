"""Affective vocabulary shared by `domain/closet` and `domain/styling` (MR-1).

`IntentTag` is the state a user wants to be in while wearing a closet item
("強気でいたい", "守られたい") — not an occasion, not a style adjective
(ADL-038). `MoodTag` is the session-level counterpart used by `UserPreference`
in `domain/styling` (MS-1).

This module lives in `domain/shared/` rather than `domain/closet/` because
neither `domain/closet` nor `domain/styling` imports the other today, and both
need this vocabulary. See the ExecPlan Decision Log entry dated 2026-08-07
("Placement changed") in
`docs/plans/20260806-mr-intent-tag-capture-and-ranking.md`.

The enum *names* are the stored, versioned values (Firestore, Elasticsearch);
display labels live only in the Flutter ARB catalogs (ADL-049). Never rename a
member without a vocabulary version bump — see `INTENT_VOCABULARY_VERSION`.
"""

from enum import Enum


INTENT_VOCABULARY_VERSION = 1


class Sensitivity(str, Enum):
    """Whether a vocabulary value may be exported outside its owning user."""

    SHAREABLE = "SHAREABLE"
    PRIVATE_ONLY = "PRIVATE_ONLY"


class IntentTag(str, Enum):
    """The state a user wants to be in while wearing a closet item (ADL-038).

    Each value carries a static arousal coordinate (ADL-049), one axis of
    NA-2's valence x arousal magazine layout. Arousal is a property of the
    vocabulary, not per-item data: it costs no storage and no extra user
    input.
    """

    CONFIDENT = "CONFIDENT"  # 強気でいたい / want to feel bold
    PROTECTED = "PROTECTED"  # 守られたい / want to feel safe
    BLEND_IN = "BLEND_IN"  # 馴染みたい / want to blend in
    PUT_TOGETHER = "PUT_TOGETHER"  # ちゃんとして見られたい / want to look put together
    AT_EASE = "AT_EASE"  # 楽でいたい / want to feel at ease
    EXPRESSIVE = "EXPRESSIVE"  # 自分らしくいたい / want to feel like myself

    @property
    def arousal(self) -> str:
        """Static arousal coordinate: "high" or "low"."""
        return _INTENT_AROUSAL[self]


_INTENT_AROUSAL = {
    IntentTag.CONFIDENT: "high",
    IntentTag.PROTECTED: "low",
    IntentTag.BLEND_IN: "low",
    IntentTag.PUT_TOGETHER: "high",
    IntentTag.AT_EASE: "low",
    IntentTag.EXPRESSIVE: "high",
}


class MoodTag(str, Enum):
    """Session-level mood, with a valence + arousal coordinate and a
    sensitivity classification. Every negative-valence mood is
    `PRIVATE_ONLY`.
    """

    CONFIDENT = "CONFIDENT"
    CALM = "CALM"
    EXCITED = "EXCITED"
    TIRED = "TIRED"
    ANXIOUS = "ANXIOUS"
    LOW = "LOW"

    @property
    def valence(self) -> str:
        """Static valence coordinate: "positive" or "negative"."""
        return _MOOD_VALENCE[self]

    @property
    def arousal(self) -> str:
        """Static arousal coordinate: "high" or "low"."""
        return _MOOD_AROUSAL[self]

    @property
    def sensitivity(self) -> Sensitivity:
        """SHAREABLE or PRIVATE_ONLY. Every negative-valence mood is
        PRIVATE_ONLY."""
        return _MOOD_SENSITIVITY[self]


_MOOD_VALENCE = {
    MoodTag.CONFIDENT: "positive",
    MoodTag.CALM: "positive",
    MoodTag.EXCITED: "positive",
    MoodTag.TIRED: "negative",
    MoodTag.ANXIOUS: "negative",
    MoodTag.LOW: "negative",
}

_MOOD_AROUSAL = {
    MoodTag.CONFIDENT: "high",
    MoodTag.CALM: "low",
    MoodTag.EXCITED: "high",
    MoodTag.TIRED: "low",
    MoodTag.ANXIOUS: "high",
    MoodTag.LOW: "low",
}

_MOOD_SENSITIVITY = {
    mood: (Sensitivity.PRIVATE_ONLY if valence == "negative" else Sensitivity.SHAREABLE)
    for mood, valence in _MOOD_VALENCE.items()
}
