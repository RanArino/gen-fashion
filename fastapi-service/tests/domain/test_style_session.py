import pytest
from uuid import uuid4
from app.domain.styling import StyleSession, StyleSessionId, StyleSessionState


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
