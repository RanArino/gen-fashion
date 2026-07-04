import pytest
from uuid import uuid4
from app.domain.styling import (
    ClothingSource,
    CoordinationMode,
    StyleResult,
    StyleSession,
    StyleSessionId,
    StyleSessionState,
    UserPreference,
)


def test_create_style_session():
    """Test creating a style session."""
    session_id = StyleSessionId(uuid4())
    user_id = "user-123"

    session = StyleSession(
        id=session_id,
        user_id=user_id,
        state=StyleSessionState.CREATED,
    )

    assert session.id == session_id
    assert session.user_id == user_id
    assert session.state == StyleSessionState.CREATED


def test_style_session_state_transitions():
    """Test valid state transitions."""
    session = StyleSession(
        id=StyleSessionId(uuid4()),
        user_id="user-123",
        state=StyleSessionState.CREATED,
    )

    # Test valid transitions
    assert session.state.can_transition_to(StyleSessionState.SOURCE_SELECTING)
    session._transition_to(StyleSessionState.SOURCE_SELECTING)
    assert session.state == StyleSessionState.SOURCE_SELECTING

    assert session.state.can_transition_to(StyleSessionState.ANALYZING)
    session._transition_to(StyleSessionState.ANALYZING)
    assert session.state == StyleSessionState.ANALYZING


def test_web_session_can_select_source_and_enter_searching():
    session = StyleSession(
        id=StyleSessionId(uuid4()),
        user_id="user-123",
        state=StyleSessionState.SOURCE_SELECTING,
    )

    session.select_source(
        ClothingSource.SHARED_CLOSET,
        UserPreference(occasion="weekend", style="clean"),
        "adult-01",
    )

    assert session.state == StyleSessionState.SEARCHING
    assert session.clothing_source == ClothingSource.SHARED_CLOSET
    assert session.shared_closet_id == "adult-01"
    assert session.user_preference.style == "clean"


def test_session_defaults_to_standard_mode_without_anchors():
    session = StyleSession(
        id=StyleSessionId(uuid4()),
        user_id="user-123",
        state=StyleSessionState.SOURCE_SELECTING,
    )

    assert session.coordination_mode == CoordinationMode.STANDARD
    assert session.anchor_items == []


def test_web_session_can_select_assisted_and_enter_searching():
    session = StyleSession(
        id=StyleSessionId(uuid4()),
        user_id="user-123",
        state=StyleSessionState.SOURCE_SELECTING,
    )
    anchors = [{"item_id": "item-1", "source": "CLOSET", "anchor": True}]

    session.select_assisted(anchors, UserPreference(style="clean"))

    assert session.state == StyleSessionState.SEARCHING
    assert session.coordination_mode == CoordinationMode.ASSISTED
    assert session.clothing_source == ClothingSource.CLOSET
    assert session.anchor_items == anchors
    assert session.user_preference.style == "clean"


def test_select_assisted_requires_source_selecting_state_and_anchors():
    session = StyleSession(
        id=StyleSessionId(uuid4()),
        user_id="user-123",
        state=StyleSessionState.SOURCE_SELECTING,
    )
    with pytest.raises(ValueError, match="at least one anchor"):
        session.select_assisted([])

    proposing = StyleSession(
        id=StyleSessionId(uuid4()),
        user_id="user-123",
        state=StyleSessionState.PROPOSING,
    )
    with pytest.raises(ValueError, match="Cannot select source"):
        proposing.select_assisted([{"item_id": "item-1"}])


def test_m5_statuses_support_error_generating_and_terminal_states():
    session = StyleSession(
        id=StyleSessionId(uuid4()),
        user_id="user-123",
        state=StyleSessionState.PROPOSING,
    )

    assert session.state.can_transition_to(StyleSessionState.GENERATING)
    session._transition_to(StyleSessionState.GENERATING)
    assert session.state.can_transition_to(StyleSessionState.COMPLETED)

    error_session = StyleSession(
        id=StyleSessionId(uuid4()),
        user_id="user-123",
        state=StyleSessionState.SEARCHING,
    )
    assert error_session.state.can_transition_to(StyleSessionState.ERROR)


def test_complete_records_completion_time():
    session = StyleSession(
        id=StyleSessionId(uuid4()),
        user_id="user-123",
        state=StyleSessionState.GENERATING,
    )

    session.complete(StyleResult(coordinate_image_url="https://example.test/result.jpg"))

    assert session.state == StyleSessionState.COMPLETED
    assert session.completed_at is not None


def test_style_session_invalid_transition():
    """Test that invalid transitions raise errors."""
    session = StyleSession(
        id=StyleSessionId(uuid4()),
        user_id="user-123",
        state=StyleSessionState.CREATED,
    )

    # Cannot skip from CREATED to ANALYZING directly
    with pytest.raises(ValueError):
        session._transition_to(StyleSessionState.ANALYZING)


def test_style_session_invalid_user_id():
    """Test that empty user_id raises error."""
    with pytest.raises(ValueError, match="user_id must not be empty"):
        StyleSession(
            id=StyleSessionId(uuid4()),
            user_id="",
            state=StyleSessionState.CREATED,
        )
