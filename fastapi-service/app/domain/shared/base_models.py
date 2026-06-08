from abc import ABC
from uuid import UUID


class ValueObject(ABC):
    """Base class for value objects. Immutable, compared by value."""
    pass


class AggregateRoot(ABC):
    """Base class for aggregate roots. Domain entities with identity."""

    id: UUID
