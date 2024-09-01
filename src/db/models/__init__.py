from typing import TypeVar, Type, List, Optional, Any, Generic, Iterable
from sqlalchemy import select, delete, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import DeclarativeBase
from pydantic import BaseModel
from sqlalchemy.sql.base import ExecutableOption

from src.db.engine import Session

T = TypeVar("T", bound="Base")
CreateSchemaType = TypeVar("CreateSchemaType", bound=BaseModel)
UpdateSchemaType = TypeVar("UpdateSchemaType", bound=BaseModel)


class Base(DeclarativeBase, Generic[CreateSchemaType, UpdateSchemaType]):
    """Base class for SQLAlchemy models with CRUD operations.

    Generic parameters:
        CreateSchemaType: Pydantic model for creating a new instance.
        UpdateSchemaType: Pydantic model for updating an existing instance.
    """

    @classmethod
    async def create(
        cls: Type[T], obj_in: CreateSchemaType, *, session: Optional[Session] = None
    ) -> T:
        """Create a new database object.

        Args:
            obj_in (CreateSchemaType): Pydantic model instance with creation data.
            session (Optional[Session]): SQLAlchemy async session. If None, a new session will be created.

        Returns:
            T: The created database object.

        Raises:
            SQLAlchemyError: If there's an error during the database operation.
        """
        async def _create(s: Session):
            try:
                db_obj = cls(**obj_in.dict())
                s.add(db_obj)
                await s.commit()
                await s.refresh(db_obj)
                return db_obj
            except SQLAlchemyError as e:
                await s.rollback()
                # Log the error here
                raise

        if session:
            return await _create(session)
        else:
            async with Session() as new_session:
                return await _create(new_session)

    @classmethod
    async def get(
        cls: Type[T],
        id: Any,
        *,
        options: Optional[Iterable[ExecutableOption]] = None,
        session: Optional[Session] = None
    ) -> Optional[T]:
        """
        Retrieve a database object by its ID.

        Args:
            id (Any): The ID of the object to retrieve.
            options (Optional[Iterable[ExecutableOption]]): Query options to apply.
            session (Optional[Session]): SQLAlchemy async session. If None, a new session will be created.

        Returns:
            Optional[T]: The retrieved object, or None if not found.

        Raises:
            SQLAlchemyError: If there's an error during the database operation.
        """
        if options is None:
            options = []

        async def _get(s: Session):
            try:
                result = await s.execute(
                    select(cls).options(*options).filter(cls.id == id)
                )
                return result.scalar_one_or_none()
            except SQLAlchemyError as e:
                # Log the error here
                raise

        if session:
            return await _get(session)
        else:
            async with Session() as new_session:
                return await _get(new_session)

    @classmethod
    async def get_many(
        cls: Type[T],
        skip: int = 0,
        limit: Optional[int] = 100,
        *,
        session: Optional[Session] = None
    ) -> List[T]:
        """
        Retrieve multiple database objects with pagination.

        Args:
            skip (int): Number of records to skip.
            limit (Optional[int]): Maximum number of records to return.
            session (Optional[Session]): SQLAlchemy async session. If None, a new session will be created.

        Returns:
            List[T]: List of retrieved objects.

        Raises:
            SQLAlchemyError: If there's an error during the database operation.
        """
        async def _get_many(s: Session):
            try:
                result = await s.execute(select(cls).offset(skip).limit(limit))
                return result.scalars().all()
            except SQLAlchemyError as e:
                # Log the error here
                raise

        if session:
            return await _get_many(session)
        else:
            async with Session() as new_session:
                return await _get_many(new_session)

    @classmethod
    async def update(
        cls: Type[T],
        id: Any,
        obj_in: UpdateSchemaType,
        *,
        session: Optional[Session] = None
    ) -> Optional[T]:
        """
        Update an existing database object.

        Args:
            id (Any): The ID of the object to update.
            obj_in (UpdateSchemaType): Pydantic model instance with update data.
            session (Optional[Session]): SQLAlchemy async session. If None, a new session will be created.

        Returns:
            Optional[T]: The updated object, or None if not found.

        Raises:
            SQLAlchemyError: If there's an error during the database operation.
        """
        async def _update(s: Session):
            try:
                stmt = (
                    update(cls)
                    .where(cls.id == id)
                    .values(**obj_in.dict(exclude_unset=True))
                    .returning(cls)
                )
                result = await s.execute(stmt)
                await s.commit()
                return result.scalar_one_or_none()
            except SQLAlchemyError as e:
                await s.rollback()
                # Log the error here
                raise

        if session:
            return await _update(session)
        else:
            async with Session() as new_session:
                return await _update(new_session)

    @classmethod
    async def delete(
        cls: Type[T], id: Any, *, session: Optional[Session] = None
    ) -> None:
        """
        Delete a database object by its ID.

        Args:
            id (Any): The ID of the object to delete.
            session (Optional[Session]): SQLAlchemy async session. If None, a new session will be created.

        Raises:
            SQLAlchemyError: If there's an error during the database operation.
        """
        async def _delete(s: Session):
            try:
                stmt = delete(cls).where(cls.id == id)
                await s.execute(stmt)
                await s.commit()
            except SQLAlchemyError as e:
                await s.rollback()
                # Log the error here
                raise

        if session:
            await _delete(session)
        else:
            async with Session() as new_session:
                await _delete(new_session)


from src.db.models.guild import Guild
from src.db.models.channel import Channel
from src.db.models.llm import LLM
from src.db.models.webhook import Webhook

metadata = Base.metadata
