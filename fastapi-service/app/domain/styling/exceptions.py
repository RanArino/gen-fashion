class StylingException(Exception):
    """Base exception for styling domain."""
    pass


class StyleSessionNotFound(StylingException):
    """Raised when a style session is not found."""
    pass


class InvalidStateTransition(StylingException):
    """Raised when an invalid state transition is attempted."""
    pass


class NoSourceSelected(StylingException):
    """Raised when clothing source is not selected."""
    pass


class NoImageUploaded(StylingException):
    """Raised when image is not uploaded for analysis."""
    pass
