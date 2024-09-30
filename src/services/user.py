from typing import Optional, List

import discord
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from src.db.models.user import User, UserCreate, UserUpdate

class UserService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(self, user_id: int) -> Optional[User]:
        return await self.session.get(User, user_id)

    async def create(self, user: discord.User) -> User:
        user = User(
            id=user.id,
            name=user.name,
            discriminator=user.discriminator
        )
        self.session.add(user)
        await self.session.commit()
        return user

    async def update(self, user: User, update_data: UserUpdate) -> User:
        for key, value in update_data.dict(exclude_unset=True).items():
            setattr(user, key, value)
        await self.session.commit()
        return user

    async def delete(self, user: User) -> None:
        await self.session.delete(user)
        await self.session.commit()

    async def get_all(self) -> List[User]:
        result = await self.session.execute(select(User))
        return list(result.scalars().all())

    async def get_or_create(self, user: discord.User) -> User:
        db_user = await self.get(user.id)
        if not db_user:
            db_user = await self.create(user)
        return db_user
