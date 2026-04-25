from typing import TypeVar, Type, List, Optional, Generic, Any
from sqlalchemy.orm import Session
from sqlalchemy import select, or_

T = TypeVar("T")


class BaseRepository(Generic[T]):
    """Generic base repository with common CRUD operations."""

    def __init__(self, db: Session, model_class: Type[T]):
        self.db = db
        self.model_class = model_class

    def get_by_id(self, id: int) -> Optional[T]:
        """Get entity by primary key."""
        return self.db.get(self.model_class, id)

    def get_by_field(self, field_name: str, value: Any) -> Optional[T]:
        """Get entity by a specific field value."""
        return self.db.query(self.model_class).filter(
            getattr(self.model_class, field_name) == value
        ).first()

    def list_all(self, skip: int = 0, limit: int = 100) -> List[T]:
        """Get paginated list of all entities."""
        return self.db.query(self.model_class).offset(skip).limit(limit).all()

    def create(self, data: dict) -> T:
        """Create a new entity from dict data."""
        entity = self.model_class(**data)
        self.db.add(entity)
        self.db.commit()
        self.db.refresh(entity)
        return entity

    def update(self, entity: T, data: dict) -> T:
        """Update entity with dict data."""
        for key, value in data.items():
            if hasattr(entity, key):
                setattr(entity, key, value)
        self.db.commit()
        self.db.refresh(entity)
        return entity

    def delete(self, entity: T) -> None:
        """Delete an entity."""
        self.db.delete(entity)
        self.db.commit()

    def exists(self, field_name: str, value: Any) -> bool:
        """Check if entity exists by field value."""
        return self.db.query(
            self.db.query(self.model_class).filter(
                getattr(self.model_class, field_name) == value
            ).exists()
        ).scalar()
