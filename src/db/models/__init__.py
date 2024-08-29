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
    CreateSchemaType: Type[CreateSchemaType]
    UpdateSchemaType: Type[UpdateSchemaType]

    @classmethod
    async def create(cls: Type[T], obj_in: CreateSchemaType, *, session: Optional[Session] = None) -> T:
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
    async def get(cls: Type[T], id: Any, *, session: Optional[Session] = None) -> Optional[T]:
        async def _get(s: Session):
            try:
                result = await s.execute(select(cls).filter(cls.id == id))
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
    async def get_many(cls: Type[T], skip: int = 0, limit: int = 100, *, session: Optional[Session] = None) -> List[T]:
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
    async def update(cls: Type[T], id: Any, obj_in: UpdateSchemaType, *, session: Optional[Session] = None) -> Optional[T]:
        async def _update(s: Session):
            try:
                stmt = update(cls).where(cls.id == id).values(**obj_in.dict(exclude_unset=True)).returning(cls)
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
    async def delete(cls: Type[T], id: Any, *, session: Optional[Session] = None) -> None:
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


from src.db.models.channel import Channel
from src.db.models.language_model import LanguageModel
from src.db.models.webhook import Webhook

metadata = Base.metadata
