"""
Generic async CRUD repository base class.

Architecture Decision:
    The Repository Pattern decouples all business logic from SQLAlchemy.
    Services call repository methods; they never write SQLAlchemy queries
    directly.  This means:

        1. Repositories are the ONLY layer that imports SQLAlchemy.
        2. Services are testable without a real database — mock the repo.
        3. Switching databases (e.g., to MongoDB) only touches this layer.

    The generic ``BaseRepository[ModelT, CreateSchemaT, UpdateSchemaT]``
    provides standard CRUD for free via inheritance.  Concrete repositories
    override or add methods for domain-specific queries.

Type Parameters:
    ModelT:        The SQLAlchemy ORM model class.
    CreateSchemaT: The Pydantic schema used for creation.
    UpdateSchemaT: The Pydantic schema used for updates.
"""

from __future__ import annotations

import uuid
from typing import Any, Generic, TypeVar

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import TimestampedBase

ModelT = TypeVar("ModelT", bound=TimestampedBase)
CreateSchemaT = TypeVar("CreateSchemaT")
UpdateSchemaT = TypeVar("UpdateSchemaT")


class BaseRepository(Generic[ModelT, CreateSchemaT, UpdateSchemaT]):
    """Generic async CRUD repository.

    Provides ``get``, ``get_or_raise``, ``list``, ``create``, ``update``,
    ``delete``, and ``count`` out of the box.  All methods are async and
    accept an injected ``AsyncSession``.

    Args:
        model: The SQLAlchemy ORM model class this repository manages.

    Example:
        class UserRepository(BaseRepository[User, UserCreate, UserUpdate]):
            model = User
    """

    model: type[ModelT]

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, record_id: uuid.UUID) -> ModelT | None:
        """Fetch a single record by primary key.

        Args:
            record_id: The UUID primary key of the record.

        Returns:
            ModelT | None: The record, or None if not found.
        """
        result = await self._session.get(self.model, record_id)
        return result

    async def get_or_raise(
        self,
        record_id: uuid.UUID,
        error_message: str | None = None,
    ) -> ModelT:
        """Fetch a single record by primary key, raising if not found.

        Args:
            record_id:     The UUID primary key of the record.
            error_message: Optional custom error message.

        Returns:
            ModelT: The record.

        Raises:
            NotFoundError: If no record with the given ID exists.
        """
        from app.core.exceptions import NotFoundError

        record = await self.get(record_id)
        if record is None:
            raise NotFoundError(
                resource=self.model.__name__,
                identifier=str(record_id),
            )
        return record

    async def list(
        self,
        *,
        offset: int = 0,
        limit: int = 20,
        filters: dict[str, Any] | None = None,
    ) -> list[ModelT]:
        """Return a paginated list of records.

        Args:
            offset:  Number of records to skip (for pagination).
            limit:   Maximum number of records to return.
            filters: Column-value equality filters to apply.

        Returns:
            list[ModelT]: Matching records.
        """
        stmt = select(self.model)
        if filters:
            for column, value in filters.items():
                stmt = stmt.where(getattr(self.model, column) == value)
        stmt = stmt.offset(offset).limit(limit)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def count(self, filters: dict[str, Any] | None = None) -> int:
        """Return the total number of records matching the given filters.

        Args:
            filters: Column-value equality filters to apply.

        Returns:
            int: Count of matching records.
        """
        stmt = select(func.count()).select_from(self.model)
        if filters:
            for column, value in filters.items():
                stmt = stmt.where(getattr(self.model, column) == value)
        result = await self._session.execute(stmt)
        return result.scalar_one()

    async def create(self, data: CreateSchemaT) -> ModelT:
        """Insert a new record.

        Args:
            data: A Pydantic schema instance with creation data.

        Returns:
            ModelT: The newly created record with DB-assigned fields populated.
        """
        if hasattr(data, "model_dump"):
            payload = data.model_dump(exclude_unset=False)
        else:
            payload = dict(data)  # type: ignore[call-overload]
        record = self.model(**payload)
        self._session.add(record)
        await self._session.flush()  # Flush to get DB-assigned fields (id, created_at)
        await self._session.refresh(record)
        return record

    async def create_from_dict(self, data: dict[str, Any]) -> ModelT:
        """Insert a new record from a plain dictionary.

        Useful when bypassing Pydantic schemas for internal operations.

        Args:
            data: Dictionary of column names and values.

        Returns:
            ModelT: The newly created record.
        """
        record = self.model(**data)
        self._session.add(record)
        await self._session.flush()
        await self._session.refresh(record)
        return record

    async def update(self, record: ModelT, data: UpdateSchemaT) -> ModelT:
        """Update an existing record's fields.

        Only fields present in the Pydantic schema (``exclude_unset=True``)
        are written — partial updates are supported by default.

        Args:
            record: The existing ORM instance to update.
            data:   A Pydantic schema instance with updated fields.

        Returns:
            ModelT: The updated record.
        """
        if hasattr(data, "model_dump"):
            updates = data.model_dump(exclude_unset=True)
        else:
            updates = dict(data)  # type: ignore[call-overload]
        for field, value in updates.items():
            setattr(record, field, value)
        self._session.add(record)
        await self._session.flush()
        await self._session.refresh(record)
        return record

    async def update_fields(self, record: ModelT, **kwargs: Any) -> ModelT:
        """Update specific fields of an ORM instance by keyword argument.

        Convenient for internal updates that don't go through a Pydantic schema.

        Args:
            record:   The existing ORM instance to update.
            **kwargs: Field names and their new values.

        Returns:
            ModelT: The updated record.
        """
        for field, value in kwargs.items():
            setattr(record, field, value)
        self._session.add(record)
        await self._session.flush()
        await self._session.refresh(record)
        return record

    async def delete(self, record: ModelT) -> None:
        """Delete a record from the database.

        Args:
            record: The ORM instance to delete.
        """
        await self._session.delete(record)
        await self._session.flush()
