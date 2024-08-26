from typing import TypeVar, Type, List, Optional, Any
from sqlalchemy import select, delete, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import DeclarativeBase
from pydantic import BaseModel

from src.db.engine import Session

class Base(DeclarativeBase):
    @classmethod
    async def create(cls, obj_in: BaseModel) -> "Base":
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
    async def get(cls, id: Any) -> Optional["Base"]:
        async with Session() as session:
            try:
                result = await session.execute(select(cls).filter(cls.id == id))
                return result.scalar_one_or_none()
            except SQLAlchemyError as e:
                # Log the error here
                raise

    @classmethod
    async def get_many(cls, skip: int = 0, limit: int = 100) -> List["Base"]:
        async with Session() as session:
            try:
                result = await session.execute(select(cls).offset(skip).limit(limit))
                return result.scalars().all()
            except SQLAlchemyError as e:
                # Log the error here
                raise

    @classmethod
    async def update(cls, id: Any, obj_in: BaseModel) -> Optional["Base"]:
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
    async def delete(cls, id: Any) -> None:
        async with Session() as session:
            try:
                stmt = delete(cls).where(cls.id == id)
                await session.execute(stmt)
                await session.commit()
            except SQLAlchemyError as e:
                await session.rollback()
                # Log the error here
                raise
