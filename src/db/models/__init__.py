from typing import TypeVar, Type, List, Optional, Any
from sqlalchemy import select, delete, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import DeclarativeBase
from pydantic import BaseModel

from src.db.engine import Session

T = TypeVar('T', bound='Base')
CreateSchemaType = TypeVar('CreateSchemaType', bound=BaseModel)
UpdateSchemaType = TypeVar('UpdateSchemaType', bound=BaseModel)

class Base(DeclarativeBase):
    @classmethod
    async def create(cls: Type[T], obj_in: CreateSchemaType) -> T:
        async with Session() as session:
            try:
                db_obj = cls(**obj_in.dict())
                session.add(db_obj)
                await session.commit()
                await session.refresh(db_obj)
                return db_obj
            except SQLAlchemyError as e:
                await session.rollback()
                # Log the error here
                raise

    @classmethod
    async def get(cls: Type[T], id: Any) -> Optional[T]:
        async with Session() as session:
            try:
                result = await session.execute(select(cls).filter(cls.id == id))
                return result.scalar_one_or_none()
            except SQLAlchemyError as e:
                # Log the error here
                raise

    @classmethod
    async def get_many(cls: Type[T], skip: int = 0, limit: int = 100) -> List[T]:
        async with Session() as session:
            try:
                result = await session.execute(select(cls).offset(skip).limit(limit))
                return result.scalars().all()
            except SQLAlchemyError as e:
                # Log the error here
                raise

    @classmethod
    async def update(cls: Type[T], id: Any, obj_in: UpdateSchemaType) -> Optional[T]:
        async with Session() as session:
            try:
                stmt = update(cls).where(cls.id == id).values(**obj_in.dict(exclude_unset=True)).returning(cls)
                result = await session.execute(stmt)
                await session.commit()
                return result.scalar_one_or_none()
            except SQLAlchemyError as e:
                await session.rollback()
                # Log the error here
                raise

    @classmethod
    async def delete(cls: Type[T], id: Any) -> None:
        async with Session() as session:
            try:
                stmt = delete(cls).where(cls.id == id)
                await session.execute(stmt)
                await session.commit()
            except SQLAlchemyError as e:
                await session.rollback()
                # Log the error here
                raise


from src.db.models.channel import Channel
from src.db.models.language_model import LanguageModel
from src.db.models.webhook import Webhook

metadata = Base.metadata
