class ClosetException(Exception):
    """Base exception for closet domain."""
    pass


class ClosetItemNotFound(ClosetException):
    """Raised when a clothing item is not found."""
    pass


class MaxClosetItemsExceeded(ClosetException):
    """Raised when the user exceeds max items in closet."""
    pass


class InvalidImageUrl(ClosetException):
    """Raised when an image URL is invalid."""
    pass
